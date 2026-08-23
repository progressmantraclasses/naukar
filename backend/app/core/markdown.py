"""Normalize common malformed Markdown emitted by language models."""
import re


_TABLE_ROW = re.compile(r"^\s*\|[^\n]*\|\s*$")
_TABLE_SEPARATOR = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")


def normalize_report_markdown(markdown: str) -> str:
    """Make pipe tables valid GFM while preserving ordinary prose."""
    cleaned = re.sub(r"<br\s*/?>", "\n", markdown or "", flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*\|\|\s*", "\n", cleaned)
    lines = cleaned.splitlines()
    output: list[str] = []
    index = 0

    def is_row(value: str) -> bool:
        stripped = value.strip()
        return bool(_TABLE_ROW.match(stripped) and "|" in stripped[1:-1])

    def separator_for(value: str) -> str:
        columns = len(value.strip().strip("|").split("|"))
        return "| " + " | ".join(["---"] * columns) + " |"

    while index < len(lines):
        if not is_row(lines[index]):
            output.append(lines[index])
            index += 1
            continue
        rows: list[str] = []
        while index < len(lines):
            if is_row(lines[index]):
                rows.append(lines[index].strip())
                index += 1
                continue
            if not lines[index].strip() and index + 1 < len(lines) and is_row(lines[index + 1]):
                index += 1
                continue
            break
        if len(rows) > 1 and not _TABLE_SEPARATOR.match(rows[1]):
            rows.insert(1, separator_for(rows[0]))
        output.extend(rows)
        output.append("")

    return re.sub(r"\n{3,}", "\n\n", "\n".join(output)).strip()
