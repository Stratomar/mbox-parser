from mbox_parser.db import Database


def _make_email(**overrides):
    base = {
        "message_id": "<test@example.com>",
        "thread_id": "123",
        "in_reply_to": None,
        "references": None,
        "from_name": "Test User",
        "from_address": "test@example.com",
        "to_addresses": [{"name": "Bob", "address": "bob@example.com"}],
        "cc_addresses": [],
        "bcc_addresses": [],
        "date": "2024-01-15T10:30:00",
        "subject": "Test Subject",
        "body_text": "Hello world",
        "body_html": "<p>Hello world</p>",
        "labels": ["Inbox", "Important"],
        "source_file": "Inbox.mbox",
        "content_type": "multipart/mixed",
        "is_chat": 0,
        "has_attachments": 0,
    }
    base.update(overrides)
    return base


class TestDatabase:
    def test_create_tables(self):
        with Database(":memory:") as db:
            db.create_tables()
            tables = db.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            table_names = [t["name"] for t in tables]
            assert "emails" in table_names
            assert "attachments" in table_names

    def test_insert_email(self):
        with Database(":memory:") as db:
            db.create_tables()
            email_id = db.insert_email(_make_email())
            assert email_id is not None
            assert email_id > 0

            row = db.conn.execute(
                "SELECT * FROM emails WHERE id = ?", (email_id,)
            ).fetchone()
            assert row["message_id"] == "<test@example.com>"
            assert row["subject"] == "Test Subject"
            assert row["from_address"] == "test@example.com"

    def test_deduplication(self):
        with Database(":memory:") as db:
            db.create_tables()
            id1 = db.insert_email(_make_email())
            id2 = db.insert_email(_make_email())
            assert id1 is not None
            assert id2 is None

            count = db.conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
            assert count == 1

    def test_different_message_ids_both_inserted(self):
        with Database(":memory:") as db:
            db.create_tables()
            id1 = db.insert_email(_make_email(message_id="<a@example.com>"))
            id2 = db.insert_email(_make_email(message_id="<b@example.com>"))
            assert id1 is not None
            assert id2 is not None
            assert id1 != id2

    def test_insert_attachment(self):
        with Database(":memory:") as db:
            db.create_tables()
            email_id = db.insert_email(_make_email())
            assert email_id is not None

            db.insert_attachment(
                {
                    "email_id": email_id,
                    "filename": "doc.pdf",
                    "content_type": "application/pdf",
                    "size_bytes": 12345,
                    "file_path": "attachments/1/doc.pdf",
                }
            )

            rows = db.conn.execute(
                "SELECT * FROM attachments WHERE email_id = ?", (email_id,)
            ).fetchall()
            assert len(rows) == 1
            assert rows[0]["filename"] == "doc.pdf"
            assert rows[0]["size_bytes"] == 12345

    def test_update_has_attachments(self):
        with Database(":memory:") as db:
            db.create_tables()
            email_id = db.insert_email(_make_email())
            assert email_id is not None

            db.update_has_attachments(email_id)
            row = db.conn.execute(
                "SELECT has_attachments FROM emails WHERE id = ?", (email_id,)
            ).fetchone()
            assert row["has_attachments"] == 1

    def test_context_manager(self):
        with Database(":memory:") as db:
            db.create_tables()
            db.insert_email(_make_email())
            db.commit()

    def test_json_serialization(self):
        with Database(":memory:") as db:
            db.create_tables()
            email_id = db.insert_email(
                _make_email(
                    labels=["Inbox", "Important", "Starred"],
                    to_addresses=[
                        {"name": "Alice", "address": "alice@example.com"},
                        {"name": "Bob", "address": "bob@example.com"},
                    ],
                )
            )
            assert email_id is not None

            row = db.conn.execute(
                "SELECT labels, to_addresses FROM emails WHERE id = ?", (email_id,)
            ).fetchone()
            import json

            assert json.loads(row["labels"]) == ["Inbox", "Important", "Starred"]
            assert len(json.loads(row["to_addresses"])) == 2
