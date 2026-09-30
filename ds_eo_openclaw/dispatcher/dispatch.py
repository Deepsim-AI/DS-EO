"""
DS-EO Dispatcher — Main dispatch orchestrator.

This is the primary interface used by the PM agent to manage tasks.
It wires together: Registry → State Manager → Workflow Engine
and provides a clean task lifecycle API.

Usage from PM:
    dispatcher = Dispatcher(workspace_root="/home/deepsim/ds_eo_openclaw")
    
    # Open a new task
    dispatcher.open_task(task_id, spec_ref, priority, notes)
    
    # Advance through gates
    dispatcher.advance_g1_approved(task_id)
    dispatcher.advance_g2_complete(task_id)
    dispatcher.advance_g3_approved(task_id) 
    dispatcher.advance_g4_approved(task_id)
    
    # Query status
    status = dispatcher.get_task_status(task_id)
    
    # Check stalls
    stalled = dispatcher.check_stalls()
"""

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .registry import AgentRegistry
from .engine import WorkflowEngine, TransitionRecord, TransitionResult
from .state_manager import TaskStateManager, TransitionSnapshot, PendingWorkSnapshot


@dataclass
class TaskStatus:
    """Current status of a task."""
    task_id: str
    current_phase: str
    phase_label: str
    workflow_version: str
    transition_count: int
    last_transition: Optional[str] = None
    last_transition_at: Optional[str] = None
    completed_at: Optional[str] = None
    stalled: bool = False
    stall_reason: Optional[str] = None
    pending_work_type: Optional[str] = None
    assigned_to: Optional[str] = None


