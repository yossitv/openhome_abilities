# YouTube Live Companion Ability

YouTube Live のチャットを追跡し、最近のコメントを要約したり、コメントが静かな時に配信者が話せる問いかけを作る OpenHome Ability です。

非公開ライブを試すため、API key だけではなく OAuth refresh token に対応しています。

## できること

- 自分のアクティブな YouTube Live を OAuth で探します。
- `liveChatId` を取得し、ライブチャットを定期的に取得します。
- 新しいコメントが一定数たまったら、読み上げではなく流れを要約して話します。
- 一定時間コメントがない場合、視聴者が反応しやすい話題を出します。
- 設定用 `main.py` と、常駐監視用 `background.py` の組み合わせで動きます。

## Ability 種別

| 項目 | 推奨値 |
| --- | --- |
| Name | `YouTube Live Companion` |
| Category | `Background Daemon` |
| Agent/System | まずは `Agent Ability` |
| Image | `dist/youtube-live-companion-icon.png` |
| Trigger Words | `youtube`, `youtube live setup`, `youtube live status`, `u two live status`, `you two live status`, `配信ステータス`, `設定リセット` |
| Required API Keys | `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token` |

## 推奨 Trigger Words

OpenHome Dashboard の Trigger Words には、次を登録してください。英語の `YouTube` は STT で `U two` や `you two` に誤変換されることがあるため、その表記ゆれも入れます。

```text
youtube
youtube live setup
youtube live status
youtube status
u two live status
you two live status
配信設定
配信ステータス
ライブステータス
設定リセット
```

`status` 単体は他の Ability や通常会話に取られやすいので、Trigger Word としては推奨しません。

## 非公開ライブで必要な Third Party API Keys

非公開ライブや自分の配信を確実に追うには OAuth が必要です。OpenHome では、秘密情報を Ability ファイルに書かず、**Third Party API Keys** に保存します。

Ability 作成 / 編集画面の **Ability Behavior → API Keys** で次の key を宣言し、required として tag してください。値は Ability 作成画面ではなく、**Settings → API Keys → Third-party Keys** に保存します。

| Key name | Provider URL | 用途 |
| --- | --- | --- |
| `youtube_client_id` | `https://console.cloud.google.com/apis/credentials` | Google OAuth client ID |
| `youtube_client_secret` | `https://console.cloud.google.com/apis/credentials` | Google OAuth client secret |
| `youtube_refresh_token` | `https://developers.google.com/oauthplayground` | YouTube readonly scope で発行した refresh token |

公開ライブだけを API key で試す場合は、任意で次も追加できます。

| Key name | Provider URL | 用途 |
| --- | --- | --- |
| `youtube_api_key` | `https://console.cloud.google.com/apis/credentials` | 公開ライブ検索用の YouTube Data API key |

必要な OAuth scope:

```text
https://www.googleapis.com/auth/youtube.readonly
```

API key だけでも公開ライブを探せる場合がありますが、非公開ライブの検証には向きません。

キー名の確認用に、`youtube_live_companion_config.json` にも空の認証項目を入れています。

```json
{
  "youtube_client_id": "",
  "youtube_client_secret": "",
  "youtube_refresh_token": "",
  "youtube_api_key": ""
}
```

`.env.example`, `.env`, `youtube_live_companion.env` も同梱していますが、OpenHome の公式 docs では Ability 用の一般的な `.env` 自動読み込みは確認できていません。まずは Live Editor で見える `youtube_live_companion_config.json` を使ってください。GitHub repo には実値を入れないでください。

```env
youtube_client_id=
youtube_client_secret=
youtube_refresh_token=
youtube_api_key=
```

推奨は **Ability Behavior -> API Keys** で宣言し、**Settings -> API Keys -> Third-party Keys** に保存する方法です。Third Party API Keys が runtime から読めない場合の fallback として、この Ability は Live Editor 上の `youtube_live_companion_config.json` を読みます。

## OAuth refresh token の用意

非公開ライブで試す場合は、YouTube アカウント画面から直接 token を取得するのではなく、Google Cloud の OAuth client を作り、その client で自分の YouTube アカウントを認可して `refresh_token` を発行します。

最終的に必要な値は次の 3 つです。

