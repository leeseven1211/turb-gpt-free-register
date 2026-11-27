"""销售入口与共享运行时的定向集成约束。"""

import unittest

from config.schema import CONFIG_SCHEMA, schema_default
from core.operations.concurrency import resolve_admission_class
from core.runtime.manifest import COMPONENTS, REQUIRED_DISPATCH_TYPES


class SalesWiringTests(unittest.TestCase):
    def test_sales_has_independent_shared_budget(self):
        policy = resolve_admission_class("sales_sync")
        self.assertEqual("SALES_SYNC_WORKERS", policy.config_key)
        self.assertEqual(1, schema_default("SALES_SYNC_WORKERS"))
        self.assertEqual("并发控制", CONFIG_SCHEMA["SALES_SYNC_WORKERS"].group)

    def test_owner_identity_is_explicit_configuration(self):
        self.assertEqual("local", schema_default("SALES_EXECUTOR_ID"))
        self.assertTrue(CONFIG_SCHEMA["SALES_EXECUTOR_ID"].restart)

    def test_managed_runtime_registers_handler_and_stoppable_producer(self):
        specs = {spec.name: spec for spec in COMPONENTS}
        self.assertEqual("core.sales.store:init", specs["sales_storage"].target)
        self.assertLess(list(specs).index("sales_storage"), list(specs).index("sales_handler"))
        self.assertEqual("core.sales.runtime:register_handler", specs["sales_handler"].target)
        self.assertEqual("core.sales.runtime:start_periodic_sync", specs["sales_sync"].target)
        self.assertIn("sales_sync", REQUIRED_DISPATCH_TYPES)
