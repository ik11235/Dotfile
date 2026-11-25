#!/usr/bin/env python3
"""analyze_permissions.py — Antigravity CLI のトランスクリプトを分析し、
~/.gemini/antigravity-cli/settings.json の permissions.allow 候補を抽出・反映する。

Claude Code の /fewer-permission-prompts に相当する処理を、Antigravity CLI の
トランスクリプト形式・ルール書式（command(...), mcp(...), read_url(...)）・
Terminal Sandbox（BypassSandbox）・RTK PreToolUse リライトに合わせて実行する。

Usage:
  analyze_permissions.py scan [--limit 50] [--min-count 2] [--format markdown|json]
  analyze_permissions.py apply --add "command(gh pr view)" --add "command(rtk gh pr view)" [--dry-run]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from typing import Any

DEFAULT_AGY_DIR = os.path.join(os.path.expanduser("~"), ".gemini", "antigravity-cli")
DEFAULT_HOOKS_PATH = os.path.join(os.path.expanduser("~"), ".gemini", "config", "hooks.json")

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\[[^\]]*\])?\+?=.*$")
VALID_CMD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]*$")
HEREDOC_START_RE = re.compile(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|\\?([A-Za-z0-9_]+))")
RULE_RE = re.compile(
    r"^(command|mcp|read_url|read_file|write_file|execute_url|download_url)\((.+)\)$"
)

# Antigravity のビルトインツール（これ以外は MCP ツール候補として扱う）
BUILTIN_TOOLS = frozenset({
    "run_command",
    "read_file",
    "write_file",
    "edit_file",
    "search_web",
    "read_url_content",
    "update_steps",
    "invoke_subagent",
    "define_subagent",
    "manage_subagents",
    "send_message",
    "manage_task",
    "schedule",
    "ask_question",
    "swarm",
    "run_workflow",
    "find_by_name",
    "grep_search",
    "list_dir",
    "view_file",
    "view_file_outline",
    "view_code_item",
    "replace_file_content",
    "multi_replace_file_content",
    "write_to_file",
    "command_status",
    "send_command_input",
    "browser_subagent",
    "generate_image",
})

# シェル組み込み・制御構文（単独の allowlist ルールにする意味が薄い）
SHELL_BUILTINS = frozenset({
    "cd", "echo", "printf", "true", "false", "export", "unset", "set",
    "exit", "return", "test", "[", "[[", "read", "shift", "trap", "wait",
    "if", "then", "else", "elif", "fi", "for", "do", "done", "while",
    "until", "case", "esac", "in", "function", "{", "}", "!",
})

# 任意コード実行・破壊的操作・書き込み系コマンド（allow 候補から自動除外）
UNSAFE_COMMANDS: dict[str, str] = {
    # 任意コード実行 / シェル / インタプリタ
    "sh": "arbitrary code execution (shell)",
    "bash": "arbitrary code execution (shell)",
    "zsh": "arbitrary code execution (shell)",
    "fish": "arbitrary code execution (shell)",
    "dash": "arbitrary code execution (shell)",
    "eval": "arbitrary code execution",
    "exec": "arbitrary code execution",
    "source": "arbitrary code execution",
    ".": "arbitrary code execution",
    "python": "arbitrary code execution (interpreter)",
    "python3": "arbitrary code execution (interpreter)",
    "node": "arbitrary code execution (interpreter)",
    "deno": "arbitrary code execution (interpreter)",
    "bun": "arbitrary code execution (interpreter)",
    "ruby": "arbitrary code execution (interpreter)",
    "perl": "arbitrary code execution (interpreter)",
    "php": "arbitrary code execution (interpreter)",
    "lua": "arbitrary code execution (interpreter)",
    "osascript": "arbitrary code execution",
    "xargs": "executes arbitrary subcommands",
    "find": "supports -exec / -delete",
    "awk": "supports system() / file output",
    "gawk": "supports system() / file output",
    "sed": "supports in-place edit (-i) and execute",
    # 特権・破壊的・ファイル変更系
    "sudo": "privilege escalation",
    "su": "privilege escalation",
    "doas": "privilege escalation",
    "rm": "destructive file deletion",
    "rmdir": "file deletion",
    "mv": "mutates filesystem",
    "cp": "mutates filesystem",
    "ln": "mutates filesystem",
    "mkdir": "mutates filesystem",
    "touch": "mutates filesystem",
    "chmod": "mutates permissions",
    "chown": "mutates ownership",
    "chgrp": "mutates ownership",
    "dd": "low-level destructive I/O",
    "tee": "writes arbitrary files",
    "truncate": "mutates files",
    "install": "writes files",
    "patch": "modifies files",
    "kill": "terminates processes",
    "pkill": "terminates processes",
    "killall": "terminates processes",
    "launchctl": "modifies system services",
    "systemctl": "modifies system services",
    # ネットワーク・リモート・DB
    "curl": "arbitrary HTTP requests / uploads / downloads",
    "wget": "arbitrary network downloads",
    "nc": "arbitrary network connections",
    "netcat": "arbitrary network connections",
    "ssh": "remote execution",
    "scp": "remote file transfer",
    "sftp": "remote file transfer",
    "rsync": "mutates files / remote transfer",
    "psql": "database client (can mutate data)",
    "mysql": "database client (can mutate data)",
    "sqlite3": "database client (can mutate data)",
    "mongosh": "database client (can mutate data)",
    "redis-cli": "database client (can mutate data)",
    # その他危険なラッパー
    "open": "opens arbitrary files/URLs/apps",
    "pbcopy": "mutates clipboard",
}

# 2〜3トークン目がサブコマンドになる CLI（先頭トークンだけだと書き込み系まで許可してしまう）
TWO_LEVEL_CLIS = frozenset({
    "git", "brew", "cargo", "go", "mise", "uv", "home-manager",
    "kubectl", "helm", "terraform", "tofu", "pulumi", "wrangler",
    "gcloud", "aws", "az", "stripe", "flyctl", "fly", "supabase",
    "vercel", "netlify", "ghq", "tmux", "defaults", "diskutil",
    "pkgutil", "codesign", "xcodebuild", "swift", "make", "just",
})

# 3トークン目でアクションが決まる (cmd, group) の組
THREE_LEVEL_GROUPS: set[tuple[str, str]] = {
    ("gh", "pr"),
    ("gh", "issue"),
    ("gh", "run"),
    ("gh", "repo"),
    ("gh", "workflow"),
    ("gh", "release"),
    ("gh", "label"),
    ("gh", "auth"),
    ("gh", "extension"),
    ("gh", "cache"),
    ("gh", "secret"),
    ("gh", "variable"),
    ("gh", "ruleset"),
    ("gh", "project"),
    ("gh", "gist"),
    ("nix", "flake"),
    ("nix", "profile"),
    ("nix", "store"),
    ("nix", "registry"),
    ("docker", "compose"),
    ("docker", "container"),
    ("docker", "image"),
    ("docker", "network"),
    ("docker", "volume"),
    ("docker", "system"),
    ("git", "worktree"),
    ("git", "remote"),
    ("git", "stash"),
    ("git", "submodule"),
    ("git", "notes"),
    ("kubectl", "config"),
    ("npm", "run"),
    ("pnpm", "run"),
    ("yarn", "run"),
    ("bun", "run"),
}

# 安全とみなすサブコマンド（ホワイトリスト的に評価を補助）
SAFE_READONLY_PREFIXES = frozenset({
    # git 読み取り専用
    "git status", "git diff", "git log", "git show", "git blame",
    "git rev-parse", "git ls-files", "git ls-tree", "git ls-remote",
    "git describe", "git merge-base", "git shortlog", "git reflog",
    "git worktree list", "git stash list", "git submodule status",
    "git remote show", "git remote -v", "git fetch", "git check-ignore",
    "git cat-file", "git for-each-ref", "git name-rev",
    # gh 読み取り専用
    "gh pr view", "gh pr list", "gh pr diff", "gh pr checks", "gh pr status",
    "gh issue view", "gh issue list", "gh issue status",
    "gh run view", "gh run list", "gh run watch",
    "gh repo view", "gh repo list",
    "gh workflow list", "gh workflow view",
    "gh release list", "gh release view",
    "gh label list", "gh auth status", "gh status", "gh search",
    "gh cache list", "gh extension list",
    # nix / home-manager 読み取り・検証
    "nix flake check", "nix flake show", "nix flake metadata",
    "nix profile list", "nix search", "nix eval", "nix build",
    "nix store", "home-manager generations", "home-manager build",
    # JS / TS 検証系
    "npm test", "npm run lint", "npm run typecheck", "npm run check",
    "npm run test", "npm run build", "npm ls", "npm outdated",
    "pnpm test", "pnpm run lint", "pnpm run typecheck", "pnpm run check",
    "yarn test", "yarn lint", "yarn typecheck",
    "npx jest", "npx vitest", "npx tsc --noEmit", "npx prettier --check",
    "npx eslint",
    # 他言語テスト・検証系
    "cargo test", "cargo check", "cargo clippy", "cargo metadata",
    "go test", "go vet", "go list", "go version",
    "brew list", "brew info", "brew outdated", "brew search", "brew doctor",
    "mise ls", "mise list", "mise current", "mise doctor",
    "ghq list", "ghq root",
    "docker ps", "docker images", "docker logs", "docker inspect",
    "docker compose ps", "docker compose logs", "docker compose config",
    "kubectl get", "kubectl describe", "kubectl logs", "kubectl version",
    "kubectl config current-context", "kubectl config get-contexts",
    # UNIX 読み取り専用ユーティリティ
    "ls", "stat", "file", "cat", "head", "tail", "wc", "sort", "uniq",
    "cut", "tr", "grep", "egrep", "fgrep", "rg", "fd", "jq", "yq",
    "diff", "cmp", "comm", "tree", "du", "df", "pwd", "which", "whereis",
    "type", "command", "date", "uname", "whoami", "id", "hostname",
    "realpath", "readlink", "dirname", "basename", "shasum", "sha256sum",
    "md5", "md5sum", "strings", "hexdump", "xxd", "unzip -p", "unzip -l",
    "tar -tf", "tar -tzf", "sw_vers", "sysctl", "ps", "lsof",
})

# 明示的に危険・書き込み系として除外するサブコマンドプレフィックス
UNSAFE_SUBCOMMAND_PREFIXES: dict[str, str] = {
    # git 書き込み・破壊的操作
    "git add": "mutates git index",
    "git commit": "mutates git history",
    "git push": "pushes to remote",
    "git pull": "mutates working tree",
    "git merge": "mutates git history",
    "git rebase": "rewrites git history",
    "git reset": "rewrites git state",
    "git checkout": "mutates working tree",
    "git switch": "mutates working tree",
    "git restore": "mutates working tree",
    "git clean": "deletes untracked files",
    "git rm": "deletes files",
    "git mv": "moves files",
    "git cherry-pick": "mutates git history",
    "git revert": "mutates git history",
    "git init": "creates repository",
    "git clone": "downloads repository",
    "git branch": "can create/delete branches (e.g. -D)",
    "git tag": "can create/delete tags",
    "git config": "can modify git config",
    "git worktree add": "mutates worktrees",
    "git worktree remove": "removes worktrees",
    "git worktree prune": "prunes worktrees",
    "git stash push": "mutates working tree",
    "git stash pop": "mutates working tree",
    "git stash drop": "deletes stash",
    "git stash apply": "mutates working tree",
    "git stash clear": "deletes stashes",
    "git remote add": "mutates git config",
    "git remote remove": "mutates git config",
    "git remote set-url": "mutates git config",
    # gh 書き込み・任意 API
    "gh api": "prefix allows POST/PUT/PATCH/DELETE mutations (use with care or regex)",
    "gh pr create": "creates PR",
    "gh pr edit": "edits PR",
    "gh pr merge": "merges PR",
    "gh pr close": "closes PR",
    "gh pr reopen": "reopens PR",
    "gh pr comment": "posts PR comment",
    "gh pr review": "posts PR review",
    "gh pr ready": "mutates PR state",
    "gh issue create": "creates issue",
    "gh issue edit": "edits issue",
    "gh issue close": "closes issue",
    "gh issue reopen": "reopens issue",
    "gh issue comment": "posts issue comment",
    "gh issue delete": "deletes issue",
    "gh run rerun": "triggers CI run",
    "gh run cancel": "cancels CI run",
    "gh run delete": "deletes CI run",
    "gh release create": "creates release",
    "gh release delete": "deletes release",
    "gh release edit": "edits release",
    "gh repo create": "creates repository",
    "gh repo delete": "deletes repository",
    "gh repo edit": "edits repository",
    "gh repo fork": "forks repository",
    "gh repo archive": "archives repository",
    "gh workflow run": "triggers workflow",
    "gh workflow enable": "mutates workflow",
    "gh workflow disable": "mutates workflow",
    "gh secret set": "mutates secrets",
    "gh secret delete": "deletes secrets",
    "gh variable set": "mutates variables",
    "gh variable delete": "deletes variables",
    "gh auth login": "mutates auth state",
    "gh auth logout": "mutates auth state",
    # パッケージマネージャ変更系
    "npm install": "installs packages / runs lifecycle scripts",
    "npm i": "installs packages / runs lifecycle scripts",
    "npm ci": "installs packages / runs lifecycle scripts",
    "npm uninstall": "mutates dependencies",
    "npm remove": "mutates dependencies",
    "npm update": "mutates dependencies",
    "npm publish": "publishes package",
    "pnpm install": "installs packages / runs lifecycle scripts",
    "pnpm add": "mutates dependencies",
    "pnpm remove": "mutates dependencies",
    "yarn add": "mutates dependencies",
    "yarn remove": "mutates dependencies",
    "yarn install": "installs packages / runs lifecycle scripts",
    "brew install": "installs packages",
    "brew uninstall": "uninstalls packages",
    "brew upgrade": "upgrades packages",
    "docker run": "executes arbitrary container",
    "docker exec": "executes arbitrary command in container",
    "docker rm": "removes container",
    "docker rmi": "removes image",
    "docker compose up": "starts/mutates containers",
    "docker compose down": "stops/removes containers",
    "docker compose exec": "executes command in container",
    "kubectl apply": "mutates cluster",
    "kubectl delete": "deletes cluster resources",
    "kubectl exec": "executes command in pod",
    "kubectl edit": "mutates cluster",
    "kubectl patch": "mutates cluster",
    "rtk bypass": "bypasses RTK filter for arbitrary commands",
    "nix run": "executes arbitrary package",
    "nix shell": "spawns shell",
    "nix develop": "spawns shell",
    "home-manager switch": "applies system configuration",
}

# MCP ツール名にこれらが含まれていれば書き込み系とみなし除外
MCP_MUTATING_KEYWORDS = (
    "create", "update", "delete", "remove", "post", "send", "write",
    "edit", "execute", "run", "add", "set", "put", "patch", "merge",
    "close", "reopen", "archive", "complete", "uncomplete", "move",
    "drop", "insert", "mutate", "publish", "deploy", "trigger", "cancel",
    "approve", "reject", "assign", "comment", "reply",
)

# 機密パス（read_file 候補から必ず除外）
SENSITIVE_PATH_PATTERNS = (
    "/.ssh", "/.aws", "/.gnupg", "/.kube", "/.config/gcloud",
    "/.netrc", "/secrets", "/.env", "credentials", ".pem", ".key",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
)

# Antigravity がプレフィックス一致を無効化するシェル構文
EXACT_MATCH_ONLY_RE = re.compile(
    r"\$\(|\$\(\(|`|<[(]|>[(]|(?<!\\)\{[^}\s,]+,[^}\s}]+\}"
)


@dataclasses.dataclass
class CommandStat:
    prefix: str
    total_count: int = 0
    bypass_count: int = 0
    sessions: set[str] = dataclasses.field(default_factory=set)
    samples: list[str] = dataclasses.field(default_factory=list)
    exact_match_only_count: int = 0
    seen_as_rtk: bool = False
    has_env_prefix_count: int = 0

    def add_sample(self, raw: str) -> None:
        compact = " ".join(raw.split())
        if len(compact) > 120:
            compact = compact[:117] + "..."
        if compact not in self.samples and len(self.samples) < 3:
            self.samples.append(compact)


@dataclasses.dataclass
class SimpleStat:
    key: str
    total_count: int = 0
    sessions: set[str] = dataclasses.field(default_factory=set)
    samples: list[str] = dataclasses.field(default_factory=list)

    def add_sample(self, raw: str) -> None:
        if raw not in self.samples and len(self.samples) < 3:
            self.samples.append(raw)


def _decode_arg_value(val: Any) -> Any:
    """transcript.jsonl（文字列化）と transcript_full.jsonl（ネイティブ型）の両方を扱う。"""
    if isinstance(val, str):
        stripped = val.strip()
        if (stripped.startswith('"') and stripped.endswith('"')) or stripped in ("true", "false"):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return val
    return val


def _is_truthy(val: Any) -> bool:
    decoded = _decode_arg_value(val)
    if isinstance(decoded, bool):
        return decoded
    if isinstance(decoded, str):
        return decoded.strip().lower() == "true"
    return False


def has_exact_match_only_construct(command: str) -> bool:
    """Antigravity がプレフィックス一致を無効化する構文を含むか判定する。"""
    # シングルクォート内は無視するため簡易的にマスクする
    masked = re.sub(r"'[^']*'", "''", command)
    if EXACT_MATCH_ONLY_RE.search(masked):
        return True
    if re.search(r"\bgit\s+-c\b", masked):
        return True
    if re.search(r"\btar\b.*--to-command", masked):
        return True
    return False


def _find_heredoc_delims(line: str) -> list[tuple[str, bool]]:
    """クォート外にある <<DELIM / <<'DELIM' / <<"DELIM" / <<-DELIM をすべて抽出する。"""
    delims: list[tuple[str, bool]] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if escaped:
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and not in_double and ch == "<" and i + 1 < n and line[i + 1] == "<":
            # <<< here-string は heredoc ではない
            if i + 2 < n and line[i + 2] == "<":
                i += 3
                continue
            m = HEREDOC_START_RE.match(line, i)
            if m:
                delim = m.group(1) or m.group(2) or m.group(3)
                if delim:
                    delims.append((delim, m.group(0).startswith("<<-")))
                i = m.end()
                continue
        i += 1
    return delims


def strip_heredocs(command: str) -> str:
    """heredoc 本体（<<'EOF' ... EOF）を除去し、本文がコマンドとして誤分割されるのを防ぐ。"""
    if "<<" not in command:
        return command
    lines = command.splitlines()
    out: list[str] = []
    pending_delims: list[tuple[str, bool]] = []  # (delimiter, strip_tabs)
    for line in lines:
        if pending_delims:
            delim, strip_tabs = pending_delims[0]
            check = line.lstrip("\t") if strip_tabs else line
            if check == delim:
                pending_delims.pop(0)
            continue
        out.append(line)
        pending_delims.extend(_find_heredoc_delims(line))
    return "\n".join(out)


def split_shell_segments(command: str) -> list[str]:
    """クォートとエスケープを尊重して &&, ||, ;, |, 改行 でコマンドを分割する。"""
    command = strip_heredocs(command)
    segments: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(command)

    def flush() -> None:
        seg = "".join(buf).strip()
        if seg:
            segments.append(seg)
        buf.clear()

    while i < n:
        ch = command[i]
        if escaped:
            buf.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            buf.append(ch)
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            buf.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            buf.append(ch)
            i += 1
            continue
        if not in_single and not in_double:
            if ch == "#" and (not buf or buf[-1].isspace()):
                # 行末までコメント
                while i < n and command[i] != "\n":
                    i += 1
                continue
            if ch in (";", "\n"):
                flush()
                i += 1
                continue
            if ch == "&" and i + 1 < n and command[i + 1] == "&":
                flush()
                i += 2
                continue
            if ch == "|":
                flush()
                if i + 1 < n and command[i + 1] == "|":
                    i += 2
                else:
                    i += 1
                continue
        buf.append(ch)
        i += 1

    flush()
    return segments


def tokenize_segment(segment: str) -> list[str]:
    """シェルセグメントをトークン化する。shlex が失敗したら空白分割にフォールバック。"""
    try:
        tokens = shlex.split(segment, posix=True)
    except ValueError:
        tokens = segment.split()
    # リダイレクト（2>&1, >/dev/null 等）を取り除く
    cleaned: list[str] = []
    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if re.match(r"^\d*[<>]+$", tok):
            skip_next = True
            continue
        if re.match(r"^\d*[<>].+$", tok):
            continue
        cleaned.append(tok)
    return cleaned


def unwrap_tokens(tokens: list[str]) -> tuple[list[str], bool, bool]:
    """先頭の環境変数代入・透過ラッパー（env, timeout, nohup, nice）・rtk を剥がす。

    Returns: (unwrapped_tokens, had_env_prefix, was_rtk_prefixed)
    """
    had_env = False
    was_rtk = False
    idx = 0
    n = len(tokens)
    while idx < n:
        tok = tokens[idx]
        if ENV_ASSIGN_RE.match(tok):
            had_env = True
            idx += 1
            continue
        if tok == "env":
            idx += 1
            while idx < n and (tokens[idx].startswith("-") or ENV_ASSIGN_RE.match(tokens[idx])):
                if ENV_ASSIGN_RE.match(tokens[idx]):
                    had_env = True
                idx += 1
            continue
        if tok in ("nohup", "command"):
            idx += 1
            continue
        if tok == "nice":
            idx += 1
            if idx < n and tokens[idx] == "-n" and idx + 1 < n:
                idx += 2
            elif idx < n and tokens[idx].startswith("-"):
                idx += 1
            continue
        if tok == "timeout":
            idx += 1
            while idx < n and tokens[idx].startswith("-"):
                if tokens[idx] in ("-s", "-k", "--signal", "--kill-after") and idx + 1 < n:
                    idx += 2
                else:
                    idx += 1
            if idx < n:
                idx += 1  # duration
            continue
        if tok == "rtk" and idx + 1 < n and tokens[idx + 1] != "bypass":
            was_rtk = True
            idx += 1
            continue
        break
    return tokens[idx:], had_env, was_rtk


def normalize_binary(tok: str) -> str:
    """フルパス指定（/usr/bin/python3 等）をコマンド名へ正規化する。"""
    if "/" in tok and not tok.startswith("./") and not tok.startswith("../"):
        return os.path.basename(tok)
    return tok


def classify_command_tokens(tokens: list[str]) -> tuple[str | None, str | None]:
    """トークン列から (正規化プレフィックス, 除外理由 or None) を返す。

    シェル組み込みや空コマンドなど無視対象は (None, None) を返す。
    """
    if not tokens:
        return None, None

    cmd = normalize_binary(tokens[0])
    if not cmd or cmd in SHELL_BUILTINS:
        return None, None
    if cmd.startswith(("./", "../", "$")):
        return cmd, "relative or variable executable path"
    if not VALID_CMD_RE.match(cmd):
        return None, None

    # rtk bypass は任意コマンドを通してしまうので除外
    if cmd == "rtk" and len(tokens) >= 2 and tokens[1] == "bypass":
        return "rtk bypass", UNSAFE_SUBCOMMAND_PREFIXES["rtk bypass"]

    # そもそも危険なコマンド
    if cmd in UNSAFE_COMMANDS:
        prefix = f"{cmd} {tokens[1]}" if len(tokens) >= 2 and tokens[1].startswith("-") else cmd
        return prefix, UNSAFE_COMMANDS[cmd]

    # git の危険なグローバルオプション (-C, -c, --exec-path, --git-dir)
    if cmd == "git" and len(tokens) >= 2:
        if tokens[1] in ("-C", "-c", "--exec-path", "--git-dir", "--work-tree"):
            return f"git {tokens[1]}", "git global flag allows arbitrary repo/command execution"
        if any(t in ("-c", "--exec-path") for t in tokens[1:]):
            return "git -c", "git -c/--exec-path allows arbitrary command execution"

    # gh の -R / --repo をサブコマンドの前に置くと全サブコマンドに一致してしまう
    if cmd == "gh" and len(tokens) >= 2 and tokens[1] in ("-R", "--repo"):
        return f"gh {tokens[1]}", "gh -R before subcommand would match write subcommands too"

    # npx / pnpx / bunx の特別扱い（ツール名＋安全フラグを残す）
    if cmd in ("npx", "pnpx", "bunx"):
        rest = [t for t in tokens[1:] if t not in ("-y", "--yes", "--no-install")]
        if not rest:
            return cmd, "bare package runner"
        pkg = rest[0]
        if pkg == "tsc" and "--noEmit" in rest[1:]:
            return f"{cmd} tsc --noEmit", None
        if pkg == "prettier" and "--check" in rest[1:]:
            return f"{cmd} prettier --check", None
        if pkg in ("jest", "vitest", "eslint", "oxlint", "biome", "stylelint", "knip", "depcheck"):
            return f"{cmd} {pkg}", None
        # 未知パッケージは is_known_safe=False (review) として候補に残し、明示的な書き込み系だけ除外する
        if pkg in ("prettier", "tsc"):
            return f"{cmd} {pkg}", f"{pkg} without --check/--noEmit may write files"
        return f"{cmd} {pkg}", None

    # unzip / tar の読み取り専用フラグチェック
    if cmd == "unzip":
        if len(tokens) >= 2 and tokens[1] in ("-p", "-l", "-Z"):
            return f"unzip {tokens[1]}", None
        return "unzip", "extracts files to disk (only -p/-l are read-only)"
    if cmd == "tar":
        if len(tokens) >= 2 and "t" in tokens[1] and "x" not in tokens[1] and "c" not in tokens[1]:
            return f"tar {tokens[1]}", None
        return "tar", "creates or extracts archives (only listing -t is read-only)"

    # 3階層サブコマンド（gh pr view, nix flake show, npm run lint 等）
    if len(tokens) >= 3 and (cmd, tokens[1]) in THREE_LEVEL_GROUPS:
        sub3 = tokens[2]
        if sub3.startswith("-") and not (cmd == "git" and tokens[1] == "remote" and sub3 == "-v"):
            return f"{cmd} {tokens[1]}", "too broad (flag instead of subcommand)"
        prefix = f"{cmd} {tokens[1]} {sub3}"
        if prefix in UNSAFE_SUBCOMMAND_PREFIXES:
            return prefix, UNSAFE_SUBCOMMAND_PREFIXES[prefix]
        return prefix, None

    # 2階層サブコマンド
    if cmd in TWO_LEVEL_CLIS or cmd in ("gh", "nix", "docker", "npm", "pnpm", "yarn"):
        if len(tokens) >= 2 and not tokens[1].startswith("-"):
            prefix = f"{cmd} {tokens[1]}"
            if prefix in UNSAFE_SUBCOMMAND_PREFIXES:
                return prefix, UNSAFE_SUBCOMMAND_PREFIXES[prefix]
            # 3階層グループなのに2語しかなかった場合（例: `gh pr` 単独）
            if (cmd, tokens[1]) in THREE_LEVEL_GROUPS:
                return prefix, "too broad (covers both read and write subcommands)"
            return prefix, None
        return cmd, "bare CLI without subcommand would match write subcommands"

    # 単体コマンド（ls, stat, rg, jq 等）
    return cmd, None


def parse_rule(rule: str) -> tuple[str, str] | None:
    m = RULE_RE.match(rule.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def command_rule_matches_prefix(rule_target: str, candidate_prefix: str) -> bool:
    """Antigravity の command(...) ルールが候補プレフィックスに一致するか判定する。"""
    target = rule_target.strip()
    if target == "*":
        return True
    if target.startswith("regex:"):
        pattern = target[len("regex:"):]
        try:
            # フルライン一致またはトークン単位一致の両方をチェック
            if re.fullmatch(pattern, candidate_prefix):
                return True
            rule_toks = pattern.split()
            cand_toks = candidate_prefix.split()
            if len(rule_toks) <= len(cand_toks):
                if all(re.fullmatch(rt, ct) for rt, ct in zip(rule_toks, cand_toks)):
                    return True
        except re.error:
            return False
        return False

    rule_toks = target.split()
    cand_toks = candidate_prefix.split()
    if not rule_toks or len(rule_toks) > len(cand_toks):
        return False
    return cand_toks[: len(rule_toks)] == rule_toks


def mcp_rule_matches(rule_target: str, mcp_target: str) -> bool:
    target = rule_target.strip()
    if target == "*":
        return True
    if target == mcp_target:
        return True
    if target.endswith("/*"):
        server = target[:-2]
        return mcp_target.startswith(server + "/")
    return False


def url_rule_matches(rule_target: str, domain: str) -> bool:
    target = rule_target.strip().lower()
    dom = domain.strip().lower()
    if target == "*":
        return True
    return dom == target or dom.endswith("." + target)


def check_rule_status(
    action: str,
    target: str,
    permissions: dict[str, list[str]],
) -> str:
    """Deny > Ask > Allow の優先順位で既存ルールとの一致状態を返す。

    Returns: "deny" | "ask" | "allow" | "none"
    """
    for bucket in ("deny", "ask", "allow"):
        for raw_rule in permissions.get(bucket, []) or []:
            parsed = parse_rule(raw_rule)
            if not parsed:
                continue
            r_action, r_target = parsed
            if r_action != action:
                continue
            if action == "command" and command_rule_matches_prefix(r_target, target):
                return bucket
            if action == "mcp" and mcp_rule_matches(r_target, target):
                return bucket
            if action == "read_url" and url_rule_matches(r_target, target):
                return bucket
    return "none"


def load_permissions(settings_path: str) -> dict[str, list[str]]:
    if not os.path.isfile(settings_path):
        return {"allow": [], "ask": [], "deny": []}
    with open(settings_path, encoding="utf-8") as fh:
        data = json.load(fh)
    perms = data.get("permissions") or {}
    return {
        "allow": list(perms.get("allow") or []),
        "ask": list(perms.get("ask") or []),
        "deny": list(perms.get("deny") or []),
    }


def detect_rtk_hook_enabled(hooks_path: str) -> bool:
    if not shutil.which("rtk") or not os.path.isfile(hooks_path):
        return False
    try:
        with open(hooks_path, encoding="utf-8") as fh:
            raw = fh.read()
        return "rtk hook antigravity" in raw
    except OSError:
        return False


def _build_rtk_probe_commands(prefix: str, sample_cmd: str | None = None) -> list[str]:
    """rtk rewrite へ渡す検証コマンド候補を順に返す（フラグ途中で切らない）。"""
    probes: list[str] = []
    if sample_cmd:
        segs = split_shell_segments(sample_cmd)
        if segs:
            toks, _, _ = unwrap_tokens(tokenize_segment(segs[0]))
            if toks and " ".join(toks).startswith(prefix) and len(toks) <= 12:
                # フラグと引数の組を壊さないよう、完全な単一セグメントをそのまま試す
                probes.append(shlex.join(toks))
    if prefix not in probes:
        probes.append(prefix)
    if " " not in prefix:
        if prefix in ("grep", "egrep", "fgrep", "rg"):
            probes.append(f"{prefix} pattern file")
        elif prefix in ("cat", "head", "tail", "wc", "stat", "file"):
            probes.append(f"{prefix} file")
    else:
        probes.append(f"{prefix} 1")
    return probes


def compute_rtk_prefix(prefix: str, sample_cmd: str | None = None) -> str | None:
    """rtk rewrite を実行して、書き換え後の command(rtk ...) プレフィックスを返す。"""
    if prefix.startswith("rtk "):
        return prefix
    for test_cmd in _build_rtk_probe_commands(prefix, sample_cmd):
        try:
            res = subprocess.run(
                ["rtk", "rewrite", test_cmd],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        rewritten = (res.stdout or "").strip()
        if not rewritten or not rewritten.startswith("rtk "):
            continue
        rw_toks = rewritten.split()
        orig_toks = prefix.split()
        if len(rw_toks) >= 1 + len(orig_toks) and rw_toks[1 : 1 + len(orig_toks)] == orig_toks:
            return " ".join(rw_toks[: 1 + len(orig_toks)])
        if len(rw_toks) >= 2:
            return " ".join(rw_toks[:2])
    return None


def find_antigravity_transcripts(antigravity_dir: str, limit: int) -> list[tuple[str, str]]:
    """直近 limit 件の (conversation_id, transcript_path) を新しい順に返す。"""
    brain_dir = os.path.join(antigravity_dir, "brain")
    if not os.path.isdir(brain_dir):
        return []
    found: list[tuple[float, str, str]] = []
    try:
        entries = os.listdir(brain_dir)
    except OSError:
        return []
    for entry in entries:
        if not UUID_RE.match(entry):
            continue
        logs_dir = os.path.join(brain_dir, entry, ".system_generated", "logs")
        chosen: str | None = None
        for fname in ("transcript_full.jsonl", "transcript.jsonl"):
            candidate = os.path.join(logs_dir, fname)
            if os.path.isfile(candidate):
                chosen = candidate
                break
        if chosen:
            try:
                mtime = os.path.getmtime(chosen)
            except OSError:
                continue
            found.append((mtime, entry, chosen))
    found.sort(key=lambda item: item[0], reverse=True)
    return [(cid, path) for _, cid, path in found[:limit]]


def normalize_mcp_tool_name(tool_name: str) -> str:
    """MCP ツール名を Antigravity の server/tool 形式へ可能な範囲で正規化する。"""
    if "/" in tool_name:
        return tool_name
    # mcp__server__tool (Claude 系) や mcp_server_tool 形式
    if tool_name.startswith("mcp__"):
        parts = tool_name[len("mcp__"):].split("__", 1)
        if len(parts) == 2:
            return f"{parts[0]}/{parts[1]}"
    if tool_name.startswith("mcp_"):
        parts = tool_name[len("mcp_"):].split("_", 1)
        if len(parts) == 2:
            return f"{parts[0]}/{parts[1]}"
    return tool_name


def is_mcp_mutating(tool_name: str) -> bool:
    lower = tool_name.lower()
    tokens = re.split(r"[^a-z0-9]+", lower)
    return any(tok in MCP_MUTATING_KEYWORDS for tok in tokens)


def scan_transcripts(
    antigravity_dir: str,
    settings_path: str,
    hooks_path: str,
    limit: int = 50,
    min_count: int = 2,
    check_rtk: bool | None = None,
) -> dict[str, Any]:
    transcripts = find_antigravity_transcripts(antigravity_dir, limit)
    permissions = load_permissions(settings_path)
    rtk_enabled = detect_rtk_hook_enabled(hooks_path) if check_rtk is None else check_rtk

    cmd_stats: dict[str, CommandStat] = {}
    excluded_cmds: dict[str, tuple[CommandStat, str]] = {}
    mcp_stats: dict[str, SimpleStat] = {}
    excluded_mcp: dict[str, tuple[SimpleStat, str]] = {}
    url_stats: dict[str, SimpleStat] = {}

    total_run_commands = 0
    total_bypass_commands = 0

    for conv_id, path in transcripts:
        try:
            fh = open(path, encoding="utf-8", errors="ignore")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                for tc in obj.get("tool_calls") or []:
                    name = tc.get("name") or ""
                    args = tc.get("args") or {}
                    if not isinstance(args, dict):
                        continue

                    if name == "run_command":
                        raw_cmd = _decode_arg_value(args.get("CommandLine", ""))
                        if not isinstance(raw_cmd, str) or not raw_cmd.strip():
                            continue
                        total_run_commands += 1
                        is_bypass = _is_truthy(args.get("BypassSandbox", False))
                        if is_bypass:
                            total_bypass_commands += 1
                        exact_only = has_exact_match_only_construct(raw_cmd)

                        for seg in split_shell_segments(raw_cmd):
                            toks = tokenize_segment(seg)
                            unwrapped, had_env, was_rtk = unwrap_tokens(toks)
                            prefix, exclude_reason = classify_command_tokens(unwrapped)
                            if not prefix:
                                continue
                            if exclude_reason is not None:
                                if prefix not in excluded_cmds:
                                    excluded_cmds[prefix] = (CommandStat(prefix=prefix), exclude_reason)
                                st = excluded_cmds[prefix][0]
                            else:
                                if prefix not in cmd_stats:
                                    cmd_stats[prefix] = CommandStat(prefix=prefix)
                                st = cmd_stats[prefix]
                            st.total_count += 1
                            if is_bypass:
                                st.bypass_count += 1
                            st.sessions.add(conv_id)
                            if exact_only:
                                st.exact_match_only_count += 1
                            if was_rtk:
                                st.seen_as_rtk = True
                            if had_env:
                                st.has_env_prefix_count += 1
                            st.add_sample(seg)

                    elif name == "read_url_content":
                        raw_url = _decode_arg_value(args.get("Url") or args.get("url") or "")
                        if isinstance(raw_url, str) and raw_url.startswith(("http://", "https://")):
                            host = (urllib.parse.urlparse(raw_url).hostname or "").lower()
                            if host and host not in ("localhost", "127.0.0.1", "::1"):
                                st = url_stats.setdefault(host, SimpleStat(key=host))
                                st.total_count += 1
                                st.sessions.add(conv_id)
                                st.add_sample(raw_url[:100])

                    elif name and name not in BUILTIN_TOOLS:
                        norm = normalize_mcp_tool_name(name)
                        if is_mcp_mutating(norm):
                            if norm not in excluded_mcp:
                                excluded_mcp[norm] = (SimpleStat(key=norm), "mutating/write-like MCP tool name")
                            st = excluded_mcp[norm][0]
                        else:
                            st = mcp_stats.setdefault(norm, SimpleStat(key=norm))
                        st.total_count += 1
                        st.sessions.add(conv_id)
                        st.add_sample(name)

    # 候補のフィルタリング・優先順位付け
    candidates: list[dict[str, Any]] = []
    already_allowed: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for prefix, st in cmd_stats.items():
        if st.total_count < min_count:
            continue
        status = check_rule_status("command", prefix, permissions)
        rtk_prefix: str | None = None
        rtk_status: str = "n/a"
        if rtk_enabled:
            rtk_prefix = compute_rtk_prefix(prefix, st.samples[0] if st.samples else None)
            if rtk_prefix:
                rtk_status = check_rule_status("command", rtk_prefix, permissions)

        suggested_rules: list[str] = []
        if status == "none":
            suggested_rules.append(f"command({prefix})")
        if rtk_prefix and rtk_status == "none":
            suggested_rules.append(f"command({rtk_prefix})")

        item = {
            "kind": "command",
            "prefix": prefix,
            "rule": f"command({prefix})",
            "rtk_rule": f"command({rtk_prefix})" if rtk_prefix else None,
            "suggested_rules": suggested_rules,
            "status": status,
            "rtk_status": rtk_status,
            "total_count": st.total_count,
            "bypass_count": st.bypass_count,
            "session_count": len(st.sessions),
            "exact_match_only_count": st.exact_match_only_count,
            "has_env_prefix_count": st.has_env_prefix_count,
            "is_known_safe": prefix in SAFE_READONLY_PREFIXES,
            "samples": st.samples,
        }

        if status in ("deny", "ask") or rtk_status in ("deny", "ask"):
            conflicts.append(item)
        elif not suggested_rules:
            already_allowed.append(item)
        else:
            candidates.append(item)

    # MCP 候補
    for norm, st in mcp_stats.items():
        if st.total_count < min_count:
            continue
        status = check_rule_status("mcp", norm, permissions)
        item = {
            "kind": "mcp",
            "prefix": norm,
            "rule": f"mcp({norm})",
            "rtk_rule": None,
            "suggested_rules": [f"mcp({norm})"] if status == "none" else [],
            "status": status,
            "rtk_status": "n/a",
            "total_count": st.total_count,
            "bypass_count": st.total_count,  # MCP はデフォルト Ask のため高優先
            "session_count": len(st.sessions),
            "exact_match_only_count": 0,
            "has_env_prefix_count": 0,
            "is_known_safe": True,
            "samples": st.samples,
        }
        if status in ("deny", "ask"):
            conflicts.append(item)
        elif status == "allow":
            already_allowed.append(item)
        else:
            candidates.append(item)

    # read_url 候補
    for host, st in url_stats.items():
        if st.total_count < min_count:
            continue
        status = check_rule_status("read_url", host, permissions)
        item = {
            "kind": "read_url",
            "prefix": host,
            "rule": f"read_url({host})",
            "rtk_rule": None,
            "suggested_rules": [f"read_url({host})"] if status == "none" else [],
            "status": status,
            "rtk_status": "n/a",
            "total_count": st.total_count,
            "bypass_count": st.total_count,  # read_url もデフォルト Ask
            "session_count": len(st.sessions),
            "exact_match_only_count": 0,
            "has_env_prefix_count": 0,
            "is_known_safe": True,
            "samples": st.samples,
        }
        if status in ("deny", "ask"):
            conflicts.append(item)
        elif status == "allow":
            already_allowed.append(item)
        else:
            candidates.append(item)

    # 優先順位: BypassSandbox/Ask回数 > セッション数 > 既知の安全 > 総回数
    candidates.sort(
        key=lambda x: (
            x["bypass_count"],
            x["session_count"],
            1 if x["is_known_safe"] else 0,
            x["total_count"],
        ),
        reverse=True,
    )
    already_allowed.sort(key=lambda x: (x["bypass_count"], x["total_count"]), reverse=True)
    conflicts.sort(key=lambda x: (x["bypass_count"], x["total_count"]), reverse=True)

    excluded_list: list[dict[str, Any]] = []
    for prefix, (st, reason) in excluded_cmds.items():
        if st.total_count < min_count:
            continue
        excluded_list.append({
            "kind": "command",
            "prefix": prefix,
            "reason": reason,
            "total_count": st.total_count,
            "bypass_count": st.bypass_count,
            "session_count": len(st.sessions),
        })
    for norm, (st, reason) in excluded_mcp.items():
        if st.total_count < min_count:
            continue
        excluded_list.append({
            "kind": "mcp",
            "prefix": norm,
            "reason": reason,
            "total_count": st.total_count,
            "bypass_count": st.total_count,
            "session_count": len(st.sessions),
        })
    excluded_list.sort(key=lambda x: (x["bypass_count"], x["total_count"]), reverse=True)

    return {
        "summary": {
            "sessions_scanned": len(transcripts),
            "total_run_commands": total_run_commands,
            "total_bypass_commands": total_bypass_commands,
            "settings_path": settings_path,
            "existing_allow_count": len(permissions["allow"]),
            "existing_ask_count": len(permissions["ask"]),
            "existing_deny_count": len(permissions["deny"]),
            "rtk_hook_detected": rtk_enabled,
        },
        "candidates": candidates,
        "already_allowed": already_allowed,
        "conflicts": conflicts,
        "excluded": excluded_list[:20],
    }


def render_markdown(report: dict[str, Any], max_candidates: int = 30) -> str:
    s = report["summary"]
    lines: list[str] = [
        "# Antigravity Permission Allowlist Analysis",
        "",
        f"- Scanned sessions: **{s['sessions_scanned']}**",
        f"- Total `run_command`: **{s['total_run_commands']}** (BypassSandbox: **{s['total_bypass_commands']}**)",
        f"- Settings: `{s['settings_path']}` (allow: {s['existing_allow_count']}, ask: {s['existing_ask_count']}, deny: {s['existing_deny_count']})",
        f"- RTK hook active: **{'yes' if s['rtk_hook_detected'] else 'no'}**",
        "",
        "## Candidates (Prioritized)",
        "",
    ]

    candidates = report["candidates"]
    if not candidates:
        lines.append("新しい追加候補はありません。")
    else:
        shown = candidates[:max_candidates]
        lines.append("| # | Suggested Rule(s) | Bypass/Ask | Total | Sessions | Safety | Notes |")
        lines.append("| --- | --- | ---: | ---: | ---: | --- | --- |")
        for idx, c in enumerate(shown, 1):
            rules_str = ", ".join(f"`{r}`" for r in c["suggested_rules"])
            safety = "known-safe" if c["is_known_safe"] else "review"
            notes: list[str] = []
            if c["status"] == "allow" and c["rtk_rule"]:
                notes.append("orig allowed; RTK rule missing")
            elif c["rtk_rule"] and c["rtk_status"] == "allow" and c["status"] == "none":
                notes.append("RTK rule already allowed")
            elif c["rtk_rule"] and c["rtk_status"] == "none":
                notes.append("includes RTK rewrite")
            if c["exact_match_only_count"] > 0:
                notes.append(f"exact-match-only x{c['exact_match_only_count']}")
            if c["has_env_prefix_count"] > 0:
                notes.append(f"env-prefix x{c['has_env_prefix_count']}")
            if c["bypass_count"] == 0 and c["kind"] == "command":
                notes.append("sandbox-only")
            lines.append(
                f"| {idx} | {rules_str} | {c['bypass_count']} | {c['total_count']} "
                f"| {c['session_count']} | {safety} | {'; '.join(notes)} |"
            )
        if len(candidates) > len(shown):
            lines.append("")
            lines.append(f"_Showing top {len(shown)} of {len(candidates)} candidates (`--max-candidates` or `--format json` for all)._")

    if report["conflicts"]:
        lines.extend(["", "## Conflicts with Existing `deny` / `ask` Rules", ""])
        for c in report["conflicts"]:
            lines.append(
                f"- `{c['rule']}` (status={c['status']}, rtk={c['rtk_status']}, "
                f"bypass={c['bypass_count']}, total={c['total_count']}) — `Deny > Ask > Allow` のため allow 追加では上書きできません"
            )

    if report["excluded"]:
        lines.extend(["", "## Auto-Excluded (Unsafe / Too Broad)", ""])
        lines.append("| Command / Tool | Bypass | Total | Reason |")
        lines.append("| --- | ---: | ---: | --- |")
        for e in report["excluded"]:
            lines.append(
                f"| `{e['prefix']}` | {e['bypass_count']} | {e['total_count']} | {e['reason']} |"
            )

    if report["already_allowed"]:
        lines.extend(["", "## Already Covered by `permissions.allow`", ""])
        covered = ", ".join(f"`{a['rule']}` ({a['total_count']})" for a in report["already_allowed"][:15])
        lines.append(covered)

    return "\n".join(lines) + "\n"


def validate_rule_for_apply(rule: str) -> str | None:
    """settings.json への追加前にルールの構文と安全性を検証する。問題があればエラー文字列を返す。"""
    parsed = parse_rule(rule)
    if not parsed:
        return f"invalid rule syntax (expected action(target)): {rule}"
    action, target = parsed
    target_stripped = target.strip()
    if not target_stripped:
        return f"empty rule target: {rule}"
    if target_stripped == "*":
        return f"refusing global wildcard rule for safety: {rule}"
    if action in ("read_file", "write_file"):
        lower_t = target_stripped.lower()
        if any(pat in lower_t for pat in SENSITIVE_PATH_PATTERNS):
            return f"refusing sensitive path rule: {rule}"
    if action == "command" and not target_stripped.startswith("regex:"):
        toks = target_stripped.split()
        unwrapped, _, _ = unwrap_tokens(toks)
        _, reason = classify_command_tokens(unwrapped)
        if reason is not None:
            return f"refusing unsafe or overly broad command rule ({reason}): {rule}"
    return None


def apply_rules(
    settings_path: str,
    rules: list[str],
    dry_run: bool = False,
) -> dict[str, Any]:
    if not rules:
        raise ValueError("at least one --add rule is required")

    for r in rules:
        err = validate_rule_for_apply(r)
        if err:
            raise ValueError(err)

    if os.path.isfile(settings_path):
        with open(settings_path, encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = {}

    if not isinstance(data, dict):
        raise ValueError(f"settings file root must be a JSON object: {settings_path}")

    perms = data.setdefault("permissions", {})
    if not isinstance(perms, dict):
        raise ValueError("settings.permissions must be a JSON object")

    allow_list: list[str] = list(perms.get("allow") or [])
    existing_perms = {
        "allow": allow_list,
        "ask": list(perms.get("ask") or []),
        "deny": list(perms.get("deny") or []),
    }

    added: list[str] = []
    skipped_existing: list[str] = []
    warnings: list[str] = []

    for rule in rules:
        rule = rule.strip()
        if rule in allow_list or rule in added:
            skipped_existing.append(rule)
            continue
        parsed = parse_rule(rule)
        assert parsed is not None
        action, target = parsed
        status = check_rule_status(action, target, existing_perms)
        if status == "deny":
            raise ValueError(f"rule conflicts with existing permissions.deny: {rule}")
        if status == "ask":
            warnings.append(f"rule is shadowed by existing permissions.ask (Ask > Allow): {rule}")
        allow_list.append(rule)
        added.append(rule)

    perms["allow"] = allow_list

    if not dry_run and added:
        parent = os.path.dirname(os.path.abspath(settings_path))
        os.makedirs(parent, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".settings-", suffix=".json.tmp", dir=parent)
        try:
            os.chmod(tmp_path, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(data, out, indent=2, ensure_ascii=False)
                out.write("\n")
            os.replace(tmp_path, settings_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    return {
        "settings_path": settings_path,
        "dry_run": dry_run,
        "added": added,
        "skipped_existing": skipped_existing,
        "warnings": warnings,
        "total_allow": len(allow_list),
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="subcommand")

    default_agy_dir = os.environ.get("ANTIGRAVITY_APP_DATA_DIR") or DEFAULT_AGY_DIR

    p_scan = sub.add_parser("scan", help="トランスクリプトを分析して allowlist 候補を抽出する")
    p_scan.add_argument("--antigravity-dir", default=default_agy_dir)
    p_scan.add_argument("--settings", default=None, help="settings.json パス（既定: <antigravity-dir>/settings.json）")
    p_scan.add_argument("--hooks", default=DEFAULT_HOOKS_PATH, help="hooks.json パス")
    p_scan.add_argument("--limit", type=int, default=50, help="スキャンする最新セッション数（既定: 50）")
    p_scan.add_argument("--min-count", type=int, default=2, help="候補に含める最小出現回数（既定: 2）")
    rtk_grp = p_scan.add_mutually_exclusive_group()
    rtk_grp.add_argument("--check-rtk", dest="check_rtk", action="store_true", default=None)
    rtk_grp.add_argument("--no-check-rtk", dest="check_rtk", action="store_false")
    p_scan.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p_scan.add_argument("--max-candidates", type=int, default=30, help="Markdown 表示する最大候補数（既定: 30）")

    p_apply = sub.add_parser("apply", help="選択したルールを settings.json の permissions.allow に安全に追加する")
    p_apply.add_argument(
        "--settings",
        default=os.path.join(default_agy_dir, "settings.json"),
        help="更新対象の settings.json パス",
    )
    p_apply.add_argument("--add", action="append", default=[], required=True, help="追加するルール（複数回指定可）")
    p_apply.add_argument("--dry-run", action="store_true", help="書き込まずに結果のみ確認する")

    return ap


def main(argv: list[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list[0].startswith("-"):
        args_list = ["scan"] + args_list

    ap = build_parser()
    args = ap.parse_args(args_list)

    if args.subcommand == "scan":
        agy_dir = os.path.abspath(os.path.expanduser(args.antigravity_dir))
        settings_path = os.path.abspath(
            os.path.expanduser(args.settings or os.path.join(agy_dir, "settings.json"))
        )
        hooks_path = os.path.abspath(os.path.expanduser(args.hooks))
        report = scan_transcripts(
            antigravity_dir=agy_dir,
            settings_path=settings_path,
            hooks_path=hooks_path,
            limit=args.limit,
            min_count=args.min_count,
            check_rtk=args.check_rtk,
        )
        if args.format == "json":
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(render_markdown(report, max_candidates=args.max_candidates))
        return 0

    if args.subcommand == "apply":
        settings_path = os.path.abspath(os.path.expanduser(args.settings))
        try:
            result = apply_rules(settings_path, args.add, dry_run=args.dry_run)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
