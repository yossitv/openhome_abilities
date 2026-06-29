---
name: openhome-skill-checker
description: Check OpenHome Ability folders against the community pre-PR checklist. Use when the user asks for an OpenHome skill checker/chacker, Ability checker, PR readiness check, community checklist check, or wants confidence before submitting an OpenHome Ability PR.
---

# OpenHome Skill Checker

Use this skill to run the OpenHome community pre-PR checklist against one or more Ability folders.

## Workflow

1. Identify the repository root and Ability folder:
   - This repo uses `abilities/<slug>/`.
   - Upstream `openhome-dev/abilities` uses `community/<slug>/`.
   - The bundled checker detects `abilities/` first, then `community/`.
2. Package the Ability first when the repo has a packaging script:
   ```bash
   ./scripts/package-abilities.sh <ability-slug>
   ```
   Skip this only when the target repo has no packaging script or the user asks for static checks only.
3. Run the bundled checker from the repository root:
   ```bash
   python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py <ability-slug>
   ```
4. For a final PR gate, use strict mode after the human confirmations are true:
   ```bash
   python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py <ability-slug> \
     --strict \
     --confirm-pr-target-dev \
     --confirm-live-editor
   ```
5. Read every `FAIL` and fix the Ability before saying it is PR-ready. Treat `WARN` as a manual verification item; do not claim it is fully complete unless the warning has been addressed or explicitly accepted.

## Checklist Coverage

The checker maps the upstream community checklist to local evidence:

- `MatchingCapability`: `main.py` and `background.py` entrypoint classes must extend `MatchingCapability`.
- Register boilerplate: entrypoints must include `#{{register_capability}}` or the existing OpenHome variant `#{{register capability}}`.
- Normal flow: `main.py` should call `resume_normal_flow()` from a `finally` block in `run()`.
- Logging: runtime files must not call `print()`; use `worker.editor_logging_handler`. `devkit_functions.py` prints are warned because Local Abilities may need stdout return data.
- Secrets: common API key, token, and private-key patterns are rejected.
- Requests timeout: detected `requests.*()` calls must include `timeout=`.
- README: `README.md` must include a description and suggested trigger words.
- PR target: strict mode requires `--confirm-pr-target-dev` or `OPENHOME_ABILITY_PR_TARGET=dev`.
- OpenHome Ability Editor: strict mode requires `--confirm-live-editor` or `OPENHOME_ABILITY_LIVE_EDITOR_RUN=1`.
- Zip layout: when `dist/<slug>.zip` exists, it must contain one top-level directory named `<slug>/`.

## Commands

List detected abilities:

```bash
python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py --list
```

Check all detected abilities:

```bash
python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py
```

Check an upstream checkout that uses `community/` explicitly:

```bash
python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py \
  --repo-root /path/to/abilities \
  --ability-root community \
  <ability-slug>
```

## Reporting

In the final response, include:

- Ability folder(s) checked.
- Whether strict mode was used.
- Count of passes, warnings, and failures.
- Any remaining manual items, especially PR target `dev` and Ability Editor execution.
