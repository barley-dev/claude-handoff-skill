# handoff plugin

Hands a conversation off to the next session, and keeps a central queue of handoffs waiting to be picked up.

## What's in it

| Path | What |
|---|---|
| `skills/handoff/` | Write the handoff document, print the copy-paste message, append to the queue, rebuild the index |
| `skills/pending-review/` | Review the queue itself: group, show dependencies, propose retirements |
| `tools/pending_index.py` | Generates the clickable index inside the queue file (idempotent; `--check` for CI) |

Two skills, not one, because "I'm wrapping up" and "I want to tidy up" are different moments. Merging them would force a handoff just to sort a list.

## Install

```
/plugin marketplace add <this repo>
/plugin install handoff
```

Or symlink it into `~/.claude/plugins/` for local use.

## Configure

Everything is optional — with no configuration the skill infers the workspace from the conversation and writes to `<WORKSPACE_ROOT>/_handoffs/`.

To pin it down, add to your `CLAUDE.md`:

```markdown
## Handoff skill configuration

- WORKSPACE_ROOT: ~/your-vault/
- HANDOFF_DIR: <WORKSPACE_ROOT>/_handoffs/
- PENDING_FILE: <WORKSPACE_ROOT>/_harness/handoffs/pending.md
```

Full list of variables: `skills/handoff/references/user-config.md`.

`tools/pending_index.py` resolves its target in this order: `--path` → `$PENDING_FILE` → `$CLAUDE_DATA_ROOT/_harness/handoffs/pending.md` → `_harness/handoffs/pending.md` relative to the working directory. It never guesses a vault name; if none of those resolve, it exits with the two commands you could run instead.

### Optional: topic grouping

The index groups entries by topic. Grouping rules are yours, not the plugin's — put them in `_topics.json` **beside** your pending file:

```json
[
  {"name": "Teaching",  "keywords": ["course", "grading"], "prefixes": ["Courses/"]},
  {"name": "Tooling",   "keywords": ["script", "pipeline"], "prefixes": ["Tools/"]}
]
```

`keywords` match the entry title, `prefixes` match its workspace path; title matches win. Without this file every entry lands in "other" and the index still works — you just get one flat group. A malformed file warns and falls back to no grouping rather than failing the handoff.

## Queue layout

```
<PENDING_DIR>/
├── pending.md          # waiting to be picked up, newest first, with a generated index
├── _format.md          # optional; if present it overrides the entry template in SKILL.md
└── archive/YYYY-MM.md  # left the queue, each tagged completed / superseded / dropped
```

An entry leaves the queue with a **reason**, never just "started": `completed`, `superseded`, or `dropped`. Starting is not leaving — if a session finishes only part of an entry, the old one is archived as `superseded` and the remainder goes back into the queue as a new entry.

## First run

If `PENDING_FILE` doesn't exist, the skill asks before creating anything (`skills/handoff/references/pending-file-setup.md`). Already have your own queue layout? Point `PENDING_FILE` at it and the setup step is skipped — the structure is a default, not a requirement.

At first run, the skill also mentions — once, in passing, never blocking — that a visible session label in your status line makes cross-session messaging (`ListAgents`/`SendMessage`) much easier to route, since a terminal tab or a two-character harness name doesn't say what a session is doing. This is unrelated to the handoff flow itself and has no bundled implementation (status lines are too personal to standardize); see `skills/handoff/references/session-identifier.md` for the general shape if you want to build one.

## Built-in completion gate

Before recording anything as done, the skill runs `ls`/`grep` to confirm the artifact exists and pastes the command output into the handoff. Chronology, self-declarations, and filenames are not evidence. This lives in the skill rather than in a user's `CLAUDE.md` because a handoff that misreports finished work causes the next session to skip real work.

## Version

v3.0.0 (2026-09-03) — merged the former `handoff` + `handoff-zh` pair into one skill. They differed only in prose language and all seven `references/` files were byte-identical; a skill instructs the model, so it needs no translated twin. Output language follows the user's `CLAUDE.md`.