| OpenHome key | 取得元 |
| --- | --- |
| `youtube_client_id` | Google Cloud Console の OAuth Client ID |
| `youtube_client_secret` | Google Cloud Console の OAuth Client secret |
| `youtube_refresh_token` | OAuth 2.0 Playground で発行した Refresh token |

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

11. 作成後に表示される `クライアント ID` を `youtube_client_id` として控える。
12. 作成後に表示される `クライアント シークレット` を `youtube_client_secret` として控える。

ここで作るのは `OAuth クライアント ID` です。`API キー` でも `サービス アカウント` でもありません。非公開ライブを扱うには、配信者本人の YouTube アカウントで OAuth 認可する必要があります。

### 2. OAuth Playground で refresh token を発行する

1. [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/) を開く。
2. 右上の歯車アイコンを開く。
3. 次のように設定する。

| 項目 | 値 |
| --- | --- |
| Use your own OAuth credentials | ON |
| OAuth Client ID | `youtube_client_id` |
| OAuth Client secret | `youtube_client_secret` |
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
8. `Refresh token` 欄に出た値を `youtube_refresh_token` として控える。

`Authorization code` 欄の `4/...` で始まる値は一時コードです。OpenHome に入れる値ではありません。`Access token` も短時間で期限切れになるため、OpenHome に入れる値ではありません。

### 3. OpenHome に Third Party API Keys として登録する

OpenHome では、Ability のコードや JSON に秘密情報を書かず、Third Party API Keys に保存します。

1. Ability 作成 / 編集画面で **Ability Behavior -> API Keys** を開く。
2. 次の key name を宣言し、required として tag する。

```text
youtube_client_id
youtube_client_secret
youtube_refresh_token
```

3. OpenHome の **Settings -> API Keys -> Third-party Keys** を開く。
4. それぞれの値を保存する。
5. Agent を restart する。

保存先の対応は次のとおりです。

| Third Party API Key | 入れる値 |
| --- | --- |
| `youtube_client_id` | Google Cloud の OAuth クライアント ID |
| `youtube_client_secret` | Google Cloud の OAuth クライアント シークレット |
| `youtube_refresh_token` | OAuth Playground の `Refresh token` 欄の値 |

### 4. Third Party API Keys で読めない場合の JSON fallback

`youtube live setup` / `配信設定` で「認証情報を設定してください」と言われ続ける場合は、Ability runtime から Third Party API Keys が読めていません。その場合は OpenHome の Live Editor で `youtube_live_companion_config.json` を開き、次の形で値を入れます。

```json
{
  "youtube_client_id": "YOUR_CLIENT_ID",
  "youtube_client_secret": "YOUR_CLIENT_SECRET",
  "youtube_refresh_token": "YOUR_REFRESH_TOKEN",
  "youtube_api_key": "",
  "video_id": "",
  "channel_id": "",
  "live_chat_id": ""
}
```

`youtube_api_key` は任意です。非公開ライブの検証では `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token` の 3 つが必要です。

`youtube_live_companion_config.json` を保存したら、Agent を restart してから `配信設定` または `配信ステータス` をもう一度試します。

### よくある詰まりどころ

`invalid_scope` で `invalid=[youtube]` と出る場合は、OAuth Playground の scope 欄に `youtube` という文字だけが入っています。scope 欄を空にして、次だけを入れ直してください。

```text
https://www.googleapis.com/auth/youtube.readonly
```

`Refresh token` が表示されない場合は、OAuth Playground の歯車で `Access type: Offline` と `Force prompt: Consent Screen` を設定してから、再度 `Authorize APIs` します。それでも出ない場合は、Google アカウント側の既存アプリ許可を取り消してから再認可します。

OAuth Playground を使う場合は、自分の OAuth client を使う設定にしてから refresh token を発行してください。OpenHome の Ability zip や GitHub repo には refresh token を入れないでください。

`YouTube API HTTP 401` と `unauthorized_client` が出る場合は、OpenHome ではなく Google OAuth 側で `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token` の組み合わせが拒否されています。次を確認してください。

- OAuth Playground の歯車で `Use your own OAuth credentials` を ON にしてから認可したか。
- `youtube_client_id` と `youtube_client_secret` が同じ Google Cloud の OAuth client から取得したペアか。
- `youtube_refresh_token` を、その同じ `youtube_client_id` / `youtube_client_secret` で作り直したか。
- Google Cloud の OAuth client type が `Web application` になっているか。
- Authorized redirect URI に `https://developers.google.com/oauthplayground` が入っているか。
- OAuth consent screen が Testing の場合、配信用 Google アカウントが `Test users` に入っているか。

