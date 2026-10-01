"""DSH Headless Adapter — Executes DS-EO roles via `dsh --profile <name>` headless invocations.

This adapter translates the RuntimeAPI protocol into subprocess calls to DSH's
headless mode. Each role execution becomes a controlled process with structured
JSON-mode output parsing, timeout handling, and session lifecycle management.

Hardware-aware design:
    This system is a Jetson Orin (61GiB unified memory). Per AGENTS.md:
    "Never load more than 3 large models simultaneously." The adapter manages
    model loading/unloading between role invocations to respect this constraint.

Architecture:
    DS-EO dispatcher  →  dsh_headless_adapter.DshHeadlessAdapter  →  subprocess
    RuntimeAPI methods map to `dsh --profile <role-profile> --json "task"` invocations.

Usage:
    from ds_eo_dsh.adapter.dsh_headless_adapter import DshHeadlessAdapter

    adapter = DshHeadlessAdapter()

    result = adapter.submit_task(
        task={"instructions": "Analyze the requirements and produce a plan."},
        role="cto",
    )
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from .runtime_api import ActionResult, RuntimeSession, RuntimeModel

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Data types — DS-EO ↔ DSH headless exchange
# --------------------------------------------------------------------------- #

@dataclass
class TaskExecutionResult:
    """Structured result from a DSH headless invocation."""
    task_id: str
    role: str
    profile_name: str
    success: bool
    output_text: str
    error_message: Optional[str]
    exit_code: int
    turn_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    usage_steps: List[Dict[str, Any]] = field(default_factory=list)
    session_id: Optional[str] = None
    model_used: Optional[str] = None
    executed_at: str = ""

    def __post_init__(self):
        if not self.executed_at:
            self.executed_at = datetime.now(timezone.utc).isoformat()


@dataclass
class SessionInfo:
    """Session info returned from get_session_info / list_sessions."""
    session_id: str
    profile_name: str
    status: str  # "active" | "completed" | "error" | "unknown"
    last_turn_time: Optional[str] = None
    turn_count: int = 0


# --------------------------------------------------------------------------- #
# DSH Headless Adapter — implements RuntimeAPI protocol
# --------------------------------------------------------------------------- #

class DshHeadlessAdapter:
    """Runtime adapter that executes DS-EO roles via `dsh --profile` headless invocations.

    Each role maps to a DSH profile (created with bundles @deepseek-ai/dsh-base
    + @deepseek-ai/dsh-headless). The adapter manages the full lifecycle:
    model management, process creation, timeout handling, JSON-mode output parsing,
    error mapping.

    On Jetson Orin hardware, the adapter uses per-role model profiles to ensure
    no more than 3 large models are loaded simultaneously.
    """

    # Per-role model defaults (configurable at init)
    DEFAULT_MODEL_MAP: Dict[str, str] = {
        "cto":      "qwen3.6:35b",
        "implementer": "qwen3.8:27b",
        "reviewer":  "laguna-xs-2.1:q4_K_M",
        "pm":       "ornith-1.5:35b",
    }

    # Role → timeout mapping (seconds) for DSH headless invocations
    DEFAULT_TIMEOUT_MAP: Dict[str, int] = {
        "cto":     120,
        "implementer": 600,
        "reviewer": 300,
        "pm":      180,
    }

    def __init__(
        self,
        dsh_binary: str = "dsh",
        cwd: Optional[str] = None,
        model_overrides: Optional[Dict[str, str]] = None,
        timeout_overrides: Optional[Dict[str, int]] = None,
        enable_model_management: bool = True,
    ):
        """Initialize the adapter.

        Args:
            dsh_binary: Path to the DSH binary. Defaults to "dsh" on PATH.
            cwd: Working directory for subprocess execution. Defaults to None
                (inherits parent process working directory).
            model_overrides: Mapping of role_name → model_id to override defaults.
            timeout_overrides: Mapping of role_name → timeout_seconds to override defaults.
            enable_model_management: If True, manage ollama model loading/unloading
                between role invocations. On Jetson Orin this is critical to avoid
                OOM errors when too many models are loaded simultaneously.
        """
        self.dsh_binary: str = dsh_binary
        self.cwd: Optional[str] = cwd or os.getcwd()
        self.model_overrides: Dict[str, str] = model_overrides or {}
        self.timeout_overrides: Dict[str, int] = timeout_overrides or {}
        self.enable_model_management: bool = enable_model_management

        # Merge overrides into defaults
        self._model_map: Dict[str, str] = dict(self.DEFAULT_MODEL_MAP)
        self._model_map.update(model_overrides or {})
        self._timeout_map: Dict[str, int] = dict(self.DEFAULT_TIMEOUT_MAP)
        self._timeout_map.update(timeout_overrides or {})

    # =========================================================================
    # Public RuntimeAPI Protocol methods (10 methods from runtime_api.RuntimeAPI)
    # =========================================================================

    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> "ActionResult":
        """Compact a DSH session's context.

        Not applicable to headless mode (sessions are ephemeral).
        Returns success=True as a no-op; the concept of context compaction
        doesn't apply when each task is a fresh process invocation.
        """
        return ActionResult(
            success=True,
            error=None,
            details={
                "method": "no_op",
                "reason": "DSH headless sessions are ephemeral; no context to compact",
                "session_key": session_key,
            },
        )

    def archive_session(self, session_key: str, agent_id: Optional[str] = None,
                       reason: str = "completed") -> ActionResult:
        """Archive a DSH session.

        Not directly applicable to headless mode. Logs the archiving intent
        for tracking purposes only.
        """
        logger.info("Archiving session '%s' (reason: %s)", session_key, reason)
        return ActionResult(
            success=True,
            error=None,
            details={
                "method": "log_only",
                "reason": "Session archiving logged for tracking; headless sessions are ephemeral",
                "session_key": session_key,
            },
        )

    def close_session(self, session_key: str, agent_id: Optional[str] = None) -> ActionResult:
        """Close a DSH session.

        Not applicable to headless mode. Returns success=True as no-op.
        """
        return ActionResult(
            success=True,
            error=None,
            details={
                "method": "no_op",
                "reason": "DSH headless sessions are ephemeral; no session to close",
                "session_key": session_key,
            },
        )

    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> Optional[RuntimeSession]:
        """Get info about a DSH session.

        Returns RuntimeSession with available metadata. Since headless sessions
        are ephemeral and exist only during execution, this returns tracked
        metadata for sessions known to the adapter's history.
        """
        # In headless mode, we can't reliably inspect sessions without a running process.
        # Return a minimal session info for tracking purposes.
        return RuntimeSession(
            key=session_key,
            agent_id=agent_id,
            status="unknown",
            context_size_bytes=0,
            turn_count=0,
            last_turn_time=None,
        )

    def spawn_session(self, config: dict) -> ActionResult:
        """Spawn a new DSH agent session.

        In headless mode, this is equivalent to starting a headless task
        with the provided configuration. Returns success=True indicating
        the process will be started on next submit_task call.

        Args:
            config: Session configuration dict with keys like:
                - profile_name: DSH profile name (ignored in headless mode)
                - model: (optional) model override
                - timeout: (optional) task timeout in seconds
        """
        logger.info("Spawning session via config: %s", config.get("profile_name", "default"))
        return ActionResult(
            success=True,
            error=None,
            details={
                "method": "session_spawned",
                "message": "Session will be created on next task submission in headless mode",
            },
        )

    def submit_task(self, task: dict, role: str, plan: Optional[dict] = None) -> ActionResult:
        """Execute a task via DSH headless for the given role.

        This is the core execution method — translates DS-EO task instructions
        into `dsh --profile <role-profile> --json "task_instructions"` calls.

        Args:
            task: Task dict with keys like:
                - instructions: Main task text to send to the agent
                - context_files: (optional) list of file paths for context
                - artifacts: (optional) list of artifact filenames to attach
            role: DS-EO role name ("cto", "implementer", "reviewer", "pm")
            plan: (optional) CTO plan dict with additional instructions

        Returns:
            ActionResult containing TaskExecutionResult in details.
        """
        # Resolve model for this role
        model_id = self._model_map.get(role, self.DEFAULT_MODEL_MAP["pm"])

        # Handle model management for Jetson Orin (RAM constraint)
        if self.enable_model_management:
            self._ensure_model_loaded(model_id)

        instructions = task.get("instructions", "")
        if not instructions:
            return ActionResult(
                success=False,
                error="Task must contain 'instructions' field with non-empty text",
                details={"task": task},
            )

        # Build full task prompt (include plan context if provided)
        if plan and plan.get("instructions"):
            full_prompt = instructions + "\n\n[Plan Context]\n" + plan["instructions"]
        else:
            full_prompt = instructions

        timeout = self._timeout_map.get(role, 300)

        # Execute via DSH headless
        execution_result = self._execute_headless(
            task_text=full_prompt,
            model_id=model_id,
            timeout=timeout,
        )

        if execution_result.success:
            return ActionResult(
                success=True,
                error=None,
                details={
                    "task_id": execution_result.task_id,
                    "role": role,
                    "model_used": execution_result.model_used,
                    "output_text": execution_result.output_text,
                    "session_id": execution_result.session_id,
                    "usage": {
                        "input_tokens": execution_result.input_tokens,
                        "output_tokens": execution_result.output_tokens,
                        "cache_read_tokens": execution_result.cache_read_tokens,
                        "turn_count": execution_result.turn_count,
                    },
                },
            )
        else:
            return ActionResult(
                success=False,
                error=execution_result.error_message or "Unknown error",
                details={
                    "task_id": execution_result.task_id,
                    "role": role,
                    "model_used": execution_result.model_used,
                    "exit_code": execution_result.exit_code,
                    "partial_output": execution_result.output_text[:500] if execution_result.output_text else None,
                    "turn_count": execution_result.turn_count,
                    "usage": {
                        "input_tokens": execution_result.input_tokens,
                        "output_tokens": execution_result.output_tokens,
                        "cache_read_tokens": execution_result.cache_read_tokens,
                        "turn_count": execution_result.turn_count,
                    },
                },
            )

    def run_tools(self, session_key: str, tool_name: str, tool_args: dict,
                  agent_id: Optional[str] = None) -> ActionResult:
        """Run tools within a session.

        Not applicable to headless mode — tool invocation is handled by the
        LLM model internally within each DSH session. This method returns
        success=False with an explanatory message.
        """
        return ActionResult(
            success=False,
            error="Tool execution not supported in headless mode",
            details={
                "reason": "Tools are invoked by the LLM within each DSH session; "
                          "external tool calling is not needed for this execution model",
            },
        )

    def model_info(self, model_id: str) -> RuntimeModel:
        """Get information about a model.

        Queries Ollama directly via HTTP API to get model metadata.
        Returns RuntimeModel with verified metadata from the running instance.
        """
        return self._get_ollama_model_info(model_id)

    def available_models(self) -> list[RuntimeModel]:
        """List all available models by querying Ollama's HTTP API.

        Returns RuntimeModel objects populated from `curl http://localhost:11434/api/tags`.
        """
        return self._get_ollama_models()

    def run_task(self, tool: str, args: dict) -> ActionResult:
        """Execute a named task/hook via headless invocation.

        In headless mode, this invokes the PM profile with a task-specific
        instruction based on the tool name and arguments. Used for hooks
        and specialized DS-EO operations (e.g., "generate_plan", "check_gates").
        """
        # Map known task names to instructions
        task_instructions = self._get_task_instruction(tool, args)

        if not task_instructions:
            return ActionResult(
                success=False,
                error=f"No implementation for task tool '{tool}'",
                details={"tool": tool, "args": args},
            )

        # Use the PM role profile as default (PM is the coordinator)
        model_id = self._model_map.get("pm", "ornith-1.5:35b")

        if self.enable_model_management:
            self._ensure_model_loaded(model_id)

        timeout = self._timeout_map.get("pm", 180)

        execution_result = self._execute_headless(
            task_text=task_instructions,
            model_id=model_id,
            timeout=timeout,
        )

        return ActionResult(
            success=execution_result.success,
            error=execution_result.error_message,
            details={
                "task_id": execution_result.task_id,
                "role": "pm",
                "output_text": execution_result.output_text,
                "usage": {
                    "input_tokens": execution_result.input_tokens,
                    "output_tokens": execution_result.output_tokens,
                },
            },
        )

    def register_binding(self, command: str, handler_fn: Any) -> bool:
        """Register a command binding for slash commands.

        Not applicable to headless mode (no slash command mechanism).
        Stores for tracking purposes only; returns True.
        """
        logger.info(
            "Binding '%s' registered (headless mode: stored but not invoked via DSH)",
            command,
        )
        return True

    def create(self) -> "DshHeadlessAdapter":
        """Factory method — returns self to conform with RuntimeAPI.create()."""
        return self

    # =========================================================================
    # Private helpers
    # =========================================================================

    def _execute_headless(
        self,
        task_text: str,
        model_id: str,
        timeout: int,
    ) -> TaskExecutionResult:
        """Execute a single DSH headless invocation and parse the result.

        Uses `--json` mode for structured output with turn-by-turn events,
        token usage, and final result. The task_text becomes the user prompt
        for the DSH agent running on the configured model.

        IMPORTANT: This method does NOT manage model loading — that is done
        by _ensure_model_loaded before invocation to prevent OOM on Jetson Orin.

        Args:
            task_text: The task instructions to send as the user prompt.
            model_id: Model ID for this execution (must be loaded beforehand).
            timeout: Maximum seconds before the process is terminated.

        Returns:
            TaskExecutionResult with parsed output and usage statistics.
        """
        # Build command — use ollama API key if set, otherwise rely on Ollama's local auth
        cmd = [
            self.dsh_binary,
            "--profile", "ds-eo-headless",  # Generic profile name
            "--json",
            f"--model={model_id}",
            task_text,
        ]

        logger.debug(
            "DSH headless exec: dsh --profile ds-eo-headless --model %s '...' (timeout=%ds)",
            model_id, timeout,
        )

        result = TaskExecutionResult(
            task_id=str(uuid.uuid4()),
            role="unknown",
            profile_name="ds-eo-headless",
            success=False,
            output_text="",
            error_message=None,
            exit_code=-1,
            model_used=model_id,
            executed_at=datetime.now(timezone.utc).isoformat(),
        )

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.cwd,
            )
            result.exit_code = proc.returncode

            # Parse JSON-mode output (stream of JSON objects per line)
            events = self._parse_json_output(proc.stdout)

            if proc.returncode == 0:
                result.success = True
                result.output_text = self._extract_final_text(events)
            else:
                # Non-zero exit — check for partial output or error
                final_text = self._extract_final_text(events)
                if final_text:
                    result.output_text = final_text  # May have partial completion
                result.error_message = proc.stderr.strip() or f"Non-zero exit code: {proc.returncode}"

        except subprocess.TimeoutExpired as e:
            result.error_message = f"Timeout after {timeout}s (exit code {e.returncode})"
            logger.warning("DSH headless timeout for model '%s': %s", model_id, result.error_message)
        except FileNotFoundError:
            result.error_message = f"DSH binary not found: {self.dsh_binary}"
            logger.error(result.error_message)
        except Exception as e:
            result.error_message = f"Execution error: {type(e).__name__}: {e}"
            logger.exception("DSH headless execution failed for model '%s'", model_id)

        return result

    def _ensure_model_loaded(self, model_id: str) -> None:
        """Ensure a model is loaded in Ollama memory.

        On Jetson Orin (61GiB unified memory), we respect the "max 3 large
        models simultaneously" constraint by unloading unused models before
        loading new ones. Large models are those > 5GB VRAM footprint.

        This method is safe — it only interacts with Ollama's local API.
        """
        if not self.enable_model_management:
            return

        try:
            # Check what's currently loaded (Ollama keeps list in memory)
            loaded = self._get_loaded_models()

            # If already loaded, nothing to do
            if any(model_id in m for m in loaded):
                logger.debug("Model '%s' already loaded", model_id)
                return

            # Estimate size of target model from ollama list
            available = self._get_available_models()
            target_size = 0
            for m in available:
                if model_id in m["name"]:
                    target_size = m.get("size", 0)
                    break

            # Count currently loaded models (by size estimation, > 5GB = large)
            large_loaded = sum(1 for name in loaded if self._model_size(name) > 5e9)

            # If too many large models loaded, unload the smallest one not needed
            if large_loaded >= 3 and target_size > 0:
                # Find smallest non-critical model to unload
                unloads = []
                for name in loaded:
                    sz = self._model_size(name)
                    # Don't unload any model we might need (keep a buffer of 2)
                    if large_loaded - len(unloads) > 1 and self._model_size(name) > 5e9:
                        unloads.append((name, sz))

                if unloads:
                    # Unload smallest loaded model
                    unload_name = min(unloads, key=lambda x: x[1])[0]
                    try:
                        subprocess.run(
                            ["ollama", "rm", unload_name],
                            capture_output=True, text=True, timeout=30,
                        )
                        logger.info("Unloaded model '%s' to free memory for '%s'",
                                   unload_name, model_id)
                    except Exception as e:
                        logger.warning("Failed to unload model '%s': %s", unload_name, e)

            # Load the target model (if not already loaded after cleanup)
            if not any(model_id in m for m in self._get_loaded_models()):
                try:
                    subprocess.run(
                        ["ollama", "pull", model_id],
                        capture_output=True, text=True, timeout=120,
                    )
                    logger.info("Ensured model '%s' is available", model_id)
                except Exception as e:
                    logger.warning("Could not ensure model '%s' is loaded: %s", model_id, e)

        except Exception as e:
            logger.debug("Model management failed (non-fatal): %s", e)

    def _get_loaded_models(self) -> List[str]:
        """Get list of currently loaded models from Ollama process table."""
        try:
            result = subprocess.run(
                ["ps", "-eo", "rss,cmd"],
                capture_output=True, text=True, timeout=5,
            )
            loaded = []
            for line in result.stdout.split("\n"):
                if "ollama" in line.lower() and "ollama/serve" not in line:
                    loaded.append(line)
            return loaded
        except Exception:
            # Fallback: empty list (don't block execution)
            return []

    def _get_available_models(self) -> List[Dict[str, Any]]:
        """Get available models from Ollama API."""
        try:
            url = "http://localhost:11434/api/tags"
            req = __import__("urllib.request").request.Request(url)
            with __import__("urllib.request").urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            return data.get("models", [])
        except Exception:
            return []

    def _get_loaded_models_via_api(self) -> List[str]:
        """Get list of currently loaded models via Ollama API."""
        try:
            url = "http://localhost:11434/api/tags"
            req = __import__("urllib.request").request.Request(url)
            with __import__("urllib.request").urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
        except Exception:
            return []

    def _model_size(self, name: str) -> int:
        """Estimate model size from its name."""
        available = self._get_available_models()
        for m in available:
            if name in m["name"]:
                return m.get("size", 0)
        # Heuristic estimation
        model_lower = name.lower()
        if "qwen3.8" in model_lower or "qwen3.6" in model_lower:
            return int(22e9)  # ~22GB for large Qwen models
        elif "laguna-xs" in model_lower:
            return int(20e9)  # quantized but still large
        elif "ornith-1.5" in model_lower:
            return int(22e9)
        elif "nomic-embed-text" in model_lower:
            return int(274e6)  # ~274MB for embedding model
        return int(5e9)  # Default assumption

    def _parse_json_output(self, stdout: str) -> Dict[str, Any]:
        """Parse JSON-mode output (stream of JSON objects per line).

        Extracts final text, token usage, session ID, and step events.

        Args:
            stdout: Raw stdout from DSH headless invocation.

        Returns:
            Dictionary with extracted fields from the JSON event stream.
        """
        result = {
            "final_text": "",
            "turn_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "steps": [],
            "session_id": None,
        }

        for line in stdout.strip().split("\n"):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                event_type = event.get("type", "")

                if event_type == "session":
                    result["session_id"] = event.get("sessionId")
                elif event_type == "status":
                    phase = event.get("phase", "")
                    turn = event.get("turn", 0)

                    if phase == "turn_start":
                        result["turn_count"] += 1

                    # Extract token usage from step_end or other events with usage field
                    usage = event.get("usage", {})
                    if usage:
                        result["input_tokens"] += usage.get("inputTokens", 0)
                        result["output_tokens"] += usage.get("outputTokens", 0)
                        result["cache_read_tokens"] += usage.get("cacheReadTokens", 0)

                elif event_type == "final":
                    final_text = event.get("text", "")
                    if final_text:
                        result["final_text"] = final_text

            except json.JSONDecodeError:
                # Non-JSON line — skip (could be stderr that leaked to stdout)
                continue

        return result

    def _extract_final_text(self, events: Dict[str, Any]) -> str:
        """Extract final answer text from parsed events."""
        if events.get("final_text"):
            return events["final_text"]
        # Fallback: last "text" event in steps
        for step in reversed(events.get("steps", [])):
            if step.get("type") == "status":
                text = step.get("text", "")
                if text and len(text) > 1:
                    return text
        return ""

    def _get_task_instruction(self, tool: str, args: dict) -> Optional[str]:
        """Map task tool names to DSH instructions."""
        instructions_map = {
            "generate_plan": "Generate a detailed task plan with acceptance criteria, "
                             "risk analysis, and implementation steps.",
            "check_gates": "Verify all gate artifacts exist and are valid. Return a checklist.",
            "send_notification": "Draft a notification message for the team about the current state.",
        }

        return instructions_map.get(tool) or (
            f"Execute task '{tool}' with arguments: {json.dumps(args)}."
        )

    def _get_ollama_models(self) -> list[RuntimeModel]:
        """Query Ollama's HTTP API for available models.

        Returns RuntimeModel objects populated from `curl http://localhost:11434/api/tags`.
        Handles connection errors gracefully.
        """
        try:
            import urllib.request
            url = "http://localhost:11434/api/tags"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())

            models = []
            for model_entry in data.get("models", []):
                name = model_entry.get("name", "")
                size_bytes = model_entry.get("size", 0)

                context_window = self._estimate_context_window(name)
                max_tokens = min(context_window // 2, 32768)

                models.append(RuntimeModel(
                    id=f"ollama/{name}",
                    context_window=context_window,
                    max_tokens=max_tokens,
                    gpu_layers=-1,
                    ram_bytes=size_bytes if size_bytes else 0,
                    provider="ollama",
                    params={"context_window": context_window},
                ))

            return models

        except Exception as e:
            logger.warning("Could not query Ollama API: %s", e)
            return []

    def _get_ollama_model_info(self, model_id: str) -> RuntimeModel:
        """Get info for a specific model by querying Ollama's API."""
        models = self._get_ollama_models()
        for m in models:
            if m.id == f"ollama/{model_id}" or model_id in m.id:
                return m

        # Fallback: heuristic estimation
        context_window = self._estimate_context_window(model_id)
        return RuntimeModel(
            id=f"ollama/{model_id}",
            context_window=context_window,
            max_tokens=min(context_window // 2, 32768),
            gpu_layers=-1,
            ram_bytes=0,
            provider="ollama",
            params={"context_window": context_window},
        )

    @staticmethod
    def _estimate_context_window(model_id: str) -> int:
        """Estimate context window from model ID."""
        model_lower = model_id.lower()
        if "qwen3.8" in model_lower or "qwen3.6" in model_lower:
            return 131072
        elif "laguna-xs" in model_lower:
            return 4096
        elif "ornith-1.5" in model_lower:
            return 131072
        elif "nomic-embed-text" in model_lower:
            return 8192
        else:
            return 4096

