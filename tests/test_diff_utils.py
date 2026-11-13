from review_bot.diff_utils import is_ignored, prepare_diff, split_by_file, truncate

TWO_FILES = (
    "diff --git a/app.py b/app.py\n+print('hi')\n"
    "diff --git a/old.py b/new.py\n-x\n+y\n"
)


def test_split_by_file_uses_b_path():
    assert [p for p, _ in split_by_file(TWO_FILES)] == ["app.py", "new.py"]


def test_split_by_file_chunks_rejoin_to_original():
    assert "".join(c for _, c in split_by_file(TWO_FILES)) == TWO_FILES


def test_split_by_file_without_headers():
    assert split_by_file("@@ -1 +1 @@\n-a\n+b\n") == [("", "@@ -1 +1 @@\n-a\n+b\n")]
    assert split_by_file("") == []


def test_is_ignored():
    assert is_ignored("frontend/package-lock.json")
    assert is_ignored("uv.lock")
    assert is_ignored("dist/bundle.js")
    assert not is_ignored("src/review_bot/main.py")


def test_truncate_short_text_unchanged():
    assert truncate("abc\n", max_chars=10) == ("abc\n", False)


def test_truncate_cuts_at_line_boundary():
    assert truncate("line1\nline2\nline3\n", max_chars=14) == ("line1\nline2\n", True)


def test_prepare_diff_drops_ignored_files():
    diff = (
        "diff --git a/uv.lock b/uv.lock\n+lots of lock data\n"
        "diff --git a/app.py b/app.py\n+print('hi')\n"
    )
    assert prepare_diff(diff) == ("diff --git a/app.py b/app.py\n+print('hi')\n", False)
