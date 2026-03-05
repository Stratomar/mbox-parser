from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.execute("PRAGMA journal_mode=wal")
        self.conn.execute("PRAGMA synchronous=normal")
        self.conn.row_factory = sqlite3.Row

    def create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                thread_id TEXT,
                in_reply_to TEXT,
                "references" TEXT,
                from_name TEXT,
                from_address TEXT,
                to_addresses TEXT,
                cc_addresses TEXT,
                bcc_addresses TEXT,
                date TEXT,
                subject TEXT,
                body_text TEXT,
                body_html TEXT,
                labels TEXT,
                source_file TEXT,
                content_type TEXT,
                is_chat INTEGER DEFAULT 0,
                has_attachments INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                filename TEXT,
                content_type TEXT,
                size_bytes INTEGER,
                file_path TEXT,
                FOREIGN KEY (email_id) REFERENCES emails(id)
            );

            CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails(message_id);
            CREATE INDEX IF NOT EXISTS idx_emails_thread_id ON emails(thread_id);
            CREATE INDEX IF NOT EXISTS idx_emails_from_address ON emails(from_address);
            CREATE INDEX IF NOT EXISTS idx_emails_date ON emails(date);
            CREATE INDEX IF NOT EXISTS idx_emails_labels ON emails(labels);
            CREATE INDEX IF NOT EXISTS idx_attachments_email_id ON attachments(email_id);
        """)

    def insert_email(self, data: dict[str, Any]) -> int | None:
        row = {
            "message_id": data["message_id"],
            "thread_id": data.get("thread_id"),
            "in_reply_to": data.get("in_reply_to"),
            "references": data.get("references"),
            "from_name": data.get("from_name"),
            "from_address": data.get("from_address"),
            "to_addresses": json.dumps(data.get("to_addresses", [])),
            "cc_addresses": json.dumps(data.get("cc_addresses", [])),
            "bcc_addresses": json.dumps(data.get("bcc_addresses", [])),
            "date": data.get("date"),
            "subject": data.get("subject"),
            "body_text": data.get("body_text"),
            "body_html": data.get("body_html"),
            "labels": json.dumps(data.get("labels", [])),
            "source_file": data.get("source_file"),
            "content_type": data.get("content_type"),
            "is_chat": data.get("is_chat", 0),
            "has_attachments": data.get("has_attachments", 0),
        }
        cursor = self.conn.execute(
            """INSERT OR IGNORE INTO emails
            (message_id, thread_id, in_reply_to, "references", from_name,
             from_address, to_addresses, cc_addresses, bcc_addresses, date,
             subject, body_text, body_html, labels, source_file, content_type,
             is_chat, has_attachments)
            VALUES
            (:message_id, :thread_id, :in_reply_to, :references, :from_name,
             :from_address, :to_addresses, :cc_addresses, :bcc_addresses, :date,
             :subject, :body_text, :body_html, :labels, :source_file, :content_type,
             :is_chat, :has_attachments)""",
            row,
        )
        if cursor.rowcount == 0:
            return None
        return cursor.lastrowid

    def insert_attachment(self, data: dict[str, Any]) -> None:
        self.conn.execute(
            """INSERT INTO attachments (email_id, filename, content_type, size_bytes, file_path)
            VALUES (:email_id, :filename, :content_type, :size_bytes, :file_path)""",
            data,
        )

    def update_has_attachments(self, email_id: int) -> None:
        self.conn.execute(
            "UPDATE emails SET has_attachments = 1 WHERE id = ?", (email_id,)
        )

    def commit(self) -> None:
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
