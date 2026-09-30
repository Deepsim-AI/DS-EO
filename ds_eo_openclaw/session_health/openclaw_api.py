"""
DS-EO Session Health — OpenClaw CLI API Wrapper (§16, §18)

Thin wrapper around the `openclaw` CLI for session lifecycle operations.
All methods use subprocess.run() with configurable timeout and return
structured results for consumption by the executor/discoverer layers.

Architecture Decision (CTO Plan §2): This module is a pure adapter — it does
not contain business logic, only translates between OpenClaw CLI semantics
and our internal ActionResult format. The real API surface lives in the
OpenClaw gateway; this layer just speaks its language.
"""

import json
import os
import subprocess
from typing import Optional


class OpenClawAPI:
    """Thin wrapper for OpenClaw CLI session lifecycle operations."""

    def __init__(self, timeout_seconds: int = 60):
        """Initialize with configurable timeout for subprocess calls.

        Args:
            timeout_seconds: Maximum seconds to wait for any single CLI call.
                             Defaults to 60s (matches OpenClaw's default RPC timeout).
        """
        self.timeout_seconds = timeout_seconds

    def compact_session(self, session_key: str, agent_id: Optional[str] = None) -> dict:
        """Compact a stored session transcript via the running gateway.

        Calls: openclaw sessions compact <key> --json [--agent <id>]

        Args:
            session_key: The session key to compact (e.g., "agent:main:main").
            agent_id: Optional agent id if the session is identified by agent.

        Returns:
            {"success": bool, "error": str|None, "context_size_kb": int|None}
        """
        args = ["openclaw", "sessions", "compact", session_key, "--json"]
        if agent_id:
            args.extend(["--agent", agent_id])

        success, stdout, stderr = self._run_cmd(args)

        if not success:
            return {
                "success": False,
                "error": f"CLI failed (exit code {stderr}): {stderr}",
                "context_size_kb": None,
            }

        try:
            result = json.loads(stdout.strip())
            # The CLI returns a JSON object with compaction details.
            # Extract context size if available; otherwise infer from success.
            context_kb = result.get("contextSizeBytes") or result.get(
                "context_size_bytes"
            )
            if context_kb is not None:
                try:
                    context_kb = int(context_kb) // 1024  # Convert bytes → KB
                except (ValueError, TypeError):
                    context_kb = None

            return {
                "success": True,
                "error": None,
                "context_size_kb": context_kb,
            }
        except json.JSONDecodeError:
            # CLI may have returned a plain string on success — treat as OK
            return {
                "success": True,
                "error": None,
                "context_size_kb": None,  # Could not parse size
            }

    def archive_session(
        self,
        session_key: str,
        agent_id: Optional[str] = None,
        dest_dir: Optional[str] = None,
    ) -> dict:
        """Export a redacted trajectory bundle for a stored session.

        Calls: openclaw sessions export-trajectory --session-key <key> --json [--agent <id>]

        Args:
            session_key: The session key to archive.
            agent_id: Optional agent id if the session is identified by agent.
            dest_dir: Directory to save the trajectory bundle (default: ~/.openclaw/sessions_archive/).

        Returns:
            {"success": bool, "file_path": str|None, "error": str|None}
        """
        # Determine output directory
        if not dest_dir:
            dest_dir = os.path.join(
                os.path.expanduser("~"), ".openclaw", "sessions_archive"
            )

        args = [
            "openclaw",
            "sessions",
            "export-trajectory",
            "--session-key",
            session_key,
            "--json",
            "--output",
            dest_dir,
        ]
        if agent_id:
            args.extend(["--agent", agent_id])

        success, stdout, stderr = self._run_cmd(args)

        if not success:
            return {
                "success": False,
                "file_path": None,
                "error": f"CLI failed (exit code {stderr}): {stderr}",
            }

        # Parse the JSON output to find where the file was written
        try:
            result = json.loads(stdout.strip())
            # The CLI may return a path in the JSON response
            file_path = (
                result.get("filePath")
                or result.get("file_path")
                or result.get("outputPath")
                or result.get("output_path")
            )

            if not file_path:
                # Fallback: check for common archive filenames in dest_dir
                if os.path.isdir(dest_dir):
                    files = [f for f in os.listdir(dest_dir) if f.endswith((".json", ".tar.gz"))]
                    if files:
                        file_path = os.path.join(dest_dir, sorted(files)[-1])

            return {
                "success": True,
                "file_path": file_path,
                "error": None,
            }
        except json.JSONDecodeError:
            # Plain text response — check if dest_dir has new files
            if os.path.isdir(dest_dir):
                files = [f for f in os.listdir(dest_dir) if f.endswith((".json", ".tar.gz"))]
                if files:
                    file_path = os.path.join(dest_dir, sorted(files)[-1])
                    return {
                        "success": True,
                        "file_path": file_path,
                        "error": None,
                    }

            return {
                "success": False,
                "file_path": None,
                "error": "Could not determine archive file path from CLI output",
            }

    def close_session(
        self, session_key: str, agent_id: Optional[str] = None
    ) -> dict:
        """Close a stored session (destructive).

        Strategy: OpenClaw has no direct 'close' API. We use cleanup with --fix-missing
        to remove the session entry from the store if its transcript file is missing,
        otherwise we log the request and return documented limitation.

        Args:
            session_key: The session key to close.
            agent_id: Optional agent id if the session is identified by agent.

        Returns:
            {"success": bool, "method": str, "error": str|None}
        """
        # Attempt cleanup with --fix-missing — only works for sessions whose
        # transcript files have been deleted (i.e., already closed/cleaned up)
        args = [
            "openclaw",
            "sessions",
            "cleanup",
            "--json",
            "--fix-missing",
        ]

        success, stdout, stderr = self._run_cmd(args)

        if not success:
            return {
                "success": False,
                "method": "none",
                "error": f"OpenClaw close not directly supported. Cleanup failed (exit code {stderr}): {stderr}",
            }

        # Check if our session was cleaned up
        try:
            result = json.loads(stdout.strip())
            removed_keys = []
            if isinstance(result, list):
                for item in result:
                    key = item.get("sessionKey") or item.get("key", "")
                    if key == session_key:
                        removed_keys.append(key)
            elif isinstance(result, dict):
                # Some cleanup responses nest under a "removed" key
                removed_list = result.get("removed", [])
                for item in removed_list:
                    key = item.get("sessionKey") or item.get("key", "")
                    if key == session_key:
                        removed_keys.append(key)

            if removed_keys:
                return {
                    "success": True,
                    "method": "cleanup_fix_missing",
                    "error": None,
                }
        except json.JSONDecodeError:
            pass  # Plain text response — assume best effort

        # Session wasn't cleaned up (still has transcript file) — log limitation
        return {
            "success": False,
            "method": "none",
            "error": (
                f"OpenClaw does not support direct session close. "
                f"The session '{session_key}' still exists in the store. "
                f"To fully remove: delete its transcript file manually or use --fix-missing after deletion."
            ),
        }

    def get_session_info(self, session_key: str, agent_id: Optional[str] = None) -> dict:
        """Get information about a specific stored session.

        Calls: openclaw sessions list --json (then filters to find target).

        Args:
            session_key: The session key to query.
            agent_id: Optional agent id if the session is identified by agent.

        Returns:
            {"success": bool, "context_size_bytes": int|None, "turn_count": int|None,
             "status": str|None, "last_turn_time": str|None, "error": str|None}
        """
        args = ["openclaw", "sessions", "list", "--json"]

        success, stdout, stderr = self._run_cmd(args)

        if not success:
            return {
                "success": False,
                "context_size_bytes": None,
                "turn_count": None,
                "status": None,
                "last_turn_time": None,
                "error": f"CLI failed (exit code {stderr}): {stderr}",
            }

        try:
            sessions = json.loads(stdout.strip())
            if not isinstance(sessions, list):
                return {
                    "success": False,
                    "context_size_bytes": None,
                    "turn_count": None,
                    "status": None,
                    "last_turn_time": None,
                    "error": f"Expected JSON array from sessions list, got: {type(sessions).__name__}",
                }

            # Find the target session in the list
            for session in sessions:
                key = session.get("key") or session.get("sessionKey", "")
                if key == session_key:
                    return {
                        "success": True,
                        "context_size_bytes": session.get(
                            "contextSizeBytes"
                        ) or session.get("context_size_bytes"),
                        "turn_count": session.get("turnCount") or session.get(
                            "turn_count"
                        ),
                        "status": session.get("status", "unknown"),
                        "last_turn_time": session.get(
                            "lastTurnTime"
                        ) or session.get("last_turn_time"),
                        "error": None,
                    }

            # Session not found in list — it may be archived or cleaned up
            return {
                "success": False,
                "context_size_bytes": None,
                "turn_count": None,
                "status": None,
                "last_turn_time": None,
                "error": f"Session '{session_key}' not found in OpenClaw session store",
            }

        except json.JSONDecodeError:
            return {
                "success": False,
                "context_size_bytes": None,
                "turn_count": None,
                "status": None,
                "last_turn_time": None,
                "error": f"Could not parse JSON from sessions list output",
            }

    def _run_cmd(self, args: list[str], timeout: int = 60) -> tuple[bool, str, str]:
        """Run a CLI command via subprocess.run() and return structured result.

        Args:
            args: Command-line arguments (must start with 'openclaw').
            timeout: Override the default timeout_seconds for this call.

        Returns:
            Tuple of (success, stdout, stderr).
        """
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=timeout or self.timeout_seconds,
            )
            success = result.returncode == 0
            return (success, result.stdout.strip(), result.stderr.strip())
        except subprocess.TimeoutExpired:
            return (False, "", f"Command timed out after {timeout}s")
        except FileNotFoundError:
            return (False, "", "openclaw CLI not found in PATH")
        except Exception as e:
            return (False, "", f"Unexpected error running command: {str(e)}")
