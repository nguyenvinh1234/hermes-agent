"""Verifies the adapter degrades gracefully instead of raising, per
rollout spec section 32/33 ("Hermes vẫn hoạt động ... skip memory").
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests  # noqa: E402
import client  # noqa: E402


def test_search_returns_empty_list_when_unconfigured(monkeypatch):
    monkeypatch.delenv("MEMORY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("MEMORY_GATEWAY_API_KEY", raising=False)
    assert client.search("anything", user_id="u") == []


def test_add_returns_none_when_unconfigured(monkeypatch):
    monkeypatch.delenv("MEMORY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("MEMORY_GATEWAY_API_KEY", raising=False)
    assert client.add("fact", user_id="u") is None


def test_feedback_returns_false_when_unconfigured(monkeypatch):
    monkeypatch.delenv("MEMORY_GATEWAY_URL", raising=False)
    monkeypatch.delenv("MEMORY_GATEWAY_API_KEY", raising=False)
    assert client.feedback("id1", "confirmed") is False


def test_search_swallows_connection_error(monkeypatch):
    monkeypatch.setenv("MEMORY_GATEWAY_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("MEMORY_GATEWAY_API_KEY", "k")

    def _boom(*args, **kwargs):
        raise requests.ConnectionError("refused")

    monkeypatch.setattr(requests, "post", _boom)
    assert client.search("anything", user_id="u") == []


def test_add_swallows_timeout(monkeypatch):
    monkeypatch.setenv("MEMORY_GATEWAY_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("MEMORY_GATEWAY_API_KEY", "k")

    def _boom(*args, **kwargs):
        raise requests.Timeout("too slow")

    monkeypatch.setattr(requests, "post", _boom)
    assert client.add("fact", user_id="u") is None


def test_feedback_rejects_unknown_type(monkeypatch):
    monkeypatch.setenv("MEMORY_GATEWAY_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("MEMORY_GATEWAY_API_KEY", "k")
    assert client.feedback("id1", "not-a-real-type") is False
