MAX_TITLE = 200


def title_from_body(body: str) -> str:
    """Title of a text node: its first non-empty line, trimmed."""
    for line in body.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:MAX_TITLE]
    return ""
