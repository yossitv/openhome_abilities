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

## Runtime Tuning Surface

The Ability intentionally keeps its runtime tuning surface small and explicit. Reviewers and OpenHome operators can adjust language, polling cadence, speaking behavior, summary thresholds, and assistant tone by editing these top-level keys in the runtime files without changing the control flow:

```text
ASSISTANT_LANGUAGE
POLL_INTERVAL_SECONDS
SUMMARY_INTERVAL_SECONDS
QUIET_AFTER_SECONDS
QUIET_COOLDOWN_SECONDS
MIN_MESSAGES_TO_SUMMARIZE
MAX_MESSAGES_PER_SUMMARY
IGNORE_EXISTING_MESSAGES_ON_START
SPEAK_CONNECTION_STATUS
SPEAK_SUMMARIES
SPEAK_QUIET_PROMPTS
SUMMARY_SYSTEM_PROMPTS
QUIET_SYSTEM_PROMPTS
```

`SUMMARY_SYSTEM_PROMPTS` and `QUIET_SYSTEM_PROMPTS` are the main tone controls. They are editable so the OpenHome team can tune how assistant-like, concise, or topic-aware the cohost guidance should be without rewriting the polling or trigger logic.

## Product Context

The original product idea is a `Live Stream Companion` for creators who are busy playing, building, presenting, or otherwise focused on the stream and may miss live chat. This is especially useful for smaller or early-stage streamers: when chat is quiet, the stream can easily become silent, which makes it harder for new viewers to engage and creates a negative loop.

The Ability is meant to make OpenHome act like a cohost assistant, not a replacement host. It supports the creator by:

- summarizing recent audience reactions instead of reading every comment aloud;
- suggesting context-aware talking points when chat has been quiet;
- giving the streamer a quick status check for whether the daemon has found an active live stream and live chat;
- reducing the chance that the streamer loses track of stream state while focused on the content.

The current implementation is intentionally scoped to assistant/cohost support. It does not moderate YouTube chat actions such as deleting comments or banning users, and it does not end a livestream automatically. The status command only surfaces the saved daemon state so the streamer can notice whether the Ability is connected, waiting for an active live, or blocked by an OAuth/API error.

## Trigger Words and Behavior to Review

Recommended Dashboard trigger words:

```text
youtube
youtube live setup
youtube live status
youtube status
youtube live summary
youtube summary
u two live status
you two live status
u two live summary
you two live summary
youtube live reset
youtube reset
reset
配信設定
配信ステータス
ライブステータス
コメント要約
コメントまとめ
チャット要約
チャットまとめ
設定リセット
```

`YouTube` can be mis-transcribed by STT as `u two` or `you two`, so those variants are included for the status and summary paths. `status` by itself is intentionally not recommended as a Dashboard trigger because it is too generic and may collide with normal conversation or other Abilities.

| Trigger family           | Example phrases                                                                                           | Runtime behavior                                                                                                                                                            |
| ------------------------ | --------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Setup / credential check | `youtube`, `youtube live setup`, `配信設定`                                                         | Checks whether `main.py` has the three placeholder OAuth values replaced. If values are present, it logs that credentials are available and does not speak by default.     |
| Status                   | `youtube live status`, `youtube status`, `u two live status`, `配信ステータス`                    | Reads `youtube_live_companion_state.json` and speaks the current daemon state, credential source, target live title, live chat ID, last error, and buffered comment count. |
| Summary                  | `youtube live summary`, `youtube summary`, `u two live summary`, `コメント要約`, `チャット要約` | Uses recent comments saved by `background.py` plus the live title/description to produce a short assistant-style summary.                                                  |
| Reset                    | `youtube live reset`, `youtube reset`, `reset`, `設定リセット`                                    | Deletes only the saved state file. It does not change OAuth placeholders or runtime credentials.                                                                            |
| Background daemon        | No speech trigger; starts as a Background Daemon                                                          | Watches for the user's active YouTube Live through OAuth, tracks live chat when available, writes state, and may speak short summaries or quiet-chat prompts.               |

Expected states to test include:

- `missing_config_values`: placeholders have not been replaced in the runtime copy.
- `waiting_for_active_live`: OAuth values are present, but no owned active live broadcast is available.
- `connected`: an active live broadcast and live chat ID were found.
- `authentication_error` / `api_error`: OAuth refresh or YouTube API calls failed.

## Pre-Submission Verification

- [X] `main.py` and `background.py` entrypoint classes extend `MatchingCapability`.
- [X] Entrypoints include OpenHome register capability boilerplate (`#{{register capability}}`, accepted by the checker).
- [X] `main.py` calls `resume_normal_flow()` from a `finally` block.
- [X] Runtime files have no `print()` calls and use `editor_logging_handler` for logs.
- [X] No hardcoded API keys, OAuth client secrets, refresh tokens, or private keys were detected.
- [X] All detected `requests.*()` calls include a `timeout` parameter.
- [X] Root Ability `README.md` includes a description and suggested trigger words, with full English/Japanese docs split into `README.en.md` and `README.ja.md`.
- [X] Upload zip layout contains a single top-level `youtube-live-companion/` directory.
- [X] Local `.env` credential testing stays outside the Ability zip and is documented as a repo-level test harness.
- [X] Runtime behavior tests pass locally, including trigger intent routing, placeholder credential rejection, OAuth refresh error handling, live-chat reset behavior, and message extraction.
- [X] OpenHome Ability Editor run has been confirmed during live testing.

Submission setting: this PR should target the `dev` branch with files under `community/youtube-live-companion/`.

This PR does not claim the final OAuth UX is complete. It provides the working ability structure, voice flow, background polling behavior, and a clear integration boundary for the OpenHome team to finish OAuth cleanly.
