import fnmatch
import posixpath
from dataclasses import dataclass


DIFF_HEADER = "diff --git "
IGNORED_PATTERNS = [
    # lock files
    "*.lock", "package-lock.json", "pnpm-lock.yaml",
    # minified / generated
    "*.min.js", "*.min.css", "*.map",
    # binaries
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.ico", "*.pdf", "*.zip",
    # build output
    "dist/*", "build/*",
]

def _path_from_header(line: str) -> str:
    # "diff --git a/old/name.py b/new/name.py\n" -> "new/name.py"
    return line.rstrip("\r\n").rsplit(" b/", 1)[-1]


def split_by_file(diff: str) -> list[tuple[str, str]]:
    if not diff.strip():
        return []

    files = []
    path = None
    lines = []
    for line in diff.splitlines(keepends=True):
        if line.startswith(DIFF_HEADER):
            if path is not None:
                files.append((path, "".join(lines)))
            path = _path_from_header(line)
            lines = []
        if path is not None:
            lines.append(line)

    if path is None:
        return [("", diff)]
    files.append((path, "".join(lines)))
    return files


def is_ignored(path: str) -> bool:
    name = posixpath.basename(path)
    return any(
        fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(name, pattern)
        for pattern in IGNORED_PATTERNS
    )

MAX_DIFF_CHARS = 100_000


def truncate(text: str, max_chars: int = MAX_DIFF_CHARS) -> tuple[str, bool]:
    """Cut text to at most max_chars, at a line boundary. Returns (text, was_truncated)."""
    if len(text) <= max_chars:
        return text, False
    cut = text.rfind("\n", 0, max_chars)
    if cut == -1:  # one giant line: no line boundary to cut at
        return text[:max_chars], True
    return text[: cut + 1], True


@dataclass
class PreparedDiff:
    """A diff ready for the LLM, plus what was left out of it."""

    text: str
    skipped_files: list[str]
    truncated: bool


def prepare_diff(diff: str) -> PreparedDiff:
    """Drop ignored files, then truncate."""
    kept = []
    skipped = []
    for path, chunk in split_by_file(diff):
        if is_ignored(path):
            skipped.append(path)
        else:
            kept.append(chunk)

    text, truncated = truncate("".join(kept))
    return PreparedDiff(text=text, skipped_files=skipped, truncated=truncated)

