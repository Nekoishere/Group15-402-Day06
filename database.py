"""
database.py — SQLite CRUD for persistent chat sessions and messages.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "chat_history.db"


def _connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create tables if they don't exist. Prune empty conversations."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            result_json TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
    """)
    # Prune conversations older than 1 hour with 0 messages (abandoned sessions)
    conn.execute("""
        DELETE FROM conversations
        WHERE id NOT IN (SELECT DISTINCT conversation_id FROM messages)
        AND created_at < datetime('now', '-1 hour')
    """)
    conn.commit()
    conn.close()


def create_conversation(title: str = "New Chat") -> str:
    """Create a new conversation and return its UUID."""
    conv_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = _connect()
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conv_id, title, now, now),
    )
    conn.commit()
    conn.close()
    return conv_id


def list_conversations() -> list[dict]:
    """Return all conversations ordered by most recently updated."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_messages(conversation_id: str) -> list[dict]:
    """Load all messages for a conversation, ordered chronologically."""
    conn = _connect()
    rows = conn.execute(
        "SELECT id, role, content, result_json, created_at FROM messages "
        "WHERE conversation_id = ? ORDER BY created_at ASC",
        (conversation_id,),
    ).fetchall()
    conn.close()
    results = []
    for r in rows:
        msg = dict(r)
        if msg["result_json"]:
            msg["result"] = json.loads(msg["result_json"])
        else:
            msg["result"] = {}
        results.append(msg)
    return results


def save_message(conversation_id: str, role: str, content: str, result: dict | None = None):
    """Insert a message and touch the conversation's updated_at."""
    now = datetime.now().isoformat()
    result_json = json.dumps(result, ensure_ascii=False) if result else None
    conn = _connect()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, result_json, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (conversation_id, role, content, result_json, now),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (now, conversation_id),
    )
    conn.commit()
    conn.close()


def delete_conversation(conversation_id: str):
    """Delete a conversation and all its messages (cascade)."""
    conn = _connect()
    conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    conn.commit()
    conn.close()


def rename_conversation(conversation_id: str, new_title: str):
    """Update the title of a conversation."""
    conn = _connect()
    conn.execute(
        "UPDATE conversations SET title = ? WHERE id = ?",
        (new_title[:60], conversation_id),
    )
    conn.commit()
    conn.close()


def get_recent_messages(conversation_id: str, limit: int = 4) -> list[dict]:
    """Get the last N messages for conversation context."""
    conn = _connect()
    rows = conn.execute(
        "SELECT role, content FROM messages "
        "WHERE conversation_id = ? ORDER BY created_at DESC LIMIT ?",
        (conversation_id, limit),
    ).fetchall()
    conn.close()
    # Reverse to chronological order
    return [dict(r) for r in reversed(rows)]
