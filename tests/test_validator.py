import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.validator import normalize_mobile, validate_code, validate_repeat, sanitize_ami_value


class TestNormalizeMobile:
    def test_standard_09_format(self):
        ok, num = normalize_mobile("09123456789")
        assert ok and num == "09123456789"

    def test_plus98_format(self):
        ok, num = normalize_mobile("+989123456789")
        assert ok and num == "09123456789"

    def test_0098_format(self):
        ok, num = normalize_mobile("00989123456789")
        assert ok and num == "09123456789"

    def test_98_format(self):
        ok, num = normalize_mobile("989123456789")
        assert ok and num == "09123456789"

    def test_invalid_short(self):
        ok, _ = normalize_mobile("0912345")
        assert not ok

    def test_invalid_wrong_prefix(self):
        ok, _ = normalize_mobile("08123456789")
        assert not ok

    def test_empty(self):
        ok, _ = normalize_mobile("")
        assert not ok

    def test_ami_injection(self):
        ok, _ = normalize_mobile("09123456789\r\nAction: Originate")
        assert not ok

    def test_whitespace_stripped(self):
        ok, num = normalize_mobile("  09123456789  ")
        assert ok and num == "09123456789"


class TestValidateCode:
    def test_4_digit(self):
        ok, _ = validate_code("1234")
        assert ok

    def test_8_digit(self):
        ok, _ = validate_code("12345678")
        assert ok

    def test_5_digit(self):
        ok, _ = validate_code("12345")
        assert ok

    def test_too_short(self):
        ok, msg = validate_code("123")
        assert not ok and msg

    def test_too_long(self):
        ok, _ = validate_code("123456789")
        assert not ok

    def test_non_digit(self):
        ok, _ = validate_code("12a4")
        assert not ok

    def test_injection(self):
        ok, _ = validate_code("1234\r\nAction: Originate")
        assert not ok


class TestValidateRepeat:
    def test_valid_1(self):
        ok, _ = validate_repeat(1)
        assert ok

    def test_valid_3(self):
        ok, _ = validate_repeat(3)
        assert ok

    def test_zero(self):
        ok, _ = validate_repeat(0)
        assert not ok

    def test_four(self):
        ok, _ = validate_repeat(4)
        assert not ok


class TestSanitize:
    def test_removes_crlf(self):
        result = sanitize_ami_value("hello\r\nworld")
        assert "\r" not in result and "\n" not in result
