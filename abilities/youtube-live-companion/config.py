# YouTube OAuth is not currently integrated with OpenHome Linked Accounts.
# This Ability version uses manual credentials as a temporary workaround.
# Replace these placeholders only in your local OpenHome Ability editor.
# Do not commit real client secrets or refresh tokens to GitHub.

# Required for private or unlisted YouTube Live streams.
YOUTUBE_CLIENT_ID = "YOUR_YOUTUBE_CLIENT_ID"
YOUTUBE_CLIENT_SECRET = "YOUR_YOUTUBE_CLIENT_SECRET"
YOUTUBE_REFRESH_TOKEN = "YOUR_YOUTUBE_REFRESH_TOKEN"

# Output language for generated comment summaries and quiet prompts.
# Supported values: "ja", "日本語", "en", or "english".
ASSISTANT_LANGUAGE = "ja"

# Polling and assistant behavior.
POLL_INTERVAL_SECONDS = 15
SUMMARY_INTERVAL_SECONDS = 60
QUIET_AFTER_SECONDS = 120
QUIET_COOLDOWN_SECONDS = 180
MIN_MESSAGES_TO_SUMMARIZE = 3
MAX_MESSAGES_PER_SUMMARY = 12
IGNORE_EXISTING_MESSAGES_ON_START = True
SPEAK_CONNECTION_STATUS = True
SPEAK_SUMMARIES = True
SPEAK_QUIET_PROMPTS = True

# -- Do not edit below this line. --

# Values in this set are examples, not usable credentials. main.py and
# background.py treat them as empty so placeholders are never sent to YouTube.
PLACEHOLDER_VALUES = {
    "",
    "YOUR_YOUTUBE_CLIENT_ID",
    "your_youtube_client_id_here",
    "YOUR_YOUTUBE_CLIENT_SECRET",
    "your_youtube_client_secret_here",
    "YOUR_YOUTUBE_REFRESH_TOKEN",
    "your_youtube_refresh_token_here",
}


LANGUAGE_ALIASES = {
    "ja": "ja",
    "jp": "ja",
    "japanese": "ja",
    "日本語": "ja",
    "en": "en",
    "english": "en",
    "英語": "en",
}

# Prompts are editable so you can tune the assistant's tone without changing
# main.py or background.py. Add another language here if you need one later.
SUMMARY_SYSTEM_PROMPTS = {
    "ja": """You are a Japanese live-stream cohost assistant.

Speak to the streamer as an assistant, not as the streamer.
Summarize recent live chat so the streamer can quickly understand what is happening.
Use the live title and description as context, and prefer suggestions that fit the stream topic.
Do not read every comment. Capture the main trend, questions, mood, and useful cue.
Use phrases like "コメントでは", "今は", "この話題に触れるとよさそうです".
Do not say lines that pretend to be the streamer, such as "僕は", "私は", "みんな", or direct audience greetings.
Return only Japanese speech text. No markdown, no labels.
Keep it natural and concise: 2 or 3 short sentences.
Do not invent viewer counts, usernames, facts, sponsors, or promises.
""",
    "en": """You are an English live-stream cohost assistant.

Speak to the streamer as an assistant, not as the streamer.
Summarize recent live chat so the streamer can quickly understand what is happening.
Use the live title and description as context, and prefer suggestions that fit the stream topic.
Do not read every comment. Capture the main trend, questions, mood, and useful cue.
Use phrases like "In the chat", "Right now", or "It may be good to mention".
Do not say lines that pretend to be the streamer, such as "I", "we", "everyone", or direct audience greetings.
Return only English speech text. No markdown, no labels.
Keep it natural and concise: 2 or 3 short sentences.
Do not invent viewer counts, usernames, facts, sponsors, or promises.
""",
}

QUIET_SYSTEM_PROMPTS = {
    "ja": """You are a Japanese live-stream cohost assistant.

Speak to the streamer as an assistant, not as the streamer.
The live chat has been quiet. Suggest a warm, low-pressure topic the streamer could bring up.
Use the live title and description as context, and avoid generic topics that ignore the stream topic.
Use assistant-style guidance like "少し静かなので", "この話題を振ると反応しやすそうです".
Do not produce a first-person line for the streamer to say directly.
Return only Japanese speech text. No markdown, no labels.
Keep it to 1 or 2 short sentences.
Do not invent viewer counts, usernames, facts, sponsors, or promises.
""",
    "en": """You are an English live-stream cohost assistant.

Speak to the streamer as an assistant, not as the streamer.
The live chat has been quiet. Suggest a warm, low-pressure topic the streamer could bring up.
Use the live title and description as context, and avoid generic topics that ignore the stream topic.
Use assistant-style guidance like "The chat is a little quiet" or "This topic may invite responses".
Do not produce a first-person line for the streamer to say directly.
Return only English speech text. No markdown, no labels.
Keep it to 1 or 2 short sentences.
Do not invent viewer counts, usernames, facts, sponsors, or promises.
""",
}


def get_assistant_language():
    language = str(ASSISTANT_LANGUAGE or "ja").strip().lower()
    return LANGUAGE_ALIASES.get(language, "ja")


def get_summary_system_prompt():
    return SUMMARY_SYSTEM_PROMPTS[get_assistant_language()]


def get_quiet_system_prompt():
    return QUIET_SYSTEM_PROMPTS[get_assistant_language()]

# User-facing and diagnostic messages that mention setup details.
MISSING_CREDENTIALS_SPEECH_TEMPLATE = (
    "YouTube の認証情報がまだ足りません。不足しているキーは {missing_keys} です。"
    "Ability の config.py に YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, "
    "YOUTUBE_REFRESH_TOKEN を設定して、Agent を再起動してください。"
)

MISSING_CREDENTIALS_STATE_ERROR = (
    "Set YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, and YOUTUBE_REFRESH_TOKEN "
    "in config.py. YouTube Live tracking uses OAuth credentials."
)

OAUTH_REFRESH_ERROR_TEMPLATE = (
    "Google OAuth token refresh failed. Re-create YOUTUBE_REFRESH_TOKEN with "
    "the same YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in OAuth Playground. "
    "Also confirm the OAuth client is a Web application and the streaming "
    "Google account is added as a test user. Original error: {error}"
)


# Advanced YouTube API endpoints. Normally do not change these.
TOKEN_URL = "https://oauth2.googleapis.com/token"
LIVE_BROADCASTS_URL = "https://www.googleapis.com/youtube/v3/liveBroadcasts"
LIVE_CHAT_MESSAGES_URL = "https://www.googleapis.com/youtube/v3/liveChat/messages"
