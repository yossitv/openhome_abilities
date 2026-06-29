# YouTube Live Companion Ability

YouTube Live のチャットを追跡し、最近のコメントを要約したり、コメントが静かな時に配信者へ話題の提案をする OpenHome Ability です。

非公開ライブや限定公開ライブも扱えるように、OAuth refresh token 前提で動作します。

## できること

- 自分のアクティブな YouTube Live を OAuth で探します。
- `liveChatId` を取得し、ライブチャットを定期的に取得します。
- ライブのタイトルと説明欄を取得し、要約や話題提案の文脈として使います。
- 新しいコメントが一定数たまったら、読み上げではなく流れを助手として要約します。
- 一定時間コメントがない場合、視聴者が反応しやすい話題を配信者へ提案します。
- 設定用 `main.py` と、常駐監視用 `background.py` の組み合わせで動きます。

## 話し方

この Ability は配信者本人になりきりません。OpenHome の発話は、配信者に向けた助手のコメントとして出します。

例:

```text
コメントでは次の企画についての質問が増えています。この話題に少し触れるとよさそうです。
少し静かなので、今日の配信で試していることを聞いてみると反応しやすそうです。
```

ライブタイトルや説明欄が取得できる場合は、それを文脈として使います。たとえばゲーム配信ならゲーム内の進行や次に試すこと、制作配信なら作業内容やこだわりに寄せた提案を出す想定です。

避ける話し方:

```text
みんな、次は何が見たい？
僕は今こう思っています。
```

## Ability 種別

| 項目 | 推奨値 |
| --- | --- |
| Name | `YouTube Live Companion` |
| Category | `Background Daemon` |
| Agent/System | まずは `Agent Ability` |
| Image | `dist/youtube-live-companion-icon.png` |
| Trigger Words | `youtube`, `youtube live setup`, `youtube live status`, `youtube live summary`, `コメント要約`, `配信ステータス`, `設定リセット` |
| Required API Keys | OpenHome API Keys は使わず、`config.py` の OAuth placeholder を置き換える |

## Authentication

OpenHome does not currently provide YouTube OAuth through Linked Accounts for this Ability. Because of that, this version uses a manual setup:

- Private or unlisted lives require manual YouTube OAuth credentials: `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, and `YOUTUBE_REFRESH_TOKEN`.
- Real OAuth client secrets, refresh tokens, `credentials.json`, `token.json`, `.env`, and `*.secret` files must never be committed to GitHub.
- OpenHome Third Party API Keys are not available for this Ability. Put local values in `config.py` in the OpenHome Ability editor.
- OS environment variables with the same names can override `config.py`, but `.env` and `youtube_live_companion.env` are not loaded at runtime.

This manual credential setup is a temporary workaround for this Ability version until YouTube OAuth is available through OpenHome Linked Accounts.

## 推奨 Trigger Words

OpenHome Dashboard の Trigger Words には、次を登録してください。英語の `YouTube` は STT で `U two` や `you two` に誤変換されることがあるため、その表記ゆれも入れます。

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
配信設定
配信ステータス
ライブステータス
コメント要約
コメントまとめ
チャット要約
チャットまとめ
設定リセット
```

`status` 単体は他の Ability や通常会話に取られやすいので、Trigger Word としては推奨しません。

## OAuth で必要な config.py 設定

この Ability は OAuth で自分の YouTube Live を探します。OpenHome Third Party API Keys は使わず、Ability 内の `config.py` から認証情報を読みます。

必要な `config.py` 変数:

| `config.py` variable | 取得元 | 用途 |
| --- | --- | --- |
| `YOUTUBE_CLIENT_ID` | `https://console.cloud.google.com/apis/credentials` | Google OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | `https://console.cloud.google.com/apis/credentials` | Google OAuth client secret |
| `YOUTUBE_REFRESH_TOKEN` | `https://developers.google.com/oauthplayground` | YouTube readonly scope で発行した refresh token |

必要な OAuth scope:

```text
https://www.googleapis.com/auth/youtube.readonly
```

