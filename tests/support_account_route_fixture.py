"""Synthetic resource storage for direct service tests with the real route owner."""
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import Mock, patch
import uuid


class AccountRouteContext(SimpleNamespace):
    """Record ownership declarations without starting a settlement consumer."""

    def __init__(self, *, run_id, execution_id, **kwargs):
        defaults = {"checkpoint": Mock(), "report": Mock(return_value={}), "finish": Mock()}
        defaults.update(kwargs)
        super().__init__(run_id=run_id, execution_id=execution_id, **defaults)
        self.cleanups = {}
        self.obligations = []

    def register_cleanup(self, cleanup, *, key, blocking=True, before_transition=False):
        if key in self.cleanups or not blocking or before_transition:
            raise AssertionError("unexpected fixture cleanup declaration")
        if key != cleanup.resource_identity:
            raise AssertionError("fixture cleanup identity changed")
        self.cleanups[key] = cleanup
        return cleanup

    def add_settlement_obligation(self, action_kind, *, resource_identity, payload, blocks_permit=True):
        self.obligations.append((action_kind, resource_identity, dict(payload), blocks_permit))


@contextmanager
def account_route_resources(testcase, context, *, routes):
    """Mock only durable storage and assert the service itself released each route."""
    testcase.assertIsInstance(context, AccountRouteContext)
    testcase.assertGreater(context.run_id, 0)
    testcase.assertTrue(context.execution_id)
    context.cleanups.clear()
    context.obligations.clear()
    resources = {}
    fixture_id = uuid.uuid4().hex

    def register_resource(run_id, *, resource_type, provider="", external_id="", detail=None):
        testcase.assertEqual(context.run_id, run_id)
        testcase.assertEqual("proxy_lease", resource_type)
        testcase.assertIn(external_id, context.cleanups)
        testcase.assertEqual(context.execution_id, detail["execution_id"])
        resource_id = len(resources) + 1
        row = {
            "id": resource_id,
            "resource_uuid": f"fixture-account-route-{fixture_id}-{resource_id}",
            "run_id": run_id,
            "external_id": external_id,
            "detail": dict(detail),
            "release_calls": 0,
        }
        resources[resource_id] = row
        return {"id": resource_id, "resource_uuid": row["resource_uuid"]}

    def release_resource(resource_id, *, state="released", detail=None):
        testcase.assertIn(resource_id, resources)
        testcase.assertEqual("released", state)
        resources[resource_id]["release_calls"] += 1
        testcase.assertEqual(1, resources[resource_id]["release_calls"])
        return True

    with (
        patch("core.accounts.operation_results.operation_task_store.register_resource", side_effect=register_resource),
        patch("core.accounts.operation_results.operation_task_store.release_resource", side_effect=release_resource),
    ):
        try:
            yield resources
        finally:
            # Never drain/release in this fixture: that could conceal a service leak.
            testcase.assertEqual(len(routes), len(resources))
            testcase.assertEqual(len(resources), len(context.cleanups))
            testcase.assertEqual(len(resources), len(context.obligations))
            testcase.assertEqual(
                sorted(id(route) for route in routes),
                sorted(id(cleanup.route) for cleanup in context.cleanups.values()),
            )
            obligations = {
                identity: (kind, payload, blocking)
                for kind, identity, payload, blocking in context.obligations
            }
            testcase.assertEqual(len(resources), len(obligations))
            for row in resources.values():
                cleanup = context.cleanups[row["external_id"]]
                testcase.assertTrue(cleanup.release_confirmed)
                testcase.assertEqual(row["id"], cleanup.resource_id)
                testcase.assertEqual(row["resource_uuid"], cleanup.resource_uuid)
                testcase.assertEqual(1, row["release_calls"])
                cleanup.route.release.assert_called_once()
                testcase.assertIsInstance(cleanup.route.release.call_args.kwargs["fault"], bool)
                testcase.assertEqual(
                    (
                        "resource_release",
                        {
                            "resource_id": row["id"], "resource_uuid": row["resource_uuid"],
                            "run_id": context.run_id, "execution_id": context.execution_id,
                            "external_id": row["external_id"],
                        },
                        True,
                    ),
                    obligations[f"operation-resource:{row['resource_uuid']}"],
                )
