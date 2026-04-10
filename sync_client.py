from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request


SYNC_CONFIG_FILE = Path(__file__).resolve().parent / "sync_config.json"


@dataclass
class SyncSettings:
    base_url: str
    api_token: str
    timeout: int = 15

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_token)


class SyncClient:
    def __init__(self, settings: SyncSettings | None) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return bool(self.settings and self.settings.enabled)

    def _build_url(self, path: str) -> str:
        assert self.settings is not None
        base = self.settings.base_url.rstrip("/")
        query = parse.urlencode({"token": self.settings.api_token})
        return f"{base}{path}?{query}"

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        if not self.enabled:
            raise RuntimeError("Синхронизация не настроена.")
        assert self.settings is not None
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        req = request.Request(self._build_url(path), data=data, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=self.settings.timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                text = response.read().decode(charset)
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body).get("error", body)
            except json.JSONDecodeError:
                detail = body or str(exc)
            raise RuntimeError(detail) from exc
        except error.URLError as exc:
            raise RuntimeError("Не удалось подключиться к серверу синхронизации.") from exc

        return json.loads(text) if text else None

    def fetch_records(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/records")
        return list(data.get("records", []))

    def add_record(self, record: dict[str, Any]) -> dict[str, Any]:
        data = self._request("POST", "/records", record)
        return dict(data.get("record", {}))

    def delete_record(self, record_id: str) -> None:
        self._request("DELETE", f"/records/{parse.quote(record_id)}")


def load_sync_settings() -> SyncSettings | None:
    env_url = os.getenv("BUDGET_SYNC_URL", "").strip()
    env_token = os.getenv("BUDGET_SYNC_TOKEN", "").strip()
    if env_url and env_token:
        return SyncSettings(base_url=env_url, api_token=env_token)

    if not SYNC_CONFIG_FILE.exists():
        return None

    try:
        raw = json.loads(SYNC_CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    base_url = str(raw.get("base_url", "")).strip()
    api_token = str(raw.get("api_token", "")).strip()
    timeout = int(raw.get("timeout", 15) or 15)
    if not base_url or not api_token:
        return None
    return SyncSettings(base_url=base_url, api_token=api_token, timeout=timeout)
