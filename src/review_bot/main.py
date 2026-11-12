import argparse

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI code review for GitLab Mrs")
    parser.add_argument("--diff-file", help="Review a local diff file instead of GitLab MRs")
    parser.add_argument("--dry-run", action="store_true", help="Print the review instead of posting it")
    
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    print(f"diff_file={args.diff_file}, dry_run={args.dry_run}")
    
if __name__ == "__main__":
    main()