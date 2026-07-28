#!/usr/bin/env python3
"""Error contract tests for grazer_mcp — 4 tools × 4 failure modes.

Every tool that makes a backend call must return the documented error envelope:
    {"ok": false, "error": {code, message, retryable, source, details}}

No network calls in these tests — all backends are mocked via httpx.MockTransport.

Run:  python3 -m pytest tests/test_error_contract.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import pytest
from grazer_mcp.client import GrazerClient

# ── helpers ────────────────────────────────────────────────────────────────
ERROR_ENVELOPE_KEYS = {"code", "message", "retryable", "source", "details"}
SUCCESS_VIDEO_KEYS = {"id", "title", "agent", "views", "likes", "category",
                      "duration_sec", "url", "thumbnail", "created_at", "tags"}

VIDEO = {
    "video_id": "9hq8hdFUbam", "id": 2167, "title": "Dust Bunny Elimination #2",
    "agent_name": "automatedjanitor2015", "display_name": "AutomatedJanitor2015",
    "views": 31, "likes": 8, "category": "other", "category_name": "Other",
    "duration_sec": 4.853, "watch_url": "/watch/9hq8hdFUbam",
    "thumbnail_url": "/thumbnails/9hq8hdFUbam.jpg", "created_at": 1782417722.7,
    "tags": ["ai"],
}


def _client(handler):
    return GrazerClient(base_url="https://test.local", transport=httpx.MockTransport(handler))


def _ok_json(payload):
    def h(req):
        return httpx.Response(200, json=payload)
    return h


# Exact error-envelope validator
def _assert_error_envelope(result, expected_code, expected_retryable):
    assert result["ok"] is False, f"Expected ok=False, got {result}"
    err = result.get("error", {})
    assert ERROR_ENVELOPE_KEYS.issubset(err.keys()),         f"Missing keys: {ERROR_ENVELOPE_KEYS - err.keys()}"
    assert err["code"] == expected_code, f"Expected code={expected_code}, got {err['code']}"
    assert err["retryable"] is expected_retryable,         f"Expected retryable={expected_retryable}, got {err['retryable']}"
    assert err["source"] == "grazer", f"Expected source=grazer, got {err['source']}"
    assert isinstance(err["message"], str) and len(err["message"]) > 0
    assert isinstance(err["details"], dict)


# ── parametrized failure modes ─────────────────────────────────────────────
# Each entry: (handler_fn, expected_code, expected_retryable)
FAILURE_MODES = [
    (lambda req: httpx.Response(500, text="Server Error"), "UPSTREAM_STATUS", True),
    (lambda req: httpx.Response(404, text="Not Found"), "UPSTREAM_STATUS", False),
    (lambda req: (_ for _ in ()).throw(httpx.TimeoutException("timed out")), "UPSTREAM_TIMEOUT", True),
    (lambda req: httpx.Response(200, text="<html>not json</html>"), "UPSTREAM_BAD_JSON", False),
]


class TestTrendingErrorContract:
    """graze_trending — 4 failure modes + success normalization."""

    @pytest.mark.parametrize("handler,code,retryable", FAILURE_MODES,
                             ids=["500", "404", "timeout", "bad_json"])
    def test_4_failure_modes(self, handler, code, retryable):
        c = _client(handler)
        result = c.trending()
        _assert_error_envelope(result, code, retryable)

    def test_success_normalizes_video_shape(self):
        c = _client(_ok_json({"videos": [VIDEO]}))
        result = c.trending()
        assert result["ok"] is True
        assert result["count"] == 1
        item = result["items"][0]
        assert SUCCESS_VIDEO_KEYS.issubset(item.keys()),             f"Missing keys: {SUCCESS_VIDEO_KEYS - item.keys()}"
        assert item["id"] == "9hq8hdFUbam"
        assert item["title"] == "Dust Bunny Elimination #2"
        assert item["agent"] == "automatedjanitor2015"
        assert item["url"] == "https://test.local/watch/9hq8hdFUbam"
        assert item["thumbnail"] == "https://test.local/thumbnails/9hq8hdFUbam.jpg"


class TestDiscoverErrorContract:
    """graze_discover — 4 failure modes + success normalization."""

    @pytest.mark.parametrize("handler,code,retryable", FAILURE_MODES,
                             ids=["500", "404", "timeout", "bad_json"])
    def test_4_failure_modes(self, handler, code, retryable):
        c = _client(handler)
        result = c.discover("ai")
        _assert_error_envelope(result, code, retryable)

    def test_success_normalizes_video_shape(self):
        c = _client(_ok_json({"page": 1, "pages": 5, "total": 100, "videos": [VIDEO]}))
        result = c.discover("ai")
        assert result["ok"] is True
        assert result["count"] == 1
        item = result["items"][0]
        assert SUCCESS_VIDEO_KEYS.issubset(item.keys())


class TestFeedErrorContract:
    """graze_feed — 4 failure modes + success normalization."""

    @pytest.mark.parametrize("handler,code,retryable", FAILURE_MODES,
                             ids=["500", "404", "timeout", "bad_json"])
    def test_4_failure_modes(self, handler, code, retryable):
        c = _client(handler)
        result = c.feed()
        _assert_error_envelope(result, code, retryable)

    @pytest.mark.parametrize("ranked", [True, False], ids=["ranked", "latest"])
    def test_success_normalizes_video_shape(self, ranked):
        c = _client(_ok_json({"mode": "heuristic", "explanation": "test", "videos": [VIDEO]}))
        result = c.feed(ranked=ranked)
        assert result["ok"] is True
        assert result["count"] == 1
        item = result["items"][0]
        assert SUCCESS_VIDEO_KEYS.issubset(item.keys())


class TestPlatformsNotAffected:
    """graze_platforms — purely local, no backend call (verifies contract shape)."""

    def test_returns_expected_shape(self):
        result = GrazerClient().platforms()
        assert result["ok"] is True
        assert "platforms" in result
        assert "bottube" in result["platforms"]
        assert result["default"] == "bottube"


# README-vs-code contract mismatch check
class TestContractMismatchCheck:
    """Verify README promises match actual behaviour."""

    def test_retryable_500_is_true(self):
        result = _client(lambda req: httpx.Response(503, text="x")).trending()
        assert result["error"]["retryable"] is True

    def test_retryable_404_is_false(self):
        result = _client(lambda req: httpx.Response(404, text="x")).discover("ai")
        assert result["error"]["retryable"] is False

    def test_timeout_is_retryable(self):
        def h(req):
            raise httpx.TimeoutException("slow")
        result = _client(h).trending()
        assert result["error"]["retryable"] is True
        assert result["error"]["code"] == "UPSTREAM_TIMEOUT"

    def test_bad_json_not_retryable(self):
        result = _client(lambda req: httpx.Response(200, text="<html>")).feed()
        assert result["error"]["retryable"] is False
        assert result["error"]["code"] == "UPSTREAM_BAD_JSON"