`config.py` には安全な placeholder だけをコミットしています。OpenHome の Live Editor で自分用の Ability を編集するときだけ、次の値を実値に置き換えます。実値を GitHub にコミットしないでください。

```python
YOUTUBE_CLIENT_ID = "YOUR_YOUTUBE_CLIENT_ID"
YOUTUBE_CLIENT_SECRET = "YOUR_YOUTUBE_CLIENT_SECRET"
YOUTUBE_REFRESH_TOKEN = "YOUR_YOUTUBE_REFRESH_TOKEN"
```

OS 環境変数 `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` が設定されている場合は、`config.py` より優先されます。`.env` と `youtube_live_companion.env` は runtime で読みません。

## OAuth refresh token の用意

非公開ライブで試す場合は、YouTube アカウント画面から直接 token を取得するのではなく、Google Cloud の OAuth client を作り、その client で自分の YouTube アカウントを認可して `refresh_token` を発行します。

最終的に必要な値は次の 3 つです。

| `config.py` variable | 取得元 |
| --- | --- |
| `YOUTUBE_CLIENT_ID` | Google Cloud Console の OAuth Client ID |
| `YOUTUBE_CLIENT_SECRET` | Google Cloud Console の OAuth Client secret |
| `YOUTUBE_REFRESH_TOKEN` | OAuth 2.0 Playground で発行した Refresh token |

### 1. Google Cloud で OAuth client を作る

1. Google Cloud Console でプロジェクトを作る。
2. YouTube Data API v3 を有効化する。
3. `API とサービス` -> `OAuth 同意画面` を開く。
4. User type は個人検証なら `External` を選ぶ。
5. App name, support email, developer contact email を入力する。
6. Testing 状態の場合は、`Test users` に自分の YouTube 配信用 Google アカウントを追加する。
7. `API とサービス` -> `認証情報` を開く。
8. `認証情報を作成` -> `OAuth クライアント ID` を選ぶ。
9. Application type は `Web application` を選ぶ。
10. Authorized redirect URI に次を追加する。

```text
https://developers.google.com/oauthplayground
```

11. 作成後に表示される `クライアント ID` を `YOUTUBE_CLIENT_ID` として控える。
12. 作成後に表示される `クライアント シークレット` を `YOUTUBE_CLIENT_SECRET` として控える。

ここで作るのは `OAuth クライアント ID` です。`API キー` でも `サービス アカウント` でもありません。非公開ライブを扱うには、配信者本人の YouTube アカウントで OAuth 認可する必要があります。

### 2. OAuth Playground で refresh token を発行する

1. [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) を開く。
2. 右上の歯車アイコンを開く。
3. 次のように設定する。

| 項目 | 値 |
| --- | --- |
| Use your own OAuth credentials | ON |
| OAuth Client ID | `YOUTUBE_CLIENT_ID` |
| OAuth Client secret | `YOUTUBE_CLIENT_SECRET` |
| OAuth flow | `Server-side` |
| Access type | `Offline` |
| Force prompt | `Consent Screen` |

4. Step 1 の scope 入力欄に次を 1 行だけ入れる。

```text
https://www.googleapis.com/auth/youtube.readonly
```

一覧から選ぶ場合は、`YouTube Data API v3` を展開し、`youtube.readonly` scope を選びます。`YouTube Analytics API` や `YouTube Reporting API` ではありません。

5. `Authorize APIs` を押す。
6. 自分の YouTube 配信用 Google アカウントでログインして許可する。
7. Step 2 に戻ったら、`Exchange authorization code for tokens` を押す。
8. `Refresh token` 欄に出た値を `YOUTUBE_REFRESH_TOKEN` として控える。

`Authorization code` 欄の `4/...` で始まる値は一時コードです。OpenHome に入れる値ではありません。`Access token` も短時間で期限切れになるため、OpenHome に入れる値ではありません。

### 3. OpenHome Ability Editor の config.py に設定する

