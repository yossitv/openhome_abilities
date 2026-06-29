import json
import os
import time

import requests
import config as ability_config

from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


STATE_FILE = "youtube_live_companion_state.json"

# YouTube OAuth is not currently integrated with OpenHome Linked Accounts.
# This Ability version uses manual credentials in config.py as a temporary
# workaround. OS environment variables with the same names override config.py.
# Do not commit real client secrets or refresh tokens.
CREDENTIAL_NAMES = {
    "client_id": "YOUTUBE_CLIENT_ID",
    "client_secret": "YOUTUBE_CLIENT_SECRET",
    "refresh_token": "YOUTUBE_REFRESH_TOKEN",
}

DEFAULT_CONFIG = {
    "poll_interval_seconds": 15,
    "summary_interval_seconds": 60,
    "quiet_after_seconds": 120,
    "quiet_cooldown_seconds": 180,
    "min_messages_to_summarize": 3,
    "max_messages_per_summary": 12,
    "ignore_existing_messages_on_start": True,
    "speak_connection_status": True,
    "speak_summaries": True,
    "speak_quiet_prompts": True,
}

CONFIG_SETTING_NAMES = {
    "poll_interval_seconds": "POLL_INTERVAL_SECONDS",
    "summary_interval_seconds": "SUMMARY_INTERVAL_SECONDS",
    "quiet_after_seconds": "QUIET_AFTER_SECONDS",
    "quiet_cooldown_seconds": "QUIET_COOLDOWN_SECONDS",
    "min_messages_to_summarize": "MIN_MESSAGES_TO_SUMMARIZE",
    "max_messages_per_summary": "MAX_MESSAGES_PER_SUMMARY",
    "ignore_existing_messages_on_start": "IGNORE_EXISTING_MESSAGES_ON_START",
    "speak_connection_status": "SPEAK_CONNECTION_STATUS",
    "speak_summaries": "SPEAK_SUMMARIES",
    "speak_quiet_prompts": "SPEAK_QUIET_PROMPTS",
}


