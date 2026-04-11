---
allowed-tools: Bash(*), Write(*), Read(*)
description: Save conversation logs with summary and hard links to raw session logs
---

## Context

- Current working directory: !`pwd`
- Claude config project dir: !`echo "$HOME/.claude/projects/$(pwd | sed 's/[\/\.\_]/-/g')"`
- Available session logs: !`ls -t "$HOME/.claude/projects/$(pwd | sed 's/[\/\.\_]/-/g')"/*.jsonl 2>/dev/null | head -5`

## Your task

Save the current conversation log. Follow these steps precisely:

### Step 1: Determine the current session

From the available session logs above, identify the most recently modified `.jsonl` file. Extract the session UUID from its filename (the filename without `.jsonl` extension).

### Step 2: Create the output directory

Create the directory `${CWD}/${SESSION_UUID}/` where `${CWD}` is the current working directory.

```bash
mkdir -p "${CWD}/${SESSION_UUID}"
```

### Step 3: Create hard links to raw conversation logs

For each `.jsonl` file belonging to this session in the Claude config project directory, create a hard link in the output directory. Skip if the link already exists.

```bash
# For each jsonl file matching the session UUID:
JSONL_SOURCE="<path to jsonl in ~/.claude/projects/...>"
JSONL_DEST="${CWD}/${SESSION_UUID}/$(basename ${JSONL_SOURCE})"
if [ ! -f "${JSONL_DEST}" ]; then
  ln "${JSONL_SOURCE}" "${JSONL_DEST}"
fi
```

### Step 4: Generate the summary markdown file

Determine a short, descriptive title for this conversation (in the language used in the conversation, max 50 characters, filesystem-safe: no `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`). Use this title as the filename.

Write the file `${CWD}/${SESSION_UUID}/${title}.md` with the following structure:

```markdown
---
session_uuid: <SESSION_UUID>
session resume command : `claude --resume <SESSION_UUID>`
date: <today's date in YYYY-MM-DD format>
---

# <title>

## Summary

<Write a concise summary of the entire conversation so far. Include key topics discussed, decisions made, and actions taken.>

## Conversation Log

<Write the full conversation log in a readable format. For each message:>

### User
<user's message>

### Assistant
<assistant's response, excluding tool calls and internal details. Keep the substantive content.>

<Repeat for all messages in the conversation>
```

### Important notes

- Write the summary and conversation log based on YOUR memory of this conversation. Do not attempt to parse the jsonl file.
- The conversation log should be human-readable, not raw JSON.
- Omit tool call details (function names, parameters, results) from the conversation log unless they are essential for understanding the conversation.
- Include only the substantive text content of each message.
- If the conversation is very long, still include the full log but keep each message concise.
