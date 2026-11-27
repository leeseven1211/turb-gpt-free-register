import io
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError


from core.sales.adapters import LiandongAdapter
from core.sales.errors import SalesError
from core.sales.sources import AccountSource


class FixtureTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, path, body, **kwargs):
        self.calls.append((path, body, kwargs))
        if not self.responses:
            raise AssertionError(f"没有为 {path} 准备响应")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


class SalesAdaptersTest(unittest.TestCase):
    def setUp(self):
        self.shop = {
            "name": "测试链动",
            "base_url": "https://wzyp.cn/",
            "token_env": "TEST_LIANDONG_TOKEN",
        }

    def test_business_unauthorized_is_not_success(self):
        transport = FixtureTransport([{"code": 401, "msg": "请先登录！"}])
        with patch.dict(os.environ, {"TEST_LIANDONG_TOKEN": "fixture-token"}):
            with self.assertRaises(SalesError) as raised:
                LiandongAdapter(self.shop, transport=transport).check()
        self.assertEqual("shop_auth_invalid", raised.exception.code)
        self.assertEqual(401, raised.exception.status)
        self.assertNotIn("请先登录", str(raised.exception))

    def test_default_liandong_transport_classifies_failures(self):
        cases = [
            (TimeoutError(), "shop_timeout"),
            (URLError(TimeoutError()), "shop_timeout"),
            (io.BytesIO(b"not-json"), "shop_response_invalid"),
            (io.BytesIO(b"\xff"), "shop_response_invalid"),
            (
                HTTPError(
                    "https://wzyp.cn/merchantApi/user/userinfo",
                    401,
                    "Unauthorized",
                    {},
                    None,
                ),
                "shop_auth_invalid",
            ),
        ]
        with patch.dict(os.environ, {"TEST_LIANDONG_TOKEN": "fixture-token"}):
            for failure, code in cases:
                with self.subTest(code=code):
                    opener = (
                        patch("core.sales.adapters.urlopen", side_effect=failure)
                        if isinstance(failure, BaseException)
                        else patch("core.sales.adapters.urlopen", return_value=failure)
                    )
                    with opener:
                        with self.assertRaises(SalesError) as raised:
                            LiandongAdapter(self.shop).check()
                    self.assertEqual(code, raised.exception.code)

    def test_env_credentials_support_custom_names_and_respect_dotenv_disabled(self):
        with patch.dict(os.environ, {
            "TEST_LIANDONG_TOKEN": "",
            "PYTHON_DOTENV_DISABLED": "0",
        }), \
                patch("config.env_loader.read_env_file", return_value={
                    "TEST_LIANDONG_TOKEN": "token-from-file",
                    "TEST_SOURCE_AUTH": "auth-from-file",
                }) as read_env:
            adapter = LiandongAdapter(self.shop, transport=FixtureTransport([]))
            self.assertEqual(
                {"Merchant-Token": "token-from-file"},
                adapter._transport_headers,
            )
            source = AccountSource({
                "id": "oracle",
                "kind": "remote",
                "base_url": "https://oracle.example.test",
                "auth_env": "TEST_SOURCE_AUTH",
            }, transport=FixtureTransport([]))
            self.assertEqual(
                {"X-Auth-Code": "auth-from-file"},
                source._transport_headers,
            )
            self.assertEqual(2, read_env.call_count)

        with patch.dict(os.environ, {
            "TEST_LIANDONG_TOKEN": "",
            "PYTHON_DOTENV_DISABLED": "1",
        }), patch("config.env_loader.read_env_file") as read_env:
            with self.assertRaises(SalesError) as raised:
                LiandongAdapter(self.shop, transport=FixtureTransport([]))
        self.assertEqual("shop_auth_missing", raised.exception.code)
        read_env.assert_not_called()

    def test_remote_default_transport_classifies_failures(self):
        source_config = {
            "id": "oracle",
            "kind": "remote",
            "base_url": "https://oracle.example.test",
            "auth_env": "TEST_SOURCE_AUTH",
        }
        cases = [
            (TimeoutError(), "source_timeout"),
            (URLError(TimeoutError()), "source_timeout"),
            (io.BytesIO(b"not-json"), "source_response_invalid"),
            (io.BytesIO(b"\xff"), "source_response_invalid"),
            (
                HTTPError(
                    "https://oracle.example.test/api/accounts",
                    401,
                    "Unauthorized",
                    {},
                    None,
                ),
                "source_auth_invalid",
            ),
        ]
        with patch.dict(os.environ, {"TEST_SOURCE_AUTH": "auth-code"}):
            for failure, code in cases:
                with self.subTest(code=code):
                    opener = (
                        patch("core.sales.sources.urlopen", side_effect=failure)
                        if isinstance(failure, BaseException)
                        else patch("core.sales.sources.urlopen", return_value=failure)
                    )
                    with opener:
                        with self.assertRaises(SalesError) as raised:
                            AccountSource(source_config).accounts([31])
                    self.assertEqual(code, raised.exception.code)

    def test_products_and_inventory_read_all_pages_and_normalize(self):
        transport = FixtureTransport([
            {"code": 1, "data": {"list": [
                {"id": 11, "goods_key": "g-11", "name": "商品 11", "status": 1, "price": 20}
            ], "total": 2}},
            {"code": 1, "data": {"list": [
                {"id": 12, "goods_key": "g-12", "name": "商品 12", "status": 0, "price": 30}
            ], "total": 2}},
            {"code": 1, "data": {"list": [
                {"id": 501, "secret": "a----b----c", "status": 0, "create_time": 1700000000}
            ], "total": 2}},
            {"code": 1, "data": {"list": [
                {"id": 502, "secret": "d----e----f", "status": 1, "create_time": 1700000001000}
            ], "total": 2}},
        ])
        with patch.dict(os.environ, {"TEST_LIANDONG_TOKEN": "fixture-token"}):
            adapter = LiandongAdapter(self.shop, transport=transport)
            self.assertEqual(
                [
                    {"external_product_id": "11", "goods_key": "g-11", "name": "商品 11", "status": "active", "price": 20},
                    {"external_product_id": "12", "goods_key": "g-12", "name": "商品 12", "status": "inactive", "price": 30},
                ],
                adapter.products(),
            )
            self.assertEqual(
                [
                    {
                        "external_inventory_id": "501",
                        "content": "a----b----c",
                        "status": "available",
                        "created_at": "2023-11-14T22:13:20+00:00",
                    },
                    {
                        "external_inventory_id": "502",
                        "content": "d----e----f",
                        "status": "sold",
                        "created_at": "2023-11-14T22:13:21+00:00",
                    },
                ],
                adapter.inventory("11"),
            )
        self.assertEqual(4, len(transport.calls))
        self.assertEqual(1, transport.calls[0][1]["current"])
        self.assertEqual(2, transport.calls[1][1]["current"])

    def test_duplicate_only_import_is_tolerated(self):
        transport = FixtureTransport([{"code": 0, "msg": "重复卡密"}])
        with patch.dict(os.environ, {"TEST_LIANDONG_TOKEN": "fixture-token"}):
            result = LiandongAdapter(self.shop, transport=transport).import_inventory(
                "11", ["a----b----c"]
            )
        self.assertEqual({"duplicate_only": True}, result)
        self.assertEqual(
            {
                "goods_id": 11,
                "content": "a----b----c",
                "first": 0,
                "remove_repeat": 1,
            },
            transport.calls[0][1],
        )

    def test_orders_read_details_and_convert_status_and_timestamp(self):
        transport = FixtureTransport([
            {"code": 1, "data": {"list": [
                {
                    "trade_no": "T-1",
                    "quantity": 1,
                    "sendout": 1,
                    "status": 1,
                    "total_amount": 20,
                    "fee": 1,
                    "fee_payer": 0,
                    "success_time": 1700000000,
                    "goods": {"goods_key": "g-11"},
                }
            ], "total": 1}},
            {"code": 1, "data": {
                "trade_no": "T-1",
                "quantity": 1,
                "sendout": 1,
                "status": 1,
                "total_amount": 20,
                "fee": 1,
                "fee_payer": 0,
                "success_time": 1700000000,
                "goods": {"goods_key": "g-11"},
                "response": {"cards": ["a----b----c"]},
            }},
        ])
        with patch.dict(os.environ, {"TEST_LIANDONG_TOKEN": "fixture-token"}):
            result = LiandongAdapter(self.shop, transport=transport).orders()
        self.assertEqual(
            [{
                "order_ref": "T-1",
                "goods_key": "g-11",
                "status": "paid",
                "quantity": 1,
                "sendout": 1,
                "cards": ["a----b----c"],
                "amount": 20,
                "fee": 1,
                "fee_payer": 0,
                "paid_at": "2023-11-14T22:13:20+00:00",
            }],
            result,
        )

    def test_order_invalid_counts_are_classified(self):
        for field in ("quantity", "sendout"):
            with self.subTest(field=field):
                summary = {
                    "trade_no": "T-1",
                    "quantity": 1,
                    "sendout": 1,
                    "status": 1,
                    "goods": {"goods_key": "g-11"},
                }
                detail = {
                    **summary,
                    field: "invalid",
                    "response": {"cards": []},
                }
                transport = FixtureTransport([
                    {"code": 1, "data": {"list": [summary], "total": 1}},
                    {"code": 1, "data": detail},
                ])
                with patch.dict(os.environ, {"TEST_LIANDONG_TOKEN": "fixture-token"}):
                    with self.assertRaises(SalesError) as raised:
                        LiandongAdapter(self.shop, transport=transport).orders()
                self.assertEqual("shop_response_invalid", raised.exception.code)

    def test_delivery_line_preserves_password_and_totp_whitespace(self):
        account = {
            "id": 9,
            "email": "space@example.test",
            "archived": False,
            "account_password": "  password  ",
            "totp_secret": "  totp  ",
        }
        with patch("core.db.get_account", return_value=account):
            result = AccountSource({"id": "local", "kind": "local"}).accounts([9])
        self.assertEqual(
            "space@example.test----  password  ----  totp  ",
            result[0]["delivery_line"],
        )

    def test_local_source_keeps_exact_normalized_email_matches_and_builds_delivery_line(self):
        accounts = [
            {
                "id": 7,
                "email": "User@Example.test",
                "current_plan_type": "plus",
                "archived": False,
                "extra_json": {"account_password": "pw-7"},
                "totp_secret": "totp-7",
            },
            {
                "id": 8,
                "email": " user@example.test ",
                "plan_type": "team",
                "archived": True,
                "extra_json": {"registration_password": "pw-8"},
                "totp_secret": "",
            },
        ]
        with patch("core.db.get_account", side_effect=lambda account_id: next(
            (row for row in accounts if row["id"] == account_id), None
        )), patch("core.storage.db_legacy._load_accounts", return_value=accounts), \
                patch(
                    "core.storage.db_legacy._decorate_account",
                    side_effect=lambda row: dict(row),
                ):
            source = AccountSource({"id": "local", "kind": "local"})
            self.assertEqual(
                [{
                    "id": 7,
                    "email": "User@Example.test",
                    "plan": "plus",
                    "archived": False,
                    "delivery_line": "User@Example.test----pw-7----totp-7",
                }],
                source.accounts([7]),
            )
            matches = source.find_accounts([" USER@example.TEST "])
        self.assertEqual([8, 7], [row["id"] for row in matches])
        self.assertEqual("user@example.test", matches[0]["email"].strip().lower())
        self.assertEqual(" user@example.test ----pw-8----", matches[0]["delivery_line"])

    def test_local_source_paginates_past_5000_and_keeps_duplicate_candidates(self):
        target = "target@example.test"
        rows = [
            {
                "id": index,
                "email": f"other-{index}@example.test",
                "note": target,
                "archived": False,
                "extra_json": {"account_password": f"pw-{index}"},
                "totp_secret": "",
            }
            for index in range(1, 5001)
        ]
        rows.extend([
            {
                "id": 5001,
                "email": target,
                "note": target,
                "archived": True,
                "extra_json": {"account_password": "pw-5001"},
                "totp_secret": "",
            },
            {
                "id": 5002,
                "email": f" {target} ",
                "note": target,
                "archived": False,
                "extra_json": {"account_password": "pw-5002"},
                "totp_secret": "",
            },
        ])

        with patch("core.storage.db_legacy._load_accounts", return_value=rows), \
                patch(
                    "core.storage.db_legacy._decorate_account",
                    side_effect=lambda row: dict(row),
                ):
            result = AccountSource({"id": "local", "kind": "local"}).find_accounts([target])
        self.assertEqual([5002, 5001], [row["id"] for row in result])
        self.assertEqual([False, True], [row["archived"] for row in result])

    def test_remote_source_uses_get_q_bulk_material_and_archive_readback(self):
        transport = FixtureTransport([
            {"ok": True, "items": [
                {"id": 31, "email": "User@Example.test", "plan": "plus", "archived": False}
            ], "total": 1},
            {"ok": True, "values": [
                {"id": 31, "email": "User@Example.test", "value": "User@Example.test----pw----totp"}
            ]},
            {"ok": True, "items": [
                {"id": 31, "email": "User@Example.test", "plan": "plus", "archived": False}
            ], "total": 1},
            {"ok": True, "updated": True, "archived": True},
            {"ok": True, "items": [
                {"id": 31, "email": "User@Example.test", "plan": "plus", "archived": True}
            ], "total": 1},
        ])
        with patch.dict(os.environ, {"TEST_SOURCE_AUTH": "auth-code"}):
            source = AccountSource({
                "id": "oracle",
                "kind": "remote",
                "base_url": "https://oracle.example.test/api",
                "auth_env": "TEST_SOURCE_AUTH",
            }, transport=transport)
            self.assertEqual(
                [{
                    "id": 31,
                    "email": "User@Example.test",
                    "plan": "plus",
                    "archived": False,
                    "delivery_line": "User@Example.test----pw----totp",
                }],
                source.find_accounts([" user@example.test "]),
            )
            self.assertTrue(source.archive(31))
        self.assertEqual("/api/accounts", transport.calls[0][0])
        self.assertEqual("GET", transport.calls[0][2]["method"])
        self.assertEqual("邮箱:user@example.test", transport.calls[0][1]["q"])
        self.assertEqual("/api/accounts/31/archive", transport.calls[3][0])
        self.assertEqual("GET", transport.calls[4][2]["method"])

    def test_remote_source_rejects_partial_secret_material(self):
        transport = FixtureTransport([
            {"ok": True, "items": [
                {"id": 31, "email": "User@Example.test", "plan": "plus", "archived": False}
            ], "total": 1},
            {"ok": True, "values": [], "skipped": [
                {"id": 31, "reason": "账号资料读取失败"},
            ]},
        ])
        with patch.dict(os.environ, {"TEST_SOURCE_AUTH": "auth-code"}):
            source = AccountSource({
                "id": "oracle",
                "kind": "remote",
                "base_url": "https://oracle.example.test",
                "auth_env": "TEST_SOURCE_AUTH",
            }, transport=transport)
            with self.assertRaises(SalesError) as raised:
                source.find_accounts(["user@example.test"])
        self.assertEqual("source_response_incomplete", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
