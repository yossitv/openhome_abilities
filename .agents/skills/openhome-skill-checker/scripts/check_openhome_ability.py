#!/usr/bin/env python3
"""Check OpenHome community Ability folders before PR submission."""

from __future__ import annotations

import argparse
import ast
import os
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path


REGISTER_MARKERS = ("#{{register_capability}}", "#{{register capability}}")

REQUESTS_METHODS = {
    "delete",
    "get",
    "head",
    "options",
    "patch",
    "post",
    "put",
    "request",
}

SECRET_PATTERNS = (
    ("google_api_key", re.compile(r"AIza[0-9A-Za-z_-]{20,}")),
    ("google_oauth_access_token", re.compile(r"ya29\.[0-9A-Za-z_-]+")),
    ("google_oauth_refresh_token", re.compile(r"1//[0-9A-Za-z_-]{20,}")),
    ("openai_api_key", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{20,}")),
    ("anthropic_api_key", re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}")),
    ("github_token", re.compile(r"gh[pousr]_[A-Za-z0-9_]{30,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)

BINARY_SUFFIXES = {
    ".avif",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".pyc",
    ".pyo",
    ".webp",
    ".zip",
}


@dataclass(frozen=True)
class Result:
    status: str
    code: str
    message: str


class Reporter:
    def __init__(self) -> None:
        self.results: list[Result] = []

    def pass_(self, code: str, message: str) -> None:
        self.results.append(Result("PASS", code, message))

    def warn(self, code: str, message: str) -> None:
        self.results.append(Result("WARN", code, message))

    def fail(self, code: str, message: str) -> None:
        self.results.append(Result("FAIL", code, message))

    def count(self, status: str) -> int:
        return sum(1 for result in self.results if result.status == status)

    def emit(self, label: str) -> None:
        print(f"\nAbility: {label}")
        for result in self.results:
            print(f"{result.status}: {result.code}: {result.message}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def choose_ability_root(repo_root: Path, requested: str | None) -> Path:
    if requested:
        return (repo_root / requested).resolve()
    for name in ("abilities", "community"):
        path = repo_root / name
        if path.is_dir():
            return path.resolve()
    return (repo_root / "abilities").resolve()


def resolve_ability(repo_root: Path, ability_root: Path, target: str) -> Path:
    candidate = Path(target).expanduser()
    if candidate.exists():
        return candidate.resolve()
    for base in (ability_root, repo_root / "abilities", repo_root / "community"):
        path = base / target
        if path.exists():
            return path.resolve()
    return (ability_root / target).resolve()


def iter_abilities(repo_root: Path, ability_root: Path, targets: list[str]) -> list[Path]:
    if targets:
        return [resolve_ability(repo_root, ability_root, target) for target in targets]
    if not ability_root.is_dir():
        return []
    return sorted(path for path in ability_root.iterdir() if path.is_dir())


def iter_python_files(ability_path: Path) -> list[Path]:
    return sorted(
        path
        for path in ability_path.rglob("*.py")
        if "__pycache__" not in path.parts and path.is_file()
    )


def iter_text_files(ability_path: Path) -> list[Path]:
    files = []
    for path in ability_path.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            continue
        files.append(path)
    return sorted(files)


def parse_python(path: Path, reporter: Reporter) -> ast.Module | None:
    try:
        return ast.parse(read_text(path), filename=str(path))
    except SyntaxError as error:
        reporter.fail("python-syntax", f"{path.name} does not compile: {error}")
        return None


def ast_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def extends_matching_capability(node: ast.ClassDef) -> bool:
    return any(ast_name(base) == "MatchingCapability" for base in node.bases)


def matching_classes(tree: ast.Module) -> list[ast.ClassDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and extends_matching_capability(node)
    ]


def calls_attr(node: ast.AST, attr: str) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Attribute):
            if child.func.attr == attr:
                return True
    return False


def function_body_without_docstring(
    node: ast.AsyncFunctionDef | ast.FunctionDef,
) -> list[ast.stmt]:
    body = list(node.body)
    if not body:
        return body
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return body[1:]
    return body


def run_has_finally_resume(node: ast.AsyncFunctionDef | ast.FunctionDef) -> bool:
    body = function_body_without_docstring(node)
    if not body or not isinstance(body[0], ast.Try):
        return False
    finalbody = ast.Module(body=body[0].finalbody, type_ignores=[])
    return calls_attr(finalbody, "resume_normal_flow")


def check_matching_capability(
    ability_path: Path,
    trees: dict[Path, ast.Module],
    reporter: Reporter,
) -> None:
    entrypoints = [ability_path / "main.py", ability_path / "background.py"]
    existing_entrypoints = [path for path in entrypoints if path.exists()]
    found = []

    for path in existing_entrypoints:
        tree = trees.get(path)
        if tree and matching_classes(tree):
            found.append(path.name)
        else:
            reporter.fail(
                "matching-capability",
                f"{path.name} exists but has no class extending MatchingCapability",
            )

    if found:
        reporter.pass_(
            "matching-capability",
            "entrypoint class extends MatchingCapability: " + ", ".join(found),
        )
    elif not existing_entrypoints:
        reporter.fail("matching-capability", "main.py or background.py is required")


def check_register_markers(ability_path: Path, reporter: Reporter) -> None:
    entrypoints = [path for path in (ability_path / "main.py", ability_path / "background.py") if path.exists()]
    if not entrypoints:
        reporter.fail("register-capability", "no main.py or background.py entrypoint found")
        return

    missing = [
        path.name
        for path in entrypoints
        if not any(marker in read_text(path) for marker in REGISTER_MARKERS)
    ]
    if missing:
        reporter.fail(
            "register-capability",
            "missing #{{register_capability}} boilerplate in " + ", ".join(missing),
        )
    else:
        reporter.pass_(
            "register-capability",
            "entrypoints include register capability boilerplate",
        )


def check_resume_normal_flow(
    ability_path: Path,
    trees: dict[Path, ast.Module],
    reporter: Reporter,
) -> None:
    main_py = ability_path / "main.py"
    if not main_py.exists():
        reporter.warn(
            "resume-normal-flow",
            "main.py is absent; manually verify background-only lifecycle behavior",
        )
        return

    tree = trees.get(main_py)
    if not tree:
        return

    classes = matching_classes(tree)
    run_methods = [
        child
        for class_node in classes
        for child in class_node.body
        if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef)) and child.name == "run"
    ]

    if not calls_attr(tree, "resume_normal_flow"):
        reporter.fail(
            "resume-normal-flow",
            "main.py should call resume_normal_flow() before returning control",
        )
        return

    if not run_methods:
        reporter.warn(
            "resume-normal-flow",
            "resume_normal_flow() exists, but no run() method was found",
        )
        return

    unsafe = [method.name for method in run_methods if not run_has_finally_resume(method)]
    if unsafe:
        reporter.fail(
            "resume-normal-flow",
            "run() should use try/finally with resume_normal_flow() in finally",
        )
    else:
        reporter.pass_(
            "resume-normal-flow",
            "run() calls resume_normal_flow() from finally",
        )


def check_print_calls(
    ability_path: Path,
    trees: dict[Path, ast.Module],
    reporter: Reporter,
) -> None:
    failures = []
    devkit_prints = []

    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "print":
                continue
            location = f"{rel(path, ability_path)}:{node.lineno}"
            if path.name == "devkit_functions.py":
                devkit_prints.append(location)
            else:
                failures.append(location)

    if failures:
        reporter.fail(
            "no-print",
            "use worker.editor_logging_handler instead of print(): " + ", ".join(failures),
        )
    else:
        reporter.pass_("no-print", "no print() calls found in runtime files")

    if devkit_prints:
        reporter.warn(
            "devkit-print",
            "devkit_functions.py prints stdout; confirm this is only for Local Ability return data: "
            + ", ".join(devkit_prints),
        )


def check_secrets(ability_path: Path, reporter: Reporter) -> None:
    offenders = []
    for path in iter_text_files(ability_path):
        text = read_text(path)
        for label, pattern in SECRET_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{rel(path, ability_path)}:{label}")

    if offenders:
        reporter.fail(
            "no-hardcoded-api-keys",
            "possible hardcoded secret values found: " + ", ".join(offenders),
        )
    else:
        reporter.pass_("no-hardcoded-api-keys", "no known secret patterns found")


def collect_requests_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    modules: set[str] = set()
    functions: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "requests":
                    modules.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "requests":
            for alias in node.names:
                if alias.name in REQUESTS_METHODS:
                    functions.add(alias.asname or alias.name)

    return modules, functions


def root_name(node: ast.AST) -> str:
    current = node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name):
        return current.id
    return ""


def is_requests_call(call: ast.Call, modules: set[str], functions: set[str]) -> bool:
    if isinstance(call.func, ast.Name):
        return call.func.id in functions
    if isinstance(call.func, ast.Attribute):
        return root_name(call.func.value) in modules and call.func.attr in REQUESTS_METHODS
    return False


def has_timeout(call: ast.Call) -> bool:
    return any(keyword.arg == "timeout" for keyword in call.keywords)


def check_requests_timeouts(
    ability_path: Path,
    trees: dict[Path, ast.Module],
    reporter: Reporter,
) -> None:
    missing = []

    for path, tree in trees.items():
        modules, functions = collect_requests_aliases(tree)
        if not modules and not functions:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and is_requests_call(node, modules, functions):
                if not has_timeout(node):
                    missing.append(f"{rel(path, ability_path)}:{node.lineno}")

    if missing:
        reporter.fail(
            "requests-timeout",
            "requests.*() calls must include timeout=: " + ", ".join(missing),
        )
    else:
        reporter.pass_("requests-timeout", "all detected requests.*() calls include timeout=")


def check_readme(ability_path: Path, reporter: Reporter) -> None:
    readme = ability_path / "README.md"
    if not readme.exists():
        reporter.fail("readme", "README.md is required")
        return

    text = read_text(readme)
    content_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    has_description = any(len(line) >= 20 for line in content_lines[:8])
    has_triggers = re.search(
        r"^#{1,4}\s+.*(trigger|トリガ|起動語|推奨).*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )

    if not has_description:
        reporter.fail("readme", "README.md should include a description")
    if not has_triggers:
        reporter.fail("readme", "README.md should include suggested trigger words")
    if has_description and has_triggers:
        reporter.pass_("readme", "README.md includes description and trigger words")


def check_zip_layout(repo_root: Path, ability_path: Path, reporter: Reporter) -> None:
    zip_path = repo_root / "dist" / f"{ability_path.name}.zip"
    if not zip_path.exists():
        reporter.warn("zip-layout", f"{rel(zip_path, repo_root)} is not present")
        return

    try:
        with zipfile.ZipFile(zip_path) as archive:
            top_levels = {
                name.split("/", 1)[0]
                for name in archive.namelist()
                if name and not name.startswith("__MACOSX/")
            }
    except zipfile.BadZipFile:
        reporter.fail("zip-layout", f"{rel(zip_path, repo_root)} is not a valid zip")
        return

    if top_levels == {ability_path.name}:
        reporter.pass_("zip-layout", "dist zip has one top-level ability directory")
    else:
        reporter.fail(
            "zip-layout",
            f"dist zip should contain only {ability_path.name}/; found {sorted(top_levels)}",
        )


def check_manual_confirmations(args: argparse.Namespace, reporter: Reporter) -> None:
    pr_target_ok = args.confirm_pr_target_dev or os.getenv("OPENHOME_ABILITY_PR_TARGET") == "dev"
    editor_ok = args.confirm_live_editor or os.getenv("OPENHOME_ABILITY_LIVE_EDITOR_RUN") == "1"
    missing = reporter.fail if args.strict else reporter.warn

    if pr_target_ok:
        reporter.pass_("pr-target-dev", "PR target dev confirmed")
    else:
        missing(
            "pr-target-dev",
            "confirm PR targets dev with --confirm-pr-target-dev or OPENHOME_ABILITY_PR_TARGET=dev",
        )

    if editor_ok:
        reporter.pass_("live-editor-run", "OpenHome Ability Editor run confirmed")
    else:
        missing(
            "live-editor-run",
            "confirm editor run with --confirm-live-editor or OPENHOME_ABILITY_LIVE_EDITOR_RUN=1",
        )


def check_ability(repo_root: Path, ability_path: Path, args: argparse.Namespace) -> Reporter:
    reporter = Reporter()
    if not ability_path.is_dir():
        reporter.fail("ability-path", f"ability directory not found: {ability_path}")
        return reporter

    trees: dict[Path, ast.Module] = {}
    for path in iter_python_files(ability_path):
        tree = parse_python(path, reporter)
        if tree is not None:
            trees[path] = tree

    if trees:
        reporter.pass_("python-files", "Python files parse successfully")
    else:
        reporter.fail("python-files", "ability should include Python files")

    check_matching_capability(ability_path, trees, reporter)
    check_register_markers(ability_path, reporter)
    check_resume_normal_flow(ability_path, trees, reporter)
    check_print_calls(ability_path, trees, reporter)
    check_secrets(ability_path, reporter)
    check_requests_timeouts(ability_path, trees, reporter)
    check_readme(ability_path, reporter)
    check_zip_layout(repo_root, ability_path, reporter)
    check_manual_confirmations(args, reporter)
    return reporter


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("abilities", nargs="*", help="Ability slug or path")
    parser.add_argument("--repo-root", default=".", help="Repository root")
    parser.add_argument(
        "--ability-root",
        help="Directory containing ability folders; defaults to abilities/ then community/",
    )
    parser.add_argument("--list", action="store_true", help="List detected ability folders")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat missing manual confirmations as failures",
    )
    parser.add_argument(
        "--confirm-pr-target-dev",
        action="store_true",
        help="Confirm the PR target branch is dev",
    )
    parser.add_argument(
        "--confirm-live-editor",
        action="store_true",
        help="Confirm code has run in the OpenHome Ability Editor",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    repo_root = Path(args.repo_root).expanduser().resolve()
    ability_root = choose_ability_root(repo_root, args.ability_root)

    if args.list:
        for path in iter_abilities(repo_root, ability_root, []):
            print(path.name)
        return 0

    abilities = iter_abilities(repo_root, ability_root, args.abilities)
    if not abilities:
        print(f"no abilities found in {ability_root}", file=sys.stderr)
        return 1

    totals = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for ability_path in abilities:
        reporter = check_ability(repo_root, ability_path, args)
        reporter.emit(rel(ability_path, repo_root))
        for status in totals:
            totals[status] += reporter.count(status)

    print(
        "\nSummary: "
        f"{totals['PASS']} passed, {totals['WARN']} warnings, {totals['FAIL']} failures"
    )
    return 1 if totals["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
