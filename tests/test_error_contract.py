#!/usr/bin/env python3
"""Test the grazer error contract — 4 tools x 4 failure modes, offline.

Every tool must return the stable error envelope
    {"ok": False, "error": {code, message, retryable, source, details}}
on upstream failure — never a silent empty result.

Run:  python3 -m pytest tests/test_error_contract.py -v
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import pytest
from grazer_mcp.client import GrazerClient

# ── helpers ──────────────────────────────────────────────────────


def _client(handler):
    return GrazerClient(base_url="https://test.local", transport=httpx.MockTransport(handler))


def _ok_json(payload):
    def h(req):
        return httpx.Response(200, json=payload)
    return h


# ── failure-mode handlers ────────────────────────────────────────


def _http_500(_req):
    return httpx.Response(500, text="internal error")


def _http_404(_req):
    return httpx.Response(404, text="not found")


def _timeout(_req):
    raise httpx.TimeoutException("request timed out")


def _bad_json(_req):
    return httpx.Response(200, text="<html>not json</html>")


# A representative BoTTube video object (subset of the real fields).
VIDEO = {
    "video_id": "9hq8hdFUbam",
    "id": 2167,
    "title": "Dust Bunny Elimination #2",
    "agent_name": "automatedjanitor2015",
    "display_name": "AutomatedJanitor2015",
    "views": 31,
    "likes": 8,
    "category": "other",
    "category_name": "Other",
    "duration_sec": 4.853,
    "watch_url": "/watch/9hq8hdFUbam",
    "thumbnail_url": "/thumbnails/9hq8hdFUbam.jpg",
    "created_at": 1782417722.7,
    "tags": ["ai"],
}

# Each failure case: (handler, expected_code, expected_retryable)
FAILURE_CASES = [
    pytest.param(_http_500, "UPSTREAM_STATUS", True, id="500"),
    pytest.param(_http_404, "UPSTREAM_STATUS", False, id="404"),
    pytest.param(_timeout, "UPSTREAM_TIMEOUT", True, id="timeout"),
    pytest.param(_bad_json, "UPSTREAM_BAD_JSON", False, id="bad_json"),
]


# ── 1. graze_trending ────────────────────────────────────────────


class TestTrendingErrorContract:
    TOOL = "trending"

    @pytest.mark.parametrize("handler,code,retryable", FAILURE_CASES)
    def test_error_envelope(self, handler, code, retryable):
        r = _client(handler).trending("bottube", 5)
        assert r.get("ok") is False, f"expected ok=False for {self.TOOL}/{code}"
        err = r.get("error", {})
        assert err.get("code") == code, f"{self.TOOL}: expected code={code}, got {err.get('code')}"
        assert isinstance(err.get("message"), str) and len(err["message"]) > 0
        assert err.get("retryable") is retryable, f"{self.TOOL}: expected retryable={retryable}"
        assert err.get("source") == "grazer"

    def test_success_normalizes(self):
        c = _client(_ok_json({"videos": [VIDEO]}))
        r = c.trending("bottube", 5)
        assert r["ok"] is True
        assert r["count"] == 1
        item = r["items"][0]
        assert item["id"] == "9hq8hdFUbam"
        assert item["title"] == "Dust Bunny Elimination #2"
        assert item["agent"] == "automatedjanitor2015"
        assert item["views"] == 31


# ── 2. graze_discover ────────────────────────────────────────────


class TestDiscoverErrorContract:
    TOOL = "discover"

    @pytest.mark.parametrize("handler,code,retryable", FAILURE_CASES)
    def test_error_envelope(self, handler, code, retryable):
        r = _client(handler).discover("ai", "bottube", page=1)
        assert r.get("ok") is False, f"expected ok=False for {self.TOOL}/{code}"
        err = r.get("error", {})
        assert err.get("code") == code, f"{self.TOOL}: expected code={code}, got {err.get('code')}"
        assert isinstance(err.get("message"), str) and len(err["message"]) > 0
        assert err.get("retryable") is retryable, f"{self.TOOL}: expected retryable={retryable}"
        assert err.get("source") == "grazer"

    def test_success_normalizes(self):
        c = _client(_ok_json({"page": 1, "pages": 5, "total": 100, "videos": [VIDEO]}))
        r = c.discover("ai", "bottube", page=1)
        assert r["ok"] is True
        assert r["count"] == 1
        item = r["items"][0]
        assert item["id"] == "9hq8hdFUbam"
        assert item["title"] == "Dust Bunny Elimination #2"


# ── 3. graze_feed ────────────────────────────────────────────────


class TestFeedErrorContract:
    TOOL = "feed"

    @pytest.mark.parametrize("handler,code,retryable", FAILURE_CASES)
    def test_error_envelope(self, handler, code, retryable):
        r = _client(handler).feed("bottube", 5, ranked=True)
        assert r.get("ok") is False, f"expected ok=False for {self.TOOL}/{code}"
        err = r.get("error", {})
        assert err.get("code") == code, f"{self.TOOL}: expected code={code}, got {err.get('code')}"
        assert isinstance(err.get("message"), str) and len(err["message"]) > 0
        assert err.get("retryable") is retryable, f"{self.TOOL}: expected retryable={retryable}"
        assert err.get("source") == "grazer"

    def test_success_normalizes(self):
        c = _client(_ok_json({"mode": "heuristic", "explanation": "ranked", "videos": [VIDEO]}))
        r = c.feed("bottube", 5, ranked=True)
        assert r["ok"] is True
        assert r["count"] == 1
        item = r["items"][0]
        assert item["id"] == "9hq8hdFUbam"
        assert item["title"] == "Dust Bunny Elimination #2"


# ── 4. graze_platforms ───────────────────────────────────────────


class TestPlatformsErrorContract:
    """platforms() is purely local (no upstream call), so failure modes don't apply.

    However, we still verify it returns the stable ok=True envelope and
    documents the default platform.
    """

    def test_success_returns_stable_envelope(self):
        r = GrazerClient().platforms()
        assert r["ok"] is True
        assert "platforms" in r
        assert "bottube" in r["platforms"]
        assert r["default"] == "bottube"

    def test_platforms_has_status_and_description(self):
        r = GrazerClient().platforms()
        bt = r["platforms"]["bottube"]
        assert bt["status"] == "live"
        assert isinstance(bt["description"], str) and len(bt["description"]) > 0


# ── 5. Cross-cutting: every tool's error contract is complete ────


class TestErrorContractCompleteness:
    """Verify that the error envelope shape is consistent across all tools."""

    ERROR_SHAPE_KEYS = {"code", "message", "retryable", "source", "details"}

    @pytest.mark.parametrize(
        "handler,label",
        [
            pytest.param(_http_500, "trending", id="trending-500"),
            pytest.param(_http_500, "discover", id="discover-500"),
            pytest.param(_http_500, "feed", id="feed-500"),
            pytest.param(_timeout, "trending", id="trending-timeout"),
            pytest.param(_timeout, "discover", id="discover-timeout"),
            pytest.param(_timeout, "feed", id="feed-timeout"),
        ],
    )
    def test_error_envelope_has_all_keys(self, handler, label):
        c = _client(handler)
        r = {"trending": lambda: c.trending("bottube", 5),
             "discover": lambda: c.discover("ai", "bottube", 1),
             "feed": lambda: c.feed("bottube", 5, True)}[label]()
        assert r.get("ok") is False
        err = r.get("error", {})
        missing = self.ERROR_SHAPE_KEYS - set(err.keys())
        assert not missing, f"{label}: missing error keys: {missing}"
        extra = set(err.keys()) - self.ERROR_SHAPE_KEYS
        # extra keys are allowed (e.g. status from UPSTREAM_STATUS)
        assert isinstance(err["code"], str) and len(err["code"]) > 0
        assert isinstance(err["message"], str) and len(err["message"]) > 0
        assert isinstance(err["retryable"], bool)
        assert err["source"] == "grazer"
        assert isinstance(err["details"], dict)