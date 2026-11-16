import argparse
import sys
from pathlib import Path

import requests
from google.genai import errors as genai_errors

from review_bot.diff_utils import PreparedDiff, prepare_diff
from review_bot.gitlab_client import GitLabClient
from review_bot.llm_client import review

REVIEW_HEADING = "## 🤖 AI Code Review"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI code review for GitLab Mrs")
    parser.add_argument("--diff-file", help="Review a local diff file instead of GitLab MRs")
    parser.add_argument("--dry-run", action="store_true", help="Print the review instead of posting it")
    return parser.parse_args(argv)


def status(message: str) -> None:
    """Progress messages go to stderr so stdout contains only the review."""
    print(message, file=sys.stderr)


def load_diff(args: argparse.Namespace, client: GitLabClient | None) -> str:
    """Read the diff from --diff-file, or fetch it from the merge request."""
    if args.diff_file:
        return Path(args.diff_file).read_text(encoding="utf-8")
    status("Fetching MR diff...")
    return client.get_mr_diff()


def build_comment(review_text: str, prepared: PreparedDiff) -> str:
    """Add the heading, plus a footer saying what was not reviewed."""
    notes = []
    if prepared.skipped_files:
        files = ", ".join(f"`{path}`" for path in prepared.skipped_files)
        notes.append(f"- Not reviewed (lock, generated or binary files): {files}")
    if prepared.truncated:
        notes.append("- The diff was too large and was truncated; this review covers only part of it.")

    parts = [REVIEW_HEADING, review_text]
    if notes:
        parts.append("---\n" + "\n".join(notes))
    return "\n\n".join(parts)


def run(args: argparse.Namespace) -> int:
    """Load, prepare, review, then print or post. Returns the process exit code."""
    try:
        client = None if args.diff_file else GitLabClient.from_env()
        diff = load_diff(args, client)

        prepared = prepare_diff(diff)
        if not prepared.text.strip():
            status("Nothing to review (diff is empty or contains only ignored files).")
            return 0

        status("Requesting review from the LLM...")
        comment = build_comment(review(prepared.text), prepared)

        if args.dry_run or client is None:
            print(comment)
            return 0

        status("Posting review...")
        client.post_comment(comment)
        status("Done.")
        return 0

    except requests.HTTPError as e:
        code = e.response.status_code
        hint = " Check GITLAB_TOKEN and that it has the 'api' scope." if code in (401, 403) else ""
        status(f"Error: GitLab API returned HTTP {code}.{hint}")
    except requests.RequestException as e:
        status(f"Error: could not reach GitLab: {e}")
    except genai_errors.APIError as e:
        hint = " Rate limit or quota exceeded; try again later." if e.code == 429 else ""
        status(f"Error: LLM request failed (HTTP {e.code}): {e.message}{hint}")
    except OSError as e:
        status(f"Error: cannot read diff file: {e}")
    except RuntimeError as e:
        status(f"Error: {e}")
    return 1



def main() -> None:
    sys.exit(run(parse_args()))


if __name__ == "__main__":
    main()
