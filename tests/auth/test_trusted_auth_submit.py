"""认证提交使用真实鼠标事件，派发不明时不追加另一种点击。"""
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from core.registration import roxy


class TrustedAuthSubmitTests(unittest.TestCase):
    def driver(self, point=None):
        return SimpleNamespace(
            execute_script=Mock(return_value={
                "clicked": True, "reason": "otp_form_submitted",
                "trusted_click": point or {"x": 100, "y": 80},
            }),
            execute_cdp_cmd=Mock(return_value={}),
        )

    def test_otp_dispatches_one_trusted_mouse_click(self):
        driver = self.driver()
        result = roxy._submit_email_otp_current_form(driver)
        self.assertTrue(result["clicked"])
        self.assertEqual([call.args for call in driver.execute_cdp_cmd.call_args_list], [
            ("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": 100.0, "y": 80.0}),
            ("Input.dispatchMouseEvent", {"type": "mousePressed", "x": 100.0, "y": 80.0,
                                         "button": "left", "clickCount": 1}),
            ("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": 100.0, "y": 80.0,
                                         "button": "left", "clickCount": 1}),
        ])
        self.assertNotIn("trusted_click", result)

    def test_otp_partial_dispatch_failure_does_not_fall_back_or_repeat(self):
        driver = self.driver()
        driver.execute_cdp_cmd.side_effect = [{}, {}, RuntimeError("连接中断")]
        with self.assertRaises(RuntimeError):
            roxy._submit_email_otp_current_form(driver)
        self.assertEqual(driver.execute_cdp_cmd.call_count, 3)
        self.assertEqual(driver.execute_script.call_count, 1)

    def test_otp_invalid_point_is_rejected_before_mouse_dispatch(self):
        driver = self.driver({"x": float("nan"), "y": 80})
        with self.assertRaises(ValueError):
            roxy._submit_email_otp_current_form(driver)
        driver.execute_cdp_cmd.assert_not_called()

    def test_otp_missing_cdp_ack_does_not_issue_more_mouse_events(self):
        driver = self.driver()
        driver.execute_cdp_cmd.return_value = None
        with self.assertRaises(RuntimeError):
            roxy._submit_email_otp_current_form(driver)
        self.assertEqual(driver.execute_cdp_cmd.call_count, 1)
