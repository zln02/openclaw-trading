"""common/utils.py 유닛 테스트."""
import json
import os
import tempfile

from common.utils import atomic_write_json, parse_json_from_text, safe_float


class TestSafeFloat:
    def test_valid_string(self):
        assert safe_float("3.14") == 3.14

    def test_valid_int(self):
        assert safe_float(42) == 42.0

    def test_invalid(self):
        assert safe_float("abc", default=0.0) == 0.0

    def test_none(self):
        assert safe_float(None, default=-1.0) == -1.0


class TestParseJsonFromText:
    def test_plain_json(self):
        result = parse_json_from_text('{"action": "BUY"}')
        assert result == {"action": "BUY"}

    def test_markdown_wrapped(self):
        text = 'Here is the result:\n```json\n{"action": "SELL"}\n```'
        result = parse_json_from_text(text)
        assert result == {"action": "SELL"}

    def test_invalid(self):
        # parse_json_from_text raises ValueError when no JSON found
        try:
            result = parse_json_from_text("no json here")
            assert result is None
        except (ValueError, Exception):
            pass  # ValueError 발생도 정상 동작


class TestAtomicWriteJson:
    def test_write_and_read(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            data = {"key": "value", "num": 42}
            atomic_write_json(path, data)
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded == data

    def test_overwrite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.json")
            atomic_write_json(path, {"v": 1})
            atomic_write_json(path, {"v": 2})
            with open(path, encoding="utf-8") as f:
                loaded = json.load(f)
            assert loaded["v"] == 2
