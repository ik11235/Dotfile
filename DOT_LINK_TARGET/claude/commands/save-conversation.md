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

For each `.jsonl` file belonging to this session in the Claude config project directory, create a hard link in the output directory.

**Stale hard link detection**: 既存リンクが残っていても、Claude Code のセッションロガーは atomic rename (tmpfile → rename) 方式で書き込むことがあり、ソース側の inode が置き換わって**過去のハードリンクが古いスナップショットに取り残される**ケースがある。この場合 vault 側は更新されず、`git diff` にも現れない。inode が一致しない場合は `rm` → `ln` で貼り直す。

```bash
# For each jsonl file matching the session UUID:
JSONL_SOURCE="<path to jsonl in ~/.claude/projects/...>"
JSONL_DEST="${CWD}/${SESSION_UUID}/$(basename ${JSONL_SOURCE})"
if [ ! -f "${JSONL_DEST}" ]; then
  ln "${JSONL_SOURCE}" "${JSONL_DEST}"
elif [ "$(ls -i "${JSONL_SOURCE}" | awk '{print $1}')" != "$(ls -i "${JSONL_DEST}" | awk '{print $1}')" ]; then
  # Stale hard link detected: source file was replaced via atomic rename.
  # Re-link so the vault copy picks up the latest session log.
  rm "${JSONL_DEST}"
  ln "${JSONL_SOURCE}" "${JSONL_DEST}"
fi
```

### Step 4: Generate the summary markdown file

Determine a short, descriptive title for this conversation (in the language used in the conversation, max 50 characters, filesystem-safe: no `/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`). Use this title as the filename. This same title will be used in Step 5 for session rename.

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

### Step 5: Rename the session

`/rename` はビルトインコマンドであり、スキルからツールとして直接呼び出せない。そのため、Step 4で決定したタイトルを使って、ユーザーが実行できるrenameコマンドを提示する。

出力例:
```
セッション名を変更するには以下を実行してください:
/rename <title>
```

タイトルにスペースが含まれていてもそのまま記載してよい（`/rename` はスペース含む引数を受け付ける）。

### Important notes

- Write the summary and conversation log based on YOUR memory of this conversation. Do not attempt to parse the jsonl file.
- The conversation log should be human-readable, not raw JSON.
- Omit tool call details (function names, parameters, results) from the conversation log unless they are essential for understanding the conversation.
- Include only the substantive text content of each message.
- If the conversation is very long, still include the full log but keep each message concise.
