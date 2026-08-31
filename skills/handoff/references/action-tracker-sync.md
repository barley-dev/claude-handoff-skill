# Action Tracker Sync (opt-in)

**Load this reference only when the user has declared `ACTION_TRACKER` in their config.** Otherwise, skip this step entirely.

## What this does

Handoff documents are scattered across workspaces. If the user maintains a single cross-workspace action list (e.g., a global TODO file), the action items captured in each handoff should propagate there so action items don't get lost.

This step is **opt-in**. A user with `ACTION_TRACKER` set gets automatic sync; a user without it is not affected.

## Flow

### 1. Read the current tracker

Read the file at `ACTION_TRACKER`. Parse its sections (typically grouped by priority or deadline).

### 2. Mark completed items

Any item listed in the current handoff's "Completed" section that matches an open item in the tracker:
- Change its checkbox from `[ ]` to `[x]`
- Move it to a "Recently completed" section (if the tracker has one)

### 3. Add new pending items

Any item in the current handoff's "Pending" section that is not already in the tracker:
- Append under the appropriate priority section
- Use this format:

```markdown
- [ ] **Task description** — Recommended tool/model — Source: `~/...handoff-path.md`
```

The "Source" link lets the user trace any tracker item back to the handoff that produced it.

### 4. Update the "last updated" timestamp

If the tracker has a "Last updated" line at the top, update it to the current date.

### 5. Staleness warning

If the tracker's "Last updated" line is more than 7 days old at the time of sync, append a note to the handoff message (the chat output, not the document):

> Note: The action tracker at `<ACTION_TRACKER>` was last updated more than 7 days ago. Consider reviewing it at the start of the next session.

## Why this matters

Handoff documents are per-session snapshots. The action tracker is the only cross-workspace, cross-session view of what's outstanding. Without sync, action items captured in a handoff are invisible to any future session that starts in a different workspace. Sync closes that loop.