class Dispatcher:
    """
    Primary dispatcher orchestrator.
    
    Manages the full task lifecycle through the G0-G4 gate machine:
      S0_OPEN (PM) → S1_PLANNING (CTO) → S2_IMPLEMENTATION (Implementer) 
      → S3_REVIEW (Reviewer) → S4_APPROVAL (CTO) → S5_COMPLETE (PM)
    """

    def __init__(self, workspace_root: str = None):
        if workspace_root is None:
            workspace_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.workspace_root = workspace_root
        self.registry = AgentRegistry(workspace_root=workspace_root)
        self.engine = WorkflowEngine()  # engine_path overridden per-task if needed
        self._registry_loaded = False

    def initialize(self) -> tuple[bool, str]:
        """Load registry and validate workflow. Call once at start of session."""
        result = self.registry.load()
        if not result.success:
            return False, f"Registry load failed: {result.error}"

        if not self.engine.load_workflow():
            return False, "Workflow engine failed to load definition"

        self._registry_loaded = True
        agents = self.registry.list_agents()
        agent_ids = ", ".join(a['id'] for a in agents)
        return True, f"Ready — {result.agents_loaded} agents [{agent_ids}]"

    def _get_registry_checksum(self) -> str:
        """Get current SHA256 of agents_list.json."""
        path = os.path.join(self.workspace_root, "agents_list.json")
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def _get_task_manager(self, task_id: str) -> TaskStateManager:
        """Get or create a state manager for a task."""
        sm = TaskStateManager(task_id, workspace_root=self.workspace_root)
        ok, msg = sm.ensure_directory()
        if not ok:
            raise RuntimeError(f"Cannot create task directory: {msg}")
        return sm

    def open_task(
        self,
        task_id: str,
        spec_ref: str = "",
        priority: str = "P1",
        notes: str = "",
        workspace_root: str = None,
    ) -> tuple[bool, str]:
        """
        Create a new task in S0_OPEN (Task Open) phase.

        Args:
            task_id: Task ID (e.g., "TASK_20260805_001")
            spec_ref: Reference to the spec or requirement
            priority: P0, P1, or P2
            notes: User-provided context

        Returns:
            (success, task_id_or_error)
        """
        if not self._registry_loaded:
            return False, "Dispatcher not initialized. Call initialize() first."

        checksum = self._get_registry_checksum()
        
        sm = self._get_task_manager(task_id)
        ok, msg = sm.create_state(
            current_phase="S0_OPEN",
            workflow_version=self.engine.workflow_version,
            registry_checksum=checksum,
            extra_metadata={
                "spec_ref": spec_ref,
                "priority": priority,
                "notes": notes,
                "registry_agents": self.registry.list_agents(),
            }
        )
        
        if not ok:
            return False, msg

        # Record G0_ENTRY transition
        now = datetime.now(timezone.utc).isoformat()
        txn_record = TransitionSnapshot(
            id=f"txn_{task_id}_g0",
            transition_name="G0_ENTRY",
            from_phase=None,
            to_phase="S0_OPEN",
            timestamp=now,
            triggered_by_agent="pm",
            event_type="TASK_OPEN",
            payload_summary=f"New task: {spec_ref} ({priority})",
        )

        # Update state with transition
        ok2, msg2 = sm.update_phase("S0_OPEN", txn_record)
        if not ok2:
            return False, f"Failed to record G0_ENTRY: {msg2}"

        # Append to dispatch log
        ok3, seq3 = sm.append_dispatch_log({
            "ts": now,
            "event_type": "G0_ENTRY",
            "phase_from": None,
            "phase_to": "S0_OPEN",
            "source_agent": "pm",
            "target_agent": "cto",
            "payload_summary": txn_record.payload_summary,
            "success": True,
        })

        return True, task_id

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get current status of a task."""
        sm = self._get_task_manager(task_id)
        state, err = sm.read_state()
        if err:
            return None
        
        # Check stalls
        sc = state.get("stall_checks", {})
        stalled = sc.get("stalled", False)
        stall_reason = ""

        if not stalled and self.engine._loaded:
            phase_entered = sc.get("current_phase_entered")
            last_update = sc.get("last_artifact_update")
            if phase_entered:
                stall = self.engine.check_stall(from_phase_entered_at=phase_entered, 
                                                  last_artifact_update=last_update)
                stalled = stall.stalled
                stall_reason = stall.reason or ""

        # Get phase label from engine
        current_phase = state.get("current_phase", "unknown")
        phase_config = self.engine.phases.get(current_phase, {})
        phase_label = phase_config.get("label", current_phase) if self.engine._loaded else current_phase

        return TaskStatus(
            task_id=task_id,
            current_phase=current_phase,
            phase_label=phase_label,
            workflow_version=state.get("workflow_version"),
            transition_count=len(state.get("transition_history", [])),
            last_transition=state.get("transition_history")[-1]["transition_name"] if state.get("transition_history") else None,
            last_transition_at=state.get("updated_at"),
            completed_at=state.get("completed_at"),
            stalled=stalled,
            stall_reason=stall_reason,
            pending_work_type=state.get("pending_work", {}).get("work_type"),
            assigned_to=state.get("pending_work", {}).get("assigned_to"),
        )

    def advance_g1(self, task_id: str, user_approved: bool = True) -> tuple[bool, str]:
        """
        Advance task through G1 (Planning → Implementation).

        Args:
            task_id: Task to advance
            user_approved: Whether user approved the plan

        Returns:
            (success, status_message)
        """
        if not self._registry_loaded:
            return False, "Not initialized"

        sm = self._get_task_manager(task_id)
        
        # Verify current phase
        state, err = sm.read_state()
        if err or state.get("current_phase") != "S1_PLANNING":
            return False, f"Task must be in S1_PLANNING. Current: {state.get('current_phase')}"

        # Verify required artifacts
        base_path = os.path.dirname(sm.state_path)  # task directory
        cto_plan_exists = os.path.exists(os.path.join(base_path, "CTO_PLAN.md"))
        if not cto_plan_exists:
            return False, f"Missing required artifact: CTO_PLAN.md (in {base_path})"

        if user_approved:
            # Execute transition
            now = datetime.now(timezone.utc).isoformat()
            txn_record = TransitionSnapshot(
                id=f"txn_{task_id}_g1",
                transition_name="G1_APPROVE",
                from_phase="S1_PLANNING",
                to_phase="S2_IMPLEMENTATION",
                timestamp=now,
                triggered_by_agent="cto",
                event_type="DELEGATE",
                payload_summary=f"Plan approved by user — delegating to Implementer",
                artifacts_verified=["CTO_PLAN.md"],
            )

            # Update state
            ok, msg = sm.update_phase("S2_IMPLEMENTATION", txn_record)
            if not ok:
                return False, f"State update failed: {msg}"

            # Append dispatch log entry
            ok_log, _ = sm.append_dispatch_log({
                "ts": now,
                "event_type": "G1_APPROVE",
                "phase_from": "S1_PLANNING",
                "phase_to": "S2_IMPLEMENTATION",
                "source_agent": "cto",
                "target_agent": "implementer",
                "payload_summary": txn_record.payload_summary,
                "artifacts_verified": ["CTO_PLAN.md"],
                "success": True,
            })

            # Update pending work
            pw = PendingWorkSnapshot(
                task_id=task_id,
                assigned_to="implementer",
                work_type="Implementation per CTO_PLAN.md",
            )
            sm.update_pending_work(pw)

            return True, f"Task {task_id} → S2_IMPLEMENTATION. Implementer delegated."

        else:
            # Revision needed — stay in S1_PLANNING
            now = datetime.now(timezone.utc).isoformat()
            txn_record = TransitionSnapshot(
                id=f"txn_{task_id}_g1_reject",
                transition_name="G1_REJECT",
                from_phase="S1_PLANNING",
                to_phase="S1_PLANNING",  # Self-loop
                timestamp=now,
                triggered_by_agent="cto",
                event_type="PLAN_REVISED",
                payload_summary=f"Plan revision requested by user",
            )
            ok, msg = sm.update_phase("S1_PLANNING", txn_record)
            return True, f"Task {task_id} stays in S1_PLANNING (revision needed)"

    def advance_g2(self, task_id: str, implementation_report_exists: bool = True) -> tuple[bool, str]:
        """
        Advance task through G2 (Implementation → Review).

        Args:
            task_id: Task to advance
            implementation_report_exists: Whether IMPLEMENTATION_REPORT.md exists

        Returns:
            (success, status_message)
        """
        sm = self._get_task_manager(task_id)
        
        state, err = sm.read_state()
        if err or state.get("current_phase") != "S2_IMPLEMENTATION":
            return False, f"Task must be in S2_IMPLEMENTATION. Current: {state.get('current_phase')}"

        base_path = os.path.dirname(sm.state_path)
        impl_report_exists = implementation_report_exists and os.path.exists(
            os.path.join(base_path, "IMPLEMENTATION_REPORT.md")
        )
        
        if not impl_report_exists:
            return False, f"Missing required artifact: IMPLEMENTATION_REPORT.md"

        now = datetime.now(timezone.utc).isoformat()
        txn_record = TransitionSnapshot(
            id=f"txn_{task_id}_g2",
            transition_name="G2_COMPLETE",
            from_phase="S2_IMPLEMENTATION",
            to_phase="S3_REVIEW",
            timestamp=now,
            triggered_by_agent="implementer",
            event_type="IMPL_COMPLETE",
            payload_summary=f"Implementation complete — ready for review",
            artifacts_verified=["IMPLEMENTATION_REPORT.md"],
        )

        ok, msg = sm.update_phase("S3_REVIEW", txn_record)
        if not ok:
            return False, f"State update failed: {msg}"

        ok_log, _ = sm.append_dispatch_log({
            "ts": now,
            "event_type": "G2_COMPLETE",
            "phase_from": "S2_IMPLEMENTATION",
            "phase_to": "S3_REVIEW",
            "source_agent": "implementer",
            "target_agent": "reviewer",
            "payload_summary": txn_record.payload_summary,
            "artifacts_verified": ["IMPLEMENTATION_REPORT.md"],
            "success": True,
        })

        pw = PendingWorkSnapshot(
            task_id=task_id,
            assigned_to="reviewer",
            work_type="Independent verification of implementation",
        )
        sm.update_pending_work(pw)

        return True, f"Task {task_id} → S3_REVIEW. Reviewer delegated."

    def advance_g3(self, task_id: str, reviewer_approved: bool = True) -> tuple[bool, str]:
        """
        Advance task through G3 (Review → Final Approval).

        Args:
            task_id: Task to advance
            reviewer_approved: Whether reviewer recommends approval

        Returns:
            (success, status_message)
        """
        sm = self._get_task_manager(task_id)
        
        state, err = sm.read_state()
        if err or state.get("current_phase") != "S3_REVIEW":
            return False, f"Task must be in S3_REVIEW. Current: {state.get('current_phase')}"

        base_path = os.path.dirname(sm.state_path)
        review_report_exists = os.path.exists(os.path.join(base_path, "REVIEW_REPORT.md"))

        if reviewer_approved and not review_report_exists:
            return False, f"Missing required artifact: REVIEW_REPORT.md"

        if reviewer_approved:
            now = datetime.now(timezone.utc).isoformat()
            txn_record = TransitionSnapshot(
                id=f"txn_{task_id}_g3",
                transition_name="G3_APPROVE",
                from_phase="S3_REVIEW",
                to_phase="S4_APPROVAL",
                timestamp=now,
                triggered_by_agent="reviewer",
                event_type="REVIEW_COMPLETE",
                payload_summary=f"Review approved — forwarding to CTO for final decision",
                artifacts_verified=["REVIEW_REPORT.md"],
            )

            ok, msg = sm.update_phase("S4_APPROVAL", txn_record)
            if not ok:
                return False, f"State update failed: {msg}"

            ok_log, _ = sm.append_dispatch_log({
                "ts": now,
                "event_type": "G3_APPROVE",
                "phase_from": "S3_REVIEW",
                "phase_to": "S4_APPROVAL",
                "source_agent": "reviewer",
                "target_agent": "cto",
                "payload_summary": txn_record.payload_summary,
                "artifacts_verified": ["REVIEW_REPORT.md"],
                "success": True,
            })

            pw = PendingWorkSnapshot(
                task_id=task_id,
                assigned_to="cto",
                work_type="Final G4 approval decision based on review",
            )
            sm.update_pending_work(pw)

            return True, f"Task {task_id} → S4_APPROVAL. CTO to issue final G4 decision."
        else:
            # Reviewer requests changes — send back to implementation
            now = datetime.now(timezone.utc).isoformat()
            txn_record = TransitionSnapshot(
                id=f"txn_{task_id}_g3_changes",
                transition_name="G3_CHANGES",
                from_phase="S3_REVIEW",
                to_phase="S2_IMPLEMENTATION",  # Back to implementation!
                timestamp=now,
                triggered_by_agent="reviewer",
                event_type="REVISION_REQUESTED",
                payload_summary=f"Reviewer requests changes — returning to Implementer",
            )

            ok, msg = sm.update_phase("S2_IMPLEMENTATION", txn_record)
            if not ok:
                return False, f"State update failed: {msg}"

            ok_log, _ = sm.append_dispatch_log({
                "ts": now,
                "event_type": "G3_CHANGES",
                "phase_from": "S3_REVIEW",
                "phase_to": "S2_IMPLEMENTATION",
                "source_agent": "reviewer",
                "target_agent": "implementer",
                "payload_summary": txn_record.payload_summary,
                "success": True,
            })

            return True, f"Task {task_id} → S2_IMPLEMENTATION (revision loop). Reviewer requested changes."

    def advance_g4(self, task_id: str, user_approved: bool = True) -> tuple[bool, str]:
        """
        Advance task through G4 (Final Approval → Complete).

        Args:
            task_id: Task to advance
            user_approved: Whether user gave final approval

        Returns:
            (success, status_message)
        """
        sm = self._get_task_manager(task_id)
        
        state, err = sm.read_state()
        if err or state.get("current_phase") != "S4_APPROVAL":
            return False, f"Task must be in S4_APPROVAL. Current: {state.get('current_phase')}"

        base_path = os.path.dirname(sm.state_path)
        
        # Verify all G4 required artifacts
        g4_required = ["CTO_PLAN.md", "IMPLEMENTATION_REPORT.md", "REVIEW_REPORT.md", "CTO_APPROVAL.md"]
        missing = [f for f in g4_required if not os.path.exists(os.path.join(base_path, f))]

        if user_approved and missing:
            return False, f"G4 requires all artifacts present. Missing: {', '.join(missing)}"

        if user_approved:
            now = datetime.now(timezone.utc).isoformat()
            txn_record = TransitionSnapshot(
                id=f"txn_{task_id}_g4",
                transition_name="G4_APPROVE",
                from_phase="S4_APPROVAL",
                to_phase="S5_COMPLETE",
                timestamp=now,
                triggered_by_agent="pm",
                event_type="PM_CLOSED",
                payload_summary=f"G4 approved by user — completing task closure",
                artifacts_verified=g4_required,
            )

            ok, msg = sm.update_phase("S5_COMPLETE", txn_record)
            if not ok:
                return False, f"State update failed: {msg}"

            # Mark complete (sets completed_at)
            ok2, _ = sm.mark_complete()
            
            ok_log, _ = sm.append_dispatch_log({
                "ts": now,
                "event_type": "G4_APPROVE",
                "phase_from": "S4_APPROVAL",
                "phase_to": "S5_COMPLETE",
                "source_agent": "pm",
                "target_agent": "pm",
                "payload_summary": txn_record.payload_summary,
                "artifacts_verified": g4_required,
                "success": True,
            })

            sm.clear_pending_work()

            return True, f"Task {task_id} → S5_COMPLETE. Post-G4 cleanup complete."
        else:
            # CTO rejects — deep rejection back to implementation
            now = datetime.now(timezone.utc).isoformat()
            txn_record = TransitionSnapshot(
                id=f"txn_{task_id}_g4_reject",
                transition_name="G4_REJECT",
                from_phase="S4_APPROVAL",
                to_phase="S2_IMPLEMENTATION",  # Deep rejection
                timestamp=now,
                triggered_by_agent="cto",
                event_type="REVISION_REQUESTED",
                payload_summary=f"G4 rejected by CTO — returning to implementation",
            )

            ok, msg = sm.update_phase("S2_IMPLEMENTATION", txn_record)
            if not ok:
                return False, f"State update failed: {msg}"

            ok_log, _ = sm.append_dispatch_log({
                "ts": now,
                "event_type": "G4_REJECT",
                "phase_from": "S4_APPROVAL",
                "phase_to": "S2_IMPLEMENTATION",
                "source_agent": "cto",
                "target_agent": "implementer",
                "payload_summary": txn_record.payload_summary,
                "success": True,
            })

            return True, f"Task {task_id} → S2_IMPLEMENTATION (deep rejection). CTO rejected final implementation."

    def check_all_stalls(self) -> list[dict]:
        """Check all tasks in docs/dispatchers/ for stalls."""
        base = os.path.join(self.workspace_root, "docs", "dispatchers")
        if not os.path.exists(base):
            return []

        stalls = []
        for entry in sorted(os.listdir(base)):
            task_dir = os.path.join(base, entry)
            if not os.path.isdir(task_dir):
                continue

            sm = TaskStateManager(entry, workspace_root=self.workspace_root)
            state, err = sm.read_state()
            if err:
                continue

            sc = state.get("stall_checks", {})
            phase_entered = sc.get("current_phase_entered")
            last_update = sc.get("last_artifact_update")

            stall = self.engine.check_stall(from_phase_entered_at=phase_entered,
                                            last_artifact_update=last_update)

            if stall.stalled:
                stalls.append({
                    "task_id": entry,
                    "current_phase": state.get("current_phase"),
                    "stalled": True,
                    "reason": stall.reason,
                    "idle_minutes": round(stall.idle_minutes, 1),
                    "phase_duration_minutes": round(stall.phase_duration_minutes, 1),
                })

        return stalls

    def get_task_transition_log(self, task_id: str) -> list[dict]:
        """Get the full transition log (from dispatch_log.jsonl)."""
        sm = TaskStateManager(task_id, workspace_root=self.workspace_root)
        log_path = os.path.join(sm.base_path, "dispatch_log.jsonl")
        
        if not os.path.exists(log_path):
            return []

        entries = []
        with open(log_path) as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        return entries


# ====================================================================
# CLI — full task lifecycle demo
# ====================================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DS-EO Dispatcher CLI")
    parser.add_argument("action", choices=["init", "open", "g1", "g2", "g3", "g4", 
                                            "status", "stalls", "log", "test"],
                       help="Action to perform")
    parser.add_argument("--task-id", "-t", help="Task ID (required for most actions)")
    parser.add_argument("--approved", action="store_true", help="Approve (vs. reject)")
    args = parser.parse_args()

    d = Dispatcher(workspace_root="/home/deepsim/ds_eo_openclaw")

    if args.action == "init":
        ok, msg = d.initialize()
        print(f"{'✓' if ok else '✗'} {msg}")

    elif args.action == "open":
        if not args.task_id:
            print("ERROR: --task-id required")
            exit(1)
        ok, msg = d.open_task(args.task_id, spec_ref="specs/FEATURE_X.md", priority="P1")
        print(f"{'✓' if ok else '✗'} {msg}")

    elif args.action == "g1":
        ok, msg = d.advance_g1(args.task_id, user_approved=args.approved)
        print(f"{'✓' if ok else '✗'} {msg}")

    elif args.action == "g2":
        ok, msg = d.advance_g2(args.task_id, implementation_report_exists=True)
        print(f"{'✓' if ok else '✗'} {msg}")

    elif args.action == "g3":
        ok, msg = d.advance_g3(args.task_id, reviewer_approved=args.approved)
        print(f"{'✓' if ok else '✗'} {msg}")

    elif args.action == "g4":
        ok, msg = d.advance_g4(args.task_id, user_approved=args.approved)
        print(f"{'✓' if ok else '✗'} {msg}")

    elif args.action == "status":
        status = d.get_task_status(args.task_id)
        if status:
            comp = f", completed={status.completed_at}" if status.completed_at else ""
            stall_str = f", STALLED ({status.stall_reason})" if status.stalled else ""
            print(f"Task {status.task_id}")
            print(f"  Phase:     {status.phase_label} ({status.current_phase})")
            print(f"  Transitions: {status.transition_count}")
            print(f"  Last transition: {status.last_transition} at {status.last_transition_at}")
            print(f"  Pending:   {status.pending_work_type or 'none'} → {status.assigned_to or 'unassigned'}")
            print(f"  Workflow:  v{status.workflow_version}{stall_str}{comp}")
        else:
            print("Task not found or has no state")

    elif args.action == "stalls":
        stalls = d.check_all_stalls()
        if stalls:
            for s in stalls:
                print(f"  ⚠ {s['task_id']}: {s['reason']} ({s['phase_duration_minutes']}m elapsed)")
        else:
            print("  ✓ No stalled tasks")

    elif args.action == "log":
        entries = d.get_task_transition_log(args.task_id)
        for e in entries:
            ts = e.get('ts', '?')[:19]
            ev = e.get('event_type', '?')
            src = e.get('source_agent', '?')
            tgt = e.get('target_agent', '?')
            pf = e.get('phase_from', 'null') or '-'
            pt = e.get('phase_to', '?')
            print(f"  [{ts}] {ev} | {pf} → {pt} | {src} → {tgt}")

    elif args.action == "test":
        # Run a full lifecycle simulation
        test_id = "TASK_20260805_CLI_TEST"
        
        print("=== Full G0-G4 Lifecycle Test ===\n")
        
        ok, msg = d.initialize()
        assert ok, f"Init failed: {msg}"
        print(f"1. Init: ✓ {msg}")

        ok, msg = d.open_task(test_id, spec_ref="specs/FEATURE_TEST.md", priority="P1")
        assert ok, f"Open failed: {msg}"
        print(f"2. Open task: ✓ → S0_OPEN ({msg})")

        # Create fake CTO_PLAN.md so G1 doesn't complain
        import os.path as osp
        task_base = osp.join("/home/deepsim/ds_eo_openclaw/docs/dispatchers", test_id)
        with open(os.path.join(task_base, "CTO_PLAN.md"), "w") as f:
            f.write("# CTO PLAN\n## Test Plan\n- Criterion 1\n- Criterion 2\n")

        ok, msg = d.advance_g1(test_id, user_approved=True)
        assert ok and "S2_IMPLEMENTATION" in msg, f"G1 failed: {msg}"
        print(f"3. G1 approved: ✓ → S2_IMPLEMENTATION")

        # Create fake IMPLEMENTATION_REPORT.md
        with open(os.path.join(task_base, "IMPLEMENTATION_REPORT.md"), "w") as f:
            f.write("# Implementation Report\n- Done\n")

        ok, msg = d.advance_g2(test_id)
        assert ok and "S3_REVIEW" in msg, f"G2 failed: {msg}"
        print(f"4. G2 complete: ✓ → S3_REVIEW")

        # Create fake REVIEW_REPORT.md
        with open(os.path.join(task_base, "REVIEW_REPORT.md"), "w") as f:
            f.write("# Review Report\nScore: 4/5\nRecommendation: APPROVE\n")

        ok, msg = d.advance_g3(test_id)
        assert ok and "S4_APPROVAL" in msg, f"G3 failed: {msg}"
        print(f"5. G3 approved: ✓ → S4_APPROVAL")

        # Create fake CTO_APPROVAL.md
        with open(os.path.join(task_base, "CTO_APPROVAL.md"), "w") as f:
            f.write("# CTO Approval\nDecision: APPROVE\n")

        ok, msg = d.advance_g4(test_id)
        assert ok and "S5_COMPLETE" in msg, f"G4 failed: {msg}"
        print(f"6. G4 approved: ✓ → S5_COMPLETE")

        # Verify status
        status = d.get_task_status(test_id)
        print(f"\n7. Final status:")
        print(f"   Phase:     {status.phase_label} ({status.current_phase})")
        print(f"   Completed: {status.completed_at}")
        print(f"   Transitions: {status.transition_count}")

        # Show log
        print(f"\n8. Transition log:")
        for e in d.get_task_transition_log(test_id):
            ts = e.get('ts', '?')[:19]
            ev = e.get('event_type', '?')
            pf = e.get('phase_from', 'null') or '-'
            pt = e.get('phase_to', '?')
            print(f"   [{ts}] {ev} | {pf} → {pt}")

        # Cleanup test dir
        if os.path.exists(task_base):
            import shutil
            shutil.rmtree(task_base)

        print(f"\n=== All lifecycle tests passed! ✓ ===")
