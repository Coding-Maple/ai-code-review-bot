import argparse
import sys
from pathlib import Path

from review_bot.diff_utils import prepare_diff
from review_bot.gitlab_client import GitLabClient
from review_bot.llm_client import review

REVIEW_HEADING = "## 🤖 AI Code Review"
TRUNCATED_NOTE = (
    "\n\n> **Note:** the diff was too large and was truncated, "
    "so this review covers only part of the changes."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI code review for GitLab Mrs")
    parser.add_argument("--diff-file", help="Review a local diff file instead of GitLab MRs")
    parser.add_argument("--dry-run", action="store_true", help="Print the review instead of posting it")

    return parser.parse_args()


def status(message: str) -> None:
    """Progress messages go to stderr so stdout contains only the review."""
    print(message, file=sys.stderr)


def main() -> None:
    args = parse_args()

    client = None
    if args.diff_file:
        try:
            diff = Path(args.diff_file).read_text(encoding="utf-8")
        except OSError as e:
            sys.exit(f"Cannot read diff file: {e}")
    else:
        client = GitLabClient.from_env()
        status("Fetching MR diff...")
        diff = client.get_mr_diff()

    diff, truncated = prepare_diff(diff)
    if not diff.strip():
        status("Nothing to review (diff is empty or contains only ignored files).")
        return

    status("Requesting review from the LLM...")
    review_text = review(diff)
    if truncated:
        review_text += TRUNCATED_NOTE

    if args.dry_run or client is None:
        print(review_text)
        return

    status("Posting review...")
    client.post_comment(f"{REVIEW_HEADING}\n\n{review_text}")
    status("Done.")


if __name__ == "__main__":
    main()
