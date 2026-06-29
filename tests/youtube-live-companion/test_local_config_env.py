#!/usr/bin/env python3
"""Local-only runtime credential injection smoke test for youtube-live-companion.

The uploaded Ability keeps credentials as placeholders in main.py and
background.py. This tester is the only place that reads a local env file, then
patches those imported runtime modules so local checks can exercise the same
helpers without committing secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from openhome_test_support import import_ability_modules


REQUIRED_ENV_KEYS = (
    "YOUTUBE_CLIENT_ID",
    "YOUTUBE_CLIENT_SECRET",
    "YOUTUBE_REFRESH_TOKEN",
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def patch_runtime_from_env(modules, env_values: dict[str, str]) -> None:
    missing = [key for key in REQUIRED_ENV_KEYS if not env_values.get(key)]
    if missing:
        raise ValueError("missing required local env keys: " + ", ".join(missing))
    for module in modules:
        for key in REQUIRED_ENV_KEYS:
            setattr(module, key, env_values[key])


async def run_smoke(env_file: Path, ability_dir: Path) -> None:
    env_values = parse_env_file(env_file)
    _ability_config, main_module, background_module = import_ability_modules(ability_dir)
    patch_runtime_from_env((main_module, background_module), env_values)

    main_capability = main_module.YoutubeLiveCompanionCapability()
    missing, source = await main_capability._missing_credentials()
    if missing:
        raise AssertionError(f"main.py still reports missing credentials: {missing}")
    if source != "main.py":
        raise AssertionError(f"main.py should report main.py source, got {source!r}")

    background_capability = background_module.YoutubeLiveCompanionBackground()
    loaded = await background_capability._load_config()
    if not loaded:
        raise AssertionError("background.py failed to load patched config credentials")

    expected = {
        "client_id": env_values["YOUTUBE_CLIENT_ID"],
        "client_secret": env_values["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": env_values["YOUTUBE_REFRESH_TOKEN"],
    }
    for key, value in expected.items():
        if loaded.get(key) != value:
            raise AssertionError(f"background config {key} mismatch")
    if loaded.get("credential_source") != "background.py":
        raise AssertionError(
            "background.py should report background.py source, "
            f"got {loaded.get('credential_source')!r}"
        )


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).with_name("example.env"),
        help="Local env file to load. Use a private .env for real credentials.",
    )
    parser.add_argument(
        "--ability-dir",
        type=Path,
        default=repo_root / "abilities" / "youtube-live-companion",
        help="Path to the youtube-live-companion Ability directory.",
    )
    args = parser.parse_args()

    asyncio.run(run_smoke(args.env_file.resolve(), args.ability_dir.resolve()))
    print("PASS: local env values patched runtime modules without committing secrets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
