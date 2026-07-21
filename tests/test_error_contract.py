#!/usr/bin/env python3
"""Test the grazer error contract — 4 tools x 4 failure modes, offline.

Verifies that every public tool returns the documented error-envelope
shape on backend failure, never a silent empty result.

Run:  python3 -m pytest tests/test_error_contract.py -q -v
      (or: python3 tests/test_error_contract.py)
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import httpx
import pytest
from grazer_mcp.client import GrazerClient

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _client(handler):
    return GrazerClient(
        base_url="https://test.local",
        transport=httpx.MockTransport(handler),
    )


def _json(payload, capture=None):
    def h(req):
        if capture is not None:
            capture["url"] = str(req.url)
        return httpx.Response(200, json=payload)
    return h


# A representative BoTTube video object (subset of the real fields).
VIDEO = {
    "video_id": "9hq8hdFUbam", "id": 2167, "title": "Dust Bunny Elimination #2",
    "agent_name": "automatedjanitor2015", "display_name": "AutomatedJanitor2015",
    "views": 31, "likes": 8, "category": "other", "category_name": "Other",
    "duration_sec": 4.853, "watch_url": "/watch/9hq8hdFUbam",
    "thumbnail_url": "/thumbnails/9hq8hdFUbam.jpg", "created_at": 1782417722.7, "tags": ["ai"],
}

TRENDING_OK = {"category": None, "videos": [VIDEO]}
SEARCH_OK = {"page": 1, "pages": 10, "total": 200, "videos": [VIDEO]}
FEED_OK = {"mode": "heuristic", "explanation": "Popularity-only ranker", "videos": [VIDEO]}

# ---------------------------------------------------------------------------
# shared failure handlers
# ---------------------------------------------------------------------------

def _http_500(_req):
    return httpx.Response(500, text="Internal Server Error")

def _http_404(_req):
    return httpx.Response(404, text="Not Found")

def _timeout(_req):
    raise httpx.TimeoutException("upstream did not respond before timeout")

def _bad_json(_req):
    return httpx.Response(200, text="<html>not json</html>")

# ---------------------------------------------------------------------------
# 1. platforms() — local-only, no network calls but still has a contract
# ---------------------------------------------------------------------------

class TestPlatforms:
    def test_success_contract(self):
        """platforms() returns ok with platform list and default."""
        r = GrazerClient().platforms()
        assert r["ok"] is True
        assert "platforms" in r
        assert "bottube" in r["platforms"]
        assert r["default"] == "bottube"

    def test_error_contract_not_network(self):
        """platforms() never makes a network call, so it never produces
        an error-envelope response.  This is by design — the test verifies
        the method is pure-local."""
        r = GrazerClient().platforms()
        assert r["ok"] is True
        assert "error" not in r

# ---------------------------------------------------------------------------
# 2. trending() — 4 failure modes
# ---------------------------------------------------------------------------

class TestTrending:
    def test_success_contract(self):
        """trending() returns ok with count and normalized items."""
        r = _client(_json(TRENDING_OK)).trending()
        assert r["ok"] is True
        assert r["count"] == 1
        it = r["items"][0]
        assert it["id"] == "9hq8hdFUbam"
        assert it["title"] == "Dust Bunny Elimination #2"
        assert it["agent"] == "automatedjanitor2015"
        assert it["views"] == 31

    def test_http_500(self):
        """HTTP 500 returns error envelope with retryable=True."""
        r = _client(_http_500).trending()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_STATUS"
        assert e["retryable"] is True
        assert "500" in e["message"]
        assert e["source"] == "grazer"
        assert isinstance(e["details"], dict)

    def test_http_404(self):
        """HTTP 404 returns error envelope with retryable=False."""
        r = _client(_http_404).trending()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_STATUS"
        assert e["retryable"] is False
        assert "404" in e["message"]
        assert e["status"] == 404

    def test_timeout(self):
        """Timeout returns error envelope with retryable=True."""
        r = _client(_timeout).trending()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_TIMEOUT"
        assert e["retryable"] is True
        assert e["source"] == "grazer"

    def test_bad_json(self):
        """Non-JSON body returns error envelope with retryable=False."""
        r = _client(_bad_json).trending()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_BAD_JSON"
        assert e["retryable"] is False
        assert e["source"] == "grazer"

    def test_unknown_platform(self):
        """Unknown platform returns error envelope with retryable=False."""
        r = GrazerClient().trending(platform="myspace")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UNKNOWN_PLATFORM"
        assert e["retryable"] is False
        assert "bottube" in e["details"]["supported"]

# ---------------------------------------------------------------------------
# 3. discover() — 4 failure modes
# ---------------------------------------------------------------------------

class TestDiscover:
    def test_success_contract(self):
        """discover() returns ok with search metadata and normalized items."""
        r = _client(_json(SEARCH_OK)).discover("ai", page=1)
        assert r["ok"] is True
        assert r["total"] == 200
        assert r["pages"] == 10
        assert r["count"] == 1
        it = r["items"][0]
        assert it["id"] == "9hq8hdFUbam"
        assert it["title"] == "Dust Bunny Elimination #2"

    def test_http_500(self):
        """HTTP 500 returns error envelope with retryable=True."""
        r = _client(_http_500).discover("cats")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_STATUS"
        assert e["retryable"] is True
        assert "500" in e["message"]
        assert e["source"] == "grazer"

    def test_http_404(self):
        """HTTP 404 returns error envelope with retryable=False."""
        r = _client(_http_404).discover("cats")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_STATUS"
        assert e["retryable"] is False
        assert "404" in e["message"]
        assert e["status"] == 404

    def test_timeout(self):
        """Timeout returns error envelope with retryable=True."""
        r = _client(_timeout).discover("cats")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_TIMEOUT"
        assert e["retryable"] is True
        assert e["source"] == "grazer"

    def test_bad_json(self):
        """Non-JSON body returns error envelope with retryable=False."""
        r = _client(_bad_json).discover("cats")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_BAD_JSON"
        assert e["retryable"] is False
        assert e["source"] == "grazer"

    def test_empty_query(self):
        """Empty/blank query returns BAD_REQUEST error before any network call."""
        r = GrazerClient().discover("   ")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "BAD_REQUEST"
        assert e["retryable"] is False
        assert e["source"] == "grazer"

    def test_unknown_platform(self):
        """Unknown platform rejected before network call."""
        r = GrazerClient().discover("cats", platform="myspace")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UNKNOWN_PLATFORM"

# ---------------------------------------------------------------------------
# 4. feed() — 4 failure modes (ranked + latest variants)
# ---------------------------------------------------------------------------

class TestFeed:
    def test_success_contract_ranked(self):
        """feed(ranked=True) returns ok with ranker metadata and normalized items."""
        r = _client(_json(FEED_OK)).feed(ranked=True)
        assert r["ok"] is True
        assert r["ranked"] is True
        assert r["ranker"] == "heuristic"
        assert r["count"] == 1
        it = r["items"][0]
        assert it["id"] == "9hq8hdFUbam"

    def test_success_contract_latest(self):
        """feed(ranked=False) returns ok with latest items."""
        r = _client(_json({"mode": "latest", "videos": [VIDEO]})).feed(ranked=False)
        assert r["ok"] is True
        assert r["ranked"] is False
        assert r["count"] == 1

    def test_http_500(self):
        """HTTP 500 returns error envelope with retryable=True."""
        r = _client(_http_500).feed()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_STATUS"
        assert e["retryable"] is True
        assert "500" in e["message"]
        assert e["source"] == "grazer"

    def test_http_404(self):
        """HTTP 404 returns error envelope with retryable=False."""
        r = _client(_http_404).feed()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_STATUS"
        assert e["retryable"] is False
        assert "404" in e["message"]

    def test_timeout(self):
        """Timeout returns error envelope with retryable=True."""
        r = _client(_timeout).feed()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_TIMEOUT"
        assert e["retryable"] is True
        assert e["source"] == "grazer"

    def test_bad_json(self):
        """Non-JSON body returns error envelope with retryable=False."""
        r = _client(_bad_json).feed()
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UPSTREAM_BAD_JSON"
        assert e["retryable"] is False
        assert e["source"] == "grazer"

    def test_unknown_platform(self):
        """Unknown platform rejected before network call."""
        r = GrazerClient().feed(platform="myspace")
        assert r["ok"] is False
        e = r["error"]
        assert e["code"] == "UNKNOWN_PLATFORM"

# ---------------------------------------------------------------------------
# parametrized cross-tool contract checks
# ---------------------------------------------------------------------------

HTTP_500_TOOLS = [
    ("trending", lambda: _client(_http_500).trending()),
    ("discover", lambda: _client(_http_500).discover("test")),
    ("feed",     lambda: _client(_http_500).feed()),
]

@pytest.mark.parametrize("name,call", HTTP_500_TOOLS)
def test_http_500_contract(name, call):
    """All network tools return the same error shape on HTTP 500."""
    r = call()
    assert r["ok"] is False, f"{name} should not be ok on 500"
    e = r["error"]
    assert e["code"] == "UPSTREAM_STATUS", f"{name} code mismatch"
    assert e["retryable"] is True, f"{name} 500 should be retryable"
    assert e["source"] == "grazer", f"{name} source mismatch"
    assert isinstance(e["details"], dict), f"{name} details should be dict"


HTTP_404_TOOLS = [
    ("trending", lambda: _client(_http_404).trending()),
    ("discover", lambda: _client(_http_404).discover("test")),
    ("feed",     lambda: _client(_http_404).feed()),
]

@pytest.mark.parametrize("name,call", HTTP_404_TOOLS)
def test_http_404_contract(name, call):
    """All network tools return the same error shape on HTTP 404."""
    r = call()
    assert r["ok"] is False, f"{name} should not be ok on 404"
    e = r["error"]
    assert e["code"] == "UPSTREAM_STATUS", f"{name} code mismatch"
    assert e["retryable"] is False, f"{name} 404 should NOT be retryable"
    assert e["source"] == "grazer", f"{name} source mismatch"
    assert e["status"] == 404, f"{name} should have status 404"


TIMEOUT_TOOLS = [
    ("trending", lambda: _client(_timeout).trending()),
    ("discover", lambda: _client(_timeout).discover("test")),
    ("feed",     lambda: _client(_timeout).feed()),
]

@pytest.mark.parametrize("name,call", TIMEOUT_TOOLS)
def test_timeout_contract(name, call):
    """All network tools return the same error shape on timeout."""
    r = call()
    assert r["ok"] is False, f"{name} should not be ok on timeout"
    e = r["error"]
    assert e["code"] == "UPSTREAM_TIMEOUT", f"{name} code mismatch"
    assert e["retryable"] is True, f"{name} timeout should be retryable"
    assert e["source"] == "grazer", f"{name} source mismatch"


BAD_JSON_TOOLS = [
    ("trending", lambda: _client(_bad_json).trending()),
    ("discover", lambda: _client(_bad_json).discover("test")),
    ("feed",     lambda: _client(_bad_json).feed()),
]

@pytest.mark.parametrize("name,call", BAD_JSON_TOOLS)
def test_bad_json_contract(name, call):
    """All network tools return the same error shape on non-JSON body."""
    r = call()
    assert r["ok"] is False, f"{name} should not be ok on bad JSON"
    e = r["error"]
    assert e["code"] == "UPSTREAM_BAD_JSON", f"{name} code mismatch"
    assert e["retryable"] is False, f"{name} bad JSON should NOT be retryable"
    assert e["source"] == "grazer", f"{name} source mismatch"


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q", "-v"]))