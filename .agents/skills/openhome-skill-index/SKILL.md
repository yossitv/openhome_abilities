---
name: openhome-skill-index
description: First-stop index for OpenHome-related Codex skills in this repository. Use when choosing which OpenHome skill to read first, recording or updating skill reference paths, auditing the OpenHome skill set, or managing the relationship between openhome-ability-builder, openhome-skill-checker, openhome-ability-publisher, and future OpenHome skills.
---

# OpenHome Skill Index

Use this skill first when the task is about OpenHome skills themselves, or when it is unclear which OpenHome skill should be loaded next.

## Skill Map

| Need | Read this skill first | Key references |
| --- | --- | --- |
| Build, scaffold, package, or troubleshoot an OpenHome Ability | `.agents/skills/openhome-ability-builder/SKILL.md` | `.agents/skills/openhome-ability-builder/references/openhome-ability-reference.md`, `.agents/skills/openhome-ability-builder/scripts/scaffold_openhome_ability.py`, `.agents/skills/openhome-ability-builder/scripts/validate_openhome_ability.py`, `scripts/package-abilities.sh` |
| Check an Ability against the community pre-PR checklist | `.agents/skills/openhome-skill-checker/SKILL.md` | `.agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py` |
| Prepare an Ability for an upstream PR to `openhome-dev/abilities` `community/` | `.agents/skills/openhome-ability-publisher/SKILL.md` | Requires `openhome-skill-checker` before PR steps |
| Decide which OpenHome skill to use, or update this skill registry | `.agents/skills/openhome-skill-index/SKILL.md` | This file |

## Routing Rules

- For code or packaging work, load `openhome-ability-builder`.
- For PR-readiness checks, load `openhome-skill-checker`.
- For publishing/upstream PR work, load `openhome-ability-publisher`, then follow its requirement to run `openhome-skill-checker`.
- For skill maintenance, load this index first, then the specific skill being changed.

## Reference Update Protocol

When adding or changing an OpenHome-related skill:

1. Update the `Skill Map` row or add a new row.
2. Record the most important `SKILL.md`, script, and reference paths.
3. Keep this index lean; do not duplicate full workflow details from the target skill.
4. Validate the changed skill and this index with:
   ```bash
   python3 /Users/ys/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/<skill-name>
   python3 /Users/ys/.codex/skills/.system/skill-creator/scripts/quick_validate.py .agents/skills/openhome-skill-index
   ```

## Naming Guidance

Prefer `openhome-skill-index` for the first-stop registry because `index` clearly means "look here first for references." Use narrower names for action skills:

- `openhome-ability-builder` for implementation.
- `openhome-skill-checker` for checklist validation.
- `openhome-ability-publisher` for upstream PR preparation.
