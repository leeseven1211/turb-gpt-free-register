"""账号 Session 批量下载的接口与 ZIP 内容验收。"""

import io
import json
import zipfile
from unittest.mock import patch

from core.storage import records as record_store
from tests.support_pg import PostgresTestCase
from webui.app import create_app


class AccountSessionDownloadTests(PostgresTestCase):
    def setUp(self):
        self.app = create_app(auth_code="test-auth")
        self.client = self.app.test_client()
        self.headers = {"X-Auth-Code": "test-auth"}

    def _post(self, payload, *, authenticated=True):
        return self.client.post(
            "/api/accounts/download-session-bulk",
            json=payload,
            headers=self.headers if authenticated else {},
        )

    def test_zip_preserves_selected_sessions_and_classifies_skipped_accounts(self):
        first_session = {
            "accessToken": "stored-session-at",
            "user": {"id": "user-1", "name": "测试用户"},
            "account": {"id": "account-1", "planType": "free"},
            "expires": "2020-01-01T00:00:00Z",
            "additional": {"nested": [1, {"keep": True}]},
        }
        second_session = {"accessToken": "second-at", "user": {"id": "user-2"}}
        first, second, missing, invalid, unselected = self.seed(record_store.ACCOUNTS, [
            {"email": "first@example.test", "access_token": "newer-account-at",
             "chatgpt_session": json.dumps(first_session), "totp_secret": "private-totp",
             "extra_json": '{"account_password":"private-password"}'},
            {"email": "path/../unsafe\\name:@example.test", "chatgpt_session": json.dumps(second_session)},
            {"email": "missing@example.test", "access_token": "at-without-session"},
            {"email": "invalid@example.test", "chatgpt_session": '{"accessToken":" "}'},
            {"email": "unselected@example.test", "chatgpt_session": '{"accessToken":"unselected-at"}'},
        ])

        response = self._post({"account_ids": [second, first, second, missing, invalid, 999999]})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/zip")
        self.assertIn("attachment;", response.headers["Content-Disposition"])
        self.assertIn("no-store", response.headers["Cache-Control"])
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["count"], 2)
            self.assertEqual(manifest["skipped_count"], 3)
            self.assertEqual([item["id"] for item in manifest["files"]], [second, first])
            self.assertEqual(
                {item["id"]: item["error_code"] for item in manifest["skipped"]},
                {missing: "session_missing", invalid: "session_invalid", 999999: "account_not_found"},
            )
            self.assertTrue(all(item["reason"] for item in manifest["skipped"]))
            self.assertEqual(len(archive.namelist()), 3)
            by_id = {item["id"]: item["filename"] for item in manifest["files"]}
            self.assertEqual(json.loads(archive.read(by_id[first])), first_session)
            self.assertEqual(json.loads(archive.read(by_id[second])), second_session)
            for name in archive.namelist():
                self.assertNotIn("/", name)
                self.assertNotIn("\\", name)
                self.assertNotIn(":", name)
            contents = "\n".join(archive.read(name).decode() for name in archive.namelist())
            for private_value in ("private-password", "private-totp", "newer-account-at", "unselected-at"):
                self.assertNotIn(private_value, contents)
        self.assertNotIn(unselected, by_id)

    def test_prepare_uses_authenticated_one_time_download_without_session_in_metadata(self):
        account_id = self.seed(record_store.ACCOUNTS, [
            {"email": "prepared@example.test", "chatgpt_session": '{"accessToken":"prepared-session-at"}'},
        ])[0]

        response = self._post({"account_ids": [account_id], "prepare": True})

        self.assertEqual(response.status_code, 200)
        prepared = response.get_json()
        self.assertTrue(prepared["prepared"])
        self.assertEqual((prepared["added_count"], prepared["skipped_count"]), (1, 0))
        self.assertNotIn("prepared-session-at", response.get_data(as_text=True))
        self.assertIn("no-store", response.headers["Cache-Control"])
        download_url = prepared["download_url"]
        self.assertTrue(download_url.startswith("/api/downloads/"))
        self.assertEqual(self.client.get(download_url).status_code, 401)
        download = self.client.get(download_url, headers=self.headers)
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.mimetype, "application/zip")
        self.assertIn("no-store", download.headers["Cache-Control"])
        with zipfile.ZipFile(io.BytesIO(download.data)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["files"][0]["id"], account_id)
        self.assertEqual(self.client.get(download_url, headers=self.headers).status_code, 404)

    def test_missing_sessions_are_reported_without_constructing_json_from_at(self):
        account_id = self.seed(record_store.ACCOUNTS, [
            {"email": "legacy@example.test", "access_token": "legacy-account-at"},
        ])[0]

        response = self._post({"account_ids": [account_id, 999999], "prepare": True})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertTrue(result["ok"])
        self.assertEqual(result["added_count"], 0)
        self.assertEqual(result["skipped_count"], 2)
        self.assertNotIn("legacy-account-at", response.get_data(as_text=True))
        download = self.client.get(result["download_url"], headers=self.headers)
        with zipfile.ZipFile(io.BytesIO(download.data)) as archive:
            self.assertEqual(archive.namelist(), ["manifest.json"])
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["count"], 0)
            self.assertEqual(manifest["skipped_count"], 2)
            self.assertIn("刷新 AT", manifest["skipped"][0]["reason"])
            self.assertEqual(manifest["skipped"][1]["error_code"], "account_not_found")

    def test_saved_non_object_sessions_are_invalid_rather_than_missing(self):
        account_ids = self.seed(record_store.ACCOUNTS, [
            {"email": "array@example.test", "chatgpt_session": "[]"},
            {"email": "broken@example.test", "chatgpt_session": json.dumps("not-json")},
            {"email": "scalar@example.test", "chatgpt_session": "42"},
        ])

        response = self._post({"account_ids": account_ids, "prepare": True})

        result = response.get_json()
        self.assertEqual(
            [item["error_code"] for item in result["skipped"]],
            ["session_invalid", "session_invalid", "session_invalid"],
        )

    def test_one_read_failure_does_not_discard_other_exported_sessions(self):
        first, second = self.seed(record_store.ACCOUNTS, [
            {"email": "unreadable@example.test", "chatgpt_session": '{"accessToken":"first-at"}'},
            {"email": "readable@example.test", "chatgpt_session": '{"accessToken":"second-at"}'},
        ])
        original_get = record_store.get_row

        def read_account(spec, account_id):
            if account_id == first:
                raise RuntimeError("private-error-context")
            return original_get(spec, account_id)

        with patch("webui.routes.accounts.record_store.get_row", side_effect=read_account):
            response = self._post({"account_ids": [first, second], "prepare": True})

        self.assertEqual(response.status_code, 200)
        result = response.get_json()
        self.assertEqual((result["added_count"], result["skipped_count"]), (1, 1))
        self.assertEqual(result["skipped"][0]["error_code"], "session_read_failed")
        self.assertIn("RuntimeError", result["skipped"][0]["reason"])
        self.assertNotIn("private-error-context", response.get_data(as_text=True))

    def test_invalid_selections_return_clear_request_errors(self):
        for payload in (
            [], {}, {"account_ids": []}, {"account_ids": "1"},
            {"account_ids": [True]}, {"account_ids": [1.5]},
            {"account_ids": [0]}, {"account_ids": [-1]},
            {"account_ids": ["not-an-id"]}, {"account_ids": [1] * 5001},
        ):
            with self.subTest(payload_type=type(payload).__name__, payload_size=len(str(payload))):
                response = self._post(payload)
                self.assertEqual(response.status_code, 400)
                result = response.get_json()
                self.assertEqual(result["error_code"], "invalid_account_ids")
                self.assertTrue(result["error"])

    def test_export_requires_authentication(self):
        response = self._post({"account_ids": [1]}, authenticated=False)
        self.assertEqual(response.status_code, 401)
