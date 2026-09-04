# Claude Handoff Plugin

A Claude Code plugin that compresses a long conversation into a **handoff document** the next session can resume from — plus a central queue of handoffs waiting to be picked up, with a clickable index.

Triggers in English and Chinese: `handoff`, `wrap up`, `session end`, `交接`, `開始交接`, `準備交接`, `寫交接` — one skill handles both.

## What's in it

| Path | What |
|---|---|
| `plugins/handoff/skills/handoff/` | Write the handoff document, print the copy-paste handoff message, append to the queue, rebuild the index |
| `plugins/handoff/skills/pending-review/` | Review the queue itself: group by topic, show dependencies, propose retirements |
| `plugins/handoff/tools/pending_index.py` | Generates the clickable index inside the queue file (idempotent; `--check` and `--audit`) |

Two skills, not one, because "I'm wrapping up" and "I want to tidy up" are different moments. Merging them would force a handoff just to sort a list.

## Install

```
/plugin marketplace add barley-dev/claude-handoff-skill
/plugin install handoff@claude-handoff
```

If the install summary says `Run /reload-plugins to activate`, run that. Already-running sessions do not pick up a new plugin until they reload or restart.

## Configure

Everything is optional. With no configuration the skill infers the workspace from the conversation and writes handoff documents to `<WORKSPACE_ROOT>/_handoffs/`.

To pin it down, add to your `CLAUDE.md`:

```markdown
## Handoff skill configuration

- WORKSPACE_ROOT: ~/your-vault/
- HANDOFF_DIR: <WORKSPACE_ROOT>/_handoffs/
- PENDING_FILE: <WORKSPACE_ROOT>/_harness/handoffs/pending.md
```

Full variable list: `plugins/handoff/skills/handoff/references/user-config.md`.

`tools/pending_index.py` resolves its target in this order: `--path` → `$PENDING_FILE` → `$CLAUDE_DATA_ROOT/_harness/handoffs/pending.md` → `_harness/handoffs/pending.md` relative to the working directory. It never guesses a vault name; if none resolve, it exits with the commands you could run instead.

### Optional: topic grouping

The index groups entries by topic. The rules are yours, not the plugin's — put them in `_topics.json` **beside** your pending file:

```json
[
  {"name": "Teaching", "keywords": ["course", "grading"], "prefixes": ["Courses/"]},
  {"name": "Tooling",  "keywords": ["script", "pipeline"], "prefixes": ["Tools/"]}
]
```

`keywords` match the entry title, `prefixes` match its workspace path; title matches win. Without this file every entry lands in "other" and the index still works — you just get one flat group.

## Queue layout

```
<PENDING_DIR>/
├── pending.md          # waiting to be picked up, newest first, with a generated index
├── _format.md          # optional; if present it overrides the entry template in SKILL.md
├── _topics.json        # optional; topic grouping rules
└── archive/YYYY-MM.md  # left the queue, each tagged completed / superseded / dropped
```

An entry leaves the queue with a **reason**, never just "started": `completed`, `superseded`, or `dropped`. Starting is not leaving — if a session finishes only part of an entry, the old one is archived as `superseded` and the remainder goes back into the queue as a new entry.

## Built-in completion gate

Before recording anything as done, the skill runs `ls`/`grep` to confirm the artifact exists and pastes the command output into the handoff. Chronology, self-declarations, and filenames are not evidence. This lives in the skill rather than in a user's `CLAUDE.md` so that anyone installing it gets the guarantee.

## Verifying the index

```bash
python3 plugins/handoff/tools/pending_index.py --check   # is the index current?
python3 plugins/handoff/tools/pending_index.py --audit   # is the index correct?
```

These answer different questions. `--check` compares the file against a freshly computed index — the tool against itself — so it cannot detect that the *generator* is wrong. `--audit` asserts invariants about the output instead: every entry indexed exactly once per section, no entry duplicated within a section, no back-link written inside a handoff message's code fence. A real duplication bug once persisted while `--check` reported success throughout; that is why `--audit` exists.

## History

Version 3.0.0 merged the former `handoff` and `handoff-zh` skills into one and converted the repo from a pair of skills into a plugin. Earlier tags in this repository hold the two-skill layout. See `CHANGELOG.md`.

## License

MIT
