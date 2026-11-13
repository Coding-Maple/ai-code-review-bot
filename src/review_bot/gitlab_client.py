"""Minimal GitLab REST API (v4) client: fetch a merge request's diff and post a comment."""

import os
from urllib.parse import quote

import requests

TIMEOUT_SECONDS = 30
PER_PAGE = 100
REQUIRED_ENV_VARS = ("CI_API_V4_URL", "CI_PROJECT_ID", "CI_MERGE_REQUEST_IID", "GITLAB_TOKEN")


class GitLabClient:
    """Talks to a single merge request through the GitLab REST API."""

    def __init__(self, api_url: str, project_id: str, mr_iid: str, token: str) -> None:
        project = quote(project_id, safe="")
        self.mr_url = f"{api_url.rstrip('/')}/projects/{project}/merge_requests/{mr_iid}"
        self.session = requests.Session()
        self.session.headers["PRIVATE-TOKEN"] = token

    @classmethod
    def from_env(cls) -> "GitLabClient":
        """Build a client from GitLab CI variables plus GITLAB_TOKEN."""
        missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
        if missing:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")
        return cls(
            api_url=os.environ["CI_API_V4_URL"],
            project_id=os.environ["CI_PROJECT_ID"],
            mr_iid=os.environ["CI_MERGE_REQUEST_IID"],
            token=os.environ["GITLAB_TOKEN"],
        )

    def get_mr_diff(self) -> str:
        """Fetch every changed file of the MR and return them as one unified diff."""
        files = []
        page = "1"
        while page:
            response = self.session.get(
                f"{self.mr_url}/diffs",
                params={"page": page, "per_page": PER_PAGE},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            for item in response.json():
                if item["diff"]:  # empty for binary or too-large files
                    files.append(_format_file_diff(item))
            page = response.headers.get("X-Next-Page", "")  # "" on the last page
        return "".join(files)

    def post_comment(self, body: str) -> None:
        """Post body (Markdown) as a comment on the MR."""
        response = self.session.post(
            f"{self.mr_url}/notes",
            json={"body": body},
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()


def _format_file_diff(item: dict) -> str:
    """Rebuild the git file header that GitLab strips from each file's diff."""
    old, new, diff = item["old_path"], item["new_path"], item["diff"]
    if not diff.endswith("\n"):
        diff += "\n"
    return f"diff --git a/{old} b/{new}\n--- a/{old}\n+++ b/{new}\n{diff}"
