"""Suite hygiene: warn (never fail) on background threads leaked by a test.

A test-time flake from a stray worker thread is otherwise unattributable:
the failure surfaces several files later with no link to the leaker.
This fixture snapshots live threads around every test and logs the
offenders so the next floater arrives with a return address.

Deliberately warning-only: some suites may legitimately leave daemon
threads, and a detector must never become a new flake source itself.
"""

from __future__ import annotations

import logging
import threading

import pytest

logger = logging.getLogger(__name__)


def _live_workers() -> dict[int, str]:
    return {
        thread.ident: f"{thread.name} (daemon={thread.daemon})"
        for thread in threading.enumerate()
        if thread is not threading.current_thread()
        and thread.name != "MainThread"
    }


@pytest.fixture(autouse=True)
def _warn_on_leaked_threads():
    before = _live_workers()
    yield
    after = _live_workers()
    leaked = {
        ident: desc for ident, desc in after.items() if ident not in before
    }
    # Threads that finished between snapshot and check vanish on their own.
    leaked = {
        ident: desc
        for ident, desc in leaked.items()
        if any(
            thread.ident == ident and thread.is_alive()
            for thread in threading.enumerate()
        )
    }
    if leaked:
        logger.warning(
            "test leaked %d background thread(s): %s",
            len(leaked),
            ", ".join(f"#{ident} {desc}" for ident, desc in leaked.items()),
        )