OpenHome Third Party API Keys はこの Ability では使いません。Ability zip に含まれる `config.py` には placeholder だけを置いています。自分の OpenHome Ability Editor 上で `config.py` を開き、ローカルの実値に差し替えます。

```python
YOUTUBE_CLIENT_ID = "your_google_oauth_client_id"
YOUTUBE_CLIENT_SECRET = "your_google_oauth_client_secret"
YOUTUBE_REFRESH_TOKEN = "your_google_oauth_refresh_token"
```

保存後は Agent を restart してください。再起動しないと、既存プロセスには新しい `config.py` の値が反映されないことがあります。

保存先の対応は次のとおりです。

| `config.py` variable | 入れる値 |
| --- | --- |
| `YOUTUBE_CLIENT_ID` | Google Cloud の OAuth クライアント ID |
| `YOUTUBE_CLIENT_SECRET` | Google Cloud の OAuth クライアント シークレット |
| `YOUTUBE_REFRESH_TOKEN` | OAuth Playground の `Refresh token` 欄の値 |

### 4. Agent を restart する

`config.py` を保存したら、Agent を restart してから `配信設定` または `配信ステータス` をもう一度試します。OAuth で `mine=true` の配信を自動取得するため、手動の動画 ID、チャンネル ID、live chat ID は設定しません。

### よくある詰まりどころ

`invalid_scope` で `invalid=[youtube]` と出る場合は、OAuth Playground の scope 欄に `youtube` という文字だけが入っています。scope 欄を空にして、次だけを入れ直してください。

```text
https://www.googleapis.com/auth/youtube.readonly
```

`Refresh token` が表示されない場合は、OAuth Playground の歯車で `Access type: Offline` と `Force prompt: Consent Screen` を設定してから、再度 `Authorize APIs` します。それでも出ない場合は、Google アカウント側の既存アプリ許可を取り消してから再認可します。

OAuth Playground を使う場合は、自分の OAuth client を使う設定にしてから refresh token を発行してください。OpenHome の Ability zip や GitHub repo には refresh token を入れないでください。

`YouTube API HTTP 401` と `unauthorized_client` が出る場合は、OpenHome ではなく Google OAuth 側で `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` の組み合わせが拒否されています。次を確認してください。

- OAuth Playground の歯車で `Use your own OAuth credentials` を ON にしてから認可したか。
- `YOUTUBE_CLIENT_ID` と `YOUTUBE_CLIENT_SECRET` が同じ Google Cloud の OAuth client から取得したペアか。
- `YOUTUBE_REFRESH_TOKEN` を、その同じ `YOUTUBE_CLIENT_ID` / `YOUTUBE_CLIENT_SECRET` で作り直したか。
- Google Cloud の OAuth client type が `Web application` になっているか。
- Authorized redirect URI に `https://developers.google.com/oauthplayground` が入っているか。
- OAuth consent screen が Testing の場合、配信用 Google アカウントが `Test users` に入っているか。

修正したら OAuth Playground で `Refresh access token` が成功することを確認し、その後 `config.py` の 3 値を同じ組み合わせで更新して Agent を restart してください。

## config.py の設定

`POLL_INTERVAL_SECONDS` などの調整値は、OpenHome の Live Editor で `config.py` を編集します。
コメント要約や無音時の声かけの出力言語は、同じ `config.py` の `ASSISTANT_LANGUAGE` で設定します。

```python
# Choose one: "ja" for Japanese, or "en" for English.
ASSISTANT_LANGUAGE = "ja"
```

話し方を調整したい場合は、`SUMMARY_SYSTEM_PROMPTS` と `QUIET_SYSTEM_PROMPTS` の `ja` / `en` の文面を編集します。

手順:

1. OpenHome に `dist/youtube-live-companion.zip` をアップロードする。
2. Ability の Live Editor で `config.py` を開く。
3. `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` を設定する。
4. `ASSISTANT_LANGUAGE` を `ja` または `en` に設定する。
5. 必要なら polling 設定を調整する。
6. 保存する。
7. Agent を restart する。

`配信設定` / `youtube live setup` の Trigger Word は、秘密情報を音声入力するためではなく、`config.py` が設定済みか確認するための案内用です。

