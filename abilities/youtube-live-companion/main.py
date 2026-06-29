import json
import os
import time

import config as ability_config

from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


STATE_FILE = "youtube_live_companion_state.json"

# YouTube OAuth is not currently integrated with OpenHome Linked Accounts.
# This Ability version uses manual credentials in config.py as a temporary
# workaround. OS environment variables with the same names override config.py.
# Do not commit real client secrets or refresh tokens.
CREDENTIAL_NAMES = (
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN",
)

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
            ability_config.MISSING_CREDENTIALS_SPEECH_TEMPLATE.format(
                missing_keys=", ".join(missing_keys)
            )
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
            system_prompt=ability_config.get_summary_system_prompt(),
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
        for filename in (STATE_FILE,):
            if await self.capability_worker.check_if_file_exists(filename, False):
                await self.capability_worker.delete_file(filename, False)
                removed = True

        if removed:
            await self.capability_worker.speak(
                "YouTube 配信アシスタントの状態を削除しました。"
            )
        else:
            await self.capability_worker.speak(
                "削除する永続状態はありませんでした。config.py の設定は手動で編集してください。"
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
        credential_values, credential_source = self._read_manual_credentials()
        if all(credential_values.get(env_name) for env_name in CREDENTIAL_NAMES):
            return [], credential_source or "config.py"

        missing = []
        for env_name in CREDENTIAL_NAMES:
            if credential_values.get(env_name):
                continue
            missing.append(env_name)

        if missing:
            return missing, "未設定"

        return [], credential_source or "config.py"

    def _read_manual_credentials(self):
        values = {}
        sources = []
        for env_name in CREDENTIAL_NAMES:
            value = self._read_credential(env_name)
            if value:
                values[env_name] = value
                sources.append(self._credential_source_label(env_name))
        return values, ", ".join(dict.fromkeys(sources))

    def _read_credential(self, env_name):
        value = self._clean_credential_value(os.getenv(env_name))
        if value:
            return value
        return self._clean_credential_value(getattr(ability_config, env_name, ""))

    def _credential_source_label(self, env_name):
        if self._clean_credential_value(os.getenv(env_name)):
            return env_name
        return "config.py"

    def _clean_credential_value(self, value):
        value = str(value or "").strip()
        if value in ability_config.PLACEHOLDER_VALUES:
            return ""
        return value

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
