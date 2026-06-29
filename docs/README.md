# OpenHome Ability 実装ガイド

このドキュメントは、OpenHome の AI アシスタントに機能を追加するための **Ability** の実装方法を、日本語で整理したものです。

参照元:

- [Abilities](https://docs.openhome.com/ability)
- [Background Abilities](https://docs.openhome.com/background-abilities)
- [Local Abilities](https://docs.openhome.com/local-ability)
- [Ability Types](https://docs.openhome.com/ability-types)

確認日: 2026-06-26

## Ability とは

Ability は、OpenHome Agent の機能を拡張するプラグインのような単位です。たとえば、Web から情報を取得する、スマートデバイスを操作する、アラームを監視する、DevKit 上のハードウェアを制御する、といった処理を Ability として追加できます。

Ability では主に次のことを設定・実装します。

| 項目 | 内容 |
| --- | --- |
| Name | Ability の名前。ダッシュボードや Marketplace に表示される。 |
| Description | Ability が何をするかの説明。 |
| Image | ダッシュボードや Marketplace 用の画像。 |
| Trigger Words | ユーザーの発話や入力から Ability を起動するための語句。 |
| Category | `Skill`, `Agent Controlled`, `Background Daemon`, `Local` のいずれか。 |
| Code | `main.py`, `background.py`, `devkit_functions.py` などの実装ファイル。 |

## Ability の種類を選ぶ

OpenHome の Ability は 4 種類に分かれます。最初にこの分類を決めると、必要なファイル構成と実装方針が決まります。

| 種類 | 使う場面 | 主なファイル | 起動方法 |
| --- | --- | --- | --- |
| Skill | ユーザーが明示的に呼び出す一回実行の機能。例: 天気確認、クイズ生成、簡単な操作。 | `main.py` | Trigger Words |
| Agent Controlled | Agent が必要に応じて呼び出す機能。例: データ検索、ツール実行、委譲アクション。 | 通常は `main.py` | Agent が判断 |
| Background Daemon | 会話と並行して常時動く監視処理。例: アラーム、リマインダー、会話メモ、定期ポーリング。 | `background.py` または `main.py` + `background.py` | セッション開始時に自動起動 |
| Local | OpenHome DevKit 上のハードウェア、ファイルシステム、シェル、ローカル Python 環境を使う機能。 | `main.py` + `devkit_functions.py` + `requirements.txt` | Trigger Words または Agent 経由 |

判断の目安:

- ユーザーが言ったときだけ動けばよいなら `Skill`。
- Agent 側が必要に応じて裏で呼ぶツールにしたいなら `Agent Controlled`。
- ユーザーが話していなくても監視し続けたいなら `Background Daemon`。
- DevKit の GPIO、センサー、LED、カメラ、OS 情報、シェルコマンドなどが必要なら `Local`。

## 作成手順

1. OpenHome の左サイドバーから `Create` -> `Abilities` を開く。
2. Ability の `Name`, `Description`, `Image` を入力する。
3. `Category` を選ぶ。
4. テンプレートを選ぶか、Ability コードを含む `.zip` をアップロードする。
5. `Trigger Words` を設定する。
6. `Save Ability` で保存する。
7. `Live Editor` でファイルを編集し、`Start Live Test` で動作確認する。
8. 問題なければ変更を commit / release する。

## zip アップロードからホームスピーカーで使うまで

ここでは、このリポジトリで作成した `simple-hello` Ability を例に、zip アップロード、OpenHome へのインストール、Agent への割り当て、ホームスピーカー / DevKit 上で使うまでの流れをまとめます。

### 1. アップロード用 zip を用意する

OpenHome の custom Ability upload では、zip の中に **単一のトップレベルディレクトリ** が必要です。今回の zip は次の構造にします。

```text
simple-hello/
  __init__.py
  README.md
  main.py
```

このリポジトリでは、アップロード用 zip を次の場所に置いています。

```text
dist/simple-hello.zip
```

zip の中身は次のようになっている必要があります。

```text
simple-hello/
simple-hello/__init__.py
simple-hello/README.md
simple-hello/main.py
```

次のように zip 直下へファイルが並んでいると、OpenHome 側で `Expected a single top-level directory in ability zipfile` というエラーになります。

```text
__init__.py
README.md
main.py
```

zip を作り直す場合は、リポジトリ直下の package script を使います。

```bash
cd /Users/ys/Documents/GitHub/openhome_abilities
./scripts/package-abilities.sh simple-hello
```

### 2. アイコン画像を用意する

OpenHome の Ability には dashboard / marketplace 表示用の画像を設定できます。`simple-hello` は動作確認用の最小 Ability なので、専用アイコンは同梱していません。必要なら任意の PNG / JPEG を用意して、Ability 作成画面の `Image` に指定してください。

`YouTube Live Companion` のアイコンは `abilities/youtube-live-companion/icon.png` にあります。

### 3. OpenHome に Ability をアップロードする

Web dashboard から作る場合の流れです。

1. [app.openhome.com](https://app.openhome.com) にログインする。
2. Dashboard を開く。
3. `Create` -> `Agent Ability` または `Abilities` を開く。
4. `Add Custom Ability` で `dist/simple-hello.zip` をアップロードする。
5. Ability 情報を入力する。

推奨設定:

| 項目 | 値 |
| --- | --- |
| Name | `Simple Hello` |
| Description | `簡易的な動作確認用 Ability` |
| Category | `Skill` |
| Image | 任意の PNG / JPEG |
| Trigger Words | `simple hello`, `hello ability`, `テスト ability`, `簡易 ability` |

`Skill` は、ユーザーが trigger word を話したときに一回実行され、処理後に通常の Personality flow へ戻る Ability です。今回の `simple-hello` は動作確認用なので `Skill` を選びます。

### 4. Agent Ability / System Ability を選ぶ

Ability の管理範囲として、Agent Ability と System Ability の選択があります。

| 種類 | 意味 | 今回の推奨 |
| --- | --- | --- |
| Agent Ability | 特定の Agent / Personality にだけ割り当てる Ability。 | 推奨。テスト用 Ability はまず特定 Agent にだけ入れる。 |
| System Ability | システム全体、または複数 Agent で共通利用する Ability。 | アラーム、家電操作、共通メモなど安定運用する機能向き。 |

今回の `Simple Hello` は **Agent Ability** として設定します。理由は、動作確認用の簡易 Ability なので、最初から全 Agent 共通にする必要がないためです。

### 5. Ability を保存・有効化する

1. `Save Ability` で保存する。
2. 保存後、Ability が `Installed Abilities` や作成済み Ability 一覧に出ることを確認する。
3. Ability が disabled になっている場合は enable にする。
4. Trigger Words が期待どおり入っていることを確認する。

同じ名前の Ability が既に存在する場合、OpenHome API では `Ability with same name already exists` になることがあります。その場合は、既存 Ability を削除してから再アップロードするか、名前を変えてアップロードします。

### 6. Ability を Agent / Personality に割り当てる

アップロードしただけでは、ホームスピーカー上で動いている Agent がその Ability を使えるとは限りません。使いたい Agent / Personality に Ability を割り当てます。

基本の流れ:

1. Dashboard で使いたい Agent / Personality を開く。
2. Ability / Matching Capabilities の設定を開く。
3. `Simple Hello` を追加する。
4. Agent 設定を保存する。

API で設定する場合は、Agent の `matching_capabilities` に Ability ID の一覧を渡します。この値は「追加分」ではなく「その Agent が持つ Ability の全リスト」として扱われるので、既存 Ability を消さないように注意します。

### 7. ホームスピーカー / DevKit 側で Agent を選ぶ

OpenHome - Voice AI DevKit App 側で、ホームスピーカー / DevKit が使う Agent を選びます。

1. iPhone の **OpenHome - Voice AI DevKit App** を開く。
2. DevKit / ホームスピーカーに接続する。
3. Dashboard の `Select Agent` で、`Simple Hello` を割り当てた Agent を選ぶ。
4. 必要なら `Restart Agent` を押す。
5. スピーカーに trigger word を話す。

例:

```text
simple hello
hello ability
テスト ability
```

正しく動くと、Ability が次の内容を話します。

```text
こんにちは。OpenHome の簡易 Ability が正しく動作しています。
```

その後、`main.py` の `resume_normal_flow()` によって通常の Personality flow に戻ります。

### 8. Local Ability の場合だけ Sync Abilities を使う

今回の `Simple Hello` は通常の `Skill` なので、基本的には DevKit アプリの `Sync Abilities` は不要です。

`Sync Abilities` が必要になるのは、主に `Local` Ability の場合です。Local Ability は `devkit_functions.py` や `requirements.txt` を DevKit 側へ同期して、DevKit 上の Python 環境やハードウェアにアクセスします。

Local Ability の場合:

- `main.py` は OpenHome platform 側の Ability runtime で動く。
- `devkit_functions.py` は OpenHome DevKit 上で動く。
- `requirements.txt` は DevKit 側にインストールされる。
- DevKit がオンラインなら Live Editor 保存時に同期される。
- DevKit がオフラインだった場合や反映されない場合は、DevKit App の `Sync Abilities` を押す。

### 9. うまく動かない時の確認項目

| 症状 | 確認すること |
| --- | --- |
| `Expected a single top-level directory in ability zipfile` | zip の中身が `simple-hello/main.py` のように単一ディレクトリ配下になっているか確認する。 |
| Trigger Word を言っても起動しない | Ability が enable か、Trigger Words が登録済みか、対象 Agent に割り当て済みか確認する。 |
| スピーカーで反応しない | DevKit App の `Select Agent` で、Ability を割り当てた Agent が選ばれているか確認する。 |
| 変更が反映されない | Agent を restart する。Local Ability の場合は `Sync Abilities` も実行する。 |
| Agent が通常会話に戻らない | `main.py` の終了経路で `resume_normal_flow()` が呼ばれているか確認する。 |
| 同じ名前でアップロードできない | 既存 Ability を削除するか、Ability 名を変えてアップロードする。 |

## 標準的な `main.py` の構成

`main.py` は、ユーザーとの会話フローを担当するファイルです。Skill や Agent Controlled Ability では、基本的に `main.py` に処理を書きます。

最小構成の考え方:

```python
from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker


class ExampleCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None

    #{{register capability}}

    async def first_function(self):
        try:
            await self.capability_worker.speak("Ability を実行しました。")
        finally:
            self.capability_worker.resume_normal_flow()

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.first_function())
```

重要な点:

- `call(self, worker)` が Ability の入口になる。
- `self.worker = worker` を設定してから `CapabilityWorker(self)` を作る。
- 非同期処理は `self.worker.session_tasks.create(...)` で開始する。
- `main.py` では終了時に必ず `resume_normal_flow()` を呼ぶ。例外が起きても戻れるように `finally` に置くのが安全。

## Background Ability の実装

Background Ability は、会話本体と並行して動く常駐処理です。ユーザーの hotword なしで、Personality への接続時に自動起動します。Personality が sleep mode でも動き続けます。

### ファイル構成

| 構成 | ファイル | 用途 |
| --- | --- | --- |
| 標準の一回実行 Ability | `main.py` | ユーザーが起動し、処理後に終了する。 |
| 常駐のみの Ability | `background.py` | セッション開始時に自動起動し、監視し続ける。 |
| 対話 + 常駐 | `main.py` + `background.py` | `main.py` が設定を受け取り、`background.py` が監視・通知する。 |

`background.py` というファイル名は固定です。別名では検出されません。

### `background.py` のテンプレート

```python
from time import time
from src.agent.capability import MatchingCapability
from src.main import AgentWorker
from src.agent.capability_worker import CapabilityWorker


class WatcherCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    background_daemon_mode: bool = False

    #{{register capability}}

    async def watcher_loop(self):
        self.worker.editor_logging_handler.info("%s: watcher started" % time())

        while True:
            self.worker.editor_logging_handler.info("%s: watcher cycle" % time())

            # ここに監視処理を書く

            await self.worker.session_tasks.sleep(20.0)

    def call(self, worker: AgentWorker, background_daemon_mode: bool):
        self.worker = worker
        self.background_daemon_mode = background_daemon_mode
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.watcher_loop())
```

`main.py` との違い:

| 項目 | `main.py` | `background.py` |
| --- | --- | --- |
| `call()` | `call(self, worker)` | `call(self, worker, background_daemon_mode)` |
| 起動 | ユーザー発話や Agent 判断 | セッション開始時に自動 |
| ライフサイクル | 一回実行して終了 | `while True` で継続 |
| `resume_normal_flow()` | 必須 | 不要 |
| sleep mode | 通常は起動しない | 動き続ける |

### Background で使う SDK メソッド

| メソッド | 同期/非同期 | 用途 |
| --- | --- | --- |
| `get_timezone()` | 同期 | ユーザーのタイムゾーン取得。アラームや予定に使う。 |
| `get_full_message_history()` | 同期 | 会話履歴の取得。メモ化・要約・監視に使う。 |
| `send_interrupt_signal()` | 非同期 | Daemon から話す前に現在の Personality 出力を止める。 |

Daemon から音声を出す場合は、先に `send_interrupt_signal()` を呼びます。

```python
await self.capability_worker.send_interrupt_signal()
await self.capability_worker.speak("アラームの時間です。")
```

### 対話 + 常駐の設計例

アラーム Ability の場合:

1. ユーザーが「木曜 15 時にアラームを設定して」と言う。
2. `main.py` が時刻を解釈し、`alarms.json` に保存する。
3. `main.py` が確認応答をして `resume_normal_flow()` する。
4. セッション開始時から動いている `background.py` が `alarms.json` を定期確認する。
5. 時刻になったら `send_interrupt_signal()` してから音声や効果音で通知する。
6. `background.py` が `alarms.json` の状態を `triggered` に更新する。

Background Ability の実装注意点:

- `asyncio.sleep()` ではなく `self.worker.session_tasks.sleep()` を使う。
- ポーリング間隔は短くしすぎない。10-30 秒程度が目安。
- 共有 JSON ファイルは存在しない可能性を前提に扱う。
- `write_file()` が追記型の場合、JSON 更新では「削除してから全体を書き直す」方式にする。
- Daemon は見えにくいので `editor_logging_handler` で十分にログを残す。
- sleep mode でも動かしたい場合、メイン処理は終わらない `while True` ループにする。

## Local Ability の実装

Local Ability は、OpenHome DevKit 上でコードを実行する特殊な Ability です。標準 Ability runtime では使えないハードウェア、OS、ファイルシステム、シェルコマンド、DevKit 側 Python パッケージを扱えます。

Local Ability は Web Live Editor のシミュレーション環境では動かず、実際の OpenHome DevKit ハードウェア上で動作します。

### ファイル構成

| ファイル | 実行場所 | 役割 |
| --- | --- | --- |
| `main.py` | 標準 Ability runtime | 音声対話、プロンプト、会話状態、SDK 呼び出し、DevKit 側関数の呼び出し。 |
| `devkit_functions.py` | OpenHome DevKit | ハードウェア制御、OS 操作、シェル実行、テレメトリ取得、DevKit 側 Python パッケージ利用。 |
| `requirements.txt` | OpenHome DevKit | `devkit_functions.py` 用の Python 依存関係。 |

`devkit_functions.py` というファイル名は固定です。別名では DevKit 側関数として認識されません。

`requirements.txt` に書いたパッケージは DevKit 側にインストールされます。`main.py` が動く標準 Ability runtime では使えません。

### `main.py` から DevKit 側関数を呼ぶ

`main.py` では `send_devkit_capability_action()` を使います。

```python
result = await self.capability_worker.send_devkit_capability_action(
    function_name="check_wifi",
    args=[],
    timeout=5,
)
```

| 引数 | 型 | 内容 |
| --- | --- | --- |
| `function_name` | `str` | `devkit_functions.py` の `FUNCTION_REGISTRY` に登録した関数名。 |
| `args` | `list[str]` | DevKit 側関数へ渡す引数。文字列として渡されるため、必要なら DevKit 側で型変換する。 |
| `timeout` | `int` | 最大待ち時間。ハードウェア処理は止まることがあるため必ず適切に設定する。 |
| `capability_name` | `str` optional | 別の Local Ability の `devkit_functions.py` を呼ぶ場合に指定する。 |

戻り値の形:

```python
{
    "success": True,
    "output": "captured stdout",
    "error": None,
    "function_name": "check_wifi",
    "args": [],
    "capability_name": "ability_name",
}
```

重要な仕様:

- `devkit_functions.py` の `print()` 出力が `result["output"]` に入る。
- Python の `return` 値は `send_devkit_capability_action()` には返らない。
- DevKit 側の診断ログは `web_logger` に書く。これは `result["output"]` ではなく Live Editor の DevKit logs に表示される。

### `devkit_functions.py` の基本形

```python
import json
import sys
from devkit_utils.devkit_logging import web_logger as log


def _print_payload(payload):
    output = json.dumps(payload)
    log.info("stdout payload: %s", output)
    print(output)


def check_wifi():
    # 実際にはここで DevKit 側の OS コマンドやハードウェア API を呼ぶ
    _print_payload({
        "success": True,
        "metric": "wifi",
        "spoken_response": "Wi-Fi status was checked.",
        "data": {},
        "error": None,
    })


FUNCTION_REGISTRY = {
    "check_wifi": check_wifi,
}


if __name__ == "__main__":
    function_name = sys.argv[1]
    FUNCTION_REGISTRY[function_name](*sys.argv[2:])
```

Local Ability の実装注意点:

- DevKit 側で呼べる関数は `FUNCTION_REGISTRY` に登録する。
- `function_name` は `FUNCTION_REGISTRY` のキーと一致させる。
- `args` は文字列として届くため、整数・真偽値・JSON などは `devkit_functions.py` 側で変換する。
- 出力は JSON 文字列を `print()` し、`main.py` 側で `json.loads(result["output"])` して読むと扱いやすい。
- ハードウェアが接続されていない場合や OS コマンドが失敗する場合を `try/except` で扱う。
- 軽い処理は 5-10 秒程度、長い処理は用途に応じて長めの `timeout` にする。
- `devkit_functions.py` と `requirements.txt` の変更は DevKit に同期される。`main.py` の変更は Agent restart を伴うことがある。

## Live Editor と DevKit 同期

Live Editor では、Ability のファイル編集、テスト、変更 commit、trigger words の調整ができます。

Local Ability で DevKit がオンラインの場合:

- `devkit_functions.py` または `requirements.txt` の変更は DevKit に同期される。
- `requirements.txt` が変わると DevKit 側に依存パッケージがインストールされる。
- `main.py` の変更は OpenHome platform に保存され、DevKit sandbox に同期されたうえで Agent が restart される。
- DevKit がオフラインの間に変更した場合は、再接続後に Advanced DevKit Controls から `Sync Abilities` を実行して反映する。

別の Local Ability の DevKit 関数を呼ぶ場合は、Ability Editor の `Quick Reference Installed Abilities` で対象 Ability 名を確認し、`capability_name` に渡します。

```python
result = await self.capability_worker.send_devkit_capability_action(
    function_name="get_sensor_value",
    args=["temperature"],
    timeout=10,
    capability_name="target_ability_name",
)
```

## 実装チェックリスト

Ability を作るときは、次の順に確認すると抜け漏れが少なくなります。

1. 目的が一回実行、Agent 判断、常駐監視、DevKit 実行のどれかを決める。
2. Category を `Skill`, `Agent Controlled`, `Background Daemon`, `Local` から選ぶ。
3. 必要ファイルを用意する。
4. `main.py` がある場合、すべての終了経路で `resume_normal_flow()` を呼ぶ。
5. `background.py` がある場合、`call(self, worker, background_daemon_mode)` と `while True` ループにする。
6. `background.py` では `self.worker` と `self.background_daemon_mode` を設定してから `CapabilityWorker(self)` を作る。
7. `background.py` では `session_tasks.sleep()` を使う。
8. Daemon が話す前に `send_interrupt_signal()` を呼ぶ。
9. Local Ability では `devkit_functions.py` に `FUNCTION_REGISTRY` と `if __name__ == "__main__"` を置く。
10. DevKit 側の結果は `print()` で JSON を出し、`main.py` 側で parse する。
11. `requirements.txt` には DevKit 側で実際に import する依存だけを書く。
12. Live Editor の `Start Live Test`、DevKit logs、通常 logs を見て動作確認する。
13. Trigger Words を実際のユーザー発話に近い表現で調整する。
14. 問題なければ変更を commit / release する。

## よくある設計パターン

### 外部 API を呼んで返答する

- Category: `Skill` または `Agent Controlled`
- 実装: `main.py`
- 注意: API 失敗時の fallback 応答を用意し、最後に `resume_normal_flow()` する。

### アラーム・リマインダー

- Category: `Background Daemon`
- 構成: ユーザーが予定を登録するなら `main.py` + `background.py`、常駐監視だけなら `background.py`
- 注意: `main.py` が予定を保存し、`background.py` が共有ファイルをポーリングする。

### 会話を裏でメモ・要約する

- Category: `Background Daemon`
- 実装: `background.py`
- 注意: `get_full_message_history()` を使い、定期的に差分を処理する。必要がない限り会話へ割り込まない。

### DevKit のセンサーや LED を操作する

- Category: `Local`
- 実装: `main.py` + `devkit_functions.py` + `requirements.txt`
- 注意: 音声対話とハードウェア制御を分離する。`main.py` はユーザー体験、`devkit_functions.py` は物理デバイス操作に集中させる。

## 実装時の落とし穴

- `background.py` や `devkit_functions.py` のファイル名を変えると OpenHome が検出できない。
- `main.py` で `resume_normal_flow()` を呼び忘れると、Agent が通常フローへ戻れない。
- Background Daemon で `asyncio.sleep()` を使うと、セッション終了時の cleanup に問題が出る可能性がある。
- Background Daemon から突然 `speak()` すると、既存の音声出力と重なる。先に `send_interrupt_signal()` を呼ぶ。
- JSON 共有ファイルに追記すると壊れる。全体を書き直す方式にする。
- Local Ability は Live Editor のシミュレーションではなく実 DevKit で検証する。
- `devkit_functions.py` の Python `return` は `main.py` に返らない。返したい内容は `print()` する。
- `requirements.txt` の依存は DevKit 側専用で、`main.py` では使えない。

## 最小実装方針

初めて Ability を作る場合は、次の順で小さく作るのが安全です。

1. まず `main.py` だけの Skill として、固定文を `speak()` する最小 Ability を作る。
2. Trigger Words で正しく起動することを確認する。
3. 実処理を追加する。
4. 常駐監視が必要になったら `background.py` を追加する。
5. DevKit のハードウェアや OS 操作が必要になった時点で Local Ability に切り出す。
6. 最後にログ、例外処理、タイムアウト、テスト発話を整える。
