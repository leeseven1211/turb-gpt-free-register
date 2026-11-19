"""Test-owned legacy permit observations; never manufacture release evidence."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import threading
import time
from unittest.mock import patch

from core.operations import concurrency
from core.storage import postgres, registration
from core.storage.operations import permits


_RETAINED_LEGACY_FIXTURES = {}


class LegacyReleaseAbort(KeyboardInterrupt):
    """Abort before a still-owned actor loses its schema or log dependencies."""


class LegacyReleaseFixture:
    def __init__(self, *, timeout=10.0):
        self.timeout = float(timeout)
        self.contexts = {}
        self._records = {}
        self._domains = {}
        self._runs = {}
        self._scopes = {}
        self._condition = threading.Condition()
        self._stack = ExitStack()
        self._started = False
        self._closed = False
        self._close_failure = None
        self._blocked_cleanups = []
        self._owner = None
        self._restoring = False
        self._entry_refused = False

    def start(self):
        assert not self._started
        if any(concurrency.release_runtime_status().values()):
            self._entry_refused = True
            raise AssertionError("prior legacy actor remains owned")
        self._original_admit = concurrency.try_admit_and_claim
        self._original_scope = concurrency.execution_scope
        self._original_start_run = registration.start_run

        def admit(*args, **kwargs):
            result = self._original_admit(*args, **kwargs)
            context = result.context
            if context is not None:
                assert not context.settlement_ticket, "legacy fixture cannot own native settlement"
                key = (context.permit_id, context.execution_id)
                with self._condition:
                    prior = self.contexts.get(key)
                    assert prior is None or prior is context, "original context identity changed"
                    self.contexts[key] = context
                    self._records.setdefault(key, {
                        "permit_id": context.permit_id, "execution_id": context.execution_id,
                        "execution_key": context.execution_key,
                    })
                    self._domains.setdefault(key, (context._domain_url, context.domain_schema))
                    self._runs.setdefault(key, [])
                    self._scopes.setdefault(key, 0)
                    self._condition.notify_all()
                row = self._permit_row(context, time.monotonic() + self.timeout)
                assert row is not None and all(
                    row[name] == value for name, value in self._records[key].items()
                ) and row["released_at"] is None, "exact original legacy admission readback failed"
                self._records[key]["run_id"] = row["run_id"]
            return result

        @contextmanager
        def scope(context):
            key = (context.permit_id, context.execution_id)
            with self._condition:
                assert self.contexts.get(key) is context, "scope lacks observed original admission"
                self._scopes[key] += 1
            try:
                with self._original_scope(context) as actual:
                    assert actual is context
                    yield actual
            finally:
                with self._condition:
                    self._scopes[key] -= 1
                    self._condition.notify_all()

        def start_run(*args, **kwargs):
            result = self._original_start_run(*args, **kwargs)
            context = concurrency.current_execution()
            if context is not None and result is not None:
                key = (context.permit_id, context.execution_id)
                identity = {name: result.get(name) for name in
                            ("id", "attempt_id", "job_id", "execution_id")}
                assert identity["execution_id"] == context.execution_id, "registration run generation changed"
                with self._condition:
                    assert self.contexts.get(key) is context
                    if identity not in self._runs[key]:
                        self._runs[key].append(identity)
            return result

        self._stack.enter_context(patch.object(concurrency, "try_admit_and_claim", admit))
        self._stack.enter_context(patch.object(concurrency, "execution_scope", scope))
        self._stack.enter_context(patch.object(registration, "start_run", start_run))
        self._started = True
        return self

    def run_identities(self, context):
        with self._condition:
            return [dict(row) for row in self._runs[(context.permit_id, context.execution_id)]]

    def only_context(self):
        with self._condition:
            assert len(self.contexts) == 1, "exactly one original admission required"
            return next(iter(self.contexts.values()))

    def _permit_row(self, context, deadline):
        from psycopg.rows import dict_row
        url, schema = self._domains[(context.permit_id, context.execution_id)]
        assert (context._domain_url, context.domain_schema) == (url, schema), "legacy domain changed"
        with postgres.connect(url, row_factory=dict_row, deadline=deadline) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            return conn.execute(
                f"SELECT permit_id,execution_id,execution_key,run_id,released_at "
                f"FROM {permits._permit_table(schema)} "
                "WHERE permit_id=%s AND execution_id=%s",
                (context.permit_id, context.execution_id),
            ).fetchone()

    def _run_row(self, record, deadline):
        from psycopg.rows import dict_row
        url, schema = self._domains[record["_context_key"]]
        table = f"{postgres.quote_identifier(schema)}.registration_runs"
        with postgres.connect(url, row_factory=dict_row, deadline=deadline) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            return conn.execute(
                f"SELECT id,attempt_id,job_id,execution_id FROM {table} WHERE id=%s AND execution_id=%s",
                (record["id"], record["execution_id"]),
            ).fetchone()

    def _readback(self, context, deadline):
        key = (context.permit_id, context.execution_id)
        row = self._permit_row(context, deadline)
        expected = self._records[key]
        assert (row is not None and all(row[name] == value for name, value in expected.items())
                and row["released_at"] is not None), "exact legacy permit release readback failed"
        for run in self.run_identities(context):
            actual = self._run_row({**run, "_context_key": key}, deadline)
            assert actual is not None and all(actual[name] == value for name, value in run.items()), \
                "exact original registration run identity changed"

    def wait_for_released(self, context=None, *, timeout=None, deadline=None):
        """Observe one original generation; never request release or run a handler."""
        context = self.only_context() if context is None else context
        key = (context.permit_id, context.execution_id)
        assert self.contexts.get(key) is context, "unknown original legacy context"
        if deadline is None:
            deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while True:
            with self._condition:
                exited = self._scopes[key] == 0
            renewal = getattr(context, "_permit_renewal", None)
            joined = renewal is None or (renewal.release_confirmed and not renewal.thread.is_alive())
            with concurrency._RELEASE_LOCK:
                pending = key in concurrency._RELEASE_PENDING
                inflight = concurrency._RELEASE_INFLIGHT
            if context.released and exited and joined and not pending and not inflight:
                self._readback(context, deadline)
                if not any(concurrency.release_runtime_status().values()):
                    return
            assert time.monotonic() < deadline, "original legacy release wait expired"
            with self._condition:
                self._condition.wait(min(.01, max(0.0, deadline - time.monotonic())))

    def close(self):
        if self._closed:
            self._restore_dependencies()
            return
        assert not self._entry_refused, "unowned prior legacy actor must be resolved before fixture entry"
        deadline = time.monotonic() + self.timeout
        try:
            with self._condition:
                assert not any(self._scopes.values()), "original legacy scope still executing"
                contexts = tuple(self.contexts.values())
            for context in contexts:
                if not context.released:
                    concurrency.release_execution(context, reason="test_original_scope_exit", deadline=deadline)
            assert concurrency.stop_release_runtime(deadline), "legacy physical release runtime did not close"
            for context in contexts:
                self.wait_for_released(context, deadline=deadline)
            assert not any(concurrency.release_runtime_status().values()), "legacy release runtime remains owned"
        except BaseException as exc:
            self._close_failure = exc
            raise
        self._close_failure = None
        self._stack.close()
        self._closed = True
        self._restore_dependencies()

    def _restore_dependencies(self):
        if self._restoring:
            return
        self._restoring = True
        try:
            while self._blocked_cleanups:
                function, args, kwargs = self._blocked_cleanups[0]
                function(*args, **kwargs)
                self._blocked_cleanups.pop(0)
            owner = self._owner
            if owner is not None and id(owner) in _RETAINED_LEGACY_FIXTURES:
                stack, _directory = owner._legacy_retained_export_scope
                stack.close()
                del owner._legacy_retained_export_scope
                _RETAINED_LEGACY_FIXTURES.pop(id(owner))
        finally:
            self._restoring = False


def install_legacy_release_fixture(test_case, *, timeout=10.0, start=True):
    fixture = LegacyReleaseFixture(timeout=timeout)
    fixture._owner = test_case
    test_case.legacy_release_fixture = fixture
    cls = type(test_case)
    if "_legacy_release_owners" not in cls.__dict__:
        cls._legacy_release_owners = []
    cls._legacy_release_owners.append(test_case)

    def schema_guard():
        for owner in cls._legacy_release_owners:
            owned = owner.legacy_release_fixture
            if not owned._closed or owned._blocked_cleanups or id(owner) in _RETAINED_LEGACY_FIXTURES:
                raise LegacyReleaseAbort("legacy actor remains owned; schema cleanup refused")
    # PostgresTestCase's narrow lifecycle hooks also protect this nonparticipant
    # fixture; no settlement responsibility or carrier is created.
    cls._native_settlement_before_schema_use = staticmethod(schema_guard)

    def after_run(stack, directory):
        if fixture._closed and not fixture._blocked_cleanups:
            return
        directory._finalizer.detach()
        test_case._legacy_retained_export_scope = (stack, directory)
        _RETAINED_LEGACY_FIXTURES[id(test_case)] = test_case
        raise LegacyReleaseAbort("legacy actor remains owned; test stage aborted")
    test_case._native_settlement_after_run = after_run
    original_add = test_case.addCleanup

    def guard(function, *args, **kwargs):
        def cleanup():
            try:
                if fixture._close_failure is not None:
                    raise fixture._close_failure
                fixture.close()
            except BaseException:
                fixture._blocked_cleanups.append((function, args, kwargs))
                raise
            return function(*args, **kwargs)
        return cleanup

    test_case._cleanups[:] = [(guard(fn, *args, **kwargs), (), {})
                             for fn, args, kwargs in test_case._cleanups]
    def add_cleanup(function, *args, **kwargs):
        original_add(guard(function, *args, **kwargs))
    test_case.addCleanup = add_cleanup
    # The initial close is an automatic unittest cleanup too. It must honor
    # the first failure from a later-added cleanup, rather than retrying the
    # physical close and restoring dependencies behind the abort boundary.
    original_add(guard(fixture.close))
    if start:
        fixture.start()
    return fixture
