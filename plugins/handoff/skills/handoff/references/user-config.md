# User Configuration

This skill adapts to each user's environment through configuration variables. Users declare these in their own `CLAUDE.md` (project-level or global). The skill reads them at runtime; nothing is hardcoded.

## Required variables

| Variable | Purpose | Example format |
|----------|---------|----------------|
| `WORKSPACE_ROOT` | Primary workspace root path | `~/<your-workspace>/` |

If `WORKSPACE_ROOT` is not declared, the skill infers it from conversation context (files mentioned, current directory). Ask the user once if inference fails.

## Optional variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `HANDOFF_DIR` | Where handoff documents are saved | `<WORKSPACE_ROOT>/_handoffs/` |
| `TEMPLATE_PATH` | Path to a user-provided handoff template | none (skill generates full content) |
| `PENDING_FILE` | Central queue of handoff messages awaiting pickup (Step 5.5/5.6) | `<WORKSPACE_ROOT>/_harness/handoffs/pending.md` |
| `ACTION_TRACKER` | Path to a cross-workspace action-list file for opt-in sync | none (sync step skipped) |
| `CENTRAL_HANDOFF_INDEX` | Path to a central handoff index that tracks handoffs across workspaces | none (cross-workspace indexing skipped) |
| `TRIGGER_PHRASES` | Additional trigger phrases in any language | English defaults only |

## Declaration format

Users add a section to their `CLAUDE.md`. Fill in values appropriate for your own environment:

```markdown
## Handoff skill configuration

- WORKSPACE_ROOT: <your-workspace-path>
- HANDOFF_DIR: <WORKSPACE_ROOT>/_handoffs/
- PENDING_FILE: <WORKSPACE_ROOT>/_harness/handoffs/pending.md
- TEMPLATE_PATH: <your-template-path>    # optional
- ACTION_TRACKER: <your-tracker-path>    # optional
- TRIGGER_PHRASES: [handoff, wrap up, session end]
```

The skill scans `CLAUDE.md` for these keys at step 1. Values may use `~` or absolute paths. `<WORKSPACE_ROOT>` inside `HANDOFF_DIR` is substituted at runtime.

## Resolution order

For any variable:

1. Value declared in `CLAUDE.md`
2. Value declared in project-level `CLAUDE.md` (overrides global if both exist)
3. Default shown in the table above

## Cross-workspace case

If the conversation spans multiple workspaces, the user may declare a list:

```markdown
- WORKSPACE_ROOT: [<workspace-a-path>, <workspace-b-path>]
```

In that case, each workspace gets its own handoff document under its own `HANDOFF_DIR`, plus a one-line cross-index (see `optional-sections.md`).

## Note on `PENDING_FILE`

Unlike `HANDOFF_DIR`, this path is **not** resolved per-workspace at write time. It is one shared queue across every workspace the user works in, so that "what is waiting for me" has a single answer. Its parent directory also holds:

- `archive/YYYY-MM.md` — entries that have left the queue, each tagged `completed` / `superseded` / `dropped`
- `_format.md` — optional; when present it is the authoritative entry format and overrides the template in `SKILL.md`