修正したら OAuth Playground で `Refresh access token` が成功することを確認し、その後 `youtube_live_companion_config.json` の 3 値を同じ組み合わせで更新してください。

## 非秘密の設定 JSON

`poll_interval_seconds` などの調整値や、公開ライブ用の `channel_id` / `video_id` / `live_chat_id` は、OpenHome の Live Editor で `youtube_live_companion_config.json` を編集します。

手順:

1. OpenHome に `dist/youtube-live-companion.zip` をアップロードする。
2. Ability Behavior → API Keys で required keys を宣言する。
3. Settings → API Keys → Third-party Keys で値を設定する。
4. 必要なら Ability の Live Editor で `youtube_live_companion_config.json` を開く。
5. `channel_id`, `video_id`, `live_chat_id` や polling 設定を調整する。
6. 保存する。
7. 必要なら Agent を restart する。

`配信設定` / `youtube live setup` の Trigger Word は、JSON や秘密情報を入力するためではなく、スピーカーから「Third Party API Keys を設定して」と確認するための案内用です。

同梱されている設定ファイルは次の形です。

```json
{
  "youtube_client_id": "",
  "youtube_client_secret": "",
  "youtube_refresh_token": "",
  "youtube_api_key": "",
  "video_id": "",
  "channel_id": "",
  "live_chat_id": "",
  "poll_interval_seconds": 15,
  "summary_interval_seconds": 60,
  "quiet_after_seconds": 120,
  "quiet_cooldown_seconds": 180,
  "min_messages_to_summarize": 3,
  "max_messages_per_summary": 12,
  "ignore_existing_messages_on_start": true,
  "speak_connection_status": true,
  "speak_summaries": true,
  "speak_quiet_prompts": true
}
```

保存される設定ファイル:

```text
youtube_live_companion_config.json
```

この MVP は次の順で設定を読みます。

1. Third Party API Keys の `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token`
2. 永続ファイル領域の `youtube_live_companion_config.json`
3. Ability 内ファイルの `youtube_live_companion_config.json`
4. `youtube_live_companion.env` または `.env` の `youtube_client_id`, `youtube_client_secret`, `youtube_refresh_token`, `youtube_api_key`

OAuth 秘密情報はできるだけ 1 の Third Party API Keys に入れます。Third Party API Keys が読めない場合だけ、OpenHome Live Editor 上の `youtube_live_companion_config.json` を fallback として使います。

公開ライブだけを API key で試す場合は、Live Editor の JSON か env ファイルに `youtube_api_key` を設定し、`channel_id` も入れます。

```json
{
  "channel_id": "YOUR_CHANNEL_ID",
  "poll_interval_seconds": 15,
  "summary_interval_seconds": 60
}
```

ただし、非公開ライブでは API key ではなく OAuth 設定を使ってください。

## live ID の特定方法

この Ability は OAuth 設定がある場合、次の順でライブチャットを探します。

1. `live_chat_id` が設定されていれば、それを直接使う。
2. `video_id` が設定されていれば、`videos.list` で `activeLiveChatId` を取得する。
3. OAuth で `liveBroadcasts.list` の `mine=true` を呼び、自分の配信だけを取得する。
4. `snippet.liveChatId` が見つかったら、`liveChatMessages.list` でコメント取得を開始する。

非公開ライブの場合は、3 の OAuth ルートを使う想定です。YouTube API は `mine` と `broadcastStatus` を同時指定できないため、取得後に `status.lifeCycleStatus == "live"` の配信だけを Ability 側で選びます。

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

## 設定リセット

Trigger Word:

```text
設定リセット
```

保存済みの config / state を削除します。

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
  main.py
  background.py
  youtube_live_companion_config.json
```

Ability の `Image` / `image_file` には、SVG ではなく画像ファイルを指定します。このリポジトリでは生成済みの PNG を次に置いています。

```text
dist/youtube-live-companion-icon.png
```

`icon.svg` を指定すると、OpenHome 側で `Unsupported file format image/svg+xml in image_file` になります。アップロード時は必ず PNG または JPEG を選んでください。
