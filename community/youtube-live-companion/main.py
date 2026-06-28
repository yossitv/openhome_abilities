import json
import time

from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


CONFIG_FILE = "youtube_live_companion_config.json"
STATE_FILE = "youtube_live_companion_state.json"
ENV_FILES = (
    "youtube_live_companion.env",
    ".env",
)

REQUIRED_API_KEYS = (
    "youtube_client_id",
    "youtube_client_secret",
    "youtube_refresh_token",
)

CREDENTIAL_ALIASES = {
    "youtube_client_id": ("youtube_client_id", "client_id"),
    "youtube_client_secret": ("youtube_client_secret", "client_secret"),
    "youtube_refresh_token": ("youtube_refresh_token", "refresh_token"),
}

SETUP_WORDS = {
    "youtube live setup",
    "youtube setup",
    "配信設定",
    "youtube設定",
    "設定",
}

STATUS_WORDS = {
    "youtube live status",
    "youtube status",
    "you tube live status",
    "you two live status",
    "u two live status",
    "配信ステータス",
    "ライブステータス",
    "状態確認",
    "status",
}

SUMMARY_WORDS = {
    "youtube live summary",
    "youtube summary",
    "you tube live summary",
    "you two live summary",
    "u two live summary",
    "comment summary",
    "chat summary",
    "コメント要約",
    "コメントまとめ",
    "チャット要約",
    "チャットまとめ",
}

RESET_WORDS = {
    "youtube live reset",
    "配信設定リセット",
    "設定リセット",
    "reset",
}

SUMMARY_SYSTEM_PROMPT = """You are a Japanese live-stream cohost assistant.

Speak to the streamer as an assistant, not as the streamer.
Summarize recent live chat so the streamer can quickly understand what is happening.
Use the live title and description as context, and prefer suggestions that fit the stream topic.
Do not read every comment. Capture the main trend, questions, mood, and useful cue.
Use phrases like "コメントでは", "今は", "この話題に触れるとよさそうです".
Do not say lines that pretend to be the streamer, such as "僕は", "私は", "みんな", or direct audience greetings.
Return only Japanese speech text. No markdown, no labels.
Keep it natural and concise: 2 or 3 short sentences.
Do not invent viewer counts, usernames, facts, sponsors, or promises.
"""


class YoutubeLiveCompanionCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None

    #{{register capability}}

    async def run(self):
        try:
            request_text = await self.capability_worker.wait_for_complete_transcription()
            request_text = self._normalize(request_text)

            if self._matches(request_text, SUMMARY_WORDS):
                await self._speak_comment_summary()
            elif self._matches(request_text, STATUS_WORDS):
                await self._speak_status()
            elif self._matches(request_text, RESET_WORDS):
                await self._reset_config()
            else:
                await self._save_config_from_user()
        except Exception as error:
            self.worker.editor_logging_handler.error(
                f"YoutubeLiveCompanionCapability failed: {error}"
            )
            await self.capability_worker.speak(
                "YouTube 配信アシスタントの設定中にエラーが発生しました。"
            )
        finally:
            self.capability_worker.resume_normal_flow()

    async def _save_config_from_user(self):
        missing_keys, credential_source = await self._missing_credentials()
        if not missing_keys:
            self.worker.editor_logging_handler.info(
                "YouTube credentials are available from "
                f"{credential_source}. The background daemon will keep tracking live chat."
            )
            return

        await self.capability_worker.speak(
            f"YouTube の認証情報がまだ足りません。不足しているキーは {', '.join(missing_keys)} です。OpenHome Dashboard の Third Party API Keys か、Live Editor の youtube_live_companion_config.json に設定してください。"
        )

    async def _speak_status(self):
        if not await self.capability_worker.check_if_file_exists(STATE_FILE, False):
            await self.capability_worker.speak(
                "まだ YouTube 配信アシスタントの状態は記録されていません。設定後、少し待ってからもう一度確認してください。"
            )
            return

        state = await self._read_state()
        if not state:
            return

        status = state.get("status") or "unknown"
        config_source = state.get("config_source") or "未取得"
        credential_source = state.get("credential_source") or "未取得"
        live_title = state.get("live_title") or "未取得"
        live_chat_id = state.get("live_chat_id") or "未取得"
        buffered_messages = state.get("buffered_messages")
        last_message_at = state.get("last_message_at_epoch")
        last_error = state.get("last_error")

        if last_error:
            await self.capability_worker.speak(
                f"現在の状態は {status} です。設定元は {config_source}、認証情報は {credential_source} です。最後のエラーは {last_error} です。"
            )
            return

        message = (
            f"現在の状態は {status} です。設定元は {config_source}、"
            f"認証情報は {credential_source} です。対象ライブは {live_title}、"
            f"ライブチャット ID は {live_chat_id} です。"
        )
        if buffered_messages is not None:
            message += f" 要約待ちの新着コメントは {buffered_messages} 件です。"
        if last_message_at:
            seconds_ago = max(0, round(time.time() - float(last_message_at)))
            message += f" 最後の新着コメントは約 {seconds_ago} 秒前です。"

        await self.capability_worker.speak(message)

    async def _speak_comment_summary(self):
        if not await self.capability_worker.check_if_file_exists(STATE_FILE, False):
            await self.capability_worker.speak(
                "まだライブチャットの状態が記録されていません。少し待ってからもう一度試してください。"
            )
            return

        state = await self._read_state()
        if not state:
            return

        last_error = state.get("last_error")
        if last_error:
            await self.capability_worker.speak(
                f"ライブチャットの取得でエラーが出ています。最後のエラーは {last_error} です。"
            )
            return

        if state.get("status") != "connected":
            await self.capability_worker.speak(
                "まだライブチャットに接続できていません。配信が開始されているか確認してください。"
            )
            return

        messages = state.get("recent_messages") or []
        if not messages:
            await self.capability_worker.speak(
                "まだ要約できる新着コメントがありません。ライブチャットに新しいコメントが来てからもう一度試してください。"
            )
            return

        prompt_lines = [
            f"- {message.get('author') or 'viewer'}: {message.get('text') or ''}"
            for message in messages
            if (message.get("text") or "").strip()
        ]
        prompt = (
            f"Live title: {state.get('live_title') or 'YouTube Live'}\n"
            f"Live description:\n{self._truncate_text(state.get('live_description') or '', 1200)}\n\n"
            "Recent YouTube live chat messages:\n"
            + "\n".join(prompt_lines)
        )
        response = self.capability_worker.text_to_text_response(
            prompt,
            [],
            system_prompt=SUMMARY_SYSTEM_PROMPT,
        )
        response = self._clean_response(response)
        if response:
            await self.capability_worker.speak(response)
            return

        await self.capability_worker.speak(
            "コメント要約を作れませんでした。少し待ってからもう一度試してください。"
        )

    async def _reset_config(self):
        removed = False
        for filename in (CONFIG_FILE, STATE_FILE):
            if await self.capability_worker.check_if_file_exists(filename, False):
                await self.capability_worker.delete_file(filename, False)
                removed = True

        if removed:
            await self.capability_worker.speak(
                "YouTube 配信アシスタントの設定と状態を削除しました。"
            )
        else:
            await self.capability_worker.speak(
                "削除する永続設定はありませんでした。Live Editor 内の設定ファイルは手動で編集してください。"
            )

    def _normalize(self, text):
        if not text:
            return ""
        return " ".join(text.strip().split())

    async def _read_state(self):
        state_text = await self.capability_worker.read_file(STATE_FILE, False)
        try:
            return json.loads(state_text)
        except (TypeError, ValueError):
            await self.capability_worker.speak(
                "状態ファイルを読み取れませんでした。Background Daemon のログを確認してください。"
            )
            return None

    async def _missing_credentials(self):
        file_values, file_source = await self._read_file_credentials()
        if all(file_values.get(key_name) for key_name in REQUIRED_API_KEYS):
            return [], file_source or "ability file"

        missing = []
        third_party_values = {}
        for key_name in REQUIRED_API_KEYS:
            third_party_value = self._get_api_key(key_name)
            if third_party_value:
                third_party_values[key_name] = third_party_value
                continue
            missing.append(key_name)

        if missing:
            return missing, "未設定"

        if all(third_party_values.get(key_name) for key_name in REQUIRED_API_KEYS):
            return [], "Third Party API Keys"

        return [], file_source or "ability file"

    async def _read_file_credentials(self):
        values = {}
        sources = []
        for config_file, is_static in (
            (CONFIG_FILE, True),
            (CONFIG_FILE, False),
        ):
            if await self.capability_worker.check_if_file_exists(config_file, is_static):
                text = await self.capability_worker.read_file(config_file, is_static)
                parsed = self._parse_json_credentials(text)
                if parsed:
                    values.update(parsed)
                    sources.append(config_file)

        for env_file in ENV_FILES:
            if await self.capability_worker.check_if_file_exists(env_file, True):
                text = await self.capability_worker.read_file(env_file, True)
                parsed = self._normalize_credentials(self._parse_env(text))
                if parsed:
                    values.update(parsed)
                    sources.append(env_file)
            if await self.capability_worker.check_if_file_exists(env_file, False):
                text = await self.capability_worker.read_file(env_file, False)
                parsed = self._normalize_credentials(self._parse_env(text))
                if parsed:
                    values.update(parsed)
                    sources.append(env_file)
        return values, ", ".join(sources)

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

    def _parse_json_credentials(self, text):
        try:
            values = json.loads(text or "{}")
        except (TypeError, ValueError):
            return {}
        if not isinstance(values, dict):
            return {}
        return self._normalize_credentials(values)

    def _normalize_credentials(self, values):
        normalized = {}
        for output_key, aliases in CREDENTIAL_ALIASES.items():
            for alias in aliases:
                value = values.get(alias)
                if value:
                    normalized[output_key] = str(value).strip()
                    break
        return {key: value for key, value in normalized.items() if value}

    def _matches(self, text, words):
        lowered = text.lower().strip(" 　。、,.!?！？")
        return lowered in {word.lower() for word in words}

    def _truncate_text(self, text, max_length):
        text = " ".join((text or "").split())
        if len(text) <= max_length:
            return text
        return text[: max_length - 1].rstrip() + "…"

    def _clean_response(self, response):
        if not response:
            return ""
        return response.strip().strip("`").strip()

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.run())
