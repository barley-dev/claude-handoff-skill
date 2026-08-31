# Claude Handoff Skill

A Claude Code / Claude Desktop skill that compresses a long conversation into a **handoff document** the next session can resume from — without re-reading the entire chat history.

Available in two trigger languages:

| Skill | Trigger phrases |
|---|---|
| `handoff` | `handoff`, `wrap up`, `session end`, `prepare handoff` |
| `handoff-zh` | `交接`、`開始交接`、`準備交接`、`寫交接` |

Both produce the same output structure and share the same reference files. Install either one, or both.

## Why

Long AI coding sessions accumulate state: decisions made, files changed, dead ends ruled out, things still pending. Starting a new conversation normally means losing all of it — or pasting a huge transcript and paying for tokens that mostly do not matter.

This skill does **active compression** instead. It reads the conversation, keeps what the next session actually needs, and drops the rest.

## What it produces

1. A structured Markdown document under your workspace's `_handoffs/` directory, containing:
   - exit condition (what "done" meant for this session)
   - completed work with verifiable evidence
   - pending items and known blockers
   - key decisions **and the reasoning behind them**
   - files changed, with paths
2. A short plain-text message you copy into the next conversation to bootstrap it.

## Install

```bash
git clone https://github.com/barley-dev/claude-handoff-skill.git
cd claude-handoff-skill
./install.sh
```

The installer symlinks the skills into `~/.claude/skills/`, so `git pull` keeps them up to date automatically.

<details>
<summary>Manual install</summary>

```bash
ln -s "$(pwd)/skills/handoff"    ~/.claude/skills/handoff
ln -s "$(pwd)/skills/handoff-zh" ~/.claude/skills/handoff-zh
```
</details>

Verify with `/skills` inside Claude Code — `handoff` should appear in the list.

## Configuration (optional)

The skill works with zero configuration: it infers your workspace root and writes to `<workspace>/_handoffs/`.

To customise, declare variables in your `CLAUDE.md`:

```markdown
WORKSPACE_ROOT: ~/projects/my-project
HANDOFF_DIR: <WORKSPACE_ROOT>/_handoffs
```

Full variable reference: [`skills/handoff/references/user-config.md`](skills/handoff/references/user-config.md).

## Usage

Just say the trigger word in any conversation:

```
handoff
```

The skill detects your environment, gathers the conversation state, writes the document, and hands you the bootstrap message.

Want a version a human will read rather than the next model?

```
handoff — write it so a person can understand it later
```

## Requirements

- Claude Code, or Claude Desktop with filesystem access
- Write permission to your workspace directory

## License

MIT — see [LICENSE](LICENSE).
