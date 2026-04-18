from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import os
import secrets
import smtplib
from datetime import date, datetime, timezone
from email.message import EmailMessage
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT_DIR = Path(__file__).resolve().parent
STATIC_DIR = ROOT_DIR / "static"
DATA_DIR = ROOT_DIR / "data"
REQUESTS_FILE = DATA_DIR / "requests.json"
REVIEWS_FILE = DATA_DIR / "reviews.json"
USERS_FILE = DATA_DIR / "users.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"
MESSAGES_FILE = DATA_DIR / "messages.json"
PASSWORD_RESETS_FILE = DATA_DIR / "password_resets.json"
UPLOADS_DIR = ROOT_DIR / "uploads"
MAX_REQUEST_SIZE = 8 * 1024 * 1024
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "change-me-please")
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USERNAME)


def ensure_storage() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    for file_path, default in (
        (REQUESTS_FILE, "[]"),
        (REVIEWS_FILE, "[]"),
        (USERS_FILE, "[]"),
        (SESSIONS_FILE, "[]"),
        (MESSAGES_FILE, "[]"),
        (PASSWORD_RESETS_FILE, "[]"),
    ):
        if not file_path.exists():
            file_path.write_text(default, encoding="utf-8")
    UPLOADS_DIR.mkdir(exist_ok=True)


def load_json_list(file_path: Path) -> list[dict]:
    ensure_storage()
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        file_path.write_text("[]", encoding="utf-8")
        return []
    return data if isinstance(data, list) else []


def write_json_list(file_path: Path, entries: list[dict]) -> None:
    file_path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_requests() -> list[dict]:
    return load_json_list(REQUESTS_FILE)


def write_requests(entries: list[dict]) -> None:
    write_json_list(REQUESTS_FILE, entries)


def load_reviews() -> list[dict]:
    return load_json_list(REVIEWS_FILE)


def write_reviews(entries: list[dict]) -> None:
    write_json_list(REVIEWS_FILE, entries)


def load_users() -> list[dict]:
    return load_json_list(USERS_FILE)


def write_users(entries: list[dict]) -> None:
    write_json_list(USERS_FILE, entries)


def load_sessions() -> list[dict]:
    return load_json_list(SESSIONS_FILE)


def write_sessions(entries: list[dict]) -> None:
    write_json_list(SESSIONS_FILE, entries)


def load_messages() -> list[dict]:
    return load_json_list(MESSAGES_FILE)


def write_messages(entries: list[dict]) -> None:
    write_json_list(MESSAGES_FILE, entries)


def load_password_resets() -> list[dict]:
    return load_json_list(PASSWORD_RESETS_FILE)


def write_password_resets(entries: list[dict]) -> None:
    write_json_list(PASSWORD_RESETS_FILE, entries)


def next_id(entries: list[dict]) -> int:
    return max((int(item.get("id", 0)) for item in entries), default=0) + 1


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def sanitize_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "email": user["email"],
        "createdAt": user["createdAt"],
    }


def find_user_by_email(email: str) -> dict | None:
    for item in load_users():
        if str(item.get("email", "")).strip().lower() == email.strip().lower():
            return item
    return None


def find_user_by_id(user_id: int) -> dict | None:
    for item in load_users():
        if int(item.get("id", 0)) == user_id:
            return item
    return None


