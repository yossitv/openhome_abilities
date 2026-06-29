#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openhome_test_support import import_ability_modules


REPO_ROOT = Path(__file__).resolve().parents[2]
ABILITY_DIR = REPO_ROOT / "abilities" / "youtube-live-companion"


class FakeLogger:
    def __init__(self):
        self.records = []

    def info(self, message):
        self.records.append(("info", message))

    def warning(self, message):
        self.records.append(("warning", message))

    def error(self, message):
        self.records.append(("error", message))


class FakeSessionTasks:
    async def sleep(self, _seconds):
        return None

    def create(self, coroutine):
        return coroutine


class FakeWorker:
    def __init__(self):
        self.editor_logging_handler = FakeLogger()
        self.session_tasks = FakeSessionTasks()


class MemoryCapabilityWorker:
    def __init__(self):
        self.files = {}
        self.writes = []
        self.spoken = []
        self.interrupts = 0

    async def check_if_file_exists(self, filename, _in_ability_directory):
        return filename in self.files

    async def delete_file(self, filename, _in_ability_directory):
        self.files.pop(filename, None)

    async def write_file(self, filename, content, _in_ability_directory, mode="w"):
        if mode == "w":
            self.files[filename] = content
        else:
            self.files[filename] = self.files.get(filename, "") + content
        self.writes.append((filename, content, mode))

    async def read_file(self, filename, _in_ability_directory):
        return self.files[filename]

    async def speak(self, text):
        self.spoken.append(text)

    async def send_interrupt_signal(self):
        self.interrupts += 1


def patch_runtime_credentials(*modules):
    for module in modules:
        module.YOUTUBE_CLIENT_ID = "client-id"
        module.YOUTUBE_CLIENT_SECRET = "client-secret"
        module.YOUTUBE_REFRESH_TOKEN = "refresh-token"


def make_background(background_module):
    capability = background_module.YoutubeLiveCompanionBackground()
    capability.worker = FakeWorker()
    capability.capability_worker = MemoryCapabilityWorker()
    capability._message_buffer = []
    capability._recent_messages = []
    capability._seen_message_ids = []
    return capability


class RuntimeBehaviorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ability_config, self.main_module, self.background_module = (
            import_ability_modules(ABILITY_DIR)
        )
        patch_runtime_credentials(self.main_module, self.background_module)

    def test_live_chat_from_broadcasts_selects_active_live_chat(self):
        capability = make_background(self.background_module)

        live = capability._live_chat_from_broadcasts(
            [
                {
                    "snippet": {"liveChatId": "scheduled-chat", "title": "Scheduled"},
                    "status": {"lifeCycleStatus": "ready"},
                },
                {
                    "snippet": {
                        "liveChatId": "live-chat",
                        "title": "Live title",
                        "description": "Live description",
                    },
                    "status": {"lifeCycleStatus": "live"},
                },
            ]
        )

        self.assertEqual(live["live_chat_id"], "live-chat")
        self.assertEqual(live["live_title"], "Live title")

    def test_extract_new_messages_dedupes_blank_messages_and_bounds_seen_ids(self):
        capability = make_background(self.background_module)
        capability._seen_message_ids = [f"old-{index}" for index in range(499)]

        messages = capability._extract_new_messages(
            {
                "items": [
                    {
                        "id": "new-1",
                        "snippet": {"displayMessage": " hello "},
                        "authorDetails": {"displayName": "Viewer A"},
                    },
                    {
                        "id": "new-1",
                        "snippet": {"displayMessage": "duplicate"},
                        "authorDetails": {"displayName": "Viewer A"},
                    },
                    {
                        "id": "new-2",
                        "snippet": {"displayMessage": "   "},
                        "authorDetails": {"displayName": "Viewer B"},
                    },
                    {
                        "id": "new-3",
                        "snippet": {"displayMessage": "world"},
                        "authorDetails": {},
                    },
                ]
            }
        )

        self.assertEqual(
            messages,
            [
                {"author": "Viewer A", "text": "hello"},
                {"author": "viewer", "text": "world"},
            ],
        )
        self.assertLessEqual(len(capability._seen_message_ids), 500)
        self.assertIn("new-1", capability._seen_message_ids)
        self.assertIn("new-3", capability._seen_message_ids)

    async def test_placeholder_credentials_are_not_loaded(self):
        self.background_module.YOUTUBE_CLIENT_ID = "YOUR_YOUTUBE_CLIENT_ID"
        self.background_module.YOUTUBE_CLIENT_SECRET = "YOUR_YOUTUBE_CLIENT_SECRET"
        self.background_module.YOUTUBE_REFRESH_TOKEN = "YOUR_YOUTUBE_REFRESH_TOKEN"
        capability = make_background(self.background_module)

        loaded = await capability._load_config()

        self.assertIsNone(loaded)
        state = json.loads(
            capability.capability_worker.files[self.background_module.STATE_FILE]
        )
        self.assertEqual(state["status"], "missing_config_values")
        self.assertEqual(state["credential_source"], "missing")

    async def test_access_token_refresh_is_async_and_cached(self):
        capability = make_background(self.background_module)
        calls = []

        async def fake_http_json(url, **_kwargs):
            calls.append(url)
            return {"access_token": "access-token", "expires_in": 120}

        capability._http_json = fake_http_json
        config = {"client_id": "cid", "client_secret": "secret", "refresh_token": "rt"}

        first = await capability._get_access_token(config)
        second = await capability._get_access_token(config)

        self.assertEqual(first, "access-token")
        self.assertEqual(second, "access-token")
        self.assertEqual(calls, [self.background_module.GOOGLE_OAUTH_TOKEN_URL])

    async def test_oauth_refresh_failure_raises_typed_error(self):
        capability = make_background(self.background_module)

        async def fake_http_json(*_args, **_kwargs):
            raise self.background_module.YouTubeApiError(401, "unauthorized")

        capability._http_json = fake_http_json

        with self.assertRaises(self.background_module.OAuthRefreshError):
            await capability._get_access_token(
                {
                    "client_id": "cid",
                    "client_secret": "secret",
                    "refresh_token": "bad-token",
                }
            )

    async def test_tick_resets_invalid_live_chat_and_records_recoverable_state(self):
        capability = make_background(self.background_module)
        capability._live_chat_id = "stale-chat"
        capability._live_title = "Old Live"
        capability._live_description = "Old description"
        capability._next_page_token = "stale-token"
        capability._chat_initialized = True
        config = {
            **self.background_module.DEFAULT_CONFIG,
            "config_source": "config.py",
            "credential_source": "config.py",
        }

        async def fake_list_messages(_config, _live_chat_id):
            raise self.background_module.YouTubeApiError(404, "live chat ended")

        capability._list_live_chat_messages = fake_list_messages

        await capability._tick(config)

        self.assertEqual(capability._live_chat_id, "")
        self.assertEqual(capability._next_page_token, "")
        self.assertFalse(capability._chat_initialized)
        state = json.loads(
            capability.capability_worker.files[self.background_module.STATE_FILE]
        )
        self.assertEqual(state["status"], "waiting_for_active_live")
        self.assertEqual(state["error_type"], "live_chat_unavailable")

    def test_foreground_intent_matches_natural_manual_triggers(self):
        capability = self.main_module.YoutubeLiveCompanionCapability()

        self.assertEqual(capability._intent_for_text("コメント要約して"), "summary")
        self.assertEqual(capability._intent_for_text("ライブの状態教えて"), "status")
        self.assertEqual(capability._intent_for_text("配信設定を確認して"), "setup")
        self.assertEqual(capability._intent_for_text("配信設定リセットして"), "reset")
        self.assertEqual(capability._intent_for_text("今日の予定を教えて"), "setup")


if __name__ == "__main__":
    unittest.main()
