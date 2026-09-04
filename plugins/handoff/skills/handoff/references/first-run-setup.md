# First-run setup

When the user first triggers this skill, their `CLAUDE.md` may not yet contain the configuration block this skill reads from. This reference describes how the skill detects that case and guides the user through a lightweight setup.

The skill never edits `CLAUDE.md` directly. It produces a ready-to-paste snippet and asks the user to add it themselves. This avoids surprising file edits and keeps the user in full control.

## When this step runs

Only run first-run setup **after the handoff is confirmed to proceed** — meaning the user triggered the handoff directly, or the AI suggested it in Step 0.5 and the user agreed. If Step 0.5 ends with the user choosing `/clear` or a new conversation instead of a handoff, skip first-run setup entirely.

## Detection

Resolve which `CLAUDE.md` files exist for this user:

1. Global: `~/.claude/CLAUDE.md` (always check)
2. Project: `<WORKSPACE_ROOT>/CLAUDE.md` if a workspace root was inferred from conversation context or `pwd`

Then grep those files for the declaration form (match at line start, allowing bullet or whitespace):

```bash
grep -lE '^[[:space:]]*[-*]?[[:space:]]*WORKSPACE_ROOT[[:space:]]*:' \
  ~/.claude/CLAUDE.md \
  "$WORKSPACE_ROOT/CLAUDE.md" 2>/dev/null
```

- Match found → configuration exists, skip setup, proceed to Step 1.
- No match → first-run detected, offer the user two options (see below).

Why the anchored pattern: matching a bare `WORKSPACE_ROOT` string would false-positive on unrelated code examples, comments, or another skill's config. The `^...WORKSPACE_ROOT:` pattern targets only the declaration form documented in `user-config.md`.

The detection only looks at the key name `WORKSPACE_ROOT`. If the user has declared the other optional variables without `WORKSPACE_ROOT`, treat it as incomplete config and still offer setup.

## Two options at first run

Present the user with a short choice, then act on their reply:

```
This looks like the first time you're using the handoff skill. I can either:

  (1) Walk you through a 3-question setup and hand you a snippet to paste into CLAUDE.md.
  (2) Use sensible defaults for this session — the skill will infer workspace root from context and save to <workspace>/_handoffs/.

Which would you like?
```

If the user picks (2) or says "skip" / "use defaults" / "just do it" — proceed to Step 1 with defaults. Do not block the handoff.

If the user picks (1) — run the three questions below.

## Three questions

Ask one at a time, waiting for each answer:

1. **Workspace root.** "What's the main workspace path you'll use this skill from? (for example `~/work/` or `~/research/`)"
2. **Handoff directory.** "Where should handoff documents be saved? Press enter to accept `<WORKSPACE_ROOT>/_handoffs/`."
3. **Extra trigger phrases (optional).** "Besides the defaults, do you want any extra phrases to trigger this skill? Leave blank to skip."

Note: there is a single `handoff` skill; the Chinese and English trigger phrases both fire it (the `handoff-zh` twin was retired in v3.0.0). Question 3 only adds **extra** trigger phrases on top of the built-in ones. Output language follows the user's `CLAUDE.md`, not the phrase that triggered the skill.

Do not ask about `TEMPLATE_PATH`, `ACTION_TRACKER`, or `CENTRAL_HANDOFF_INDEX` here. Those are advanced options documented in `user-config.md` — the user can add them later.

## Produce the snippet

After collecting answers, generate a plain-text markdown snippet and present it in the chat. Do not write to `CLAUDE.md` directly.

Example output (no extra triggers):

```markdown
## Handoff skill configuration

- WORKSPACE_ROOT: ~/work/
- HANDOFF_DIR: <WORKSPACE_ROOT>/_handoffs/
```

Example output (user added extra triggers):

```markdown
## Handoff skill configuration

- WORKSPACE_ROOT: ~/research/
- HANDOFF_DIR: <WORKSPACE_ROOT>/_handoffs/
- TRIGGER_PHRASES: [ship it, end session]
```

Tell the user:

1. Where to paste it — usually `~/.claude/CLAUDE.md` (global) or `<WORKSPACE_ROOT>/CLAUDE.md` (project).
2. That the skill will pick it up automatically from the next invocation onward.
3. That advanced options (template, action tracker, central index) are documented in `references/user-config.md` if they want them later.

## Proceed with the current handoff

After the snippet is delivered, continue with the handoff using the values the user just provided for *this session*. The user does not need to finish editing `CLAUDE.md` before the current handoff runs.

This means first-run setup costs one extra exchange at the beginning and zero extra exchanges thereafter.
