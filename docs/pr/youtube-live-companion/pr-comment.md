# PR Comment: YouTube Live Companion

This ability is intended as a community draft for `community/youtube-live-companion/`.

The current implementation does not import `config.py` at runtime. The OAuth placeholders, assistant prompts, polling controls, and speech templates are duplicated directly in `main.py` and `background.py` because the OpenHome upload/runtime loader currently treats each entrypoint as an isolated capability module. This avoids `No module named 'config'` failures when loading the background daemon.

`config.py` is intentionally left in the ability folder as a comparison/reference file only. It shows the previous centralized setup shape so reviewers can compare the inline `main.py` / `background.py` values against the older shared-config version while deciding how OpenHome-managed OAuth should replace the manual placeholder layer.

OAuth is intentionally draft-level in this PR. The ability currently uses manual placeholders for:

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

The expected production direction is to replace that manual layer with OpenHome-managed OAuth / Linked Accounts once the OpenHome team wires up the final integration. Until then, `main.py`, `background.py`, and the reference-only `config.py` should contain placeholders only. Real client secrets or refresh tokens must not be committed.

Local credential tests are intentionally kept outside the Ability folder so they are not packaged into the upload zip. The local test harness may read a private `.env` file and patch the imported `main.py` / `background.py` modules during local smoke checks. The development-only test files live in this repo at [`tests/youtube-live-companion/`](https://github.com/yossitv/openhome_abilities/tree/main/tests/youtube-live-companion). OpenHome Cloud / Ability Editor does not read `.env`, and `.env` must never be committed or included in the Ability zip.

The background daemon is responsible for finding the active owned YouTube Live broadcast, polling live chat, storing recent chat state, and optionally speaking short assistant-style summaries or quiet-chat prompts. The interactive `main.py` reads that saved state for setup, status, summary, and reset commands.

Before merge, I expect the remaining review focus to be:

- Confirm the folder is submitted as `community/youtube-live-companion/`.
- Confirm the OpenHome Ability Editor can run the placeholder / missing-credentials path.
- Confirm the local runtime-credential injection smoke test passes from the repo-level `tests/youtube-live-companion/` harness.
- Confirm the daemon behaves safely when no active live broadcast exists.
- Confirm a real OAuth-enabled test can connect to a private or unlisted live chat.
- Replace manual inline OAuth placeholders with the OpenHome-managed OAuth path if the team prefers to complete that integration before accepting the ability.

## Pre-Submission Checklist

- [x] Extends `MatchingCapability`
- [x] Includes `#{{register_capability}}` boilerplate
- [x] Calls `resume_normal_flow()` on every `main.py` exit path
- [x] Has no `print()` statements; uses `editor_logging_handler`
- [x] Has no hardcoded API keys, OAuth client secrets, or refresh tokens
- [x] All `requests.*()` calls include a `timeout` parameter
- [x] Includes a `README.md` with description and suggested trigger words
- [x] Keeps local `.env` testing outside the Ability zip and documents the repo-level test harness
- [ ] PR targets the `dev` branch
- [ ] Code has run in the OpenHome Ability Editor

This PR does not claim the final OAuth UX is complete. It provides the working ability structure, voice flow, background polling behavior, and a clear integration boundary for the OpenHome team to finish OAuth cleanly.
