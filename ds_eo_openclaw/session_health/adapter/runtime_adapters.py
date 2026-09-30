# DS-EO Session Health -- shared RuntimeAPI implementations (Phase 2).

"""Neutral runtime helpers for the adapter RuntimeAPI.

These keep private backend-agnostic logic OUT of the per-backend
adapters so each adapter only translates between native concepts and
ExecutionHandle:
  * RuntimeRegistry : stable execution_id -> ExecutionHandle bookkeeping.
  * SubprocessRuntime : a RuntimeAPI over the one verified DSH primitive in
  this environment -- local subprocess execution. It implements an honest
  subset of RuntimeAPI; model registry returns clearly-marked empty results.
"""

from __future__ import annotations

import asyncio
import subprocess
import time

from .execution_handle import (
    ExecutionHandle,
    ExecutionStatus,
    RuntimeAPI,
    RuntimeKind,
)

__all__ = ["RuntimeRegistry", "SubprocessRuntime"]


class RuntimeRegistry:
    """Maps stable execution_ids to their ExecutionHandles.

Backends expose opaque native_ids (pids, remote runnable ids); callers
still hold only the stable execution_id they passed in, keeping DS-EO
core backend-agnostic in its bookkeeping as well.
    """

    def __init__(self) -> None:
        self._by_id: dict = {}

    def register(self, execution_id: str, handle) -> None:
        self._by_id[execution_id] = handle

    def get(self, execution_id, *, create=False):
        exec_id = execution_id or "exec-" + str(int(time.time() * 1000))
        if exec_id not in self._by_id:
            if not create:
                return None
            handle = ExecutionHandle(
                execution_id=exec_id,
                runtime=RuntimeKind.DSH,
                native_id=exec_id,
                metadata={"created_at": int(time.time() * 1000)},
            )
            self._by_id[exec_id] = handle
        return self._by_id[exec_id]

    def remove(self, execution_id: str) -> None:
        self._by_id.pop(execution_id, None)


class _DummyProc:
    """Stand-in for a finished subprocess (only a returncode)."""

    def __init__(self, code):
        self.returncode = code


class SubprocessRuntime(RuntimeAPI):
    """A RuntimeAPI implemented over local subprocess execution.

The DSH adapter verified primitive: DS-EO execute a small local job
maps to spawning a program. Model registry returns clearly-marked empty
results.
    """

    def __init__(self, *, registry=None):
        self.registry = registry or RuntimeRegistry()
        self._procs: dict = {}
        self._cache: dict = {}

    async def status(self, execution_id: str):
        handle = self.registry.get(execution_id)
        if handle is None:
            return ExecutionHandle(
                execution_id=execution_id or "exec-unknown",
                runtime=RuntimeKind.DSH,
                native_id=execution_id or "unknown",
                status=ExecutionStatus.ERROR,
                metadata={"reason": "unknown execution_id"},
            )
        if handle.is_terminal():
            return handle
        proc = self._procs.get(handle.native_id)
        if proc is None:
            new_status = ExecutionStatus.RUNNING
        elif proc.returncode == 0:
            new_status = ExecutionStatus.DONE
        else:
            new_status = ExecutionStatus.ERROR
        if new_status != handle.status:
            self.registry.register(handle.execution_id, handle.copy_with(status=new_status))
            return self.registry.get(handle.execution_id)
        return handle

    async def submit(self, task_id, execution_id=None, *, prompt="",
                  tool=None, args=None, model=None, role=None, metadata=None):
        exec_id = execution_id or str(task_id)
        handle = ExecutionHandle(
            execution_id=exec_id,
            runtime=RuntimeKind.DSH,
            native_id=exec_id,
            status=ExecutionStatus.CREATED,
            metadata={
                "task_id": task_id,
                "tool": tool,
                "prompt": prompt,
                "args": args,
                "model": model,
                "role": role,
                "created_at": int(time.time() * 1000),
                **(metadata or {}),
            },
        )
        self.registry.register(exec_id, handle)
        self._procs[handle.native_id] = _DummyProc(-1)
        return handle

    async def cancel(self, execution_id: str):
        handle = self.registry.get(execution_id)
        if handle is None:
            return ExecutionHandle(
                execution_id=execution_id,
                runtime=RuntimeKind.DSH,
                native_id=execution_id,
                status=ExecutionStatus.ERROR,
                metadata={"reason": "unknown execution_id"},
            )
        new_handle = handle.copy_with(status=ExecutionStatus.CANCELLED)
        self.registry.register(handle.execution_id, new_handle)
        return new_handle

    async def recover(self, execution_id, metadata=None):
        existing = self.registry.get(execution_id)
        if existing is None:
            return ExecutionHandle(
                execution_id=execution_id,
                runtime=RuntimeKind.DSH,
                native_id=execution_id,
                status=ExecutionStatus.ERROR,
                metadata={"reason": "unknown execution_id"},
            )
        new_status = ExecutionStatus.ERROR if existing.status == ExecutionStatus.DONE else ExecutionStatus.CREATED
        new_handle = existing.copy_with(status=new_status, metadata=metadata or {})
        self.registry.register(execution_id, new_handle)
        return new_handle

    async def execute(self, command, *, tool=None, args=None, prompt="",
                     model=None, role=None, metadata=None):
        cmd = command if isinstance(command, list) else ["bash", "-c", command]
        exec_id = "exec-" + str(int(time.time() * 1000))
        handle = ExecutionHandle(
            execution_id=exec_id,
            runtime=RuntimeKind.DSH,
            native_id=exec_id,
            status=ExecutionStatus.CREATED,
            metadata={
                "tool": tool,
                "args": args,
                "prompt": prompt,
                "model": model,
                "role": role,
                "command": cmd,
                "created_at": int(time.time() * 1000),
                **(metadata or {}),
            },
        )
        self.registry.register(exec_id, handle)
        self._procs[handle.native_id] = _DummyProc(-1)
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.DEVNULL,
            )
            # asyncio.wait_for raises CancelledError/TimeoutError on the awaited
            # coroutine; the underlying process is captured in `proc` and reaped
            # at the bottom of the function so no process leaks across retries.
            coro = asyncio.shield(asyncio.wait_for(proc.communicate(), timeout=120))
            try:
                data, err = await coro
            except (asyncio.TimeoutError, asyncio.CancelledError):
                # Kill and reap the process on timeout (process is always local).
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                await proc.wait()
                returncode = -1
                sterr = "Process timed out after 120s"
                out = ""
                raise subprocess.SubprocessError(sterr) from None
            returncode = proc.returncode
            out = (data or b"").decode("utf8", "replace")
            sterr = (err or b"").decode("utf8", "replace")
        except (subprocess.SubprocessError, OSError) as exc:
            returncode = -1
            out = "" + str(exc)
            sterr = ""
        self._procs[handle.native_id] = _DummyProc(returncode)
        self._cache.setdefault(exec_id, []).extend((out + " " + sterr).splitlines())
        result = self.registry.get(exec_id)
        return result.copy_with(status=ExecutionStatus.DONE if returncode == 0 else ExecutionStatus.ERROR)

    async def logs(self, execution_id: str, limit=200):
        return list(self._cache.get(execution_id, [])[-limit:])

    async def artifacts(self, execution_id: str, limit=200):
        return []  # SubprocessRuntime tracks no artifacts.

    async def available_models(self):
        return []  # SubprocessRuntime exposes no model registry.

    async def model_info(self, model_id: str):
        return None  # SubprocessRuntime exposes no model registry.
