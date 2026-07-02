import pytest

from apps.core.templatetags.core_extras import markdown_html, safe_url


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, "#"),
        ("", "#"),
        ("   ", "#"),
        ("javascript:alert(1)", "#"),
        ("JavaScript:alert(1)", "#"),
        ("chrome://settings", "#"),
        ("about:blank", "#"),
        ("java\nscript:alert(1)", "#"),  # newline-smuggled scheme
        ("http://example.com", "http://example.com"),
        ("https://example.com", "https://example.com"),
        ("example.com", "http://example.com"),
        ("  example.com  ", "http://example.com"),
    ],
)
def test_safe_url_blocks_dangerous_schemes_and_normalizes(value, expected):
    assert safe_url(value) == expected


def test_markdown_html_renders_bold_and_escapes_nothing_dangerous():
    result = markdown_html("Hello **world**")
    assert "<strong>world</strong>" in result


def test_markdown_html_empty_input():
    assert markdown_html("") == ""
    assert markdown_html(None) == ""
