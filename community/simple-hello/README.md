# Simple Hello Ability

OpenHome の最小構成を確認するための簡易 Ability です。

## できること

Trigger Words で起動されると、短い挨拶と動作確認メッセージを話し、通常の Personality flow に戻ります。

## 推奨 Trigger Words

- `hello ability`
- `simple hello`
- `簡易 ability`
- `テスト ability`

## ファイル構成

| ファイル | 役割 |
| --- | --- |
| `main.py` | Ability 本体。挨拶を話して `resume_normal_flow()` します。 |
| `README.md` | Ability の説明。 |
| `__init__.py` | Python パッケージとして扱うための空ファイル。 |

## OpenHome への入れ方

1. OpenHome の `Create` -> `Abilities` を開きます。
2. `Add Custom Ability` からこのフォルダを zip 化したものをアップロードします。
3. Category は `Skill` を選びます。
4. Trigger Words に上記の例を登録します。
5. Live Editor の `Start Live Test` で起動確認します。
