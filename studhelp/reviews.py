from __future__ import annotations

from datetime import date, datetime, timezone

from .storage import Storage


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
        haystack = " ".join(str(item.get(field, "")) for field in ("name", "contact", "taskType", "deadline", "details")).lower()
        if query.lower() not in haystack:
            return False
    return True


def matches_review_filters(item: dict, query: str, status: str) -> bool:
    if status and str(item.get("status", "")).strip().lower() != status.strip().lower():
        return False
    if query:
        haystack = " ".join(str(item.get(field, "")) for field in ("name", "role", "text")).lower()
        if query.lower() not in haystack:
            return False
    return True


class ReviewService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def save_request(self, payload: dict) -> dict:
        entries = self.storage.load_requests()
        record = {
            "id": self.storage.next_json_id(entries),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            **payload,
        }
        entries.append(record)
        self.storage.write_requests(entries)
        return record

    def filter_requests(self, query: str, task_type: str, date_from: date | None, date_to: date | None) -> list[dict]:
        return [
            item
            for item in reversed(self.storage.load_requests())
            if matches_request_filters(item, query, task_type, date_from, date_to)
        ]

    def delete_request(self, request_id: int) -> dict | None:
        entries = self.storage.load_requests()
        remaining: list[dict] = []
        deleted: dict | None = None
        for item in entries:
            if int(item.get("id", 0)) == request_id and deleted is None:
                deleted = item
                continue
            remaining.append(item)
        if deleted is None:
            return None
        self.storage.write_requests(remaining)
        return deleted

    def save_review(self, payload: dict) -> dict:
        entries = self.storage.load_reviews()
        record = {
            "id": self.storage.next_json_id(entries),
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "status": "pending",
            **payload,
        }
        entries.append(record)
        self.storage.write_reviews(entries)
        return record

    def public_reviews(self) -> list[dict]:
        return [item for item in reversed(self.storage.load_reviews()) if str(item.get("status", "")) == "approved"]

    def filter_reviews(self, query: str, status: str) -> list[dict]:
        return [
            item
            for item in reversed(self.storage.load_reviews())
            if matches_review_filters(item, query, status)
        ]

    def update_review_status(self, review_id: int, status: str) -> dict | None:
        entries = self.storage.load_reviews()
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
        self.storage.write_reviews(entries)
        return updated

    def update_review(self, review_id: int, payload: dict) -> dict | None:
        entries = self.storage.load_reviews()
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
        self.storage.write_reviews(entries)
        return updated

    def delete_review(self, review_id: int) -> dict | None:
        entries = self.storage.load_reviews()
        remaining: list[dict] = []
        deleted: dict | None = None
        for item in entries:
            if int(item.get("id", 0)) == review_id and deleted is None:
                deleted = item
                continue
            remaining.append(item)
        if deleted is None:
            return None
        self.storage.write_reviews(remaining)
        return deleted
