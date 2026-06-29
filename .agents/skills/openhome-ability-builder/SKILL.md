---
name: openhome-ability-builder
description: Build, scaffold, package, validate, and troubleshoot OpenHome Abilities in openhome_abilities or similar repos. Use when creating or modifying an OpenHome Ability, choosing Skill, Brain Skill or Agent Controlled, Background Daemon, or Local architecture, writing main.py, background.py, devkit_functions.py, config.py, creating upload zip files, or debugging OpenHome trigger, runtime, packaging, or DevKit sync issues.
---

# OpenHome Ability Builder

Use this skill to turn an OpenHome Ability idea into a repo-ready ability folder and uploadable zip. Prefer the target repo's existing conventions over generic templates.

## Workflow

1. Inspect the target repo before editing:
   - In `openhome_abilities`, check `abilities/`, `docs/README.md`, and `scripts/package-abilities.sh` when relevant.
   - Preserve existing user changes and repo-specific naming.
2. Classify the ability before writing code:
   - `Skill`: user-invoked, one-shot behavior.
   - `Brain Skill` / `Agent Controlled`: agent-invoked tool behavior. OpenHome docs and dashboard labels may differ; treat these as the same design family unless the current UI/API proves otherwise.
   - `Background Daemon`: session-start watcher or poller. Requires `background.py`.
   - `Local`: DevKit-side hardware, shell, filesystem, or local Python work. Requires `devkit_functions.py`, usually with `main.py`.
3. For a new ability, scaffold first unless the repo already has a closer local template:
   ```bash
   python3 .agents/skills/openhome-ability-builder/scripts/scaffold_openhome_ability.py "Ability Name" --repo-root . --kind skill
   ```
4. Implement the smallest complete behavior:
   - Keep user-editable constants, prompts, endpoints, and placeholder credentials in `config.py` when there is meaningful setup.
   - Keep `main.py` focused on user interaction and OpenHome runtime calls.
   - Keep `background.py` focused on long-running monitoring.
   - Keep `devkit_functions.py` focused on DevKit-side effects and machine-readable stdout.
5. Validate before claiming completion:
   ```bash
   python3 .agents/skills/openhome-ability-builder/scripts/validate_openhome_ability.py ability-slug --repo-root .
   ./scripts/package-abilities.sh ability-slug
   unzip -Z1 dist/ability-slug.zip
   ```

## Required Patterns

- Ability folders live under `abilities/<slug>/` in this repo.
- Upload zips must contain exactly one top-level directory named `<slug>/`.
- `main.py` exit paths must call `resume_normal_flow()`, preferably in `finally`.
- Create async work with `self.worker.session_tasks.create(...)`.
- Background daemons must expose `call(self, worker, background_daemon_mode)`.
- Background daemons must use `self.worker.session_tasks.sleep(...)`, not `asyncio.sleep(...)`.
- Daemons that speak should call `send_interrupt_signal()` before `speak(...)`.
- Local DevKit functions must be registered in `FUNCTION_REGISTRY`.
- Local DevKit functions return data by printing stdout; Python return values are not sent back to `main.py`.
- Do not commit real API keys, OAuth refresh tokens, client secrets, or private keys.

## Resource Routing

- Read `.agents/skills/openhome-ability-builder/references/openhome-ability-reference.md` for detailed category decisions, runtime templates, packaging rules, and troubleshooting.
- Use `.agents/skills/openhome-ability-builder/scripts/scaffold_openhome_ability.py` to create a new ability skeleton.
- Use `.agents/skills/openhome-ability-builder/scripts/validate_openhome_ability.py` for local structural checks before packaging or review.

## Verification Checklist

Run the checks that match the change:

- `python3 .agents/skills/openhome-ability-builder/scripts/validate_openhome_ability.py <slug> --repo-root <repo>` from this repository root
- `./scripts/package-abilities.sh <slug>` from the target repo
- `unzip -Z1 dist/<slug>.zip` and confirm all entries start with `<slug>/`
- Secret scan with `rg -n "AIza|ya29\\.|1//|sk-[A-Za-z0-9]|BEGIN PRIVATE KEY|client_secret|refresh_token" abilities/<slug>`

For Local abilities, state clearly when real DevKit verification was not possible. For Background daemons, preserve OpenHome lifecycle behavior even when refactoring.