同梱されている設定ファイルは次の形です。

```python
YOUTUBE_CLIENT_ID = "YOUR_YOUTUBE_CLIENT_ID"
YOUTUBE_CLIENT_SECRET = "YOUR_YOUTUBE_CLIENT_SECRET"
YOUTUBE_REFRESH_TOKEN = "YOUR_YOUTUBE_REFRESH_TOKEN"

ASSISTANT_LANGUAGE = "ja"

TOKEN_URL = "https://oauth2.googleapis.com/token"
LIVE_BROADCASTS_URL = "https://www.googleapis.com/youtube/v3/liveBroadcasts"
LIVE_CHAT_MESSAGES_URL = "https://www.googleapis.com/youtube/v3/liveChat/messages"

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

SUMMARY_SYSTEM_PROMPTS = {
    "ja": """You are a Japanese live-stream cohost assistant.
    ...
    """,
    "en": """You are an English live-stream cohost assistant.
    ...
    """,
}

QUIET_SYSTEM_PROMPTS = {
    "ja": """You are a Japanese live-stream cohost assistant.
    ...
    """,
    "en": """You are an English live-stream cohost assistant.
    ...
    """,
}
```

設定ファイル:

```text
config.py
```

この MVP は次の場所から認証情報を読みます。実値は GitHub に入れないでください。

1. `config.py` の `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`
2. 同名の OS 環境変数。設定されている場合は `config.py` より優先

OpenHome Third Party API Keys、`.env`、`youtube_live_companion.env`、JSON 設定ファイルは認証情報の読み込み元として使いません。

## ライブチャットの特定方法

この Ability は OAuth 設定で、次の順にライブチャットを探します。

1. OAuth refresh token から access token を取得する。
2. `liveBroadcasts.list` の `mine=true` を呼び、自分の配信だけを取得する。
3. `status.lifeCycleStatus == "live"` の配信を選ぶ。
4. `snippet.liveChatId` が見つかったら、`liveChatMessages.list` でコメント取得を開始する。

YouTube API は `mine` と `broadcastStatus` を同時指定できないため、取得後に `status.lifeCycleStatus == "live"` の配信だけを Ability 側で選びます。

## 状態確認

Trigger Word:

```text
配信ステータス
youtube live status
u two live status
you two live status
```

状態ファイル:

```text
youtube_live_companion_state.json
```

接続中の `live_chat_id`、ライブタイトル、最後のエラーなどを確認できます。

## コメント要約

Trigger Word:

```text
コメント要約
チャット要約
youtube live summary
u two live summary
you two live summary
```

Background Daemon が保存している直近コメントを、配信タイトル・説明欄と合わせて要約します。

自動で話してほしくない場合は、`config.py` で次を `False` にしておくと、トリガーした時だけ要約できます。

```python
SPEAK_SUMMARIES = False
SPEAK_QUIET_PROMPTS = False
```

## 設定リセット

Trigger Word:

```text
設定リセット
```

保存済みの state を削除します。`config.py` の値は手動で編集してください。

## 注意

- OAuth refresh token は秘密情報です。公開 repo や zip に入れないでください。
- Google 側の OAuth consent / test user 設定が未完了だと refresh token が使えないことがあります。
- YouTube API には quota があります。短すぎる polling は避けてください。
- この MVP はチャット追跡用です。配信者の音声内容そのものを理解するには、別途 Speech-to-Text 連携が必要です。

## アップロード用 zip

zip は単一トップレベルディレクトリ構造にしてください。

```text
youtube-live-companion/
  __init__.py
  README.md
  config.py
  main.py
  background.py
```

Ability の `Image` / `image_file` には、SVG ではなく画像ファイルを指定します。このリポジトリでは生成済みの PNG を次に置いています。

```text
dist/youtube-live-companion-icon.png
```

`icon.svg` を指定すると、OpenHome 側で `Unsupported file format image/svg+xml in image_file` になります。アップロード時は必ず PNG または JPEG を選んでください。
