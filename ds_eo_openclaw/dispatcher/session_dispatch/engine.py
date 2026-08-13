"""
DS-EO Dispatcher — Session Dispatch Layer

Wraps OpenClaw's sessions_spawn/sessions_send for agent-to-agent handoffs.
Provides:
1. spawn_agent(target, prompt_text, task_id) — isolated session with rendered prompt
2. send_message(target_session_key, message) — structured cross-session messaging
3. get_completion_status(session_key) — check if spawned agent finished
4. cleanup_session(session_key) — close session when done

All handoffs use context="isolated" per protocol mandate.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class SpawnResult:
    """Result of a sessions_spawn call."""
    success: bool
    session_key: Optional[str] = None
    agent_id: Optional[str] = None
    task_id: Optional[str] = None
    prompt_preview: str = ""
    error: Optional[str] = None
    spawn_timestamp: Optional[str] = None

@dataclass
class SendMessageResult:
    """Result of a sessions_send call."""
    success: bool
    message_id: Optional[str] = None
    target_session_key: Optional[str] = None
    error: Optional[str] = None


class SessionDispatcher:
    """
    Dispatch agent sessions and messages via OpenClaw's multi-agent API.
    
    This is the bridge between the dispatcher engine (which decides WHAT to do)
    and the actual session management (which DOES it).
    
    Key principle: All cross-phase handoffs use context="isolated" — no session
    history bleed between phases per protocol mandate (TASK_DS_EO_005/006).
    """

    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_root = workspace_root

    # ===== SPawning Agent Sessions =====

    def spawn_agent(
        self,
        target_agent_id: str,
        prompt_text: str,
        task_id: str = None,
        model_override: str = None,
        workspace_override: str = None,
    ) -> SpawnResult:
        """
        Spawn a real OpenClaw agent session via SessionSpawnManager.

        Delegates to the Phase 8 real spawn infrastructure (TASK_DS_EO_038).
        Returns structured result for downstream consumption.

        Args:
            target_agent_id: Agent role to spawn (e.g., "implementer")
            prompt_text: Full rendered prompt for the receiving agent
            task_id: Optional task context
            model_override: Override agent's default model
            workspace_override: Override agent's workspace

        Returns:
            SpawnResult with session key, status, and preview
        """
        from ds_eo_openclaw.dispatcher.session_spawn import (
            SessionSpawnManager,
        )

        mgr = SessionSpawnManager(
            workspace_root=workspace_override or self.workspace_root
        )
        outcome = mgr.spawn_agent(
            task_id=task_id or "untracked",
            agent_role=target_agent_id,
            prompt_content=prompt_text,
            model_override=model_override,
        )

        return SpawnResult(
            success=outcome.success,
            session_key=outcome.session_key,
            agent_id=target_agent_id,
            task_id=task_id,
            prompt_preview=prompt_text[:200] + ("..." if len(prompt_text) > 200 else ""),
            error=outcome.error,
            spawn_timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def spawn_via_sessions_spawn_tool(
        self,
        target_agent_id: str,
        prompt_text: str,
        task_id: str = None,
        **kwargs,
    ) -> SpawnResult:
        """
        Spawn using the actual OpenClaw sessions_spawn tool interface.
        
        In production, this would call:
            sessions_spawn(
                agent=target_agent_id,
                prompt=prompt_text,
                context="isolated",
                ...
            )
        
        Returns structured result for logging and state tracking.
        """
        now = datetime.now(timezone.utc).isoformat()
        session_key = f"agent:{target_agent_id}:subagent:{task_id or 'untracked'}"

        # In production, the actual call would be:
        # result = await sessions_spawn(
        #     agent=target_agent_id,
        #     prompt=prompt_text,
        #     context="isolated",
        #     model_override=model_override,
        #     workspace_override=workspace_override,
        # )
        
        return SpawnResult(
            success=True,
            session_key=session_key,
            agent_id=target_agent_id,
            task_id=task_id,
            prompt_preview=prompt_text[:200] + ("..." if len(prompt_text) > 200 else ""),
            spawn_timestamp=now,
        )

    # ===== COMPLETION CHECKING =====

    def check_completion(self, session_key: str = None) -> dict:
        """
        Check if a spawned agent session has completed.

        Args:
            session_key: The session key to check (e.g., "agent:implementer:subagent:abc123")

        Returns:
            Dict with status info. In production, this would call sessions_list/sessions_history.
        """
        if not session_key:
            return {"status": "error", "message": "No session key provided"}

        # In production, check via:
        # result = await sessions_list(limit=1, label=session_key)
        # if result and result[0].get("status") == "completed":
        #     return {"status": "completed", "session_key": session_key}
        
        return {
            "status": "running",  # placeholder
            "session_key": session_key,
            "message": f"Session {session_key} is running (mock)",
        }

    def yield_for_completion(self, session_keys: list[str], timeout_seconds: int = 300) -> dict:
        """
        Yield current turn and wait for specified sessions to complete.

        In production, this calls:
            await sessions_yield(timeout=timeout_seconds, expect=session_keys)
        
        The dispatcher uses this after spawning parallel agents to wait for results.
        """
        return {
            "action": "yield",
            "waiting_for": session_keys,
            "timeout_seconds": timeout_seconds,
        }

    # ===== CROSS-SESSION MESSAGING =====

    def send_message(
        self,
        target_session_key: str,
        message_text: str,
        task_id: str = None,
    ) -> SendMessageResult:
        """
        Send a structured message to an existing agent session.

        Used for follow-up communication (e.g., G4 feedback to implementer).
        """
        now = datetime.now(timezone.utc).isoformat()

        # In production, this would call:
        # await sessions_send(session_key=target_session_key, message=message_text)

        return SendMessageResult(
            success=True,
            message_id=f"msg_{task_id or 'global'}_{now[:13]}",
            target_session_key=target_session_key,
        )

    # ===== SESSION CLEANUP =====

    def cleanup_session(self, session_key: str = None) -> dict:
        """Close/clean up a completed session."""
        if not session_key:
            return {"success": False, "error": "No session key provided"}

        return {
            "success": True,
            "action": "cleanup",
            "session_key": session_key,
        }

    # ===== PROMPT RENDERING =====

    def render_spawn_prompt(
        self,
        target_agent_id: str,
        transition_name: str,
        task_id: str,
        engine=None,  # WorkflowEngine for template lookup
        extra_context: dict = None,
    ) -> tuple[str, str]:
        """
        Render the full prompt for spawning an agent.

        Combines:
        1. Role identity (who is receiving)
        2. Transition context (what gate just fired)
        3. Task details (from task directory)
        4. Prompt template from workflow definition
        5. Additional runtime context (artifacts, etc.)

        Args:
            target_agent_id: Who to spawn
            transition_name: Gate that triggered this (e.g., "G1_APPROVE")
            task_id: Task being dispatched
            engine: WorkflowEngine for prompt template lookup
            extra_context: Additional context from task directory/state

        Returns:
            (full_prompt, template_used)
        """
        parts = []

        # 1. Role identity
        role_map = {
            "implementer": "Implementer",
            "reviewer": "Senior Code Reviewer",
            "cto": "CTO / Architect",
            "pm": "Project Manager",
        }
        role_name = role_map.get(target_agent_id, target_agent_id)
        parts.append(f"You are the **{role_name}**.\n")

        # 2. Transition context
        parts.append(f"\n## DISPATCH: {transition_name}\n")
        parts.append(f"Task: `{task_id}`\n")

        # 3. Prompt template from engine
        template = ""
        if engine and hasattr(engine, 'prompt_templates'):
            template_key_map = {
                "G1_APPROVE": "delegation_prompt",
                "G2_COMPLETE": "review_request",
                "G3_APPROVE": "approval_request",
                "G1_REJECT": "plan_revision",
                "G3_CHANGES": "review_request",  # Use review template for revision too
                "G4_APPROVE": "approval_request",
            }
            tmpl_key = template_key_map.get(transition_name)
            if tmpl_key and engine.prompt_templates.get(tmpl_key):
                try:
                    template = engine.format_prompt(engine.prompt_templates[tmpl_key])
                except Exception:
                    template = f"Template '{tmpl_key}' not found for transition {transition_name}"

        if template:
            parts.append(f"\n## Instructions\n{template}")
        
        # 4. Runtime context from task directory
        if extra_context:
            parts.append("\n## Task Context\n")
            for key, value in extra_context.items():
                if isinstance(value, list):
                    parts.append(f"- {key}: {'; '.join(str(v) for v in value)}")
                else:
                    parts.append(f"- {key}: {value}")

        return "\n".join(parts), template or "none"

    # ===== BATCH DISPATCH =====

    def dispatch_parallel(
        self,
        dispatches: list[dict],  # [{target_agent_id, prompt_text, task_id}, ...]
        yield_timeout: int = 600,
    ) -> dict:
        """
        Dispatch to multiple agents in parallel and wait for completion.

        Used when the PM needs to query multiple agents simultaneously
        (e.g., ask CTO and Reviewer to independently assess a task).

        Args:
            dispatches: List of {target_agent_id, prompt_text, task_id} dicts
            yield_timeout: Seconds to wait for all completions

        Returns:
            Dict with spawn results and completion status
        """
        results = {}
        session_keys = []
        for d in dispatches:
            target = d.get("target_agent_id", "pm")
            prompt = d.get("prompt_text", "")
            task = d.get("task_id", "")
            
            result = self.spawn_via_sessions_spawn_tool(target, prompt, task)
            results[target] = result
            
            if result.session_key:
                session_keys.append(result.session_key)

        return {
            "dispatched": len(dispatches),
            "results": {k: {"success": r.success, "session_key": r.session_key} for k, r in results.items()},
            "waiting_for": session_keys,
            "yield_timeout_seconds": yield_timeout if session_keys else 0,
        }

    # ===== DISPATCH INTEGRATION WITH ENGINE =====

    def trigger_transition_dispatch(
        self,
        transition_name: str,
        task_id: str,
        engine=None,
        state_manager=None,
    ) -> dict:
        """
        End-to-end dispatch for a gate transition.

        1. Get transition details from engine
        2. Read current artifacts from state manager
        3. Render prompt template
        4. Spawn agent session
        5. Update pending_work in state
        6. Return dispatch result

        This is the main integration point between dispatcher/dispatch.py
        and the actual session spawning.
        """
        if not engine:
            return {"success": False, "error": "WorkflowEngine required"}

        # Get transition config
        tconfig = engine.transitions.get(transition_name)
        if not tconfig:
            return {"success": False, "error": f"Unknown transition: {transition_name}"}

        target_agent = tconfig.get("agent")
        phase_to = tconfig.get("to")

        # Get task state for context
        task_context = {}
        if state_manager:
            state, err = state_manager.read_state()
            if err:
                return {"success": False, "error": f"Cannot read state: {err}"}
            
            # Gather artifact paths from transition requirements
            artifacts = tconfig.get("requires_artifacts", [])
            task_context["required_artifacts"] = artifacts
            task_context["current_phase"] = state.get("current_phase")
            task_context["workflow_version"] = state.get("workflow_version")

        # Render prompt
        prompt, template_used = self.render_spawn_prompt(
            target_agent_id=target_agent,
            transition_name=transition_name,
            task_id=task_id,
            engine=engine,
            extra_context=task_context,
        )

        # Spawn
        result = self.spawn_via_sessions_spawn_tool(target_agent, prompt, task_id)

        # Update pending work in state manager
        if state_manager and result.success:
            from ..state_manager import PendingWorkSnapshot
            pw = PendingWorkSnapshot(
                task_id=task_id,
                assigned_to=target_agent,
                work_type=f"{transition_name} — {phase_to}",
                spawn_session_key=result.session_key,
                spawned_at=result.spawn_timestamp,
            )
            state_manager.update_pending_work(pw)

        return {
            "success": result.success,
            "session_key": result.session_key,
            "target_agent": target_agent,
            "phase_to": phase_to,
            "transition": transition_name,
            "prompt_template_used": template_used,
            "prompt_length": len(prompt),
            "spawn_timestamp": result.spawn_timestamp,
        }


# ===== CLI — Test the session dispatch layer =====
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DS-EO Session Dispatch Tester")
    parser.add_argument("action", choices=["spawn", "render", "parallel", "transition"], help="Action")
    parser.add_argument("--target", "-t", help="Target agent (implementer, reviewer, cto, pm)")
    parser.add_argument("--task-id", "-T", default="TASK_20260805_TEST")
    args = parser.parse_args()

    sd = SessionDispatcher(workspace_root="/home/deepsim/ds_eo_openclaw")

    if args.action == "spawn":
        prompt = "Test dispatch for review."
        result = sd.spawn_agent(args.target or "implementer", prompt, args.task_id)
        print(f"Spawn result:")
        print(f"  Success: {result.success}")
        print(f"  Session: {result.session_key}")
        print(f"  Agent: {result.agent_id}")
        print(f"  Preview: {result.prompt_preview[:100]}")

    elif args.action == "render":
        from ..engine import WorkflowEngine
        engine = WorkflowEngine()
        engine.load_workflow()
        prompt, tmpl = sd.render_spawn_prompt(
            target_agent_id=args.target or "implementer",
            transition_name="G1_APPROVE",
            task_id=args.task_id,
            engine=engine,
            extra_context={"spec_ref": "specs/TEST.md", "priority": "P1"},
        )
        print(f"Template used: {tmpl}")
        print(f"Prompt ({len(prompt)} chars):")
        print(prompt[:500])

    elif args.action == "parallel":
        result = sd.dispatch_parallel([
            {"target_agent_id": "implementer", "prompt_text": "Review this plan.", "task_id": args.task_id},
            {"target_agent_id": "reviewer", "prompt_text": "Assess quality.", "task_id": args.task_id},
        ])
        print(f"Parallel dispatch: {result['dispatched']} agents")
        for agent, res in result["results"].items():
            print(f"  {agent}: session={res['session_key']}, success={res['success']}")

    elif args.action == "transition":
        from ..engine import WorkflowEngine
        engine = WorkflowEngine()
        engine.load_workflow()
        result = sd.trigger_transition_dispatch(
            transition_name="G1_APPROVE",
            task_id=args.task_id,
            engine=engine,
        )
        print(f"Transition dispatch: {json.dumps({k:str(v)[:80] for k,v in result.items()}, indent=2)}")
