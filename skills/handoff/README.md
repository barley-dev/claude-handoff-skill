# handoff

A Claude Code / Claude Desktop skill that compresses the current conversation into a handoff document the next session can resume from — without reading the full chat history.

## What this skill does

Handoff is **active compression**. When you trigger it, the skill:

1. Scans the current conversation.
2. Extracts exit conditions, completed work, pending items, key decisions, and file changes.
3. Writes a structured handoff document under your workspace's `_handoffs/` directory.
4. Produces a short copy-paste message you drop into the next conversation.

The goal: the next Claude session can reconstruct your working context from the document alone.

The default audience for a handoff is the *next model session*, not a human. The output is dense and structured to save tokens. If you want a human-readable version, say so in the trigger message (see the [advanced section](#advanced) below).

## Quick start

### 1. Install

Place the `handoff/` directory anywhere on your machine, then link it into Claude Code's skills directory:

```bash
ln -s /path/to/handoff ~/.claude/skills/handoff
```

(If you also want Chinese triggers, link the sibling `handoff-zh/` the same way.)

### 2. Configure (optional)

On first invocation, the skill will check your `~/.claude/CLAUDE.md` for a `WORKSPACE_ROOT` declaration. If nothing is configured, the skill offers you two options:

- **Walk-through setup** — three short questions, then a copy-paste snippet for your `CLAUDE.md`.
- **Use defaults** — the skill infers workspace root from the current conversation and saves handoffs to `<workspace>/_handoffs/`.

Either option lets the current handoff proceed immediately. You can configure later.

### 3. Trigger

In any conversation, say:

- `handoff`
- `wrap up`
- `session end`
- `prepare handoff`

or, if you installed `handoff-zh`:

- `交接`
- `開始交接`
- `準備交接`

The skill runs through its steps and writes the document. The chat ends with a plain-text handoff message you can copy into the next session.

## Configuration

The skill reads runtime config from your `CLAUDE.md` (global or project-level). The variables are documented in [`references/user-config.md`](references/user-config.md).

Required:

- `WORKSPACE_ROOT` — the main workspace path this skill operates under.

Optional:

- `HANDOFF_DIR` — where handoff documents are saved (default: `<WORKSPACE_ROOT>/_handoffs/`).
- `TEMPLATE_PATH` — your own handoff template if the default structure doesn't fit.
- `ACTION_TRACKER` — path to a cross-workspace action list; if set, the skill syncs completed and pending items here too.
- `CENTRAL_HANDOFF_INDEX` — path to a central index of handoffs across workspaces.
- `TRIGGER_PHRASES` — extra phrases that should also fire the skill.

All variables work with `~/` or absolute paths. `<WORKSPACE_ROOT>` is substituted at runtime inside other variables.

## Advanced

### Audience: model vs human

Every handoff document records an `audience` field in its frontmatter:

- `audience: model` (default) — dense, structured, token-efficient.
- `audience: human` — full sentences, explicit rationale, no model-oriented shorthand.

To request a human-readable handoff, say so in the trigger message: *"handoff for me to read later"*, *"write it so a person can understand"*, or similar.

### Pairing with `save-conversation`

`handoff` drops anything not needed by the next session. If you also want a raw archive of the full conversation, pair it with a `save-conversation`-style skill. Run `handoff` first, then `save-conversation` — both artifacts are produced without interfering.

### Proactive suggestions

The skill also decides when to *suggest* a handoff (on long conversations, topic shifts, or when a deliverable is complete). You can always override by saying `just keep going` or by triggering a fresh session yourself.

## File layout

```
handoff/
├── SKILL.md
├── README.md  (this file)
└── references/
    ├── user-config.md          # config variable definitions
    ├── path-resolution.md      # path handling rules
    ├── template-workflow.md    # template-based flow
    ├── optional-sections.md    # decision rules for optional sections
    ├── type-b-structure.md     # code-task handoff structure
    ├── action-tracker-sync.md  # action tracker sync (opt-in)
    └── first-run-setup.md      # onboarding flow
```

`handoff-zh/` is a Chinese-trigger variant with the same `references/` files and Chinese step descriptions. Install whichever you prefer, or both.

## License

See repository root.
