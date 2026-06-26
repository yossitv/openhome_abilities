import json
import time

import requests

from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


CONFIG_FILE = "youtube_live_companion_config.json"
STATE_FILE = "youtube_live_companion_state.json"
ENV_FILES = (
    "youtube_live_companion.env",
    ".env",
)

THIRD_PARTY_API_KEY_NAMES = {
    "client_id": "youtube_client_id",
    "client_secret": "youtube_client_secret",
    "refresh_token": "youtube_refresh_token",
}

FILE_CREDENTIAL_NAMES = {
    **THIRD_PARTY_API_KEY_NAMES,
    "api_key": "youtube_api_key",
}

CONFIG_CREDENTIAL_ALIASES = {
    "client_id": ("client_id", "youtube_client_id"),
    "client_secret": ("client_secret", "youtube_client_secret"),
    "refresh_token": ("refresh_token", "youtube_refresh_token"),
    "api_key": ("api_key", "youtube_api_key"),
}

REQUIRED_OAUTH_KEYS = (
    "youtube_client_id",
    "youtube_client_secret",
    "youtube_refresh_token",
)

TOKEN_URL = "https://oauth2.googleapis.com/token"
LIVE_BROADCASTS_URL = "https://www.googleapis.com/youtube/v3/liveBroadcasts"
SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"
LIVE_CHAT_MESSAGES_URL = "https://www.googleapis.com/youtube/v3/liveChat/messages"

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

SUMMARY_SYSTEM_PROMPT = """You are a Japanese live-stream cohost assistant.

Summarize recent live chat for the streamer to say aloud.
Do not read every comment. Capture the main trend, questions, mood, and useful cue.
Return only Japanese speech text. No markdown, no labels.
Keep it natural and concise: 2 or 3 short sentences.
Do not invent viewer counts, usernames, facts, sponsors, or promises.
"""

QUIET_SYSTEM_PROMPT = """You are a Japanese live-stream cohost assistant.

The live chat has been quiet. Create a warm, low-pressure topic starter that the streamer can say aloud.
Return only Japanese speech text. No markdown, no labels.
Keep it to 1 or 2 short sentences.
Do not invent viewer counts, usernames, facts, sponsors, or promises.
"""


