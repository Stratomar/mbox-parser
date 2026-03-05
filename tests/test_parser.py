import mailbox
from pathlib import Path

from mbox_parser.db import Database
from mbox_parser.parser import count_messages, parse_message, parse_mbox

SAMPLE_MBOX = """\
From sender@example.com Mon Jan 15 10:30:00 2024
Message-ID: <msg1@example.com>
From: Alice <alice@example.com>
To: Bob <bob@example.com>
Subject: Test email 1
Date: Mon, 15 Jan 2024 10:30:00 +0000
X-Gmail-Labels: Inbox, Important
X-GM-THRID: 12345
Content-Type: text/plain; charset="utf-8"

Hello from email 1

From sender@example.com Mon Jan 15 11:00:00 2024
Message-ID: <msg2@example.com>
From: Bob <bob@example.com>
To: Alice <alice@example.com>
Subject: Test email 2
Date: Mon, 15 Jan 2024 11:00:00 +0000
X-Gmail-Labels: Sent
Content-Type: text/plain; charset="utf-8"

Hello from email 2

"""


def _write_mbox(tmp_path: Path, content: str = SAMPLE_MBOX) -> Path:
    mbox_path = tmp_path / "test.mbox"
    mbox_path.write_text(content)
    return mbox_path


class TestCountMessages:
    def test_counts_from_lines(self, tmp_path: Path):
        mbox_path = _write_mbox(tmp_path)
        assert count_messages(mbox_path) == 2

    def test_empty_file(self, tmp_path: Path):
        mbox_path = tmp_path / "empty.mbox"
        mbox_path.write_text("")
        assert count_messages(mbox_path) == 0


class TestParseMessage:
    def test_inserts_email(self, tmp_path: Path):
        mbox_path = _write_mbox(tmp_path)
        mbox = mailbox.mbox(str(mbox_path))
        messages = list(mbox)

        with Database(":memory:") as db:
            db.create_tables()
            result = parse_message(messages[0], "test.mbox", db, tmp_path)
            db.commit()

            assert result is True
            row = db.conn.execute("SELECT * FROM emails").fetchone()
            assert row["message_id"] == "<msg1@example.com>"
            assert row["from_address"] == "alice@example.com"
            assert row["subject"] == "Test email 1"

    def test_skips_duplicate(self, tmp_path: Path):
        mbox_path = _write_mbox(tmp_path)
        mbox = mailbox.mbox(str(mbox_path))
        messages = list(mbox)

        with Database(":memory:") as db:
            db.create_tables()
            assert parse_message(messages[0], "test.mbox", db, tmp_path) is True
            assert parse_message(messages[0], "test.mbox", db, tmp_path) is False

    def test_skips_message_without_id(self, tmp_path: Path):
        no_id_mbox = """\
From sender@example.com Mon Jan 15 10:30:00 2024
From: Alice <alice@example.com>
Subject: No message ID
Content-Type: text/plain; charset="utf-8"

Body text

"""
        mbox_path = _write_mbox(tmp_path, no_id_mbox)
        mbox = mailbox.mbox(str(mbox_path))
        messages = list(mbox)

        with Database(":memory:") as db:
            db.create_tables()
            result = parse_message(messages[0], "test.mbox", db, tmp_path)
            assert result is False


class TestParseMbox:
    def test_parses_all_messages(self, tmp_path: Path):
        mbox_path = _write_mbox(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with Database(":memory:") as db:
            db.create_tables()
            stats = parse_mbox(mbox_path, db, output_dir)

            assert stats["total"] == 2
            assert stats["inserted"] == 2
            assert stats["skipped"] == 0
            assert stats["errors"] == 0

    def test_deduplication_across_calls(self, tmp_path: Path):
        mbox_path = _write_mbox(tmp_path)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with Database(":memory:") as db:
            db.create_tables()
            stats1 = parse_mbox(mbox_path, db, output_dir)
            stats2 = parse_mbox(mbox_path, db, output_dir)

            assert stats1["inserted"] == 2
            assert stats2["inserted"] == 0
            assert stats2["skipped"] == 2
