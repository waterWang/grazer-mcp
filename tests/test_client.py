#!/usr/bin/env python3
"""Tests for grazer_mcp.client — no network (httpx MockTransport).

Run:  python3 tests/test_client.py   (or: python3 -m pytest -q)
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import httpx  # noqa: E402
from grazer_mcp.client import GrazerClient, PLATFORMS  # noqa: E402


def _client(handler):
    return GrazerClient(base_url="https://test.local", transport=httpx.MockTransport(handler))


def _ok(payload):
    return lambda req: httpx.Response(200, json=payload)


def test_platforms_lists_bottube():
    c = GrazerClient()
    p = c.platforms()
    assert p["ok"] and "bottube" in p["platforms"] and p["default"] == "bottube"


def test_trending_happy_path_and_params():
    seen = {}
    def h(req):
        seen["url"] = str(req.url)
        return httpx.Response(200, json=[{"id": "v1"}, {"id": "v2"}])
    c = _client(h)
    r = c.trending("bottube", 5)
    assert r["ok"] and r["platform"] == "bottube" and len(r["items"]) == 2
    assert "/api/trending" in seen["url"] and "limit=5" in seen["url"]


def test_trending_clamps_limit():
    seen = {}
    def h(req):
        seen["url"] = str(req.url); return httpx.Response(200, json=[])
    _client(h).trending("bottube", 999)
    assert "limit=50" in seen["url"]   # clamped to max


def test_discover_requires_query():
    r = GrazerClient().discover("   ")
    assert not r["ok"] and r["error"]["code"] == "BAD_REQUEST"


def test_unknown_platform_rejected():
    r = GrazerClient().trending("myspace")
    assert not r["ok"] and r["error"]["code"] == "UNKNOWN_PLATFORM"
    assert "bottube" in r["error"]["details"]["supported"]


def test_upstream_500_is_retryable_error():
    c = _client(lambda req: httpx.Response(503, text="down"))
    r = c.trending()
    assert not r["ok"] and r["error"]["code"] == "UPSTREAM_STATUS" and r["error"]["retryable"] is True


def test_upstream_404_not_retryable():
    c = _client(lambda req: httpx.Response(404, text="nope"))
    r = c.discover("cats")
    assert not r["ok"] and r["error"]["retryable"] is False


def test_timeout_maps_to_stable_error():
    def h(req): raise httpx.TimeoutException("slow")
    r = _client(h).trending()
    assert not r["ok"] and r["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_bad_json_is_handled():
    c = _client(lambda req: httpx.Response(200, text="<html>not json</html>"))
    r = c.trending()
    assert not r["ok"] and r["error"]["code"] == "UPSTREAM_BAD_JSON"


def test_feed_aggregates_and_reports_errors():
    # bottube ok; unknown platform surfaces in errors, not feed
    c = _client(_ok([{"id": "v1"}]))
    r = c.feed(["bottube", "myspace"], 3)
    assert r["ok"] and "bottube" in r["feed"]
    assert r["errors"] and "myspace" in r["errors"]


def _run():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    ok = 0
    for t in tests:
        try:
            t(); print(f"  PASS {t.__name__}"); ok += 1
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
        except Exception as e:
            print(f"  ERROR {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{ok}/{len(tests)} passed")
    return ok == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run() else 1)