def create_user(payload: dict) -> dict:
    entries = load_users()
    user = {
        "id": next_id(entries),
        "name": payload["name"].strip(),
        "email": payload["email"].strip().lower(),
        "passwordHash": hash_password(payload["password"]),
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    entries.append(user)
    write_users(entries)
    return user


def create_session(user_id: int) -> dict:
    entries = load_sessions()
    token = secrets.token_hex(24)
    session = {
        "token": token,
        "userId": user_id,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    entries = [item for item in entries if int(item.get("userId", 0)) != user_id]
    entries.append(session)
    write_sessions(entries)
    return session


def find_session(token: str) -> dict | None:
    for item in load_sessions():
        if item.get("token") == token:
            return item
    return None


def delete_session(token: str) -> None:
    entries = [item for item in load_sessions() if item.get("token") != token]
    write_sessions(entries)


def store_attachment(payload: dict) -> dict:
    filename = str(payload.get("name", "file")).strip() or "file"
    content_type = str(payload.get("contentType", "application/octet-stream")).strip() or "application/octet-stream"
    content_base64 = str(payload.get("contentBase64", ""))
    raw_bytes = base64.b64decode(content_base64.encode("utf-8"), validate=True)
    if len(raw_bytes) > MAX_ATTACHMENT_SIZE:
        raise ValueError("Файл слишком большой.")
    suffix = Path(filename).suffix or ""
    stored_name = f"{secrets.token_hex(12)}{suffix}"
    stored_path = UPLOADS_DIR / stored_name
    stored_path.write_bytes(raw_bytes)
    return {
        "name": filename,
        "contentType": content_type,
        "path": f"/uploads/{stored_name}",
        "size": len(raw_bytes),
    }


def create_message(user_id: int, sender: str, text: str, attachment: dict | None = None) -> dict:
    entries = load_messages()
    message = {
        "id": next_id(entries),
        "userId": user_id,
        "sender": sender,
        "text": text.strip(),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "readByAdmin": sender == "admin",
        "readByUser": sender == "user",
    }
    if attachment:
        message["attachment"] = attachment
    entries.append(message)
    write_messages(entries)
    return message


def get_user_messages(user_id: int) -> list[dict]:
    return [
        item
        for item in load_messages()
        if int(item.get("userId", 0)) == user_id
    ]


def mark_messages_read(user_id: int, reader: str) -> None:
    entries = load_messages()
    changed = False
    for item in entries:
        if int(item.get("userId", 0)) != user_id:
            continue
        if reader == "admin" and item.get("sender") == "user" and not item.get("readByAdmin", False):
            item["readByAdmin"] = True
            changed = True
        if reader == "user" and item.get("sender") == "admin" and not item.get("readByUser", False):
            item["readByUser"] = True
            changed = True
    if changed:
        write_messages(entries)


def count_unread_for_admin(user_id: int) -> int:
    return sum(
        1
        for item in load_messages()
        if int(item.get("userId", 0)) == user_id
        and item.get("sender") == "user"
        and not item.get("readByAdmin", False)
    )


def get_admin_chats() -> list[dict]:
    users = {int(item["id"]): item for item in load_users()}
    chats: list[dict] = []
    for user_id, user in users.items():
        messages = get_user_messages(user_id)
        last_message = messages[-1] if messages else None
        chats.append(
            {
                "user": sanitize_user(user),
                "lastMessage": last_message,
                "messageCount": len(messages),
                "unreadCount": count_unread_for_admin(user_id),
            }
        )
    chats.sort(
        key=lambda item: item["lastMessage"]["createdAt"] if item["lastMessage"] else item["user"]["createdAt"],
        reverse=True,
    )
    return chats


def create_reset_code(email: str) -> str:
    code = f"{secrets.randbelow(1_000_000):06d}"
    entries = [item for item in load_password_resets() if item.get("email") != email.strip().lower()]
    entries.append(
        {
            "email": email.strip().lower(),
            "code": code,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
    )
    write_password_resets(entries)
    return code


def verify_reset_code(email: str, code: str) -> bool:
    for item in load_password_resets():
        if item.get("email") == email.strip().lower() and item.get("code") == code.strip():
            return True
    return False


def clear_reset_code(email: str) -> None:
    entries = [item for item in load_password_resets() if item.get("email") != email.strip().lower()]
    write_password_resets(entries)


def update_user_password(email: str, password: str) -> bool:
    entries = load_users()
    updated = False
    for item in entries:
        if str(item.get("email", "")).strip().lower() != email.strip().lower():
            continue
        item["passwordHash"] = hash_password(password)
        updated = True
        break
    if updated:
        write_users(entries)
    return updated


def send_reset_email(email: str, code: str) -> None:
    if not SMTP_HOST or not SMTP_FROM:
        raise RuntimeError("Почтовый сервер не настроен.")
    message = EmailMessage()
    message["Subject"] = "Код восстановления пароля"
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(f"Ваш код восстановления пароля: {code}")
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as client:
        client.starttls()
        if SMTP_USERNAME:
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
        client.send_message(message)


def save_request(payload: dict) -> dict:
    entries = load_requests()
    record = {
        "id": next_id(entries),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    entries.append(record)
    write_requests(entries)
    return record


def save_review(payload: dict) -> dict:
    entries = load_reviews()
    record = {
        "id": next_id(entries),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        **payload,
    }
    entries.append(record)
    write_reviews(entries)
    return record


def delete_request(request_id: int) -> dict | None:
    entries = load_requests()
    remaining: list[dict] = []
    deleted: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) == request_id and deleted is None:
            deleted = item
            continue
        remaining.append(item)

    if deleted is None:
        return None

    write_requests(remaining)
    return deleted


def update_review_status(review_id: int, status: str) -> dict | None:
    entries = load_reviews()
    updated: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) != review_id:
            continue
        item["status"] = status
        item["moderatedAt"] = datetime.now(timezone.utc).isoformat()
        updated = item
        break

    if updated is None:
        return None

    write_reviews(entries)
    return updated


def update_review(review_id: int, payload: dict) -> dict | None:
    entries = load_reviews()
    updated: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) != review_id:
            continue
        item["name"] = payload["name"]
        item["role"] = payload["role"]
        item["text"] = payload["text"]
        item["updatedAt"] = datetime.now(timezone.utc).isoformat()
        updated = item
        break

    if updated is None:
        return None

    write_reviews(entries)
    return updated


def delete_review(review_id: int) -> dict | None:
    entries = load_reviews()
    remaining: list[dict] = []
    deleted: dict | None = None

    for item in entries:
        if int(item.get("id", 0)) == review_id and deleted is None:
            deleted = item
            continue
        remaining.append(item)

    if deleted is None:
        return None

    write_reviews(remaining)
    return deleted


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def safe_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value).date() if value else None
    except ValueError:
        return None


