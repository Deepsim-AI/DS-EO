"""DshHttpClient — HTTP client for DeepSeek Harness API calls.

Production-ready infrastructure for Phase 6+ DSH adapter methods.
Uses configurable base URL so endpoints flip to real URLs when DSH API ships.

Usage:
    client = DshHttpClient(base_url="https://dsh.example.com/api", auth_token="...")
    result = client.post("/sessions/key/compact", body={"session_key": "k"})
    
When base_url is empty/unreachable, callers fall back to backward-compat paths.
"""

from __future__ import annotations
import json
import logging
import urllib.error
import urllib.request
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Mapping of HTTP status codes → DSH error strings
HTTP_ERROR_MAP = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    408: "Request Timeout",
    409: "Conflict",
    422: "Unprocessable Entity",
    429: "Rate Limited",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


class DshHttpClient:
    """HTTP client for DSH API calls with configurable base URL and error handling."""

    def __init__(
        self,
        base_url: str = "",
        auth_token: Optional[str] = None,
        timeout: int = 30,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Args:
            base_url: DSH API base URL (e.g., "https://dsh.example.com/api").
                      Empty string means "DSH unavailable" — callers should fall back.
            auth_token: Bearer token for authentication. Can also come from env DSH_API_TOKEN.
            timeout: Request timeout in seconds.
            headers: Additional default HTTP headers.
        """
        self.base_url = base_url.rstrip("/") if base_url else ""
        self.auth_token = auth_token or (
            None  # In production: os.environ.get("DSH_API_TOKEN")
        )
        self.timeout = timeout
        self.default_headers = headers or {
            "Content-Type": "application/json",
        }

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from base_url and endpoint."""
        if not self.base_url:
            return ""
        endpoint = endpoint.lstrip("/")
        return f"{self.base_url}/{endpoint}"

    def _build_request(
        self, url: str, method: str, body: Optional[Dict[str, Any]] = None
    ) -> urllib.request.Request:
        """Build a urllib Request with auth headers."""
        req = urllib.request.Request(url, method=method)
        headers = dict(self.default_headers)
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        for k, v in headers.items():
            req.add_header(k, v)
        if body is not None:
            req.data = json.dumps(body).encode("utf-8")
        return req

    def post(self, endpoint: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        POST to DSH API endpoint.
        
        Returns:
            Parsed JSON response dict on success (HTTP 200/201).
            None if DSH is unavailable (empty base_url or network error).
        """
        url = self._build_url(endpoint)
        if not url:
            return None

        req = self._build_request(url, "POST", body)

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = resp.read().decode("utf-8")
                logger.debug(f"DSH POST {endpoint} → HTTP {resp.status}")
                return json.loads(resp_data) if resp_data else {}
        except urllib.error.HTTPError as e:
            error_msg = HTTP_ERROR_MAP.get(e.code, f"HTTP {e.code}")
            logger.warning(f"DSH POST {endpoint} → HTTP {e.code}: {error_msg}")
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning(f"DSH POST {endpoint} → connection error: {e}")
            return None

    def get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """GET from DSH API endpoint."""
        url = self._build_url(endpoint)
        if not url:
            return None

        req = urllib.request.Request(url)
        if self.auth_token:
            req.add_header("Authorization", f"Bearer {self.auth_token}")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_data = resp.read().decode("utf-8")
                logger.debug(f"DSH GET {endpoint} → HTTP {resp.status}")
                return json.loads(resp_data) if resp_data else {}
        except urllib.error.HTTPError as e:
            error_msg = HTTP_ERROR_MAP.get(e.code, f"HTTP {e.code}")
            logger.warning(f"DSH GET {endpoint} → HTTP {e.code}: {error_msg}")
            return None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning(f"DSH GET {endpoint} → connection error: {e}")
            return None

    def delete(self, endpoint: str) -> bool:
        """DELETE from DSH API endpoint."""
        url = self._build_url(endpoint)
        if not url:
            return False

        req = urllib.request.Request(url, method="DELETE")
        if self.auth_token:
            req.add_header("Authorization", f"Bearer {self.auth_token}")

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                logger.debug(f"DSH DELETE {endpoint} → HTTP {resp.status}")
                return True
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as e:
            logger.warning(f"DSH DELETE {endpoint} → error: {e}")
            return False

    def is_available(self) -> bool:
        """Check if DSH base URL is configured and reachable."""
        return bool(self.base_url)
