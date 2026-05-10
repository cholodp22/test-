"""json-backed state for cron-mode bot.

state lives in two human-readable files committed to the repo so github
actions persists it between scheduled runs:

- state/accounts.json — list of tracked accounts + resolved x user_ids
- state/last_seen.json — {username: last_tweet_id} per account
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class TrackedAccount:
    username: str
    user_id: str | None = None


def normalize_username(username: str) -> str:
    return username.strip().lstrip("@").lower()


# private alias kept for internal use within this module
_norm = normalize_username


class JsonState:
    def __init__(
        self,
        accounts_path: str = "state/accounts.json",
        last_seen_path: str = "state/last_seen.json",
    ) -> None:
        self._accounts_path = Path(accounts_path)
        self._last_seen_path = Path(last_seen_path)

    def _ensure_dir(self) -> None:
        self._accounts_path.parent.mkdir(parents=True, exist_ok=True)

    def list_accounts(self) -> list[TrackedAccount]:
        if not self._accounts_path.exists():
            return []
        raw = self._accounts_path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        data = json.loads(raw)
        return [
            TrackedAccount(
                username=_norm(item["username"]),
                user_id=item.get("user_id"),
            )
            for item in data
        ]

    def _save_accounts(self, accounts: list[TrackedAccount]) -> None:
        self._ensure_dir()
        ordered = sorted(accounts, key=lambda a: a.username)
        payload = json.dumps(
            [asdict(a) for a in ordered],
            indent=2,
            ensure_ascii=False,
        )
        self._accounts_path.write_text(payload + "\n", encoding="utf-8")

    def add_account(self, username: str) -> bool:
        username = _norm(username)
        if not username:
            return False
        accounts = self.list_accounts()
        if any(a.username == username for a in accounts):
            return False
        accounts.append(TrackedAccount(username=username))
        self._save_accounts(accounts)
        return True

    def remove_account(self, username: str) -> bool:
        username = _norm(username)
        accounts = self.list_accounts()
        new_accounts = [a for a in accounts if a.username != username]
        if len(new_accounts) == len(accounts):
            return False
        self._save_accounts(new_accounts)
        last_seen = self.load_last_seen()
        if username in last_seen:
            del last_seen[username]
            self._save_last_seen(last_seen)
        return True

    def set_user_id(self, username: str, user_id: str) -> None:
        username = _norm(username)
        accounts = self.list_accounts()
        for i, a in enumerate(accounts):
            if a.username == username and a.user_id != user_id:
                accounts[i] = TrackedAccount(username=a.username, user_id=user_id)
                self._save_accounts(accounts)
                return

    def load_last_seen(self) -> dict[str, str]:
        if not self._last_seen_path.exists():
            return {}
        raw = self._last_seen_path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return {_norm(k): str(v) for k, v in data.items()}

    def _save_last_seen(self, data: dict[str, str]) -> None:
        self._ensure_dir()
        ordered = {k: data[k] for k in sorted(data)}
        payload = json.dumps(ordered, indent=2, ensure_ascii=False)
        self._last_seen_path.write_text(payload + "\n", encoding="utf-8")

    def set_last_seen(self, username: str, tweet_id: str) -> None:
        username = _norm(username)
        data = self.load_last_seen()
        if data.get(username) != tweet_id:
            data[username] = tweet_id
            self._save_last_seen(data)
