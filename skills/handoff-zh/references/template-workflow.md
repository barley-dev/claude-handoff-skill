# Template Workflow (for Filesystem MCP environments)

**Load this reference only when the user has declared `TEMPLATE_PATH` in their config AND a Filesystem MCP is available.** Otherwise, skip this file and generate the handoff document inline.

## When to use

- `TEMPLATE_PATH` is set in user config (see `user-config.md`)
- Filesystem MCP or `osascript` is available to run shell commands
- The template at `TEMPLATE_PATH` uses the placeholder convention described below

If any of these is false, generate the handoff inline without a template.

## Placeholder convention

The user's template file (at `TEMPLATE_PATH`) uses these placeholders:

| Placeholder | Replaced with |
|-------------|---------------|
| `{{DATE}}` | Date from `date '+%Y-%m-%d'` |
| `{{TOPIC}}` | Conversation topic (short phrase) |
| `{{WORKSPACE_ROOT}}` | Resolved `WORKSPACE_ROOT` |
| `{{DOC_PATH}}` | Full `~/...` path of the handoff document being written |
| `{{EXIT_CONDITION}}` | One-line exit condition |
| `{{PREV_HANDOFF}}` | Path to previous handoff, or the line is deleted |
| `{{COMPLETED_ITEMS}}` | Multi-line: what was accomplished |
| `{{TODO_ITEMS}}` | Multi-line: what is pending |
| `{{DECISIONS}}` | Multi-line: key decisions and rationale |
| `{{PITFALL_ITEMS}}` | Multi-line: pitfalls hit, or "None" |
| `{{FILE_CHANGES}}` | Multi-line: files created / modified / deleted |

## Flow

### Step 1: Copy template to destination

```bash
cp "$TEMPLATE_PATH" "$TARGET_PATH"
```

### Step 2: Fill short fixed fields with sed

Short single-line placeholders are fastest to fill via `sed`:

```bash
FILE="$TARGET_PATH"
sed -i '' "s/{{DATE}}/2026-04-22/g" "$FILE"
sed -i '' "s/{{TOPIC}}/Project name/g" "$FILE"
sed -i '' "s|{{WORKSPACE_ROOT}}|<your-workspace-root>|g" "$FILE"
sed -i '' "s|{{DOC_PATH}}|$FILE|g" "$FILE"
sed -i '' "s/{{EXIT_CONDITION}}/Complete — one-line description/g" "$FILE"
sed -i '' "s|{{PREV_HANDOFF}}|~/...prev-handoff.md or delete this line|g" "$FILE"
```

Both steps above can be combined into a single `osascript do shell script` call.

### Step 3: Fill multi-line blocks via edit_file

Long blocks (`{{COMPLETED_ITEMS}}`, `{{TODO_ITEMS}}`, `{{DECISIONS}}`, `{{PITFALL_ITEMS}}`, `{{FILE_CHANGES}}`) often contain special characters that break `sed`. Use `Filesystem:edit_file` (or equivalent) to replace each placeholder with its actual multi-line content.

### Step 4: Append optional sections

Based on `optional-sections.md`, append any optional sections at the end of the document via `edit_file`.

## Why this split

- `sed` handles short fixed strings in one shell call — fastest
- `edit_file` handles multi-line content reliably — no escaping concerns
- Combined, this beats full-text generation on both speed and accuracy
