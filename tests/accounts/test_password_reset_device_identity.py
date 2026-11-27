"""协议改密优先复用完整同源设备，历史画像缺失时仍可普通认证。"""
from copy import deepcopy
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from core.accounts.password_setup import reset
from core.auth.protocol.session import BrowserSession
from tests.accounts.test_password_reset_protocol import _ResetSession


class PasswordResetDeviceIdentityTests(TestCase):
    email = "password-reset-device@example.test"
    profile = {
        "screen_width": 1920,
        "screen_height": 1080,
        "device_pixel_ratio": 2,
        "hardware_concurrency": 8,
        "device_memory": 8,
        "js_heap_size_limit": 4294705152,
    }

    def _device(self, device_id, *, impersonate=None):
        profile = dict(self.profile)
        if impersonate:
            profile["impersonate"] = impersonate
        return {"device_id": device_id, "browser_profile": profile}

    def _run_reset(
        self, *, remembered, cached, refreshed_remembered=None,
        refreshed_context=None, preflight_error=None,
    ):
        recovery = Mock()
        recovery.checkpoint = SimpleNamespace(state="prepared", password="Candidate-password-42")
        session = _ResetSession([])
        responses = (session, "https://auth.openai.com/authorize")
        preflight = Mock(return_value=responses)
        if preflight_error is not None:
            preflight.side_effect = [preflight_error, responses]
        refresh_enabled = refreshed_context is not None
        remembered_values = [remembered]
        if refresh_enabled:
            remembered_values.append(refreshed_remembered or {})

        def refresh(_email, *, authenticated_context, **_kwargs):
            authenticated_context.update(refreshed_context)

        with (
            patch("core.db.get_account_by_email", return_value={"id": 42, "email": self.email}),
            patch("core.auth.browser.password_recovery.PasswordRecoverySession", return_value=recovery),
            patch("core.storage.accounts.protocol_sessions.load_session", return_value=cached),
            patch("core.storage.accounts.device_profiles.load_profile", side_effect=remembered_values),
            patch.object(reset, "_check_reset_mailbox"),
            patch.object(reset, "_session_stale", return_value=True),
            patch.object(reset, "_refresh_before_reset", side_effect=refresh) as refresh_call,
            patch.object(reset, "_network_preflight_with_retry", preflight),
            patch("config.email.OTP_RESEND_COUNT", 0),
            patch.object(reset, "_send_reset_otp") as send,
            patch.object(reset, "_wait_reset_otp", side_effect=reset.ProtocolPasswordResetError(
                "password_reset_otp_timeout", "测试在发码后停止", stage="wait_otp",
            )),
        ):
            result = reset.run_protocol_password_reset(
                self.email,
                execution_fence={"run_id": 7, "execution_id": "worker", "lease_token": "lease"},
                refresh_before_reset=refresh_enabled,
            )
        self.assertEqual("password_reset_otp_timeout", result["error"])
        send.assert_called_once()
        self.assertEqual(int(refresh_enabled), refresh_call.call_count)
        return preflight

    def test_partial_device_falls_back_to_complete_cached_identity(self):
        cached = self._device("cached-device", impersonate="chrome146")
        partials = [
            {"device_id": "remembered-device"},
            {"device_id": "remembered-device", "browser_profile": {}},
            {"device_id": "remembered-device", "browser_profile": {"user_agent": "旧画像"}},
        ]
        for field in self.profile:
            partial = self._device("remembered-device")
            del partial["browser_profile"][field]
            partials.append(partial)
        for remembered in partials:
            with self.subTest(remembered=remembered):
                preflight = self._run_reset(remembered=remembered, cached=cached)
                identity = preflight.call_args.kwargs["identity"]
                self.assertIsInstance(identity, dict)
                self.assertEqual("cached-device", identity["device_id"])
                self.assertEqual(cached["browser_profile"], identity["browser_profile"])
                self.assertEqual({"impersonate": "chrome146"}, identity["chrome_identity"])

    def test_complete_device_wins_without_mutating_either_source(self):
        remembered = self._device("remembered-device", impersonate="chrome146")
        cached = self._device("cached-device", impersonate="chrome149")
        before = deepcopy((remembered, cached))
        preflight = self._run_reset(remembered=remembered, cached=cached)
        identity = preflight.call_args.kwargs["identity"]
        self.assertEqual("remembered-device", identity["device_id"])
        self.assertEqual(remembered["browser_profile"], identity["browser_profile"])
        self.assertEqual({"impersonate": "chrome146"}, identity["chrome_identity"])
        self.assertEqual(before, (remembered, cached))

    def test_invalid_device_id_falls_back_to_complete_cache(self):
        for device_id in (None, "", "  ", 42):
            with self.subTest(device_id=device_id):
                preflight = self._run_reset(
                    remembered=self._device(device_id), cached=self._device("cached-device"),
                )
                self.assertEqual("cached-device", (preflight.call_args.kwargs["identity"] or {}).get("device_id"))

    def test_unusable_required_values_fall_back_to_complete_cache(self):
        for field in self.profile:
            for invalid in (None, True, False, 0, -1, "错误值", float("nan"), float("inf")):
                with self.subTest(field=field, invalid=invalid):
                    remembered = self._device("remembered-device")
                    remembered["browser_profile"][field] = invalid
                    preflight = self._run_reset(remembered=remembered, cached=self._device("cached-device"))
                    self.assertEqual("cached-device", preflight.call_args.kwargs["identity"]["device_id"])

    def test_consumable_numeric_strings_keep_the_original_profile(self):
        remembered = self._device("remembered-device")
        remembered["browser_profile"] = {field: str(value) for field, value in self.profile.items()}
        preflight = self._run_reset(remembered=remembered, cached=self._device("cached-device"))
        self.assertEqual(remembered, preflight.call_args.kwargs["identity"])

    def test_non_consumable_integer_fields_fall_back_to_complete_cache(self):
        for field in (
            "screen_width", "screen_height", "hardware_concurrency", "device_memory", "js_heap_size_limit",
        ):
            for invalid in ("1.5", "1e3", 0.5):
                with self.subTest(field=field, invalid=invalid):
                    remembered = self._device("remembered-device")
                    remembered["browser_profile"][field] = invalid
                    preflight = self._run_reset(remembered=remembered, cached=self._device("cached-device"))
                    self.assertEqual("cached-device", preflight.call_args.kwargs["identity"]["device_id"])

    def test_optional_null_is_skipped_before_real_browser_session_construction(self):
        for field in ("screen_avail_width", "outer_width", "timezone_offset_minutes"):
            with self.subTest(field=field):
                remembered = self._device("remembered-device")
                remembered["browser_profile"][field] = None
                cached = self._device("cached-device")
                with (
                    patch("curl_cffi.requests.Session.request", side_effect=AssertionError("测试禁止网络")) as network,
                    patch("core.network.protocol_traffic.ProtocolTrafficCapture.for_current_context", return_value=None),
                ):
                    session = BrowserSession(
                        proxy="", detect_exit_geo=False,
                        identity=reset._select_reset_identity(remembered, cached),
                    )
                    try:
                        self.assertEqual("cached-device", session.device_id)
                    finally:
                        session.session.close()
                network.assert_not_called()
                self.assertIsNone(remembered["browser_profile"][field])

    def test_incompatible_optional_integer_fields_fall_back_to_cache_or_plain_authentication(self):
        for field in (
            "screen_avail_width", "screen_avail_height", "outer_width", "outer_height",
            "inner_width", "inner_height", "viewport_width", "viewport_height",
            "color_depth", "timezone_offset_minutes",
        ):
            for invalid in (None, "", "错误值", "1.5", "1e3", float("nan"), float("inf")):
                for cache_available in (False, True):
                    with self.subTest(field=field, invalid=invalid, cache_available=cache_available):
                        remembered = self._device("remembered-device")
                        remembered["browser_profile"][field] = invalid
                        cached = self._device("cached-device") if cache_available else {}
                        preflight = self._run_reset(remembered=remembered, cached=cached)
                        identity = preflight.call_args.kwargs["identity"]
                        if cache_available:
                            self.assertEqual("cached-device", identity["device_id"])
                        else:
                            self.assertIsNone(identity)

    def test_optional_zero_sizes_and_signed_timezone_remain_usable_without_mutation(self):
        for offset in (-480, 0, "480"):
            with self.subTest(offset=offset):
                remembered = self._device("remembered-device")
                remembered["browser_profile"].update({
                    "screen_avail_width": 0, "screen_avail_height": "0",
                    "outer_width": 0, "outer_height": "0", "inner_width": 0, "inner_height": "0",
                    "viewport_width": 0, "viewport_height": "0", "color_depth": "24",
                    "timezone_offset_minutes": offset, "max_touch_points": 0,
                })
                before = deepcopy(remembered)
                preflight = self._run_reset(remembered=remembered, cached=self._device("cached-device"))
                self.assertEqual(remembered, preflight.call_args.kwargs["identity"])
                self.assertEqual(before, remembered)

    def test_unused_viewport_and_touch_values_do_not_block_usable_inner_dimensions(self):
        remembered = self._device("remembered-device")
        remembered["browser_profile"].update({
            "inner_width": 1400, "inner_height": 800,
            "viewport_width": None, "viewport_height": None, "max_touch_points": None,
        })
        preflight = self._run_reset(remembered=remembered, cached=self._device("cached-device"))
        self.assertEqual(remembered, preflight.call_args.kwargs["identity"])

    def test_timezone_outside_datetime_range_falls_back_to_cache(self):
        for invalid in (-1440, 1440, "1000000"):
            with self.subTest(invalid=invalid):
                remembered = self._device("remembered-device")
                remembered["browser_profile"]["timezone_offset_minutes"] = invalid
                preflight = self._run_reset(remembered=remembered, cached=self._device("cached-device"))
                self.assertEqual("cached-device", preflight.call_args.kwargs["identity"]["device_id"])

    def test_incomplete_sources_do_not_mix_and_allow_plain_authentication(self):
        preflight = self._run_reset(
            remembered={"device_id": "remembered-device"},
            cached={"browser_profile": self.profile},
        )
        self.assertIsNone(preflight.call_args.kwargs["identity"])

    def test_refresh_reselects_complete_cached_identity_with_its_tls(self):
        refreshed = self._device("refreshed-device", impersonate="chrome149")
        preflight = self._run_reset(
            remembered=self._device("old-device", impersonate="chrome146"), cached={},
            refreshed_remembered={"device_id": "partial-device"}, refreshed_context=refreshed,
        )
        identity = preflight.call_args.kwargs["identity"]
        self.assertEqual("refreshed-device", identity["device_id"])
        self.assertEqual(refreshed["browser_profile"], identity["browser_profile"])
        self.assertEqual({"impersonate": "chrome149"}, identity["chrome_identity"])

    def test_refresh_keeps_complete_device_priority_and_profile_tls_priority(self):
        remembered = self._device("remembered-device", impersonate="chrome146")
        remembered["impersonate"] = "chrome149"
        preflight = self._run_reset(
            remembered={}, cached={}, refreshed_remembered=remembered,
            refreshed_context=self._device("refreshed-device", impersonate="chrome149"),
        )
        identity = preflight.call_args.kwargs["identity"]
        self.assertEqual("remembered-device", identity["device_id"])
        self.assertEqual({"impersonate": "chrome146"}, identity.get("chrome_identity"))

    def test_top_level_tls_is_preserved_before_and_after_refresh(self):
        remembered = {**self._device("remembered-device"), "impersonate": "chrome146"}
        for refresh_enabled in (False, True):
            with self.subTest(refresh_enabled=refresh_enabled):
                preflight = self._run_reset(
                    remembered=remembered, cached={},
                    refreshed_remembered=remembered,
                    refreshed_context={"device_id": "partial-device"} if refresh_enabled else None,
                )
                self.assertEqual(
                    {"impersonate": "chrome146"}, preflight.call_args.kwargs["identity"].get("chrome_identity"),
                )

    def test_refresh_without_complete_source_discards_previous_identity(self):
        preflight = self._run_reset(
            remembered=self._device("old-device", impersonate="chrome146"), cached={},
            refreshed_remembered={"device_id": "partial-device"},
            refreshed_context={"device_id": "refreshed-device", "browser_profile": {"user_agent": "旧画像"}},
        )
        self.assertIsNone(preflight.call_args.kwargs["identity"])

    def test_value_error_still_retries_plain_authentication(self):
        remembered = self._device("remembered-device", impersonate="chrome146")
        preflight = self._run_reset(
            remembered=remembered, cached={}, preflight_error=ValueError("测试模拟不兼容画像"),
        )
        self.assertEqual(2, preflight.call_count)
        self.assertEqual("remembered-device", preflight.call_args_list[0].kwargs["identity"]["device_id"])
        self.assertNotIn("identity", preflight.call_args_list[1].kwargs)

    def test_cancelled_preflight_is_not_retried_as_plain_authentication(self):
        with self.assertRaises(reset.OperationCancelled):
            self._run_reset(
                remembered=self._device("remembered-device"), cached={},
                preflight_error=reset.OperationCancelled("测试取消"),
            )
