"""
Level 2 — Agent mocked tests.

Tests agent wiring and retry logic without making real LLM calls.
The LLM is replaced with a Mock that returns a fixed response.
"""

import pytest
from unittest.mock import patch, MagicMock


def _make_mock_result(content: str) -> dict:
    """Build a fake agent.invoke() return value."""
    msg = MagicMock()
    msg.content = content
    return {"messages": [msg]}


# ─── happy path ──────────────────────────────────────────────────────────────

def test_run_inventory_monitor_returns_string():
    """run_inventory_monitor should always return a string."""
    with patch("graph.inventory_agent.agent") as mock_agent:
        mock_agent.invoke.return_value = _make_mock_result("All good.")
        from graph.inventory_agent import run_inventory_monitor
        result = run_inventory_monitor()

    assert isinstance(result, str)


def test_run_inventory_monitor_returns_last_message():
    """Should return the content of the last message."""
    expected = "CRITICAL: Coffee Pods needs restocking."
    with patch("graph.inventory_agent.agent") as mock_agent:
        mock_agent.invoke.return_value = _make_mock_result(expected)
        from graph.inventory_agent import run_inventory_monitor
        result = run_inventory_monitor()

    assert result == expected


# ─── retry logic ─────────────────────────────────────────────────────────────

def test_run_inventory_monitor_retries_on_failure():
    """Agent should retry when invoke raises an exception."""
    with patch("graph.inventory_agent.agent") as mock_agent:
        with patch("time.sleep"):  # skip actual sleep in tests
            mock_agent.invoke.side_effect = [
                Exception("API timeout"),        # attempt 1 fails
                _make_mock_result("Recovered."), # attempt 2 succeeds
            ]
            from graph.inventory_agent import run_inventory_monitor
            result = run_inventory_monitor()

    assert result == "Recovered."
    assert mock_agent.invoke.call_count == 2


def test_run_inventory_monitor_fails_after_all_retries():
    """After all retries exhausted, should return an error string."""
    with patch("graph.inventory_agent.agent") as mock_agent:
        with patch("time.sleep"):
            mock_agent.invoke.side_effect = Exception("Persistent failure")
            from graph.inventory_agent import run_inventory_monitor
            result = run_inventory_monitor(retries=3)

    assert "failed" in result.lower()
    assert mock_agent.invoke.call_count == 3


def test_run_inventory_monitor_retry_count_respected():
    """retries=1 should only try once."""
    with patch("graph.inventory_agent.agent") as mock_agent:
        with patch("time.sleep"):
            mock_agent.invoke.side_effect = Exception("Error")
            from graph.inventory_agent import run_inventory_monitor
            run_inventory_monitor(retries=1)

    assert mock_agent.invoke.call_count == 1
