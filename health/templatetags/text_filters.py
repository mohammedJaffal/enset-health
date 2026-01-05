import re

from django import template

register = template.Library()


@register.filter
def clean_ai_response(value):
    if not value:
        return ''

    cleaned_lines = []
    for line in str(value).splitlines():
        stripped = line.strip()
        if re.fullmatch(r'[-*_]{3,}', stripped):
            continue
        line = re.sub(r'^\s*#{1,6}\s+', '', line)
        line = re.sub(r'\*\*(.*?)\*\*', r'\1', line)
        line = re.sub(r'__(.*?)__', r'\1', line)
        line = re.sub(r'`([^`]+)`', r'\1', line)
        cleaned_lines.append(line)

    return '\n'.join(cleaned_lines).strip()
