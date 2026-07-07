import re

import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="markdown_html")
def markdown_html(text):
    """Ported from ApplicationHelper#markdown_html (Redcarpet -> python-markdown,
    fenced code blocks + hard line breaks to match the original rendering)."""
    if not text:
        return ""
    html = md.markdown(text, extensions=["fenced_code", "nl2br"])
    return mark_safe(html)


@register.filter(name="safe_url")
def safe_url(value):
    """Ported from ApplicationHelper#safe_url — strips whitespace, blocks
    javascript:/chrome:/about: schemes, force-prefixes http:// if missing."""
    s = (value or "").strip()
    if not s:
        return "#"
    s = re.sub(r"[\r\n\s]", "", s)
    if re.match(r"(?i)^(javascript|chrome|about)", s):
        return "#"
    if not re.match(r"(?i)^https?://", s):
        return f"http://{s}"
    return s


@register.filter(name="with_tz")
def with_tz(value, fmt="l F d Y g:i A"):
    """Formats a datetime in the active timezone *with an explicit
    timezone label* (e.g. "Saturday July 12 2026 6:30 PM IST") — Rev 3
    directive: times must never be ambiguous, since online/hybrid
    attendees may not share the event's timezone."""
    from django.utils import formats, timezone as tz

    if not value:
        return ""
    local = tz.localtime(value)
    return f"{formats.dateformat.format(local, fmt)} {local.tzname()}"
