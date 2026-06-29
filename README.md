# OpenHome Abilities

## English

This repository is a workspace for building and managing custom OpenHome Abilities.

Abilities are implemented under `abilities/`, packaged as ZIP files, and uploaded to OpenHome for testing or use. The generated upload files are local build artifacts and should not be committed.

### Workflow

1. Check the relevant OpenHome skill before editing.

   Use `.agents/skills/openhome-skill-index/SKILL.md` as the entry point.

   | Skill | Use Case |
   | --- | --- |
   | `openhome-ability-builder` | Build, edit, package, or troubleshoot an Ability. |
   | `openhome-skill-checker` | Check an Ability before a community PR. |
   | `openhome-ability-publisher` | Prepare a PR for `openhome-dev/abilities`. |

2. Add or edit the Ability under `abilities/`.

   ```text
   abilities/
     simple-hello/
     youtube-live-companion/
   ```

   A minimal Ability usually has:

   ```text
   abilities/<ability-name>/
     __init__.py
     README.md
     main.py
   ```

   Background Daemon and Local Abilities may also need files such as `background.py`, `devkit_functions.py`, or `requirements.txt`.

3. Package the Ability from the repository root.

   ```bash
   ./scripts/package-abilities.sh <ability-name>
   ```

   Example:

   ```bash
   ./scripts/package-abilities.sh youtube-live-companion
   ```

   The generated ZIP is written to `dist/`. The `dist/` directory is ignored by git because it is regenerated as needed.

4. Upload the ZIP to OpenHome.

   1. Open the OpenHome Dashboard.
   2. Open the Ability creation page: [app.openhome.com/dashboard/create/abilities](https://app.openhome.com/dashboard/create/abilities)
   3. Upload `dist/<ability-name>.zip`.
   4. Set Name, Description, Category, Trigger Words, and related settings.
   5. Assign the Ability to the Agent / Personality that should use it.
   6. Verify it with Live Test or a real device.

### Packaging Rule

OpenHome custom Ability uploads require one top-level directory inside the ZIP.

Correct:

```text
youtube-live-companion/
  __init__.py
  README.md
  main.py
  background.py
```

Incorrect:

```text
README.md
main.py
background.py
```

Use `scripts/package-abilities.sh` so the archive layout stays valid.

### Repository Layout

```text
.
├── .agents/
│   └── skills/                # Codex skills for OpenHome Ability work
├── abilities/                 # Ability source directories
│   ├── simple-hello/
│   └── youtube-live-companion/
├── docs/                      # Supporting docs and PR notes
└── scripts/
    └── package-abilities.sh   # Packages abilities into upload ZIP files
```

### Notes

- Do not commit real API keys, OAuth tokens, client secrets, refresh tokens, or private keys.
- Keep generated ZIPs and other `dist/` artifacts out of git.
- Each Ability should document its trigger words, setup values, credentials, and operational notes in its own README.
- Before uploading, run local structure checks and package validation.

## 日本語

このリポジトリは、OpenHome のカスタム Ability を作成・管理するための作業場所です。

Ability は `abilities/` 配下に実装し、ZIP にパッケージングして OpenHome にアップロードします。生成されたアップロード用ファイルはローカル成果物なので、基本的にコミットしません。

### 基本ワークフロー

1. 編集前に関連する OpenHome skill を確認する。

   入口は `.agents/skills/openhome-skill-index/SKILL.md` です。

   | Skill | 使う場面 |
   | --- | --- |
   | `openhome-ability-builder` | Ability の作成、修正、パッケージング、トラブルシュートを行う。 |
   | `openhome-skill-checker` | community PR 前に Ability をチェックする。 |
   | `openhome-ability-publisher` | `openhome-dev/abilities` への PR 準備を行う。 |

2. Ability を `abilities/` 配下に追加または修正する。

   ```text
   abilities/
     simple-hello/
     youtube-live-companion/
   ```

   最小構成の Ability は、通常次のファイルを持ちます。

   ```text
   abilities/<ability-name>/
     __init__.py
     README.md
     main.py
   ```

   Background Daemon や Local Ability では、`background.py`, `devkit_functions.py`, `requirements.txt` などが追加で必要になることがあります。

3. リポジトリルートで Ability をパッケージングする。

   ```bash
   ./scripts/package-abilities.sh <ability-name>
   ```

   例:

   ```bash
   ./scripts/package-abilities.sh youtube-live-companion
   ```

   生成された ZIP は `dist/` に出力されます。`dist/` は必要に応じて再生成するため、git では ignore しています。

4. ZIP を OpenHome にアップロードする。

   1. OpenHome Dashboard を開く。
   2. Ability 作成ページを開く: [app.openhome.com/dashboard/create/abilities](https://app.openhome.com/dashboard/create/abilities)
   3. `dist/<ability-name>.zip` をアップロードする。
   4. Name, Description, Category, Trigger Words などを設定する。
   5. 利用する Agent / Personality に Ability を割り当てる。
   6. Live Test または実機で動作確認する。

### パッケージング規則

OpenHome のカスタム Ability アップロードでは、ZIP の中に単一のトップレベルディレクトリが必要です。

正しい例:

```text
youtube-live-companion/
  __init__.py
  README.md
  main.py
  background.py
```

誤った例:

```text
README.md
main.py
background.py
```

ZIP レイアウトを崩さないため、`scripts/package-abilities.sh` を使ってください。

### ディレクトリ構成

```text
.
├── .agents/
│   └── skills/                # OpenHome Ability 作業用の Codex skill
├── abilities/                 # Ability の実装ディレクトリ
│   ├── simple-hello/
│   └── youtube-live-companion/
├── docs/                      # 補助ドキュメントや PR メモ
└── scripts/
    └── package-abilities.sh   # Ability をアップロード用 ZIP にするスクリプト
```

### 注意事項

- API キー、OAuth token、client secret、refresh token、private key などの実値はコミットしません。
- 生成された ZIP や `dist/` 配下の成果物は git に含めません。
- Trigger Words、設定値、認証情報の扱い、運用上の注意点は各 Ability の README に記載します。
- アップロード前に、ローカルで構造チェックとパッケージング確認を行います。
