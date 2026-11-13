import argparse
import sys
from pathlib import Path

from review_bot.llm_client import review

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI code review for GitLab Mrs")
    parser.add_argument("--diff-file", help="Review a local diff file instead of GitLab MRs")
    parser.add_argument("--dry-run", action="store_true", help="Print the review instead of posting it")
    
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    if not args.diff_file:
        sys.exit("Only --diff-file is supported for now (GitLab mode comes later).")

    diff = Path(args.diff_file).read_text(encoding="utf-8")
    if not diff.strip():
        print("Diff is empty, nothing to review.")
        return

    print(review(diff))
    
if __name__ == "__main__":
    main()