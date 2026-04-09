import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import CONVS_DIR, MEMORY_WINDOW


class ConversationMemory:
    """Manages conversation history stored as JSON files on disk."""

    # ── Internal helpers ──────────────────────────────────────────

    def _conv_dir(self, session_id: str) -> Path:
        d = CONVS_DIR / session_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _conv_path(self, session_id: str, conv_id: str) -> Path:
        return self._conv_dir(session_id) / f"{conv_id}.json"

    def _read(self, path: Path) -> dict | None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

    def _write(self, path: Path, data: dict) -> None:
        """Atomic write: write to .tmp then replace."""
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # ── Public API ────────────────────────────────────────────────

    def get_conversations(self, session_id: str) -> list[dict]:
        """Return list of conversation metadata (no messages), sorted newest first."""
        d = self._conv_dir(session_id)
        convs = []
        for p in d.glob("*.json"):
            data = self._read(p)
            if data:
                convs.append({
                    "id": data["id"],
                    "title": data.get("title", "Cuộc trò chuyện mới"),
                    "created_at": data.get("created_at", ""),
                    "updated_at": data.get("updated_at", ""),
                    "message_count": len(data.get("messages", [])),
                })
        convs.sort(key=lambda x: x["updated_at"], reverse=True)
        return convs

    def create_conversation(self, session_id: str) -> dict:
        """Create a new empty conversation and return its metadata."""
        conv_id = str(uuid.uuid4())
        now = self._now()
        data = {
            "id": conv_id,
            "session_id": session_id,
            "title": "Cuộc trò chuyện mới",
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        self._write(self._conv_path(session_id, conv_id), data)
        return {
            "id": conv_id,
            "title": data["title"],
            "created_at": now,
            "updated_at": now,
            "message_count": 0,
        }

    def get_conversation(self, session_id: str, conv_id: str) -> dict | None:
        """Return full conversation dict or None if not found."""
        return self._read(self._conv_path(session_id, conv_id))

    def add_message(
        self,
        session_id: str,
        conv_id: str,
        role: str,
        content: str,
        sources: list | None = None,
        query_type: str | None = None,
    ) -> None:
        """Append a message to the conversation and save."""
        path = self._conv_path(session_id, conv_id)
        data = self._read(path)
        if data is None:
            return  # conversation doesn't exist

        msg: dict = {
            "role": role,
            "content": content,
            "timestamp": self._now(),
        }
        if sources is not None:
            msg["sources"] = sources
        if query_type is not None:
            msg["query_type"] = query_type

        data["messages"].append(msg)
        data["updated_at"] = self._now()

        # Auto-title from first user message
        if data["title"] == "Cuộc trò chuyện mới" and role == "user":
            data["title"] = content[:60].strip()
            if len(content) > 60:
                data["title"] += "..."

        self._write(path, data)

    def delete_conversation(self, session_id: str, conv_id: str) -> bool:
        """Delete conversation file. Returns True if it existed."""
        path = self._conv_path(session_id, conv_id)
        if path.exists():
            path.unlink()
            return True
        return False

    def get_recent_messages(
        self, session_id: str, conv_id: str, n: int = MEMORY_WINDOW
    ) -> list[dict]:
        """Return the last n messages from the conversation (for LLM context)."""
        data = self._read(self._conv_path(session_id, conv_id))
        if not data:
            return []
        messages = data.get("messages", [])
        return messages[-n:] if len(messages) > n else messages
