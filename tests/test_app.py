from __future__ import annotations

import base64
import json
import threading
import time
import unittest
from http import HTTPStatus
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from server import create_server
from studhelp.config import Settings


class AppServerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        root_dir = Path(__file__).resolve().parents[1]
        self.database_path = root_dir / "data" / f"test-{time.time_ns()}.sqlite3"
        self.sent_codes: list[tuple[str, str]] = []
        settings = Settings(
            root_dir=root_dir,
            static_dir=root_dir / "static",
            data_dir=root_dir / "data",
            uploads_dir=root_dir / "uploads",
            database_path=self.database_path,
            email_sender=lambda email, code: self.sent_codes.append((email, code)),
            login_rate_limit_count=2,
            login_rate_limit_window_seconds=60,
            reset_request_rate_limit_count=3,
            reset_request_rate_limit_window_seconds=60,
            reset_confirm_rate_limit_count=3,
            reset_confirm_rate_limit_window_seconds=60,
        )
        self.server = create_server(settings=settings, host="127.0.0.1", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"
        self.user_opener = build_opener(HTTPCookieProcessor())
        self.admin_basic = base64.b64encode(b"admin:change-me-please").decode("ascii")
        time.sleep(0.1)

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        if self.database_path.exists():
            self.database_path.unlink()

    def request_json(self, path: str, *, method: str = "GET", payload: dict | None = None, opener=None, headers: dict[str, str] | None = None):
        body = None
        request_headers = dict(headers or {})
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(f"{self.base_url}{path}", data=body, headers=request_headers, method=method)
        active_opener = opener or self.user_opener
        try:
            with active_opener.open(request, timeout=5) as response:
                raw = response.read().decode("utf-8")
                return response.status, json.loads(raw) if raw else {}
        except HTTPError as error:
            raw = error.read().decode("utf-8")
            return error.code, json.loads(raw) if raw else {}

    def register_user(self, email: str = "user@example.com", password: str = "secret123") -> dict:
        status, result = self.request_json(
            "/api/auth/register",
            method="POST",
            payload={"name": "User", "email": email, "password": password},
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        return result

    def test_auth_cookie_session_flow(self) -> None:
        self.register_user()
        status, result = self.request_json("/api/auth/me")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(result["user"]["email"], "user@example.com")

        status, _ = self.request_json("/api/auth/logout", method="POST")
        self.assertEqual(status, HTTPStatus.OK)

        status, result = self.request_json("/api/auth/me")
        self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
        self.assertFalse(result["ok"])

    def test_password_reset_flow(self) -> None:
        self.register_user(email="reset@example.com", password="oldpass1")
        status, result = self.request_json(
            "/api/auth/password-reset/request",
            method="POST",
            payload={"email": "reset@example.com"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(self.sent_codes)
        _, code = self.sent_codes[-1]

        status, result = self.request_json(
            "/api/auth/password-reset/confirm",
            method="POST",
            payload={"email": "reset@example.com", "code": code, "password": "newpass1"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertTrue(result["ok"])

        self.request_json("/api/auth/logout", method="POST")
        status, result = self.request_json(
            "/api/auth/login",
            method="POST",
            payload={"email": "reset@example.com", "password": "newpass1"},
        )
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(result["user"]["email"], "reset@example.com")

    def test_attachment_flow(self) -> None:
        self.register_user(email="files@example.com")
        attachment = {
            "name": "note.txt",
            "contentType": "text/plain",
            "contentBase64": base64.b64encode(b"hello attachment").decode("ascii"),
        }
        status, result = self.request_json(
            "/api/chat/messages",
            method="POST",
            payload={"text": "message with file", "attachment": attachment},
        )
        self.assertEqual(status, HTTPStatus.CREATED)
        self.assertIn("attachment", result["item"])
        saved_path = Path(__file__).resolve().parents[1] / result["item"]["attachment"]["path"].lstrip("/")
        self.assertTrue(saved_path.exists())

        status, result = self.request_json("/api/chat/messages")
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(result["items"][0]["attachment"]["name"], "note.txt")

    def test_unread_logic_for_admin_chat(self) -> None:
        self.register_user(email="chat@example.com")
        status, _ = self.request_json(
            "/api/chat/messages",
            method="POST",
            payload={"text": "new unread message"},
        )
        self.assertEqual(status, HTTPStatus.CREATED)

        admin_headers = {"Authorization": f"Basic {self.admin_basic}"}
        status, result = self.request_json("/api/admin/chats", opener=self.user_opener, headers=admin_headers)
        self.assertEqual(status, HTTPStatus.OK)
        target_chat = next(item for item in result["items"] if item["user"]["email"] == "chat@example.com")
        self.assertEqual(target_chat["unreadCount"], 1)

        status, _ = self.request_json(
            f"/api/admin/chats/{target_chat['user']['id']}/messages",
            opener=self.user_opener,
            headers=admin_headers,
        )
        self.assertEqual(status, HTTPStatus.OK)

        status, result = self.request_json("/api/admin/chats", opener=self.user_opener, headers=admin_headers)
        self.assertEqual(status, HTTPStatus.OK)
        target_chat = next(item for item in result["items"] if item["user"]["email"] == "chat@example.com")
        self.assertEqual(target_chat["unreadCount"], 0)

    def test_login_rate_limit(self) -> None:
        self.register_user(email="limit@example.com", password="secret123")
        for _ in range(2):
            status, _ = self.request_json(
                "/api/auth/login",
                method="POST",
                payload={"email": "limit@example.com", "password": "wrongpass"},
                opener=build_opener(HTTPCookieProcessor()),
            )
            self.assertEqual(status, HTTPStatus.UNAUTHORIZED)
        status, result = self.request_json(
            "/api/auth/login",
            method="POST",
            payload={"email": "limit@example.com", "password": "wrongpass"},
            opener=build_opener(HTTPCookieProcessor()),
        )
        self.assertEqual(status, HTTPStatus.TOO_MANY_REQUESTS)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
