#!/usr/bin/env python3
"""Grazer discovery client — pure logic, no MCP dependency (fully unit-testable).

Stable error contract: every method returns {"ok": True, ...} or a predictable
{"ok": False, "error": {...}} object, never a silent empty result.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

# Supported platforms. Keep status honest: "live" = backed now, others declared.
PLATFORMS = {
    "bottube": {"status": "live", "description": "BoTTube AI-native video platform"},
}


def err(code: str, message: str, *, retryable: bool = True, **details) -> dict:
    return {"ok": False, "error": {"code": code, "message": message,
                                   "retryable": retryable, "source": "grazer",
                                   "details": details or {}}}


def clamp(n: Any, lo: int, hi: int) -> int:
    try:
        return max(lo, min(int(n), hi))
    except (TypeError, ValueError):
        return lo


class GrazerClient:
    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None,
                 transport: Optional[httpx.BaseTransport] = None):
        self.base_url = (base_url or os.environ.get("GRAZER_API_URL", "https://bottube.ai")).rstrip("/")
        self.timeout = timeout if timeout is not None else float(os.environ.get("GRAZER_TIMEOUT", "20"))
        self._transport = transport  # for tests (httpx.MockTransport)

    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        try:
            with httpx.Client(timeout=self.timeout, follow_redirects=True,
                              transport=self._transport) as c:
                r = c.get(f"{self.base_url}{path}", params=params or {})
        except httpx.TimeoutException:
            return err("UPSTREAM_TIMEOUT", f"{path} did not respond before {self.timeout}s")
        except httpx.HTTPError as e:
            return err("UPSTREAM_UNREACHABLE", str(e))
        if r.status_code != 200:
            return err("UPSTREAM_STATUS", f"{path} returned HTTP {r.status_code}",
                       retryable=r.status_code >= 500, status=r.status_code)
        try:
            return {"ok": True, "data": r.json()}
        except ValueError:
            return err("UPSTREAM_BAD_JSON", f"{path} returned non-JSON", retryable=False)

    def _check_platform(self, platform: str) -> Optional[dict]:
        if platform not in PLATFORMS:
            return err("UNKNOWN_PLATFORM", f"unsupported platform: {platform}",
                       retryable=False, supported=list(PLATFORMS))
        return None

    # --- public surface (mirrored by the MCP tools) --- #
    def platforms(self) -> dict:
        return {"ok": True, "platforms": PLATFORMS, "default": "bottube"}

    def trending(self, platform: str = "bottube", limit: int = 10) -> dict:
        if (e := self._check_platform(platform)):
            return e
        res = self._get("/api/trending", {"limit": clamp(limit, 1, 50)})
        return res if not res["ok"] else {"ok": True, "platform": platform, "items": res["data"]}

    def discover(self, query: str, platform: str = "bottube", limit: int = 10) -> dict:
        if not query or not query.strip():
            return err("BAD_REQUEST", "query is required", retryable=False)
        if (e := self._check_platform(platform)):
            return e
        res = self._get("/api/search", {"q": query.strip(), "limit": clamp(limit, 1, 50)})
        return res if not res["ok"] else {"ok": True, "platform": platform,
                                          "query": query.strip(), "items": res["data"]}

    def feed(self, platforms: Optional[list[str]] = None, limit: int = 10) -> dict:
        targets = platforms or [p for p, m in PLATFORMS.items() if m["status"] == "live"]
        feed: dict[str, Any] = {}
        errors: dict[str, Any] = {}
        for p in targets:
            if (e := self._check_platform(p)):
                errors[p] = e["error"]
                continue
            r = self.trending(p, limit)
            if r["ok"]:
                feed[p] = r["items"]
            else:
                errors[p] = r["error"]
        return {"ok": feed != {}, "feed": feed, "errors": errors or None}
