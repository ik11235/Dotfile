#!/usr/bin/env python3
"""save_conversation.py — Claude Code 会話ログ保存の機械処理を一括実行する。

やること:
  1. セッション UUID の特定（--session > $CLAUDE_CODE_SESSION_ID > 最新 mtime の jsonl）
  2. ${cwd}/${uuid}/ の作成
  3. 生ログ jsonl のハードリンク作成（atomic rename による stale link は inode 比較で検出して貼り直す）
  4. jsonl から user/assistant のテキストを機械抽出し、frontmatter + Summary + Conversation Log の
     要約 MD を組み立てて書き出す

モデル側はタイトルと Summary 本文（--summary-file）だけ用意すればよい。

usage:
  save_conversation.py --title "会話のタイトル" --summary-file /tmp/summary.md
  save_conversation.py --title "..." --summary-file ... --session <uuid> --cwd <dir> --project-dir <dir>
"""
import argparse
import datetime
import glob
import json
import os
import re
import sys

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)


def encode_cwd(cwd: str) -> str:
    """既存コマンドの sed 's/[\\/\\._]/-/g' と同じ変換。"""
    return re.sub(r"[/._]", "-", cwd)


def sanitize_title(title: str) -> str:
    """ファイルシステム安全なタイトルに整形（最大50文字）。"""
    title = re.sub(r'[\\/:*?"<>|]', " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title[:50].strip()


def find_session(project_dir: str, session: str | None, env_session: str | None) -> str:
    if session:  # --session 明示指定は厳密に従う
        return session
    # 環境変数のセッションは project_dir に実在する場合のみ採用
    # （--cwd/--project-dir を別環境に向けたときに誤爆しないため）
    if env_session and glob.glob(os.path.join(project_dir, f"*{env_session}*.jsonl")):
        return env_session
    candidates = []
    for p in glob.glob(os.path.join(project_dir, "*.jsonl")):
        stem = os.path.splitext(os.path.basename(p))[0]
        if UUID_RE.match(stem):
            candidates.append(p)
    if not candidates:
        sys.exit(f"error: no session jsonl found in {project_dir}")
    latest = max(candidates, key=os.path.getmtime)
    return os.path.splitext(os.path.basename(latest))[0]


def hard_link_logs(project_dir: str, session: str, dest_dir: str) -> list[str]:
    """セッションの jsonl をハードリンク。inode 不一致（stale link）は貼り直す。"""
    linked = []
    sources = sorted(glob.glob(os.path.join(project_dir, f"*{session}*.jsonl")))
    if not sources:
        sys.exit(f"error: no jsonl matching session {session} in {project_dir}")
    for src in sources:
        dst = os.path.join(dest_dir, os.path.basename(src))
        if os.path.exists(dst):
            if os.stat(src).st_ino == os.stat(dst).st_ino:
                linked.append(f"{dst} (up to date)")
                continue
            # atomic rename でソース inode が置き換わった stale link → 貼り直し
            os.remove(dst)
            os.link(src, dst)
            linked.append(f"{dst} (relinked: stale inode)")
        else:
            os.link(src, dst)
            linked.append(f"{dst} (linked)")
    return linked


# --- 会話テキスト抽出 -------------------------------------------------------

SYSTEM_REMINDER_RE = re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL)
COMMAND_NAME_RE = re.compile(r"<command-name>(.*?)</command-name>", re.DOTALL)
COMMAND_ARGS_RE = re.compile(r"<command-args>(.*?)</command-args>", re.DOTALL)
COMMAND_MSG_RE = re.compile(r"<command-message>.*?</command-message>", re.DOTALL)
LOCAL_STDOUT_RE = re.compile(r"<local-command-stdout>.*?</local-command-stdout>", re.DOTALL)


def clean_text(text: str) -> str:
    """ハーネス由来のメタタグを除去し、コマンド呼び出しは1行に正規化する。"""
    cmd = COMMAND_NAME_RE.search(text)
    if cmd:
        args = COMMAND_ARGS_RE.search(text)
        args_s = args.group(1).strip() if args else ""
        return f"{cmd.group(1).strip()} {args_s}".strip()
    text = SYSTEM_REMINDER_RE.sub("", text)
    text = COMMAND_MSG_RE.sub("", text)
    text = LOCAL_STDOUT_RE.sub("", text)
    return text.strip()


def content_to_text(content) -> str:
    """message.content（str または block 配列）からテキストのみ取り出す。

    tool_use / tool_result / thinking ブロックは要約 MD には載せない
    （生ログ jsonl が完全な形で残るため）。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "\n".join(parts)
    return ""


def extract_messages(jsonl_path: str) -> list[tuple[str, str]]:
    msgs: list[tuple[str, str]] = []
    seen: set[str] = set()
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") not in ("user", "assistant"):
                continue
            if obj.get("isSidechain"):
                continue
            uid = obj.get("uuid")
            if uid:
                if uid in seen:
                    continue
                seen.add(uid)
            message = obj.get("message") or {}
            text = clean_text(content_to_text(message.get("content")))
            if not text:
                continue
            role = "User" if message.get("role") == "user" else "Assistant"
            # 同一 role の連続 assistant メッセージ（ツール実行を挟んだ続き）は結合する
            if msgs and msgs[-1][0] == role == "Assistant":
                msgs[-1] = (role, msgs[-1][1] + "\n\n" + text)
            else:
                msgs.append((role, text))
    return msgs


def build_markdown(session: str, title: str, summary: str, msgs: list[tuple[str, str]]) -> str:
    today = datetime.date.today().isoformat()
    lines = [
        "---",
        f"session_uuid: {session}",
        f"session resume command : `claude --resume {session}`",
        f"date: {today}",
        "---",
        "",
        f"# {title}",
        "",
        "## Summary",
        "",
        summary.strip(),
        "",
        "## Conversation Log",
        "",
    ]
    for role, text in msgs:
        lines.append(f"### {role}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", required=True, help="会話タイトル（ファイル名に使用）")
    ap.add_argument("--summary-file", required=True, help="Summary 本文を書いたファイル")
    ap.add_argument("--session", default=None)
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--project-dir", default=None,
                    help="セッション jsonl のあるディレクトリ（デフォルト: ~/.claude/projects/<encoded-cwd>）")
    args = ap.parse_args()

    cwd = os.path.abspath(args.cwd)
    project_dir = args.project_dir or os.path.join(
        os.path.expanduser("~"), ".claude", "projects", encode_cwd(cwd)
    )
    if not os.path.isdir(project_dir):
        sys.exit(f"error: project dir not found: {project_dir}")

    session = find_session(
        project_dir, args.session, os.environ.get("CLAUDE_CODE_SESSION_ID") or None
    )
    dest_dir = os.path.join(cwd, session)
    os.makedirs(dest_dir, exist_ok=True)

    linked = hard_link_logs(project_dir, session, dest_dir)

    with open(args.summary_file, encoding="utf-8") as f:
        summary = f.read()

    title = sanitize_title(args.title)
    if not title:
        sys.exit("error: title is empty after sanitization")

    main_jsonl = os.path.join(dest_dir, f"{session}.jsonl")
    if not os.path.exists(main_jsonl):
        main_jsonl = os.path.join(project_dir, f"{session}.jsonl")
    msgs = extract_messages(main_jsonl)

    md_path = os.path.join(dest_dir, f"{title}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_markdown(session, title, summary, msgs))

    print(f"session: {session}")
    for entry in linked:
        print(f"jsonl:   {entry}")
    print(f"summary: {md_path}  ({len(msgs)} messages)")
    print(f"rename:  /rename {title}")


if __name__ == "__main__":
    main()
