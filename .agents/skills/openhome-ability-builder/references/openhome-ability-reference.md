# OpenHome Ability Reference

Checked against OpenHome docs on 2026-06-29:

- https://docs.openhome.com/ability
- https://docs.openhome.com/building-abilities/how-to-build
- https://docs.openhome.com/api-sdk/sdk-reference
- https://docs.openhome.com/background-abilities
- https://docs.openhome.com/local-ability
- https://docs.openhome.com/building-abilities/templates
- https://docs.openhome.com/api-sdk/endpoints/upload-ability

Use the live docs when API or dashboard labels matter. Local repo docs may lag the product.

## Category Decision

| Need | Category | Files | Notes |
| --- | --- | --- | --- |
| Run only when the user explicitly asks | `Skill` | `main.py` | Trigger-word-driven one-shot task. |
| Let the agent choose a tool/action | `Brain Skill` / `Agent Controlled` | `main.py` | OpenHome naming has drifted; verify current UI labels. |
| Keep watching while the conversation continues | `Background Daemon` | `background.py`, optionally `main.py` | Auto-starts with the agent/session. |
| Use DevKit hardware, local files, shell, OS, or DevKit Python packages | `Local` | `main.py`, `devkit_functions.py`, optional `requirements.txt` | Live Editor simulation is not enough; verify on real DevKit when possible. |

Default to `Skill` for simple prototypes. Use `Background Daemon` only when the ability must act without a direct user utterance. Use `Local` only when standard runtime APIs cannot do the job.

## Repo Layout

Expected layout in this repo:

```text
abilities/
  ability-slug/
    __init__.py
    README.md
    main.py
    background.py          # only for background behavior
    config.py              # for editable setup
    devkit_functions.py    # only for Local abilities
    requirements.txt       # only for DevKit-side Python deps
dist/
  ability-slug.zip
scripts/
  package-abilities.sh
```

Package from the repo root:

```bash
./scripts/package-abilities.sh ability-slug
python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py ability-slug
```

The zip must contain one top-level directory:

```text
ability-slug/
ability-slug/__init__.py
ability-slug/main.py
```

Loose files at zip root are invalid.

## One-Shot main.py Pattern

Use this pattern for `Skill` and most `Brain Skill` / `Agent Controlled` abilities:

```python
from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


class ExampleCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None

    #{{register capability}}

    async def run(self):
        try:
            await self.capability_worker.speak("Ability completed.")
        except Exception as error:
            self.worker.editor_logging_handler.error(
                f"ExampleCapability failed: {error}"
            )
            await self.capability_worker.speak("The ability encountered an error.")
        finally:
            self.capability_worker.resume_normal_flow()

    def call(self, worker: AgentWorker):
        self.worker = worker
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.run())
```

Rules:

- Leave `#{{register capability}}` in place.
- Assign `self.worker` before constructing `CapabilityWorker(self)`.
- Start async work through `self.worker.session_tasks.create(...)`.
- Call `resume_normal_flow()` in every completion path.
- Keep spoken output short and assistant-like. Avoid pretending to be the user, streamer, or device.

## Background Daemon Pattern

`background.py` is a fixed filename. Use this shape:

```python
from src.agent.capability import MatchingCapability
from src.agent.capability_worker import CapabilityWorker
from src.main import AgentWorker


class WatcherCapability(MatchingCapability):
    worker: AgentWorker = None
    capability_worker: CapabilityWorker = None
    background_daemon_mode: bool = False

    #{{register capability}}

    async def watch(self):
        self.worker.editor_logging_handler.info("watcher started")

        while True:
            try:
                # monitor, poll, or update state here
                await self.worker.session_tasks.sleep(30.0)
            except Exception as error:
                self.worker.editor_logging_handler.error(f"watcher failed: {error}")
                await self.worker.session_tasks.sleep(30.0)

    def call(self, worker: AgentWorker, background_daemon_mode: bool):
        self.worker = worker
        self.background_daemon_mode = background_daemon_mode
        self.capability_worker = CapabilityWorker(self)
        self.worker.session_tasks.create(self.watch())
```

Rules:

- Do not use `asyncio.sleep(...)`.
- Use a conservative poll interval, usually 10-30 seconds or more.
- Log enough state for Live Editor debugging.
- If the daemon needs to speak, interrupt first:

```python
await self.capability_worker.send_interrupt_signal()
await self.capability_worker.speak("Notification text.")
```

## Local DevKit Pattern

`main.py` calls DevKit-side functions:

```python
result = await self.capability_worker.send_devkit_capability_action(
    function_name="ping",
    args=[],
    timeout=5,
)
```

`devkit_functions.py` runs on the DevKit and must print data:

```python
import json
import sys


def _print_payload(payload):
    print(json.dumps(payload))


def ping():
    _print_payload({"success": True, "spoken_response": "DevKit is reachable."})


FUNCTION_REGISTRY = {
    "ping": ping,
}


if __name__ == "__main__":
    function_name = sys.argv[1]
    FUNCTION_REGISTRY[function_name](*sys.argv[2:])
```

Rules:

- `args` arrive as strings; parse numbers, booleans, or JSON explicitly.
- Python return values do not reach `main.py`; print JSON.
- `requirements.txt` applies to DevKit-side code, not standard runtime `main.py`.
- Hardware failures and missing devices must be handled with `try/except`.

## config.py Convention

Use `config.py` when the user will edit setup values, prompts, endpoint URLs, thresholds, or placeholder credentials. Keep real secrets out of the repo.

Good candidates:

- OAuth client IDs, client secrets, and refresh tokens as placeholders only.
- Poll intervals and feature toggles.
- Speech templates and system prompts.
- API endpoint constants.

Runtime code should import `config as ability_config` and read through helpers where validation or placeholder handling matters.

## Verification

Minimum checks for a standard ability:

```bash
python3 .agents/skills/openhome-ability-builder/scripts/validate_openhome_ability.py ability-slug --repo-root .
./scripts/package-abilities.sh ability-slug
unzip -Z1 dist/ability-slug.zip
```

Add targeted checks as appropriate:

- Background daemon: inspect logs, confirm `session_tasks.sleep(...)`, and avoid duplicate speech loops.
- Local ability: test `devkit_functions.py` directly when possible, then verify on real DevKit.
- External API ability: test failure paths without live credentials and scan for secrets.
- Refactor: preserve `resume_normal_flow()`, `send_interrupt_signal()`, and existing setup files.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| `Expected a single top-level directory in ability zipfile` | Zip root contains loose files | Package the enclosing folder, not its contents. |
| Trigger word does nothing | Ability disabled, missing trigger, or not assigned to agent | Check dashboard enablement and agent matching capabilities. |
| Agent does not return to normal conversation | Missing `resume_normal_flow()` | Add it in `finally` in `main.py`. |
| Background daemon will not start | Wrong filename or call signature | Use `background.py` and `call(self, worker, background_daemon_mode)`. |
| Daemon cleanup behaves badly | Used `asyncio.sleep(...)` | Use `self.worker.session_tasks.sleep(...)`. |
| Daemon speech overlaps personality speech | Missing interrupt | Call `send_interrupt_signal()` before `speak(...)`. |
| Local function output is empty | Used Python `return` | Print JSON from `devkit_functions.py`. |
| Local dependency missing | Dependency installed in wrong runtime | Put DevKit-side deps in `requirements.txt`; keep standard runtime imports minimal. |
