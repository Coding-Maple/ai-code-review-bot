from unittest.mock import patch

from review_bot.diff_utils import PreparedDiff
from review_bot.gitlab_client import REQUIRED_ENV_VARS
from review_bot.main import REVIEW_HEADING, build_comment, parse_args, run

CODE_DIFF = "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -0,0 +1 @@\n+print('hi')\n"
LOCK_DIFF = "diff --git a/uv.lock b/uv.lock\n--- a/uv.lock\n+++ b/uv.lock\n@@ -1 +1 @@\n-old\n+new\n"


def write_diff(tmp_path, text: str) -> str:
    """Save text to a temporary .diff file and return its path."""
    path = tmp_path / "change.diff"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_diff_file_dry_run_prints_review(tmp_path, capsys):
    args = parse_args(["--diff-file", write_diff(tmp_path, CODE_DIFF), "--dry-run"])
    with patch("review_bot.main.review", return_value="Looks good.") as mock_review:
        assert run(args) == 0

    mock_review.assert_called_once_with(CODE_DIFF)
    out = capsys.readouterr().out
    assert out.startswith(REVIEW_HEADING)
    assert "Looks good." in out


def test_only_ignored_files_never_calls_llm(tmp_path, capsys):
    args = parse_args(["--diff-file", write_diff(tmp_path, LOCK_DIFF)])
    with patch("review_bot.main.review") as mock_review:
        assert run(args) == 0

    mock_review.assert_not_called()
    assert "Nothing to review" in capsys.readouterr().err


def test_gitlab_mode_posts_comment():
    with (
        patch("review_bot.main.GitLabClient") as MockClient,
        patch("review_bot.main.review", return_value="Looks good."),
    ):
        client = MockClient.from_env.return_value
        client.get_mr_diff.return_value = CODE_DIFF
        assert run(parse_args([])) == 0

    client.post_comment.assert_called_once()
    posted = client.post_comment.call_args.args[0]
    assert posted.startswith(REVIEW_HEADING)
    assert "Looks good." in posted


def test_missing_env_vars_returns_1(monkeypatch, capsys):
    for name in REQUIRED_ENV_VARS:
        monkeypatch.delenv(name, raising=False)

    assert run(parse_args([])) == 1
    assert "Missing required environment variables" in capsys.readouterr().err


def test_build_comment_without_footer():
    prepared = PreparedDiff(text=CODE_DIFF, skipped_files=[], truncated=False)
    assert build_comment("Looks good.", prepared) == f"{REVIEW_HEADING}\n\nLooks good."


def test_build_comment_with_footer():
    prepared = PreparedDiff(text=CODE_DIFF, skipped_files=["uv.lock"], truncated=True)
    comment = build_comment("Looks good.", prepared)

    assert "\n\n---\n" in comment
    assert "`uv.lock`" in comment
    assert "truncated" in comment
