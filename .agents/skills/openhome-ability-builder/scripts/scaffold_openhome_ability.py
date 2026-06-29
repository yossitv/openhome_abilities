#!/usr/bin/env python3
"""Scaffold an OpenHome ability folder."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


KIND_CHOICES = ("skill", "brain", "background", "combined", "local")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower())
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    if not slug:
        raise ValueError("ability name must contain at least one letter or digit")
    return slug


def class_base(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("-"))


def py_string(value: str) -> str:
    return repr(value)


def write_file(path: Path, content: str, *, force: bool, dry_run: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"{path} already exists; use --force to overwrite")
    if dry_run:
        print(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def readme_template(display_name: str, slug: str, kind: str, description: str) -> str:
    return f"""# {display_name}

{description}

## OpenHome settings

| Field | Value |
| --- | --- |
| Name | {display_name} |
| Category | {kind} |
| Trigger Words | TODO |

## Development

Package from the repo root:

```bash
./scripts/package-abilities.sh {slug}
```
"""


def main_template(class_name: str, spoken_success: str) -> str:
    return f'''from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


class {class_name}Capability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None

    #{{{{register capability}}}}

    async def run(self):
        try:
            await self.capability_worker.speak({py_string(spoken_success)})
        except Exception as error:
            self.worker.editor_logging_handler.error(
                f"{class_name}Capability failed: {{error}}"
            )
            await self.capability_worker.speak(
                "The ability encountered an error."
            )
        finally:
            self.capability_worker.resume_normal_flow()

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.run())
'''


def config_template() -> str:
    return '''"""User-editable setup for this OpenHome ability."""

# Keep real secrets out of git. Store placeholders here and prefer dashboard or
# environment-provided values when OpenHome supports them.
PLACEHOLDER_VALUES = {"", "replace-me", "TODO"}


SPEECH = {
    "setup_error": "The ability encountered an error.",
}


def is_placeholder(value):
    return value is None or str(value).strip() in PLACEHOLDER_VALUES
'''


def background_template(class_name: str, slug: str) -> str:
    return f'''from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


class {class_name}Background(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    background_daemon_mode: bool = False

    #{{{{register capability}}}}

    async def watch(self):
        self.worker.editor_logging_handler.info("{slug} background daemon started")

        while True:
            try:
                # TODO: Monitor external state, update files, or notify the user.
                await self.worker.session_tasks.sleep(30.0)
            except Exception as error:
                self.worker.editor_logging_handler.error(
                    f"{class_name}Background failed: {{error}}"
                )
                await self.worker.session_tasks.sleep(30.0)

    def call(self, worker: AgentWorker, background_daemon_mode: bool):
        self.worker = worker
        self.background_daemon_mode = background_daemon_mode
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.watch())
'''


def local_main_template(class_name: str) -> str:
    return f'''import json

from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


class {class_name}Capability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None

    #{{{{register capability}}}}

    async def run(self):
        try:
            result = await self.capability_worker.send_devkit_capability_action(
                function_name="ping",
                args=[],
                timeout=5,
            )
            payload = self._parse_payload(result)
            if payload.get("success"):
                await self.capability_worker.speak(
                    payload.get("spoken_response") or "DevKit action completed."
                )
            else:
                await self.capability_worker.speak(
                    payload.get("error") or "DevKit action failed."
                )
        except Exception as error:
            self.worker.editor_logging_handler.error(
                f"{class_name}Capability failed: {{error}}"
            )
            await self.capability_worker.speak(
                "The local ability encountered an error."
            )
        finally:
            self.capability_worker.resume_normal_flow()

    def _parse_payload(self, result):
        output = (result or {{}}).get("output") or "{{}}"
        try:
            return json.loads(output)
        except ValueError:
            return {{"success": False, "error": "DevKit returned invalid output."}}

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.run())
'''


def devkit_functions_template() -> str:
    return '''import json
import sys

try:
    from devkit_utils.devkit_logging import web_logger as log
except Exception:  # Allows direct local smoke tests outside the DevKit.
    log = None


def _print_payload(payload):
    output = json.dumps(payload)
    if log:
        log.info("stdout payload: %s", output)
    print(output)


def ping():
    _print_payload({
        "success": True,
        "spoken_response": "DevKit is reachable.",
        "error": None,
    })


FUNCTION_REGISTRY = {
    "ping": ping,
}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        _print_payload({"success": False, "error": "Missing function name."})
        sys.exit(1)

    function_name = sys.argv[1]
    function = FUNCTION_REGISTRY.get(function_name)
    if not function:
        _print_payload({"success": False, "error": f"Unknown function: {function_name}"})
        sys.exit(1)

    function(*sys.argv[2:])
'''


def create_files(args: argparse.Namespace) -> list[Path]:
    slug = args.slug or slugify(args.name)
    display_name = args.display_name or " ".join(part.capitalize() for part in slug.split("-"))
    description = args.description or "TODO: Describe what this OpenHome ability does."
    class_name = class_base(slug)
    ability_dir = Path(args.repo_root).expanduser().resolve() / "abilities" / slug

    files: dict[str, str] = {
        "__init__.py": "",
        "README.md": readme_template(display_name, slug, args.kind, description),
    }

    if args.kind in {"skill", "brain", "combined"}:
        files["main.py"] = main_template(class_name, args.spoken_success)
    elif args.kind == "local":
        files["main.py"] = local_main_template(class_name)

    if args.kind in {"background", "combined"}:
        files["background.py"] = background_template(class_name, slug)

    if args.kind == "local":
        files["devkit_functions.py"] = devkit_functions_template()
        files["requirements.txt"] = "# Add DevKit-side Python dependencies here.\n"

    if args.with_config:
        files["config.py"] = config_template()

    written = []
    for relative_path, content in files.items():
        path = ability_dir / relative_path
        write_file(path, content, force=args.force, dry_run=args.dry_run)
        written.append(path)
    return written


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Ability display name or slug")
    parser.add_argument("--repo-root", default=".", help="Repository root containing abilities/")
    parser.add_argument("--kind", choices=KIND_CHOICES, default="skill")
    parser.add_argument("--slug", help="Override generated slug")
    parser.add_argument("--display-name", help="OpenHome dashboard display name")
    parser.add_argument("--description", help="Short README description")
    parser.add_argument(
        "--spoken-success",
        default="The OpenHome ability is working.",
        help="Default success line for generated main.py",
    )
    parser.add_argument(
        "--with-config",
        action="store_true",
        help="Add config.py for user-editable setup",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--dry-run", action="store_true", help="Print files without writing")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    try:
        written = create_files(args)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if not args.dry_run:
        for path in written:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