class YoutubeLiveCompanionBackground(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    background_daemon_mode: bool = False

    _access_token = None
    _access_token_expires_at = 0
    _live_chat_id = ""
    _live_title = ""
    _live_description = ""
    _next_page_token = ""
    _chat_initialized = False
    _last_message_at = 0
    _last_spoken_at = 0
    _last_quiet_prompt_at = 0
    _next_sleep_seconds = 15
    _message_buffer = None
    _recent_messages = None
    _seen_message_ids = None
    _announced_connection = False
    _logged_missing_config = False

    #{{register capability}}

    async def watch_live_chat(self):
        self._message_buffer = []
        self._recent_messages = []
        self._seen_message_ids = []
        self.worker.editor_logging_handler.info("YouTube live companion watcher started")

        while True:
            try:
                config = await self._load_config()
                if not config:
                    await self.worker.session_tasks.sleep(30.0)
                    continue

                await self._tick(config)
                await self.worker.session_tasks.sleep(float(self._next_sleep_seconds))
            except Exception as error:
                self.worker.editor_logging_handler.error(
                    f"YouTube live companion watcher failed: {error}"
                )
                await self._write_state(
                    {
                        "status": "error",
                        "last_error": str(error),
                        "updated_at_epoch": round(time.time()),
                    }
                )
                await self.worker.session_tasks.sleep(30.0)

    async def _tick(self, config):
        self._next_sleep_seconds = float(config["poll_interval_seconds"])

        if not self._live_chat_id:
            live = self._resolve_live_chat_from_owned_broadcast(config)
            if not live:
                await self._write_state(
                    {
                        "status": "waiting_for_active_live",
                        "config_source": config.get("config_source"),
                        "credential_source": config.get("credential_source"),
                        "live_chat_id": "",
                        "live_title": "",
                        "live_description": "",
                        "recent_messages": [],
                        "recent_messages_count": 0,
                        "last_error": None,
                        "updated_at_epoch": round(time.time()),
                    }
                )
                return

            self._live_chat_id = live["live_chat_id"]
            self._live_title = live.get("live_title") or "YouTube Live"
            self._live_description = live.get("live_description") or ""
            self._recent_messages = []
            self._chat_initialized = False
            self._next_page_token = ""
            self._last_message_at = time.time()

            await self._write_state(
                {
                    "status": "connected",
                    "config_source": config.get("config_source"),
                    "credential_source": config.get("credential_source"),
                    "live_chat_id": self._live_chat_id,
                    "live_title": self._live_title,
                    "live_description": self._truncate_text(self._live_description, 500),
                    "recent_messages": [],
                    "recent_messages_count": 0,
                    "last_error": None,
                    "updated_at_epoch": round(time.time()),
                }
            )

            if config["speak_connection_status"] and not self._announced_connection:
                await self._speak(
                    f"YouTube ライブチャットに接続しました。対象は {self._live_title} です。"
                )
                self._announced_connection = True

        messages_response = self._list_live_chat_messages(config, self._live_chat_id)
        self._next_page_token = messages_response.get("nextPageToken") or self._next_page_token

        polling_interval = messages_response.get("pollingIntervalMillis")
        if polling_interval:
            self._next_sleep_seconds = max(
                float(config["poll_interval_seconds"]),
                float(polling_interval) / 1000.0,
            )

        new_messages = self._extract_new_messages(messages_response)
        if not self._chat_initialized:
            self._chat_initialized = True
            if config["ignore_existing_messages_on_start"]:
                return

        if new_messages:
            self._last_message_at = time.time()
            self._message_buffer.extend(new_messages)
            self._recent_messages.extend(new_messages)
            self._recent_messages = self._recent_messages[-20:]

        await self._maybe_summarize(config)
        await self._maybe_prompt_when_quiet(config)

        await self._write_state(
            {
                "status": "connected",
                "config_source": config.get("config_source"),
                "credential_source": config.get("credential_source"),
                "live_chat_id": self._live_chat_id,
                "live_title": self._live_title,
                "live_description": self._truncate_text(self._live_description, 500),
                "buffered_messages": len(self._message_buffer),
                "recent_messages": self._messages_for_state(config),
                "recent_messages_count": len(self._recent_messages),
                "last_message_at_epoch": round(self._last_message_at),
                "next_sleep_seconds": self._next_sleep_seconds,
                "last_error": None,
                "updated_at_epoch": round(time.time()),
            }
        )

    async def _maybe_summarize(self, config):
        now = time.time()
        if not config["speak_summaries"]:
            return
        if len(self._message_buffer) < int(config["min_messages_to_summarize"]):
            return
        if now - self._last_spoken_at < float(config["summary_interval_seconds"]):
            return

        messages = self._message_buffer[-int(config["max_messages_per_summary"]) :]
        prompt_lines = [
            f"- {message['author']}: {message['text']}" for message in messages
        ]
        prompt = (
            self._live_context_prompt()
            + "\n\nRecent YouTube live chat messages:\n"
            + "\n".join(prompt_lines)
        )
        response = self.capability_worker.text_to_text_response(
            prompt,
            [],
            system_prompt=ability_config.get_summary_system_prompt(),
        )
        response = self._clean_response(response)
        if response:
            await self._speak(response)
            self._last_spoken_at = now
            self._message_buffer = []

    async def _maybe_prompt_when_quiet(self, config):
        now = time.time()
        if not config["speak_quiet_prompts"]:
            return
        if self._message_buffer:
            return
        if now - self._last_message_at < float(config["quiet_after_seconds"]):
            return
        if now - self._last_quiet_prompt_at < float(config["quiet_cooldown_seconds"]):
            return

        prompt = (
            self._live_context_prompt()
            + "\n"
            f"No new chat messages for about {round(now - self._last_message_at)} seconds."
        )
        response = self.capability_worker.text_to_text_response(
            prompt,
            [],
            system_prompt=ability_config.get_quiet_system_prompt(),
        )
        response = self._clean_response(response)
        if response:
            await self._speak(response)
            self._last_spoken_at = now
            self._last_quiet_prompt_at = now

    async def _speak(self, text):
        await self.capability_worker.send_interrupt_signal()
        await self.capability_worker.speak(text)

    async def _load_config(self):
        self._logged_missing_config = False
        merged = dict(DEFAULT_CONFIG)
        merged.update(self._read_config_py_settings())
        credential_source = self._apply_manual_credentials(merged)
        merged["config_source"] = "config.py"
        merged["credential_source"] = self._credential_source(merged, credential_source)

        if not self._has_oauth(merged):
            await self._write_state(
                {
                    "status": "missing_config_values",
                    "config_source": "config.py",
                    "credential_source": "missing",
                    "last_error": ability_config.MISSING_CREDENTIALS_STATE_ERROR,
                    "updated_at_epoch": round(time.time()),
                }
            )
            return None

        return merged

    def _read_config_py_settings(self):
        values = {}
        for config_key, variable_name in CONFIG_SETTING_NAMES.items():
            value = getattr(ability_config, variable_name, None)
            if value is not None:
                values[config_key] = value
        return values

    def _apply_manual_credentials(self, config):
        applied = []
        for config_key, env_name in CREDENTIAL_NAMES.items():
            if config.get(config_key):
                continue
            value, source = self._read_credential(env_name)
            if value:
                config[config_key] = value
                applied.append(source)
        return ", ".join(dict.fromkeys(applied))

    def _read_credential(self, env_name):
        value = self._clean_credential_value(os.getenv(env_name))
        if value:
            return value, env_name
        value = self._clean_credential_value(getattr(ability_config, env_name, ""))
        if value:
            return value, "config.py"
        return "", ""

    def _credential_source(self, config, credential_source):
        if credential_source and self._has_oauth(config):
            return credential_source
        return "config.py"

    def _clean_credential_value(self, value):
        value = str(value or "").strip()
        if value in ability_config.PLACEHOLDER_VALUES:
            return ""
        return value

    async def _write_state(self, state):
        if await self.capability_worker.check_if_file_exists(STATE_FILE, False):
            await self.capability_worker.delete_file(STATE_FILE, False)
        await self.capability_worker.write_file(
            STATE_FILE,
            json.dumps(state, ensure_ascii=False, indent=2),
            False,
        )

    def _resolve_live_chat_from_owned_broadcast(self, config):
        data = self._youtube_get(
            ability_config.LIVE_BROADCASTS_URL,
            {
                "part": "id,snippet,status",
                "broadcastType": "all",
                "maxResults": "50",
                "mine": "true",
            },
            config,
        )
        return self._live_chat_from_broadcasts(data.get("items", []))

    def _live_chat_from_broadcasts(self, items):
        for item in items:
            snippet = item.get("snippet") or {}
            status = item.get("status") or {}
            if status.get("lifeCycleStatus") != "live":
                continue

            live_chat_id = snippet.get("liveChatId")
            if live_chat_id:
                return {
                    "live_chat_id": live_chat_id,
                    "live_title": snippet.get("title") or "YouTube Live",
                    "live_description": snippet.get("description") or "",
                }
        return None

    def _list_live_chat_messages(self, config, live_chat_id):
        params = {
            "liveChatId": live_chat_id,
            "part": "snippet,authorDetails",
            "maxResults": "200",
        }
        if self._next_page_token:
            params["pageToken"] = self._next_page_token

        return self._youtube_get(
            ability_config.LIVE_CHAT_MESSAGES_URL,
            params,
            config,
        )

    def _extract_new_messages(self, messages_response):
        new_messages = []
        for item in messages_response.get("items", []):
            message_id = item.get("id")
            if message_id and message_id in self._seen_message_ids:
                continue

            if message_id:
                self._seen_message_ids.append(message_id)
                self._seen_message_ids = self._seen_message_ids[-500:]

            snippet = item.get("snippet") or {}
            author_details = item.get("authorDetails") or {}
            text = snippet.get("displayMessage") or ""
            if not text.strip():
                continue

            new_messages.append(
                {
                    "author": author_details.get("displayName") or "viewer",
                    "text": text.strip(),
                }
            )

        return new_messages

    def _youtube_get(self, url, params, config):
        request_params = dict(params)
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._get_access_token(config)}",
        }

        return self._http_json(url, headers=headers, params=request_params)

    def _get_access_token(self, config):
        now = time.time()
        if self._access_token and now < self._access_token_expires_at - 60:
            return self._access_token

        try:
            payload = self._http_json(
                ability_config.TOKEN_URL,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                method="POST",
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "refresh_token": config["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
        except RuntimeError as error:
            raise RuntimeError(
                ability_config.OAUTH_REFRESH_ERROR_TEMPLATE.format(error=error)
            )
        self._access_token = payload["access_token"]
        self._access_token_expires_at = now + int(payload.get("expires_in", 3600))
        return self._access_token

    def _http_json(self, url, headers=None, method="GET", data=None, params=None):
        response = requests.request(
            method,
            url,
            headers=headers or {"Accept": "application/json"},
            data=data,
            params=params,
            timeout=12,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"YouTube API HTTP {response.status_code}: {response.text}")
        try:
            return response.json()
        except ValueError as error:
            raise RuntimeError(f"YouTube API returned invalid JSON: {error}")

    def _has_oauth(self, config):
        return bool(
            config.get("client_id")
            and config.get("client_secret")
            and config.get("refresh_token")
        )

    def _live_context_prompt(self):
        description = self._truncate_text(self._live_description, 1200)
        if not description:
            description = "No live description is available."
        return f"Live title: {self._live_title}\nLive description:\n{description}"

    def _truncate_text(self, text, max_length):
        text = " ".join((text or "").split())
        if len(text) <= max_length:
            return text
        return text[: max_length - 1].rstrip() + "…"

    def _messages_for_state(self, config):
        limit = int(config.get("max_messages_per_summary", 12))
        messages = self._recent_messages[-limit:]
        return [
            {
                "author": self._truncate_text(message.get("author") or "viewer", 80),
                "text": self._truncate_text(message.get("text") or "", 300),
            }
            for message in messages
            if (message.get("text") or "").strip()
        ]

    def _clean_response(self, response):
        if not response:
            return ""
        return response.strip().strip("`").strip()

    def call(self, worker: AgentWorker, background_daemon_mode: bool):
        self.worker = worker
        self.background_daemon_mode = background_daemon_mode
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.watch_live_chat())
