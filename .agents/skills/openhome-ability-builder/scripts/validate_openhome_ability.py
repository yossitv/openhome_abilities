#!/usr/bin/env python3
"""Run structural checks for an OpenHome ability folder."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path


SECRET_PATTERNS = (
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"ya29\."),
    re.compile(r"1//[0-9A-Za-z_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


class Reporter:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def emit(self) -> int:
        for message in self.warnings:
            print(f"WARN: {message}")
        for message in self.errors:
            print(f"FAIL: {message}")
        if self.errors:
            return 1
        print("PASS: OpenHome ability structure looks valid")
        return 0


def resolve_ability_path(target: str, repo_root: Path) -> Path:
    candidate = Path(target).expanduser()
    if candidate.exists():
        return candidate.resolve()
    return (repo_root / "abilities" / target).resolve()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def compile_python(path: Path, reporter: Reporter) -> None:
    try:
        compile(read_text(path), str(path), "exec")
    except SyntaxError as error:
        reporter.error(f"{path.name} does not compile: {error}")


def check_secrets(ability_path: Path, reporter: Reporter) -> None:
    for path in ability_path.rglob("*"):
        if not path.is_file() or path.suffix in {".png", ".jpg", ".jpeg", ".zip"}:
            continue
        text = read_text(path)
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                reporter.error(f"possible secret in {path.relative_to(ability_path)}: {pattern.pattern}")


def check_main(path: Path, reporter: Reporter) -> None:
    text = read_text(path)
    compile_python(path, reporter)
    if "#{{register capability}}" not in text:
        reporter.warning("main.py is missing #{{register capability}} marker")
    if "resume_normal_flow()" not in text:
        reporter.error("main.py should call resume_normal_flow() on completion")
    if "CapabilityWorker(self)" not in text:
        reporter.error("main.py should construct CapabilityWorker(self)")
    if "session_tasks.create" not in text:
        reporter.warning("main.py usually starts async work with session_tasks.create(...)")


def check_background(path: Path, reporter: Reporter) -> None:
    text = read_text(path)
    compile_python(path, reporter)
    if "background_daemon_mode" not in text:
        reporter.error("background.py call signature should include background_daemon_mode")
    if "while True" not in text:
        reporter.warning("background.py usually contains a long-running while True loop")
    if "session_tasks.sleep" not in text:
        reporter.error("background.py should use self.worker.session_tasks.sleep(...)")
    if "asyncio.sleep" in text:
        reporter.error("background.py should not use asyncio.sleep(...)")


def check_devkit(path: Path, reporter: Reporter) -> None:
    text = read_text(path)
    compile_python(path, reporter)
    if "FUNCTION_REGISTRY" not in text:
        reporter.error("devkit_functions.py should define FUNCTION_REGISTRY")
    if "if __name__ == \"__main__\"" not in text:
        reporter.error("devkit_functions.py should expose a __main__ dispatcher")
    if "print(" not in text:
        reporter.warning("devkit_functions.py should print JSON payloads for main.py")


def check_zip(zip_path: Path, expected_top_level: str, reporter: Reporter) -> None:
    if not zip_path.exists():
        return
    try:
        with zipfile.ZipFile(zip_path) as archive:
            top_levels = {
                name.split("/", 1)[0]
                for name in archive.namelist()
                if name and not name.startswith("__MACOSX/")
            }
    except zipfile.BadZipFile:
        reporter.error(f"{zip_path} is not a valid zip")
        return
    if top_levels != {expected_top_level}:
        reporter.error(
            f"{zip_path} should contain only top-level directory {expected_top_level}/; found {sorted(top_levels)}"
        )


def validate(args: argparse.Namespace) -> int:
    reporter = Reporter()
    repo_root = Path(args.repo_root).expanduser().resolve()
    ability_path = resolve_ability_path(args.ability, repo_root)

    if not ability_path.exists() or not ability_path.is_dir():
        reporter.error(f"ability directory not found: {ability_path}")
        return reporter.emit()

    if not (ability_path / "__init__.py").exists():
        reporter.warning("__init__.py is missing")

    main_py = ability_path / "main.py"
    background_py = ability_path / "background.py"
    devkit_py = ability_path / "devkit_functions.py"

    if not any(path.exists() for path in (main_py, background_py, devkit_py)):
        reporter.error("ability should include main.py, background.py, or devkit_functions.py")

    if main_py.exists():
        check_main(main_py, reporter)
    if background_py.exists():
        check_background(background_py, reporter)
    if devkit_py.exists():
        check_devkit(devkit_py, reporter)

    check_secrets(ability_path, reporter)
    check_zip(repo_root / "dist" / f"{ability_path.name}.zip", ability_path.name, reporter)
    return reporter.emit()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ability", help="Ability slug or path")
    parser.add_argument("--repo-root", default=".", help="Repository root containing abilities/")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    return validate(parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
