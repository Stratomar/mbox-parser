from email.message import EmailMessage

from mbox_parser.chat import extract_chat_body, is_chat_message, parse_chat_xml

SAMPLE_CHAT_XML = """\
<con:conversation xmlns:con="google:archive:conversation">
  <con:message from="alice@example.com">
    <con:time ms="1700000000000" />
    <con:body>Hello Bob!</con:body>
  </con:message>
  <con:message from="bob@example.com">
    <con:time ms="1700000060000" />
    <con:body>Hi Alice!</con:body>
  </con:message>
</con:conversation>
"""


class TestParseChatXml:
    def test_parses_messages(self):
        result = parse_chat_xml(SAMPLE_CHAT_XML)
        assert "alice@example.com" in result
        assert "Hello Bob!" in result
        assert "bob@example.com" in result
        assert "Hi Alice!" in result

    def test_includes_timestamps(self):
        result = parse_chat_xml(SAMPLE_CHAT_XML)
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert lines[0].startswith("[")

    def test_invalid_xml_returns_input(self):
        bad_xml = "this is not xml <<<"
        result = parse_chat_xml(bad_xml)
        assert result == bad_xml

    def test_empty_conversation(self):
        xml = '<con:conversation xmlns:con="google:archive:conversation"></con:conversation>'
        result = parse_chat_xml(xml)
        assert result == xml  # no messages found, returns original

    def test_message_without_timestamp(self):
        xml = """\
<con:conversation xmlns:con="google:archive:conversation">
  <con:message from="alice@example.com">
    <con:body>No timestamp</con:body>
  </con:message>
</con:conversation>
"""
        result = parse_chat_xml(xml)
        assert "alice@example.com: No timestamp" in result
        assert "[" not in result

    def test_message_with_empty_body(self):
        xml = """\
<con:conversation xmlns:con="google:archive:conversation">
  <con:message from="alice@example.com">
    <con:time ms="1700000000000" />
    <con:body></con:body>
  </con:message>
</con:conversation>
"""
        result = parse_chat_xml(xml)
        assert "alice@example.com:" in result


class TestIsChatMessage:
    def test_plain_email_is_not_chat(self):
        msg = EmailMessage()
        msg.set_content("Just a plain email")
        assert is_chat_message(msg) is False

    def test_xml_with_chat_namespace_is_chat(self):
        msg = EmailMessage()
        msg.set_content(SAMPLE_CHAT_XML, subtype="xml")
        assert is_chat_message(msg) is True

    def test_xml_without_chat_namespace_is_not_chat(self):
        msg = EmailMessage()
        msg.set_content("<root><item>data</item></root>", subtype="xml")
        assert is_chat_message(msg) is False


class TestExtractChatBody:
    def test_extracts_from_chat_message(self):
        msg = EmailMessage()
        msg.set_content(SAMPLE_CHAT_XML, subtype="xml")
        result = extract_chat_body(msg)
        assert result is not None
        assert "Hello Bob!" in result

    def test_returns_none_for_non_chat(self):
        msg = EmailMessage()
        msg.set_content("Just text")
        result = extract_chat_body(msg)
        assert result is None