class YoutubeLiveCompanionBackground(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    background_daemon_mode: bool = False

    _access_token = None
    _access_token_expires_at = 0
    _live_chat_id = ""
    _live_title = ""
    _next_page_token = ""
    _chat_initialized = False
    _last_message_at = 0
    _last_spoken_at = 0
    _last_quiet_prompt_at = 0
    _next_sleep_seconds = 15
    _message_buffer = None
    _seen_message_ids = None
    _announced_connection = False
    _logged_missing_config = False

    #{{register capability}}

    async def watch_live_chat(self):
        self._message_buffer = []
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
            live = self._resolve_live_chat(config)
            if not live:
                await self._write_state(
                    {
                        "status": "waiting_for_active_live",
                        "config_source": config.get("config_source"),
                        "credential_source": config.get("credential_source"),
                        "live_chat_id": "",
                        "live_title": "",
                        "last_error": None,
                        "updated_at_epoch": round(time.time()),
                    }
                )
                return

            self._live_chat_id = live["live_chat_id"]
            self._live_title = live.get("live_title") or "YouTube Live"
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

        await self._maybe_summarize(config)
        await self._maybe_prompt_when_quiet(config)

        await self._write_state(
            {
                "status": "connected",
                "config_source": config.get("config_source"),
                "credential_source": config.get("credential_source"),
                "live_chat_id": self._live_chat_id,
                "live_title": self._live_title,
                "buffered_messages": len(self._message_buffer),
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
        prompt = "Recent YouTube live chat messages:\n" + "\n".join(prompt_lines)
        response = self.capability_worker.text_to_text_response(
            prompt,
            [],
            system_prompt=SUMMARY_SYSTEM_PROMPT,
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
            f"Live title: {self._live_title}\n"
            f"No new chat messages for about {round(now - self._last_message_at)} seconds."
        )
        response = self.capability_worker.text_to_text_response(
            prompt,
            [],
            system_prompt=QUIET_SYSTEM_PROMPT,
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
        raw_config = "{}"
        config_source = "defaults"

        if await self.capability_worker.check_if_file_exists(CONFIG_FILE, False):
            raw_config = await self.capability_worker.read_file(CONFIG_FILE, False)
            config_source = "persistent"
        elif await self.capability_worker.check_if_file_exists(CONFIG_FILE, True):
            raw_config = await self.capability_worker.read_file(CONFIG_FILE, True)
            config_source = "ability"

        self._logged_missing_config = False
        config = json.loads(raw_config)
        merged = dict(DEFAULT_CONFIG)
        merged.update(config)
        self._normalize_config_credentials(merged)
        third_party_keys = self._apply_third_party_api_keys(merged)
        file_source = await self._apply_env_values(merged)
        merged["config_source"] = config_source
        merged["credential_source"] = self._credential_source(
            merged, file_source, third_party_keys
        )

        if not self._has_oauth(merged) and not merged.get("api_key"):
            await self._write_state(
                {
                    "status": "missing_config_values",
                    "config_source": config_source,
                    "credential_source": "missing",
                    "last_error": (
                        "Set youtube_client_id, youtube_client_secret, "
                        "and youtube_refresh_token in Third Party API Keys or youtube_live_companion_config.json. "
                        "Private lives require OAuth."
                    ),
                    "updated_at_epoch": round(time.time()),
                }
            )
            return None

        return merged

    def _apply_third_party_api_keys(self, config):
        applied = set()
        for config_key, api_key_name in THIRD_PARTY_API_KEY_NAMES.items():
            if config.get(config_key):
                continue
            value = self._get_api_key(api_key_name)
            if value:
                config[config_key] = value
                applied.add(config_key)

        needs_public_api_key = (
            not self._has_oauth(config)
            and config.get("channel_id")
            and not config.get("api_key")
        )
        if needs_public_api_key:
            value = self._get_api_key("youtube_api_key")
            if value:
                config["api_key"] = value
                applied.add("api_key")
        return applied

    async def _apply_env_values(self, config):
        env_values, env_source = await self._read_env_values()
        for config_key, env_name in FILE_CREDENTIAL_NAMES.items():
            if config.get(config_key):
                continue
            value = env_values.get(env_name)
            if value:
                config[config_key] = value
        return env_source

    async def _read_env_values(self):
        values = {}
        sources = []
        for env_file in ENV_FILES:
            if await self.capability_worker.check_if_file_exists(env_file, False):
                text = await self.capability_worker.read_file(env_file, False)
                parsed = self._non_empty_values(self._parse_env(text))
                if parsed:
                    values.update(parsed)
                    sources.append(f"persistent {env_file}")
            if await self.capability_worker.check_if_file_exists(env_file, True):
                text = await self.capability_worker.read_file(env_file, True)
                parsed = self._non_empty_values(self._parse_env(text))
                if parsed:
                    values.update(parsed)
                    sources.append(f"ability {env_file}")
        return values, ", ".join(sources)

    def _normalize_config_credentials(self, config):
        for output_key, aliases in CONFIG_CREDENTIAL_ALIASES.items():
            if config.get(output_key):
                continue
            for alias in aliases:
                value = config.get(alias)
                if value:
                    config[output_key] = str(value).strip()
                    break

    def _get_api_key(self, key_name):
        try:
            return self.capability_worker.get_api_keys(key_name)
        except Exception as error:
            self.worker.editor_logging_handler.info(
                f"OpenHome API key {key_name} is unavailable: {error}"
            )
            return None

    def _parse_env(self, text):
        values = {}
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                values[key] = value
        return values

    def _non_empty_values(self, values):
        return {key: value for key, value in values.items() if value}

    def _credential_source(self, config, env_source, third_party_keys):
        if all(
            config_key in third_party_keys
            for config_key in ("client_id", "client_secret", "refresh_token")
        ):
            return "Third Party API Keys"
        if env_source and self._has_oauth(config):
            return env_source
        if self._has_oauth(config):
            return CONFIG_FILE
        if config.get("api_key"):
            return "api_key"
        return "mixed"

    async def _write_state(self, state):
        if await self.capability_worker.check_if_file_exists(STATE_FILE, False):
            await self.capability_worker.delete_file(STATE_FILE, False)
        await self.capability_worker.write_file(
            STATE_FILE,
            json.dumps(state, ensure_ascii=False, indent=2),
            False,
        )

    def _resolve_live_chat(self, config):
        if config.get("live_chat_id"):
            return {
                "live_chat_id": config["live_chat_id"],
                "live_title": config.get("live_title") or "YouTube Live",
            }

        if config.get("video_id"):
            return self._resolve_live_chat_from_video(config, config["video_id"])

        if self._has_oauth(config):
            live = self._resolve_live_chat_from_owned_broadcast(config)
            if live:
                return live

        if config.get("api_key") and config.get("channel_id"):
            video_id = self._find_public_live_video_id(config)
            if video_id:
                return self._resolve_live_chat_from_video(config, video_id)

        return None

    def _resolve_live_chat_from_owned_broadcast(self, config):
        data = self._youtube_get(
            LIVE_BROADCASTS_URL,
            {
                "part": "id,snippet,status",
                "broadcastType": "all",
                "maxResults": "50",
                "mine": "true",
            },
            config,
            auth_required=True,
        )
        return self._live_chat_from_broadcasts(data.get("items", []), active_only=True)

    def _live_chat_from_broadcasts(self, items, active_only):
        fallback = None
        for item in items:
            snippet = item.get("snippet") or {}
            status = item.get("status") or {}
            if active_only and status.get("lifeCycleStatus") != "live":
                continue

            live_chat_id = snippet.get("liveChatId")
            if live_chat_id:
                live = {
                    "live_chat_id": live_chat_id,
                    "live_title": snippet.get("title") or "YouTube Live",
                }
                if status.get("lifeCycleStatus") == "live":
                    return live
                fallback = fallback or live
        return fallback

    def _find_public_live_video_id(self, config):
        data = self._youtube_get(
            SEARCH_URL,
            {
                "part": "snippet",
                "channelId": config["channel_id"],
                "eventType": "live",
                "type": "video",
                "maxResults": "1",
            },
            config,
            auth_required=False,
        )
        for item in data.get("items", []):
            video_id = (item.get("id") or {}).get("videoId")
            if video_id:
                return video_id
        return None

    def _resolve_live_chat_from_video(self, config, video_id):
        data = self._youtube_get(
            VIDEOS_URL,
            {
                "part": "snippet,liveStreamingDetails",
                "id": video_id,
            },
            config,
            auth_required=self._has_oauth(config),
        )
        for item in data.get("items", []):
            details = item.get("liveStreamingDetails") or {}
            live_chat_id = details.get("activeLiveChatId")
            if live_chat_id:
                snippet = item.get("snippet") or {}
                return {
                    "live_chat_id": live_chat_id,
                    "live_title": snippet.get("title") or "YouTube Live",
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
            LIVE_CHAT_MESSAGES_URL,
            params,
            config,
            auth_required=self._has_oauth(config),
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

    def _youtube_get(self, url, params, config, auth_required):
        request_params = dict(params)
        headers = {"Accept": "application/json"}

        if auth_required:
            headers["Authorization"] = f"Bearer {self._get_access_token(config)}"
        elif config.get("api_key"):
            request_params["key"] = config["api_key"]
        elif self._has_oauth(config):
            headers["Authorization"] = f"Bearer {self._get_access_token(config)}"
        else:
            raise ValueError("YouTube API key or OAuth config is required")

        return self._http_json(url, headers=headers, params=request_params)

    def _get_access_token(self, config):
        now = time.time()
        if self._access_token and now < self._access_token_expires_at - 60:
            return self._access_token

        try:
            payload = self._http_json(
                TOKEN_URL,
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
                "Google OAuth token refresh failed. Re-create youtube_refresh_token "
                "with the same youtube_client_id and youtube_client_secret in OAuth Playground. "
                "Also confirm the OAuth client is a Web application and the streaming Google "
                "account is added as a test user. "
                f"Original error: {error}"
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

    def _clean_response(self, response):
        if not response:
            return ""
        return response.strip().strip("`").strip()

    def call(self, worker: AgentWorker, background_daemon_mode: bool):
        self.worker = worker
        self.background_daemon_mode = background_daemon_mode
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.watch_live_chat())
