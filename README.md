=======
# AI Code Review Bot

A GitLab CI bot that reviews every merge request with an LLM (Google Gemini) and posts the
review as a comment on the MR.

On each merge request pipeline, the bot fetches the MR's diff from the GitLab API, drops
files that are not worth reviewing (lock files, minified bundles, binaries), sends the rest
to Gemini with a structured review prompt, and posts the result back to the MR.

> **Note:** development and CI happen on GitLab. If you are viewing this on GitHub, it is a
> mirror, so pipelines do not run here.

<!-- Add a screenshot of a real review comment here, e.g.:
![Example review comment](docs/example-review.png) -->

## What a review contains

Each review is Markdown with fixed sections:

- **Summary**: what the change does, in one to three sentences
- **Bugs**, **Security**, **Readability**: concrete findings with `file:line` references
- **Suggestions**: specific improvements, with code where useful

If a section has no real findings, the model writes "Looks good." instead of inventing problems.

## How it works

```
GitLab MR pipeline
  │
  ├─ test    uv + pytest
  ├─ build   docker build → push registry.gitlab.com/...:<commit-sha>
  └─ review  run the image built for this commit:
               GitLab API ──get diff──▶ prepare_diff ──▶ Gemini ──▶ post MR comment
```

| Module | Responsibility |
|---|---|
| `main.py` | CLI entry point (`review-bot`): loads the diff, runs the review, prints or posts it, maps errors to exit codes |
| `gitlab_client.py` | GitLab REST API v4: fetches the MR diff (with pagination) and posts the comment |
| `diff_utils.py` | Splits a unified diff by file, filters ignored files, truncates very large diffs |
| `prompt.py` | System prompt and the user message that wraps the diff |
| `llm_client.py` | Calls Gemini via `google-genai`, with a timeout and retries |

## Features

- **Noise filtering.** Lock files, minified/generated files, binaries and `dist/`/`build/`
  output are skipped. The comment's footer lists what was skipped.
- **Size limit.** Diffs over 100,000 characters are cut at a line boundary, and the comment
  says the review is partial.
- **Prompt guardrails.** The diff is marked as untrusted data, which defends against prompt
  injection hidden in code comments. The model is also told not to report library or model
  names as wrong just because it doesn't recognize them.
- **CI-friendly errors.** Missing configuration, GitLab HTTP errors and LLM errors become one
  readable line on stderr and exit code 1, so the pipeline job fails visibly. "Nothing to
  review" exits with 0.
- **Safe container.** The image runs as a non-root user and contains no secrets. Keys are
  passed in only at runtime.
- **Dry-run mode.** `--dry-run` prints exactly the comment that would be posted.

## Quick start (local)

Requirements: [uv](https://docs.astral.sh/uv/) and a
[Gemini API key](https://aistudio.google.com/apikey). uv installs the right Python version
(3.14) automatically.

```bash
git clone <this-repo-url>
cd ai-code-review-bot
uv sync

cp .env.example .env        # then fill in LLM_API_KEY (and GITLAB_TOKEN for GitLab mode)

# Review a local diff
git diff HEAD~1 > sample.diff
uv run --env-file .env review-bot --diff-file sample.diff
```

### Review a real merge request from your machine

```bash
export CI_API_V4_URL=https://gitlab.com/api/v4
export CI_PROJECT_ID=<project id or namespace/project>
export CI_MERGE_REQUEST_IID=<MR number>

uv run --env-file .env review-bot --dry-run   # print only
uv run --env-file .env review-bot             # post the comment
```

## Configuration

All configuration comes from environment variables. Nothing is hard-coded.

| Variable | Required | Description |
|---|---|---|
| `LLM_API_KEY` | yes | Google Gemini API key |
| `LLM_MODEL` | no | Gemini model name (default: `gemini-3.5-flash`) |
| `GITLAB_TOKEN` | GitLab mode | Personal access token with the `api` scope (sent as `PRIVATE-TOKEN`) |
| `CI_API_V4_URL` | GitLab mode | e.g. `https://gitlab.com/api/v4`. Set automatically in GitLab CI |
| `CI_PROJECT_ID` | GitLab mode | Numeric ID or `namespace/project`. Set automatically in GitLab CI |
| `CI_MERGE_REQUEST_IID` | GitLab mode | MR number. Set automatically in MR pipelines |

## Docker

```bash
docker build -t ai-review-bot .

# Review a local diff (the file has to be mounted into the container)
docker run --rm --env-file .env -v "$(pwd)":/data:ro \
  ai-review-bot --diff-file /data/sample.diff --dry-run
```

The image is based on `python:3.14-slim` and uses a pinned uv binary. Dependencies are
installed in their own layer, so code changes rebuild in seconds. The container runs as a
non-root user, and `ENTRYPOINT ["review-bot"]` passes `docker run` arguments straight to
the bot.

## GitLab CI setup

The pipeline (`.gitlab-ci.yml`) has three stages:

| Stage | Job | Runs on | What it does |
|---|---|---|---|
| test | `test` | every pipeline | `uv sync --frozen` + `pytest`, with uv's download cache keyed on `uv.lock` |
| build | `build` | every pipeline | Builds the image with Docker-in-Docker and pushes it tagged with the commit SHA (and `:latest` on the default branch) |
| review | `review` | merge request pipelines | Runs `review-bot` from the image built for this exact commit |

`workflow:rules` creates merge request pipelines, plus branch pipelines only for branches
without an open MR, so the same commit never gets two pipelines.

To use it in your project:

1. **Settings → CI/CD → Variables:** add `LLM_API_KEY` and `GITLAB_TOKEN`, both **masked**
   and **not protected** (protected variables are not available on feature branches).
2. **Settings → General → Visibility, project features, permissions:** turn on the
   **Container registry**.
3. Open a merge request. The review appears as a comment once the pipeline finishes.

## Tests

```bash
uv run pytest -v
```

The tests use `unittest.mock` for every external call: they cover diff parsing and
filtering, the GitLab client (headers, pagination, URL encoding), and the CLI flow
(dry-run, posting, skipping the LLM when only ignored files changed, exit codes). They
make no network calls and need no API keys.

## Design decisions

- **The review job uses the commit-SHA image tag, not `:latest`.** The bot reviewing an MR
  is the code from that MR, and parallel pipelines can't overwrite each other's image.
- **Rebuilt `diff --git` headers.** GitLab's diff API returns each file's hunks without the
  git file header. The client rebuilds it, so API diffs and local `git diff` output go
  through the same code.
- **Errors are handled in one place.** Lower layers raise exceptions, and `run()` turns
  expected failures into messages and exit codes. Unexpected errors still show a full
  traceback.
- **Secrets only at runtime.** `.env` is excluded by both `.gitignore` and `.dockerignore`,
  and CI provides keys as masked variables.

## Limitations and ideas

- LLM output varies between runs, and `file:line` references can be slightly off. The
  review is advisory, not a quality gate.
- Every MR pipeline posts a new comment. Updating a single bot comment would be cleaner.
- Use separate exit codes for "LLM unavailable" and "misconfigured", so that
  `allow_failure: exit_codes` can tolerate provider outages while still failing on
  configuration errors.
- Add line numbers to the diff before sending it, to make references more accurate.

## Tech stack

Python 3.14 · uv · google-genai (Gemini) · requests · pytest · Docker · GitLab CI
>>>>>>> 1b7de89 (Add README with setup, architecture and design decisions)
