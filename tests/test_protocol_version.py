# -*- coding: utf-8 -*-
import os
import unittest
from unittest.mock import patch

from config import openai_protocol
from core.protocol_version import (
    PROTOCOL_STEP_CAPABILITIES,
    normalize_protocol_version,
    resolve_protocol_version,
)


class ProtocolVersionTests(unittest.TestCase):
    def test_normalize_accepts_only_public_v1_or_v2_values(self):
        self.assertEqual("v1", normalize_protocol_version("1"))
        self.assertEqual("v2", normalize_protocol_version("v2"))
        with self.assertRaises(ValueError):
            normalize_protocol_version("protocol_v2")

    def test_two_version_step_follows_shared_protocol_version(self):
        with patch.object(openai_protocol, "OPENAI_PROTOCOL_VERSION", "v2", create=True):
            self.assertEqual("v2", resolve_protocol_version("refresh_at"))

        with patch.object(openai_protocol, "OPENAI_PROTOCOL_VERSION", "v1", create=True):
            self.assertEqual("v1", resolve_protocol_version("refresh_at"))

    def test_single_version_step_ignores_shared_protocol_version(self):
        with patch.object(openai_protocol, "OPENAI_PROTOCOL_VERSION", "v2", create=True):
            self.assertEqual("v1", resolve_protocol_version("registration"))
            self.assertEqual("v1", resolve_protocol_version("twofa"))
            self.assertEqual("v1", resolve_protocol_version("plan_check"))

    def test_capability_matrix_exposes_only_refresh_as_v1_and_v2_for_now(self):
        dual_version_steps = {
            step for step, versions in PROTOCOL_STEP_CAPABILITIES.items()
            if versions == frozenset({"v1", "v2"})
        }
        self.assertEqual({"refresh_at"}, dual_version_steps)

    def test_new_environment_setting_takes_precedence_over_legacy_refresh_setting(self):
        from core.protocol_version import configured_protocol_version

        with patch.dict(
            os.environ,
            {"OPENAI_PROTOCOL_VERSION": "v1", "ACCOUNT_TOKEN_REFRESH_DRIVER": "protocol_v2"},
            clear=True,
        ):
            self.assertEqual("v1", configured_protocol_version())

    def test_legacy_refresh_setting_is_migrated_when_new_setting_is_absent(self):
        from core.protocol_version import configured_protocol_version

        with patch.dict(os.environ, {"ACCOUNT_TOKEN_REFRESH_DRIVER": "protocol_v2"}, clear=True):
            self.assertEqual("v2", configured_protocol_version())
        with patch.dict(os.environ, {"ACCOUNT_TOKEN_REFRESH_DRIVER": "legacy"}, clear=True):
            self.assertEqual("v1", configured_protocol_version())


if __name__ == "__main__":
    unittest.main()
