"""Explicit no-I/O process-owner fixture for business admission tests."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import threading
from unittest.mock import patch


class FakeStandaloneOwner:
    """Only the process fence is fake; PostgreSQL permits remain real."""
    def __init__(self):
        self.closed = False

    def require_owner(self):
        if self.closed:
            raise RuntimeError("test_standalone_owner_closed")

    def close(self):
        self.closed = True


@contextmanager
def standalone_owner_fixture():
    """Preserve the caller's complete fence; never start a monitor or register atexit."""
    from core.runtime import standalone

    owner = FakeStandaloneOwner()
    with ExitStack() as stack:
        stack.enter_context(patch.object(standalone, "_OWNER", owner))
        stack.enter_context(patch.object(standalone, "_BINDING", None))
        stack.enter_context(patch.object(standalone, "_LOST", threading.Event()))
        try:
            yield owner
        finally:
            owner.close()
