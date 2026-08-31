# Path Resolution

A handoff document is read by a future Claude session with zero context about directory structure. Every path in the document must be self-contained and unambiguous. This is not a side-note — it is the single most important correctness constraint of the skill.

## The rule

**Every path in a handoff document starts with `~/` (or an absolute path the receiving session can resolve).** No bare relative paths. No `/Users/<username>/...` form. No paths that require knowing the current working directory.

## Workflow

### 1. Identify the workspace root(s)

Scan the conversation history for the workspace(s) involved. Resolve each to a full `~` path. The form looks like:

- `~/<workspace-parent>/<workspace-name>/`

(Actual paths are user-specific and read from `WORKSPACE_ROOT` in user config.)

If `WORKSPACE_ROOT` is declared in the user's `CLAUDE.md` (see `user-config.md`), use that. Otherwise infer from context. If ambiguous, ask the user once.

### 2. Convert every relative path

Go through the entire conversation and extract every file path, directory reference, and location mention. Convert each one:

| Form found in conversation | Convert to |
|---------------------------|-----------|
| `_handoffs/Handoff_...md` | `<WORKSPACE_ROOT>/_handoffs/Handoff_...md` |
| `notes.md` (bare filename) | `<WORKSPACE_ROOT>/notes.md` if its location is clear, otherwise ask |
| `../other-project/x.md` | Resolve against workspace root and expand to `~/...` |
| `/Users/<username>/x` | `~/x` |

### 3. Validation checklist

Before writing the handoff document, verify:

- [ ] Every path in the document starts with `~/` or is an unambiguous absolute path
- [ ] No path uses the `/Users/<username>/...` form
- [ ] No bare relative paths appear anywhere in the document
- [ ] Paths that were mentioned in conversation have been resolved, not just copied verbatim
- [ ] Cross-workspace paths use full `~/...` form even if the "home" workspace is obvious from context

### 4. When a path cannot be resolved

Do not guess. Ask the user. A wrong path in a handoff document causes the receiving session to waste time searching for a file that does not exist, or worse, reads the wrong file.

## Why this matters enough to be its own step

Every other step of the handoff can be repaired by the receiving Claude session if something is missing — it can ask follow-up questions. But a receiving session that cannot locate a file cannot repair the problem through questioning; it has no way to know what was meant. Path resolution is the one step where a mistake is silently propagated.
