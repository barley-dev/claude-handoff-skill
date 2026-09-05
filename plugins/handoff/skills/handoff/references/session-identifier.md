# Session identifiers (optional, not part of the handoff flow itself)

Cross-session messaging (`ListAgents` / `SendMessage`) only works if you can tell sessions apart. A terminal tab titled by its working directory, or a harness-assigned two-character name, does not say what that session is *doing* — so when the user wants to route a follow-up to "the one doing the poster" or ask this session to relay something to another, there is nothing to go on.

This is a general cross-session-messaging concern, not something the handoff skill depends on. Nothing here blocks or gates the handoff flow.

## What to suggest, once, at first run

If the user's status line has no visible session label (no obvious name, task summary, or short alias — check by asking, not by reading their status line config file, which this skill does not know the path to), mention it in passing:

```
Unrelated to the handoff itself: if you ever run multiple Claude Code sessions at once,
giving each one a visible label in your status line (a short alias, or a one-line task
summary) makes it much easier to tell them apart when routing a handoff or a cross-session
message. Totally optional — skip if you don't run concurrent sessions.
```

Do not re-raise this after the first mention. Do not check for it on every handoff.

## Why this skill doesn't implement one

Status line configuration is user-owned and highly personal — terminal, color scheme, what metrics matter to *this* user. The plugin has no visibility into it and must not assume a specific status line setup exists, write to one, or require one. Different users will want different things in their status line; a plugin that hard-codes an opinion here would be overreaching.

## Pointers, not a bundled implementation

There is no bundled script here on purpose — a working implementation is necessarily specific to one status line setup (what it already shows, what colors/fields matter to that user). If the user asks how, the general shape is:

1. The harness writes a per-session identity file the status line command can read (check the harness's session/identity file location for the current Claude Code version).
2. A status line command script can read that file and print whatever identifier the user wants — a name, a short numeric alias, or both.
3. Any alias scheme is local bookkeeping only (e.g. a text file mapping a persistent process/session identifier to a short number) — it must never be treated as an address `SendMessage` or `ListAgents` recognize. Those tools have their own addressing; a status-line alias is a spoken/display convenience layered on top, not a replacement for it.

Point the user to their Claude Code version's docs for the exact status line command interface and the harness's session-identity file location — both can change between versions.
