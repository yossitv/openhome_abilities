---
name: openhome-ability-publisher
description: Prepare and submit OpenHome Ability pull requests to openhome-dev/abilities community on the dev branch. Use when the user wants to publish, submit, PR, or upstream an OpenHome Ability, especially to https://github.com/openhome-dev/abilities/tree/dev/community. Always run the OpenHome checker first and ask for explicit confirmation before creating the PR.
---

# OpenHome Ability Publisher

Use this skill to move an Ability toward an upstream PR at `openhome-dev/abilities`, targeting `dev`, with files under `community/<ability-slug>/`.

## Hard Rules

- Run `$openhome-skill-checker` before any PR creation step.
- Do not create a PR until the checker has no `FAIL` results.
- Do not create a PR until you show the PR plan and the user explicitly confirms.
- Treat PR creation, pushing, branch changes, and remote setup as side-effectful git operations; report what will happen before doing them.
- Target `https://github.com/openhome-dev/abilities/tree/dev/community` only, unless the user explicitly names another target.

## Workflow

1. Identify the Ability slug and source directory.
   - In this repo, source folders usually live at `abilities/<slug>/`.
   - In an upstream checkout, source folders live at `community/<slug>/`.
   - If the user does not name a slug, list candidate folders and choose only when unambiguous.
2. Read and run the checker.
   - Read `.agents/skills/openhome-skill-checker/SKILL.md` before using its script.
   - Package first when the current repo has `./scripts/package-abilities.sh`.
   - Run from this repository root:
     ```bash
     python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py <ability-slug>
     ```
   - For the final gate, run strict mode only after the manual facts are true:
     ```bash
     python3 .agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py <ability-slug> \
       --strict \
       --confirm-pr-target-dev \
       --confirm-live-editor
     ```
3. Fix or stop on checker results.
   - Any `FAIL`: fix the Ability or report exactly what blocks publishing.
   - Any `WARN`: resolve it, or ask the user to explicitly accept the risk before continuing.
   - Missing OpenHome Ability Editor execution is not something Codex can infer; ask the user to confirm it when needed.
4. Prepare the upstream PR workspace.
   - Confirm the target repository is `openhome-dev/abilities` or a fork configured to push a PR there.
   - Confirm the base branch is `dev`.
   - If the current repo is not the upstream/fork checkout, ask for or use the known upstream checkout path; do not pretend this local repo can PR to upstream by itself.
   - Copy the Ability folder to `community/<ability-slug>/`.
   - Do not copy generated junk: `__pycache__/`, `.DS_Store`, local state files, `.env`, zip files, or real credentials.
5. Re-run the checker in the PR workspace:
   ```bash
   python3 /path/to/this-repo/.agents/skills/openhome-skill-checker/scripts/check_openhome_ability.py \
     --repo-root /path/to/openhome-dev-abilities \
     --ability-root community \
     <ability-slug>
   ```
6. Present a PR confirmation summary and stop.
   - Include source folder, target repo, base branch `dev`, target folder `community/<slug>/`, checker result counts, files to commit, proposed branch name, proposed PR title, and any manual confirmations.
   - Ask one direct question: whether to create the PR.
7. Only after explicit confirmation, create the branch/commit/push/PR.
   - Use a branch like `codex/<ability-slug>-community`.
   - Commit only intended Ability files.
   - Follow the active repo's commit-message rules.
   - Create the PR with base `dev`.

## PR Body Template

Use a concise PR body:

```markdown
## Summary
- Add `<ability-slug>` community Ability.
- Include README with description and trigger words.

## Verification
- Ran OpenHome checker: `<pass-count>` passed, `<warning-count>` warnings, `<failure-count>` failures.
- Confirmed PR target branch: `dev`.
- Confirmed OpenHome Ability Editor run: `<yes/no/user-confirmed>`.

## Notes
- `<manual notes or omitted if none>`
```

## Reporting

When done, report:

- Checker command and result.
- Whether PR creation was only prepared or actually completed.
- PR URL if created.
- Any remaining manual or repository setup blockers.
