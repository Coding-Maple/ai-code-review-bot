from unittest.mock import MagicMock, patch

import pytest

from review_bot.gitlab_client import GitLabClient

API = "https://gitlab.example.com/api/v4"
MR_URL = f"{API}/projects/42/merge_requests/7"


def make_client(project_id: str = "42") -> GitLabClient:
    return GitLabClient(api_url=API, project_id=project_id, mr_iid="7", token="secret")


def fake_response(items: list[dict], next_page: str = "") -> MagicMock:
    """A stand-in for requests.Response: .json() returns items, headers carry pagination."""
    response = MagicMock()
    response.json.return_value = items
    response.headers = {"X-Next-Page": next_page}
    return response


def item(old: str, new: str, diff: str) -> dict:
    return {"old_path": old, "new_path": new, "diff": diff}


def test_get_mr_diff_rebuilds_git_headers():
    client = make_client()
    api_items = [item("old.py", "new.py", "@@ -1 +1 @@\n-a\n+b\n")]
    with patch.object(client.session, "get", return_value=fake_response(api_items)):
        diff = client.get_mr_diff()

    assert diff == (
        "diff --git a/old.py b/new.py\n"
        "--- a/old.py\n"
        "+++ b/new.py\n"
        "@@ -1 +1 @@\n-a\n+b\n"
    )


def test_get_mr_diff_follows_pagination():
    client = make_client()
    pages = [
        fake_response([item("a.py", "a.py", "+1\n")], next_page="2"),
        fake_response([item("b.py", "b.py", "+2\n")], next_page=""),
    ]
    with patch.object(client.session, "get", side_effect=pages) as get:
        diff = client.get_mr_diff()

    assert get.call_count == 2
    assert get.call_args_list[0].kwargs["params"] == {"page": "1", "per_page": 100}
    assert get.call_args_list[1].kwargs["params"] == {"page": "2", "per_page": 100}
    assert "b/a.py" in diff and "b/b.py" in diff


def test_get_mr_diff_skips_empty_diffs():
    client = make_client()
    api_items = [item("logo.png", "logo.png", ""), item("app.py", "app.py", "+x\n")]
    with patch.object(client.session, "get", return_value=fake_response(api_items)):
        diff = client.get_mr_diff()

    assert "logo.png" not in diff
    assert "diff --git a/app.py b/app.py" in diff


def test_post_comment_sends_note():
    client = make_client()
    with patch.object(client.session, "post") as post:
        client.post_comment("Looks good.")

    post.assert_called_once_with(f"{MR_URL}/notes", json={"body": "Looks good."}, timeout=30)
    post.return_value.raise_for_status.assert_called_once()
    assert client.session.headers["PRIVATE-TOKEN"] == "secret"


def test_from_env_names_missing_variables(monkeypatch):
    monkeypatch.setenv("CI_API_V4_URL", API)
    monkeypatch.setenv("CI_PROJECT_ID", "42")
    monkeypatch.delenv("CI_MERGE_REQUEST_IID", raising=False)
    monkeypatch.delenv("GITLAB_TOKEN", raising=False)

    with pytest.raises(RuntimeError, match="CI_MERGE_REQUEST_IID, GITLAB_TOKEN"):
        GitLabClient.from_env()


def test_project_path_is_url_encoded():
    client = make_client(project_id="user/repo")
    assert client.mr_url == f"{API}/projects/user%2Frepo/merge_requests/7"