def matches_request_filters(item: dict, query: str, task_type: str, date_from: date | None, date_to: date | None) -> bool:
    created_at = safe_date(str(item.get("createdAt", "")))
    if date_from and (created_at is None or created_at < date_from):
        return False
    if date_to and (created_at is None or created_at > date_to):
        return False
    if task_type and str(item.get("taskType", "")).strip().lower() != task_type.strip().lower():
        return False
    if query:
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("name", "contact", "taskType", "deadline", "details")
        ).lower()
        if query.lower() not in haystack:
            return False
    return True


def matches_review_filters(item: dict, query: str, status: str) -> bool:
    if status and str(item.get("status", "")).strip().lower() != status.strip().lower():
        return False
    if query:
        haystack = " ".join(
            str(item.get(field, ""))
            for field in ("name", "role", "text")
        ).lower()
        if query.lower() not in haystack:
            return False
    return True


class AppHandler(BaseHTTPRequestHandler):
    server_version = "ProsePrincessClone/1.3"

    def do_GET(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)

        if parsed.path == "/api/health":
            self._send_json({"status": "ok"})
            return

        if parsed.path == "/api/requests":
            self._require_admin()
            if self._response_sent:
                return
            params = parse_qs(parsed.query)
            items = self._filter_requests(params)
            self._send_json({"ok": True, "items": items})
            return

        if parsed.path == "/api/reviews":
            approved = [
                item
                for item in reversed(load_reviews())
                if str(item.get("status", "")) == "approved"
            ]
            self._send_json({"ok": True, "items": approved})
            return

        if parsed.path == "/api/auth/me":
            user = self._require_user()
            if self._response_sent or user is None:
                return
            self._send_json({"ok": True, "user": sanitize_user(user)})
            return

        if parsed.path == "/api/chat/messages":
            user = self._require_user()
            if self._response_sent or user is None:
                return
            mark_messages_read(int(user["id"]), "user")
            self._send_json({"ok": True, "items": get_user_messages(int(user["id"]))})
            return

        if parsed.path == "/api/admin/chats":
            self._require_admin()
            if self._response_sent:
                return
            self._send_json({"ok": True, "items": get_admin_chats()})
            return

        if parsed.path.startswith("/api/admin/chats/") and parsed.path.endswith("/messages"):
            self._require_admin()
            if self._response_sent:
                return
            user_id_raw = (
                parsed.path.removeprefix("/api/admin/chats/")
                .removesuffix("/messages")
                .strip("/")
            )
            if not user_id_raw.isdigit():
                self._send_json({"ok": False, "message": "Некорректный идентификатор пользователя."}, status=HTTPStatus.BAD_REQUEST)
                return
            mark_messages_read(int(user_id_raw), "admin")
            self._send_json({"ok": True, "items": get_user_messages(int(user_id_raw))})
            return

        if parsed.path == "/api/admin/reviews":
            self._require_admin()
            if self._response_sent:
                return
            params = parse_qs(parsed.query)
            items = self._filter_reviews(params)
            self._send_json({"ok": True, "items": items})
            return

        self._serve_static(parsed.path)

    def do_POST(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)

        if parsed.path == "/api/auth/register":
            payload = self._read_json_body()
            if payload is None:
                return
            errors = self._validate_user_auth(payload, with_name=True)
            if errors:
                self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                return
            if find_user_by_email(payload["email"]):
                self._send_json({"ok": False, "message": "Пользователь с такой почтой уже существует."}, status=HTTPStatus.CONFLICT)
                return
            user = create_user(payload)
            session = create_session(int(user["id"]))
            self._send_json({"ok": True, "token": session["token"], "user": sanitize_user(user)}, status=HTTPStatus.CREATED)
            return

        if parsed.path == "/api/auth/login":
            payload = self._read_json_body()
            if payload is None:
                return
            errors = self._validate_user_auth(payload, with_name=False)
            if errors:
                self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                return
            user = find_user_by_email(payload["email"])
            if user is None or user.get("passwordHash") != hash_password(payload["password"]):
                self._send_json({"ok": False, "message": "Неверная почта или пароль."}, status=HTTPStatus.UNAUTHORIZED)
                return
            session = create_session(int(user["id"]))
            self._send_json({"ok": True, "token": session["token"], "user": sanitize_user(user)})
            return

        if parsed.path == "/api/auth/password-reset/request":
            payload = self._read_json_body()
            if payload is None:
                return
            email = str(payload.get("email", "")).strip().lower()
            if "@" not in email or "." not in email:
                self._send_json({"ok": False, "message": "Укажите корректную почту."}, status=HTTPStatus.BAD_REQUEST)
                return
            user = find_user_by_email(email)
            if user is None:
                self._send_json({"ok": True, "message": "Если почта зарегистрирована, код будет отправлен."})
                return
            code = create_reset_code(email)
            try:
                send_reset_email(email, code)
            except Exception as error:
                self._send_json({"ok": False, "message": str(error)}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            self._send_json({"ok": True, "message": "Код отправлен на электронную почту."})
            return

        if parsed.path == "/api/auth/password-reset/confirm":
            payload = self._read_json_body()
            if payload is None:
                return
            email = str(payload.get("email", "")).strip().lower()
            code = str(payload.get("code", "")).strip()
            password = str(payload.get("password", ""))
            if len(password) < 6:
                self._send_json({"ok": False, "message": "Пароль должен содержать минимум 6 символов."}, status=HTTPStatus.BAD_REQUEST)
                return
            if not verify_reset_code(email, code):
                self._send_json({"ok": False, "message": "Неверный код восстановления."}, status=HTTPStatus.BAD_REQUEST)
                return
            if not update_user_password(email, password):
                self._send_json({"ok": False, "message": "Пользователь не найден."}, status=HTTPStatus.NOT_FOUND)
                return
            clear_reset_code(email)
            self._send_json({"ok": True, "message": "Пароль обновлён. Теперь можно войти."})
            return

        if parsed.path == "/api/auth/logout":
            token = self._get_bearer_token()
            if token:
                delete_session(token)
            self._send_json({"ok": True})
            return

        if parsed.path == "/api/chat/messages":
            user = self._require_user()
            if self._response_sent or user is None:
                return
            payload = self._read_json_body()
            if payload is None:
                return
            text = str(payload.get("text", "")).strip()
            attachment = payload.get("attachment")
            if len(text) < 1 and not attachment:
                self._send_json({"ok": False, "message": "Сообщение не может быть пустым."}, status=HTTPStatus.BAD_REQUEST)
                return
            stored_attachment = None
            if isinstance(attachment, dict) and attachment.get("contentBase64"):
                try:
                    stored_attachment = store_attachment(attachment)
                except Exception as error:
                    self._send_json({"ok": False, "message": str(error)}, status=HTTPStatus.BAD_REQUEST)
                    return
            message = create_message(int(user["id"]), "user", text, stored_attachment)
            self._send_json({"ok": True, "item": message}, status=HTTPStatus.CREATED)
            return

        if parsed.path.startswith("/api/admin/chats/") and parsed.path.endswith("/messages"):
            self._require_admin()
            if self._response_sent:
                return
            user_id_raw = (
                parsed.path.removeprefix("/api/admin/chats/")
                .removesuffix("/messages")
                .strip("/")
            )
            if not user_id_raw.isdigit():
                self._send_json({"ok": False, "message": "Некорректный идентификатор пользователя."}, status=HTTPStatus.BAD_REQUEST)
                return
            payload = self._read_json_body()
            if payload is None:
                return
            text = str(payload.get("text", "")).strip()
            if len(text) < 1:
                self._send_json({"ok": False, "message": "Сообщение не может быть пустым."}, status=HTTPStatus.BAD_REQUEST)
                return
            if find_user_by_id(int(user_id_raw)) is None:
                self._send_json({"ok": False, "message": "Пользователь не найден."}, status=HTTPStatus.NOT_FOUND)
                return
            message = create_message(int(user_id_raw), "admin", text)
            self._send_json({"ok": True, "item": message}, status=HTTPStatus.CREATED)
            return

        if parsed.path == "/api/requests":
            payload = self._read_json_body()
            if payload is None:
                return
            errors = self._validate_request(payload)
            if errors:
                self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                return
            record = save_request(payload)
            self._send_json(
                {
                    "ok": True,
                    "message": "Заявка отправлена. Я свяжусь с вами в ближайшее время.",
                    "requestId": record["id"],
                },
                status=HTTPStatus.CREATED,
            )
            return

        if parsed.path == "/api/reviews":
            payload = self._read_json_body()
            if payload is None:
                return
            errors = self._validate_review(payload)
            if errors:
                self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
                return
            record = save_review(payload)
            self._send_json(
                {
                    "ok": True,
                    "message": "Отзыв отправлен и ждёт одобрения администратора.",
                    "reviewId": record["id"],
                },
                status=HTTPStatus.CREATED,
            )
            return

        if parsed.path.startswith("/api/admin/reviews/") and parsed.path.endswith("/approve"):
            self._change_review_status(parsed.path, "approved")
            return

        if parsed.path.startswith("/api/admin/reviews/") and parsed.path.endswith("/reject"):
            self._change_review_status(parsed.path, "rejected")
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def do_DELETE(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/admin/reviews/"):
            self._require_admin()
            if self._response_sent:
                return

            review_id_raw = parsed.path.removeprefix("/api/admin/reviews/").strip("/")
            if not review_id_raw.isdigit():
                self._send_json({"ok": False, "message": "Некорректный идентификатор отзыва."}, status=HTTPStatus.BAD_REQUEST)
                return

            deleted = delete_review(int(review_id_raw))
            if deleted is None:
                self._send_json({"ok": False, "message": "Отзыв не найден."}, status=HTTPStatus.NOT_FOUND)
                return

            self._send_json({"ok": True, "message": f"Отзыв #{review_id_raw} удалён."})
            return

        if not parsed.path.startswith("/api/requests/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")
            return

        self._require_admin()
        if self._response_sent:
            return

        request_id_raw = parsed.path.removeprefix("/api/requests/").strip("/")
        if not request_id_raw.isdigit():
            self._send_json({"ok": False, "message": "Некорректный идентификатор заявки."}, status=HTTPStatus.BAD_REQUEST)
            return

        deleted = delete_request(int(request_id_raw))
        if deleted is None:
            self._send_json({"ok": False, "message": "Заявка не найдена."}, status=HTTPStatus.NOT_FOUND)
            return

        self._send_json({"ok": True, "message": f"Заявка #{request_id_raw} удалена."})

    def do_PUT(self) -> None:
        self._response_sent = False
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/admin/reviews/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")
            return

        self._require_admin()
        if self._response_sent:
            return

        review_id_raw = parsed.path.removeprefix("/api/admin/reviews/").strip("/")
        if not review_id_raw.isdigit():
            self._send_json({"ok": False, "message": "Некорректный идентификатор отзыва."}, status=HTTPStatus.BAD_REQUEST)
            return

        payload = self._read_json_body()
        if payload is None:
            return

        errors = self._validate_review(payload)
        if errors:
            self._send_json({"ok": False, "errors": errors}, status=HTTPStatus.BAD_REQUEST)
            return

        updated = update_review(int(review_id_raw), payload)
        if updated is None:
            self._send_json({"ok": False, "message": "Отзыв не найден."}, status=HTTPStatus.NOT_FOUND)
            return

        self._send_json({"ok": True, "message": f"Отзыв #{review_id_raw} сохранён.", "item": updated})

    @property
    def _response_sent(self) -> bool:
        return getattr(self, "__response_sent", False)

    @_response_sent.setter
    def _response_sent(self, value: bool) -> None:
        self.__response_sent = value

    def _filter_requests(self, params: dict[str, list[str]]) -> list[dict]:
        query = params.get("q", [""])[0].strip()
        task_type = params.get("taskType", [""])[0].strip()
        date_from = parse_iso_date(params.get("dateFrom", [""])[0].strip()) if params.get("dateFrom") else None
        date_to = parse_iso_date(params.get("dateTo", [""])[0].strip()) if params.get("dateTo") else None
        return [
            item
            for item in reversed(load_requests())
            if matches_request_filters(item, query, task_type, date_from, date_to)
        ]

    def _filter_reviews(self, params: dict[str, list[str]]) -> list[dict]:
        query = params.get("q", [""])[0].strip()
        status = params.get("status", [""])[0].strip()
        return [
            item
            for item in reversed(load_reviews())
            if matches_review_filters(item, query, status)
        ]

    def _read_json_body(self) -> dict | None:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0 or content_length > MAX_REQUEST_SIZE:
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid request size")
            self._response_sent = True
            return None
        try:
            raw_body = self.rfile.read(content_length)
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_error(HTTPStatus.BAD_REQUEST, "Invalid JSON payload")
            self._response_sent = True
            return None
        if not isinstance(payload, dict):
            self._send_json({"ok": False, "message": "Ожидался JSON-объект."}, status=HTTPStatus.BAD_REQUEST)
            return None
        return payload

    def _change_review_status(self, path: str, status: str) -> None:
        self._require_admin()
        if self._response_sent:
            return
        review_id_raw = (
            path.removeprefix("/api/admin/reviews/")
            .removesuffix("/approve")
            .removesuffix("/reject")
            .strip("/")
        )
        if not review_id_raw.isdigit():
            self._send_json({"ok": False, "message": "Некорректный идентификатор отзыва."}, status=HTTPStatus.BAD_REQUEST)
            return
        updated = update_review_status(int(review_id_raw), status)
        if updated is None:
            self._send_json({"ok": False, "message": "Отзыв не найден."}, status=HTTPStatus.NOT_FOUND)
            return
        verb = "одобрен" if status == "approved" else "отклонён"
        self._send_json({"ok": True, "message": f"Отзыв #{review_id_raw} {verb}."})

    def _get_bearer_token(self) -> str:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return ""
        return header.removeprefix("Bearer ").strip()

    def _require_user(self) -> dict | None:
        token = self._get_bearer_token()
        if not token:
            self._send_json({"ok": False, "message": "Требуется авторизация пользователя."}, status=HTTPStatus.UNAUTHORIZED)
            return None
        session = find_session(token)
        if session is None:
            self._send_json({"ok": False, "message": "Сессия пользователя не найдена."}, status=HTTPStatus.UNAUTHORIZED)
            return None
        user = find_user_by_id(int(session["userId"]))
        if user is None:
            self._send_json({"ok": False, "message": "Пользователь не найден."}, status=HTTPStatus.UNAUTHORIZED)
            return None
        return user

    def _require_admin(self) -> None:
        if self._is_authorized():
            return
        self._send_auth_required()

    def _is_authorized(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        token = header.removeprefix("Basic ").strip()
        try:
            decoded = base64.b64decode(token).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return False
        username, separator, password = decoded.partition(":")
        return bool(separator) and username == ADMIN_USERNAME and password == ADMIN_PASSWORD

    def _send_auth_required(self) -> None:
        body = json.dumps(
            {"ok": False, "message": "Требуется авторизация для доступа к админ-панели."},
            ensure_ascii=False,
        ).encode("utf-8")
        self.send_response(HTTPStatus.UNAUTHORIZED)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("WWW-Authenticate", 'Basic realm="Admin Panel"')
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._response_sent = True

    def _validate_request(self, payload: dict) -> dict[str, str]:
        required_fields = {
            "name": "Укажите имя.",
            "contact": "Укажите способ связи.",
            "taskType": "Выберите тип работы.",
            "deadline": "Укажите срок.",
            "details": "Опишите задачу.",
        }
        errors: dict[str, str] = {}
        for field, message in required_fields.items():
            value = payload.get(field, "")
            if not isinstance(value, str) or not value.strip():
                errors[field] = message
        details = str(payload.get("details", ""))
        if details and len(details.strip()) < 20:
            errors["details"] = "Опишите задачу чуть подробнее, минимум 20 символов."
        return errors

    def _validate_review(self, payload: dict) -> dict[str, str]:
        required_fields = {
            "name": "Укажите имя.",
            "role": "Укажите, кто вы или на каком направлении учитесь.",
            "text": "Напишите отзыв.",
        }
        errors: dict[str, str] = {}
        for field, message in required_fields.items():
            value = payload.get(field, "")
            if not isinstance(value, str) or not value.strip():
                errors[field] = message
        text = str(payload.get("text", ""))
        if text and len(text.strip()) < 30:
            errors["text"] = "Отзыв должен быть чуть подробнее, минимум 30 символов."
        return errors

    def _validate_user_auth(self, payload: dict, with_name: bool) -> dict[str, str]:
        errors: dict[str, str] = {}
        if with_name:
            name = str(payload.get("name", "")).strip()
            if len(name) < 2:
                errors["name"] = "Укажите имя, минимум 2 символа."
        email = str(payload.get("email", "")).strip()
        password = str(payload.get("password", ""))
        if "@" not in email or "." not in email:
            errors["email"] = "Укажите корректную почту."
        if len(password) < 6:
            errors["password"] = "Пароль должен содержать минимум 6 символов."
        return errors

    def _validate_user_auth(self, payload: dict, with_name: bool) -> dict[str, str]:
        errors: dict[str, str] = {}
        if with_name:
            name = str(payload.get("name", "")).strip()
            if len(name) < 2:
                errors["name"] = "Укажите имя, минимум 2 символа."
        email = str(payload.get("email", "")).strip()
        password = str(payload.get("password", ""))
        if "@" not in email or "." not in email:
            errors["email"] = "Укажите корректную почту."
        if len(password) < 6:
            errors["password"] = "Пароль должен содержать минимум 6 символов."
        return errors

    def _serve_static(self, raw_path: str) -> None:
        routes = {
            "/": "/index.html",
            "/chat": "/chat.html",
            "/admin": "/admin.html",
            "/admin/chats": "/admin-chats.html",
        }
        requested = routes.get(raw_path.rstrip("/") or "/", raw_path.rstrip("/") or "/index.html")
        if raw_path.startswith("/uploads/"):
            relative_upload_path = raw_path.removeprefix("/uploads/").lstrip("/")
            file_path = (UPLOADS_DIR / relative_upload_path).resolve()
            allowed_root = UPLOADS_DIR
        else:
            file_path = (STATIC_DIR / requested.lstrip("/")).resolve()
            allowed_root = STATIC_DIR
        if allowed_root not in file_path.parents and file_path != allowed_root:
            self.send_error(HTTPStatus.FORBIDDEN, "Forbidden")
            self._response_sent = True
            return
        if not file_path.exists() or not file_path.is_file():
            if raw_path.startswith("/uploads/"):
                self.send_error(HTTPStatus.NOT_FOUND, "File not found")
                self._response_sent = True
                return
            file_path = STATIC_DIR / "index.html"
        try:
            content = file_path.read_bytes()
        except OSError:
            self.send_error(HTTPStatus.INTERNAL_SERVER_ERROR, "Unable to read file")
            self._response_sent = True
            return
        content_type, _ = mimetypes.guess_type(str(file_path))
        self.send_response(HTTPStatus.OK)
        resolved_content_type = content_type or "application/octet-stream"
        if resolved_content_type.startswith("text/") or resolved_content_type in {"application/javascript", "application/json", "image/svg+xml"}:
            resolved_content_type = f"{resolved_content_type}; charset=utf-8"
        self.send_header("Content-Type", resolved_content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
        self._response_sent = True

    def _send_json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self._response_sent = True

    def log_message(self, format: str, *args: object) -> None:
        return


def run() -> None:
    ensure_storage()
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Server running on http://{host}:{port}")
    print(f"Admin panel: http://{host}:{port}/admin")
    print("Set ADMIN_USERNAME and ADMIN_PASSWORD to change admin credentials.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
