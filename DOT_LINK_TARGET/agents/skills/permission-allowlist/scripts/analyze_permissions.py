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
import concurrent.futures
import dataclasses
import json
import os
import posixpath
import re
import shlex
import shutil
import stat as stat_mod
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
VALID_SUBCMD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:-]*$")
HEREDOC_START_RE = re.compile(r"<<-?\s*(?:'([^']+)'|\"([^\"]+)\"|\\?([^\s;&|<>()]+))")
RULE_RE = re.compile(
    r"^(command|mcp|read_url|read_file|write_file|execute_url|download_url)\((.+)\)$"
)
SHELL_META_IN_RULE_RE = re.compile(r"['\"\\;|&<>`$()]")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

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

# 任意コード実行・破壊的操作・書き込み系・機密ファイル読み取り迂回コマンド（自動除外）
UNSAFE_COMMANDS: dict[str, str] = {
    # 任意コード実行 / シェル / インタプリタ / ラッパー
    "sh": "arbitrary code execution (shell)",
    "bash": "arbitrary code execution (shell)",
    "zsh": "arbitrary code execution (shell)",
    "fish": "arbitrary code execution (shell)",
    "dash": "arbitrary code execution (shell)",
    "eval": "arbitrary code execution",
    "exec": "arbitrary code execution",
    "source": "arbitrary code execution",
    ".": "arbitrary code execution",
    "env": "arbitrary command wrapper",
    "nohup": "arbitrary command wrapper",
    "nice": "arbitrary command wrapper",
    "timeout": "arbitrary command wrapper",
    "command": "arbitrary command wrapper",
    "rtk": "bare rtk wrapper matches arbitrary subcommands",
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
    "fd": "supports -x / -X arbitrary command execution",
    "awk": "supports system() / file output",
    "gawk": "supports system() / file output",
    "sed": "supports in-place edit (-i) and execute",
    "yq": "supports in-place edit (-i)",
    # 任意ファイル内容読み取り・ファイル書き込み可能なユーティリティ（BypassSandbox 経由で read_file deny / sandbox 保護を迂回）
    "cat": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "head": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "tail": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "grep": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "egrep": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "fgrep": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rg": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "sort": "can write arbitrary files (-o) and read arbitrary files",
    "uniq": "can write arbitrary files (output arg) and read arbitrary files",
    "xxd": "can write arbitrary files (-r) and read arbitrary files",
    "strings": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "hexdump": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "cut": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "diff": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "comm": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "jq": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "tar": "supports --use-compress-program/-I/--to-command arbitrary execution and archive extraction",
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
    "git", "gh", "nix", "docker", "npm", "pnpm", "yarn",
    "brew", "cargo", "go", "mise", "uv", "home-manager",
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
}

# 安全とみなすサブコマンド（known-safe ラベル付け用）
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
    "nix store ls", "nix store path-info",
    "home-manager generations", "home-manager build",
    # JS / TS 検証系
    "npm test", "npm run lint", "npm run typecheck", "npm run check",
    "npm run test", "npm run build", "npm ls", "npm outdated",
    "pnpm test", "pnpm run lint", "pnpm run typecheck", "pnpm run check",
    "yarn test", "yarn lint", "yarn typecheck",
    "npx jest", "npx vitest", "npx tsc --noEmit", "npx prettier --check",
    "npx eslint", "tsc --noEmit", "prettier --check",
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
    # UNIX 読み取り専用ユーティリティ（任意ファイル内容読み取り・書き込み可能な cat/grep/sort/uniq/jq/tar 等は除外済み）
    "ls", "stat", "file", "wc", "tr",
    "cmp", "tree", "du", "df", "pwd", "which", "whereis",
    "type", "date", "uname", "whoami", "id", "hostname",
    "realpath", "readlink", "dirname", "basename", "shasum", "sha256sum",
    "md5", "md5sum", "unzip -p", "unzip -l", "unzip -Z",
    "sw_vers", "sysctl", "ps", "lsof",
    # RTK ネイティブ読み取り専用サブコマンド
    "rtk gain", "rtk discover", "rtk session", "rtk verify",
    "rtk hook-audit", "rtk cc-economics", "rtk help",
})

# RTK 自身の安全なネイティブサブコマンド（unwrap_tokens で rtk を剥がさない）
RTK_NATIVE_SAFE_SUBCOMMANDS = frozenset({
    "gain", "discover", "session", "verify", "hook-audit",
    "cc-economics", "help", "methods", "tasks", "pipeline",
})

# 安全な読み取り専用実行に必須フラグを要求するツール（直接呼び出し・npx 経由で共有）
REQUIRED_SAFE_FLAGS: dict[str, tuple[str, str]] = {
    "tsc": ("--noEmit", "tsc without --noEmit may write files"),
    "prettier": ("--check", "prettier without --check may write files"),
}

# 明示的に危険・書き込み系として除外するサブコマンドプレフィックス
UNSAFE_SUBCOMMAND_PREFIXES: dict[str, str] = {
    # rtk の危険・任意実行・機密ファイル読み取り迂回サブコマンド
    "rtk bypass": "bypasses RTK filter for arbitrary commands",
    "rtk proxy": "bypasses RTK filter for arbitrary commands (deprecated alias of rtk bypass)",
    "rtk run": "executes arbitrary command/shell via rtk",
    "rtk err": "executes arbitrary command via rtk",
    "rtk summary": "executes arbitrary command via rtk",
    "rtk test": "executes arbitrary command via rtk",
    "rtk trust": "modifies rtk trust configuration",
    "rtk untrust": "modifies rtk trust configuration",
    "rtk init": "modifies hooks/configuration",
    "rtk config": "modifies rtk configuration",
    "rtk read": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rtk grep": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rtk rg": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rtk find": "wraps find (can bypass file restrictions)",
    "rtk json": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rtk log": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rtk smart": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rtk ast-grep": "reads arbitrary files (can bypass read_file deny / sandbox protection)",
    "rtk plugins": "executes/manages arbitrary plugins",
    "rtk llm-proxy": "runs proxy / network service",
    "rtk telemetry": "modifies telemetry / network settings",
    "rtk env": "exposes environment variables / secrets",
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
    "gh auth token": "prints authentication token",
    # パッケージマネージャ・ランナー・コンテナ・クラスタ・IaC 変更系
    "uv run": "executes arbitrary command/script",
    "mise exec": "executes arbitrary command",
    "mise x": "executes arbitrary command",
    "cargo run": "compiles and executes arbitrary binary",
    "go run": "compiles and executes arbitrary code",
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
    "docker compose run": "executes arbitrary container",
    "docker container exec": "executes arbitrary command in container",
    "docker container run": "executes arbitrary container",
    "kubectl apply": "mutates cluster",
    "kubectl delete": "deletes cluster resources",
    "kubectl exec": "executes command in pod",
    "kubectl run": "executes arbitrary pod/container",
    "kubectl cp": "copies files to/from cluster pods",
    "kubectl edit": "mutates cluster",
    "kubectl patch": "mutates cluster",
    "terraform apply": "mutates infrastructure",
    "terraform destroy": "destroys infrastructure",
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

# 機密パス（先頭 / 付きの境界一致パターンと部分一致パターン）
SENSITIVE_PATH_SEGMENT_PATTERNS = (
    "/.ssh", "/.aws", "/.gnupg", "/.kube", "/.config/gcloud",
    "/.netrc", "/secrets", "/.env",
)
SENSITIVE_PATH_SUBSTR_PATTERNS = (
    "credentials", ".pem", ".key", ".p12", ".pfx",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
)

# Antigravity がプレフィックス一致を無効化するシェル構文
EXACT_MATCH_ONLY_RE = re.compile(
    r"\$\(|\$\(\(|`|<[(]|>[(]|(?<!\\)\{[^}\s,]+,[^}\s}]+\}"
)

# env の引数を 1 つ消費する安全な環境変数オプション（-S/--split-string/-P は任意実行・検索パス改変のため剥がさない）
ENV_VALUE_FLAGS = frozenset({"-u", "-C", "--unset", "--chdir"})
ENV_UNSAFE_FLAGS = frozenset({"-S", "--split-string", "-P"})
NICE_VALUE_RE = re.compile(r"^[+-]?\d+$")
TIMEOUT_DURATION_RE = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
WRAPPER_BINARIES = frozenset({"env", "nohup", "nice", "timeout", "command"})


@dataclasses.dataclass
class CommandStat:
    prefix: str
    total_count: int = 0
    bypass_count: int = 0
    sessions: set[str] = dataclasses.field(default_factory=set)
    samples: list[str] = dataclasses.field(default_factory=list)
    exact_match_only_count: int = 0
    has_env_prefix_count: int = 0
    non_pipe_downstream_count: int = 0

    def add_sample(self, raw: str) -> None:
        if len(self.samples) >= 3:
            return
        compact = " ".join(raw.split())
        if len(compact) > 120:
            compact = compact[:117] + "..."
        if compact not in self.samples:
            self.samples.append(compact)


@dataclasses.dataclass
class SimpleStat:
    key: str
    total_count: int = 0
    sessions: set[str] = dataclasses.field(default_factory=set)
    samples: list[str] = dataclasses.field(default_factory=list)

    def add_sample(self, raw: str) -> None:
        if len(self.samples) >= 3:
            return
        if raw not in self.samples:
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
    masked = re.sub(r"'[^']*'", "''", command)
    if EXACT_MATCH_ONLY_RE.search(masked):
        return True
    if re.search(r"\bgit\s+-c\b", masked):
        return True
    if re.search(r"\btar\b.*--to-command", masked):
        return True
    return False


def _find_heredoc_delims(
    line: str,
    in_single: bool = False,
    in_double: bool = False,
) -> tuple[list[tuple[str, bool]], bool, bool]:
    """クォート外・コメント外・算術展開外にある <<DELIM / <<'DELIM' / <<"DELIM" / <<-DELIM を抽出する。"""
    delims: list[tuple[str, bool]] = []
    escaped = False
    arith_depth = 0
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
        if not in_single and ch == "$" and i + 2 < n and line[i + 1 : i + 3] == "((":
            arith_depth += 1
            i += 3
            continue
        if arith_depth > 0:
            if ch == ")" and i + 1 < n and line[i + 1] == ")":
                arith_depth -= 1
                i += 2
            else:
                i += 1
            continue
        if not in_single and not in_double:
            if ch == "#" and (i == 0 or line[i - 1].isspace()):
                break
            if ch == "<" and i + 1 < n and line[i + 1] == "<":
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
    return delims, in_single, in_double


def strip_heredocs(command: str) -> str:
    """heredoc 本体（<<'EOF' ... EOF）を除去し、本文がコマンドとして誤分割されるのを防ぐ。"""
    if "<<" not in command:
        return command
    lines = command.splitlines()
    out: list[str] = []
    pending_delims: list[tuple[str, bool]] = []
    in_single = False
    in_double = False
    for line in lines:
        if pending_delims:
            delim, strip_tabs = pending_delims[0]
            check = line.lstrip("\t") if strip_tabs else line
            if check == delim:
                pending_delims.pop(0)
            continue
        out.append(line)
        found, in_single, in_double = _find_heredoc_delims(line, in_single, in_double)
        pending_delims.extend(found)
    return "\n".join(out)


def split_shell_segments_with_meta(command: str) -> list[tuple[str, bool]]:
    """クォートとエスケープを尊重して &&, ||, ;, |, &, サブシェル括弧, 改行 で分割し、(segment, is_pipe_downstream) を返す。"""
    command = strip_heredocs(command)
    segments: list[tuple[str, bool]] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    subexpr_depth = 0
    cur_pipe_downstream = False
    i = 0
    n = len(command)

    def flush(next_is_pipe: bool) -> None:
        nonlocal cur_pipe_downstream
        seg = "".join(buf).strip()
        if seg:
            segments.append((seg, cur_pipe_downstream))
        buf.clear()
        cur_pipe_downstream = next_is_pipe

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
                while i < n and command[i] != "\n":
                    i += 1
                continue
            # $(...) / $((...)) / <(...) / >(...) はサブシェル分割せず 1 セグメント内に保持
            if ch in ("$", "<", ">") and i + 1 < n and command[i + 1] == "(":
                subexpr_depth += 1
                buf.append(ch)
                buf.append("(")
                i += 2
                continue
            if ch == "(":
                if subexpr_depth > 0:
                    subexpr_depth += 1
                    buf.append(ch)
                else:
                    flush(False)
                i += 1
                continue
            if ch == ")":
                if subexpr_depth > 0:
                    subexpr_depth -= 1
                    buf.append(ch)
                else:
                    flush(False)
                i += 1
                continue
            if ch in (";", "\n"):
                flush(False)
                i += 1
                continue
            if ch == "&":
                if i + 1 < n and command[i + 1] == "&":
                    flush(False)
                    i += 2
                    continue
                if i + 1 < n and command[i + 1] == ">":
                    buf.append("&>")
                    i += 2
                    continue
                if buf and buf[-1] in (">", "<"):
                    buf.append(ch)
                    i += 1
                    continue
                # 単独の &（バックグラウンド実行）はセグメント区切り
                flush(False)
                i += 1
                continue
            if ch == "|":
                if i + 1 < n and command[i + 1] == "|":
                    flush(False)
                    i += 2
                elif i + 1 < n and command[i + 1] == "&":
                    flush(True)
                    i += 2
                else:
                    flush(True)
                    i += 1
                continue
        buf.append(ch)
        i += 1

    flush(False)
    return segments


def split_shell_segments(command: str) -> list[str]:
    """クォートとエスケープを尊重して &&, ||, ;, |, 改行 でコマンドを分割する。"""
    return [seg for seg, _ in split_shell_segments_with_meta(command)]


def _pad_unquoted_redirections(segment: str) -> str:
    """クォート外の空白なしリダイレクト（例: git push>/dev/null）の前後に空白を補う。"""
    out: list[str] = []
    in_single = False
    in_double = False
    escaped = False
    i = 0
    n = len(segment)
    while i < n:
        ch = segment[i]
        if escaped:
            out.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\" and not in_single:
            out.append(ch)
            escaped = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            out.append(ch)
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            out.append(ch)
            i += 1
            continue
        if not in_single and not in_double and ch in ("<", ">"):
            # 直前の fd 数字 (例: 2>&1) または &>（&&> は除く）をリダイレクト側へ寄せる
            fd_prefix = ""
            if out and out[-1].isdigit() and (len(out) == 1 or out[-2].isspace()):
                fd_prefix = out.pop()
            elif out and out[-1] == "&" and ch == ">" and not (len(out) >= 2 and out[-2] == "&"):
                fd_prefix = out.pop()
            op = fd_prefix + ch
            i += 1
            while i < n and segment[i] in ("<", ">", "&", "-"):
                nxt = segment[i]
                if nxt == "-" and not (op == "<<" or op.endswith("&")):
                    break
                op += nxt
                i += 1
                if op.endswith("&") and i < n and segment[i].isdigit():
                    op += segment[i]
                    i += 1
                    break
            out.append(f" {op} ")
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def tokenize_segment(segment: str) -> list[str]:
    """シェルセグメントをトークン化する。shlex が失敗したら空白分割にフォールバック。"""
    padded = _pad_unquoted_redirections(segment)
    try:
        tokens = shlex.split(padded, posix=True)
    except ValueError:
        tokens = padded.split()
    # リダイレクト（2>&1, >/dev/null, <<-EOF, >& /dev/null, 2>&- 等）を取り除く
    cleaned: list[str] = []
    skip_next = False
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        # 直後トークンをターゲット/区切り子として消費する演算子（>&- / <&- / 2>&1 は消費しない）
        if re.match(r"^(?:\d*<<-|(?:&|\d*)[<>]+|\d*>&)$", tok):
            skip_next = True
            continue
        if re.match(r"^(?:&|\d*)[<>].+$", tok):
            continue
        cleaned.append(tok)
    return cleaned


def normalize_binary(tok: str) -> str:
    """フルパス指定（/usr/bin/python3 等）をコマンド名へ正規化する。"""
    if "/" in tok and not tok.startswith("./") and not tok.startswith("../"):
        return os.path.basename(tok)
    return tok


def unwrap_tokens(tokens: list[str]) -> tuple[list[str], bool, bool]:
    """先頭の環境変数代入・透過ラッパー（env, timeout, nohup, nice, command）・安全な rtk を剥がす。

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
        norm = normalize_binary(tok)
        if norm == "env":
            env_idx = idx
            idx += 1
            unsafe_env = False
            while idx < n:
                cur = tokens[idx]
                if cur == "--":
                    idx += 1
                    break
                if ENV_ASSIGN_RE.match(cur):
                    had_env = True
                    idx += 1
                    continue
                if (
                    cur in ENV_UNSAFE_FLAGS
                    or cur.startswith("--split-string=")
                    or cur.startswith("-S")
                    or cur.startswith("-P")
                    or (cur.startswith("-") and not cur.startswith("--") and ("S" in cur[1:] or "P" in cur[1:]))
                ):
                    unsafe_env = True
                    break
                if cur in ENV_VALUE_FLAGS and idx + 1 < n:
                    idx += 2
                    continue
                if cur.startswith("-"):
                    idx += 1
                    continue
                break
            if unsafe_env:
                return tokens[env_idx:], had_env, was_rtk
            continue
        if norm == "nohup":
            idx += 1
            continue
        if norm == "command":
            idx += 1
            is_query = False
            while idx < n and tokens[idx].startswith("-") and tokens[idx] != "--":
                flag = tokens[idx]
                if "v" in flag[1:] or "V" in flag[1:]:
                    is_query = True
                idx += 1
            if is_query:
                return [], had_env, was_rtk
            if idx < n and tokens[idx] == "--":
                idx += 1
            continue
        if norm == "nice":
            nice_idx = idx
            idx += 1
            if idx < n and tokens[idx] == "-n":
                if idx + 1 < n and NICE_VALUE_RE.match(tokens[idx + 1]):
                    idx += 2
                else:
                    return tokens[nice_idx:], had_env, was_rtk
            elif idx < n and re.match(r"^-\d+$", tokens[idx]):
                idx += 1
            continue
        if norm == "timeout":
            to_idx = idx
            idx += 1
            while idx < n and tokens[idx].startswith("-"):
                if tokens[idx] == "--":
                    idx += 1
                    break
                if tokens[idx] in ("-s", "-k", "--signal", "--kill-after") and idx + 1 < n:
                    idx += 2
                else:
                    idx += 1
            if idx < n and TIMEOUT_DURATION_RE.match(tokens[idx]):
                idx += 1
            else:
                return tokens[to_idx:], had_env, was_rtk
            continue
        if norm == "rtk":
            if idx + 1 >= n:
                break
            next_tok = tokens[idx + 1]
            if (
                next_tok.startswith("-")
                or f"rtk {next_tok}" in UNSAFE_SUBCOMMAND_PREFIXES
                or next_tok in RTK_NATIVE_SAFE_SUBCOMMANDS
            ):
                break
            was_rtk = True
            idx += 1
            continue
        break
    return tokens[idx:], had_env, was_rtk


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

    # rtk 単独・フラグ付き・危険サブコマンドを明示的に除外し、安全なネイティブサブコマンドのみ許可
    if cmd == "rtk":
        if len(tokens) >= 2:
            sub = f"rtk {tokens[1]}"
            if sub in UNSAFE_SUBCOMMAND_PREFIXES:
                return sub, UNSAFE_SUBCOMMAND_PREFIXES[sub]
            if tokens[1].startswith("-"):
                return sub, "rtk global flag before subcommand is unsafe"
            if tokens[1] in RTK_NATIVE_SAFE_SUBCOMMANDS:
                return sub, None
        return "rtk", UNSAFE_COMMANDS["rtk"]

    # UNSAFE_COMMANDS は VALID_CMD_RE より先に評価する（"." などの記号コマンドを取りこぼさないため）
    if cmd in UNSAFE_COMMANDS:
        prefix = f"{cmd} {tokens[1]}" if len(tokens) >= 2 and tokens[1].startswith("-") else cmd
        return prefix, UNSAFE_COMMANDS[cmd]

    if not VALID_CMD_RE.match(cmd):
        return None, None

    # git の危険なグローバルオプション (-C, -c, --exec-path, --git-dir, --work-tree)
    if cmd == "git" and len(tokens) >= 2:
        if tokens[1] in ("-C", "-c", "--exec-path", "--git-dir", "--work-tree") or tokens[1].startswith(
            ("--exec-path=", "--git-dir=", "--work-tree=")
        ):
            return f"git {tokens[1].split('=', 1)[0]}", "git global flag allows arbitrary repo/command execution"
        if any(t in ("-c", "--exec-path") or t.startswith("--exec-path=") for t in tokens[1:]):
            return "git -c", "git -c/--exec-path allows arbitrary command execution"

    # gh の -R / --repo をサブコマンドの前に置くと全サブコマンドに一致してしまう
    if cmd == "gh" and len(tokens) >= 2 and tokens[1] in ("-R", "--repo"):
        return f"gh {tokens[1]}", "gh -R before subcommand would match write subcommands too"

    # 直接呼び出しの prettier / tsc（rtk rewrite 後を含む）も安全フラグを要求
    if cmd in REQUIRED_SAFE_FLAGS:
        req_flag, req_reason = REQUIRED_SAFE_FLAGS[cmd]
        if req_flag in tokens[1:]:
            return f"{cmd} {req_flag}", None
        return cmd, req_reason

    # npx / pnpx / bunx の特別扱い（ツール名＋安全フラグを残し、危険コマンドやパス指定を拒否）
    if cmd in ("npx", "pnpx", "bunx"):
        rest = [t for t in tokens[1:] if t not in ("-y", "--yes", "--no-install")]
        if not rest:
            return cmd, "bare package runner"
        pkg = rest[0]
        if pkg.startswith("-"):
            return f"{cmd} {pkg}", "flag passed to package runner may execute arbitrary command/package"
        if pkg.startswith(("/", "./", "../", "~")) or ("/" in pkg and not pkg.startswith("@")):
            return f"{cmd} {pkg}", "path-qualified package in package runner"
        if pkg.startswith("@"):
            if not re.fullmatch(r"@[A-Za-z0-9._-]+/[A-Za-z0-9._-]+(?:@[A-Za-z0-9._+-]+)?", pkg):
                return f"{cmd} {pkg}", "invalid scoped package name in package runner"
            base_pkg = pkg.split("/", 1)[1].split("@", 1)[0]
        else:
            base_pkg = pkg.split("@", 1)[0]
            if not VALID_CMD_RE.match(base_pkg):
                return f"{cmd} {pkg}", "invalid package name in package runner"
        if base_pkg in UNSAFE_COMMANDS or base_pkg in WRAPPER_BINARIES or base_pkg in SHELL_BUILTINS:
            return f"{cmd} {pkg}", f"unsafe package/command in package runner ({base_pkg})"
        if base_pkg in REQUIRED_SAFE_FLAGS:
            req_flag, req_reason = REQUIRED_SAFE_FLAGS[base_pkg]
            if req_flag in rest[1:]:
                return f"{cmd} {base_pkg} {req_flag}", None
            return f"{cmd} {base_pkg}", req_reason
        return f"{cmd} {pkg}", None

    # unzip の読み取り専用フラグチェック（tar は --use-compress-program 等の任意実行経路があるため UNSAFE_COMMANDS 側で一律除外）
    if cmd == "unzip":
        if len(tokens) >= 2 and tokens[1] in ("-p", "-l", "-Z"):
            return f"unzip {tokens[1]}", None
        return "unzip", "extracts files to disk (only -p/-l/-Z are read-only)"

    # 3階層サブコマンド（gh pr view, nix flake show, npm run lint 等）
    if len(tokens) >= 3 and (cmd, tokens[1]) in THREE_LEVEL_GROUPS:
        sub3 = tokens[2]
        if sub3.startswith("-") and not (cmd == "git" and tokens[1] == "remote" and sub3 == "-v"):
            return f"{cmd} {tokens[1]}", "too broad (flag instead of subcommand)"
        if not (cmd == "git" and tokens[1] == "remote" and sub3 == "-v") and not VALID_SUBCMD_RE.match(sub3):
            return f"{cmd} {tokens[1]}", "invalid subcommand token"
        prefix = f"{cmd} {tokens[1]} {sub3}"
        if prefix in UNSAFE_SUBCOMMAND_PREFIXES:
            return prefix, UNSAFE_SUBCOMMAND_PREFIXES[prefix]
        return prefix, None

    # 2階層サブコマンド
    if cmd in TWO_LEVEL_CLIS:
        if len(tokens) >= 2 and not tokens[1].startswith("-"):
            if not VALID_SUBCMD_RE.match(tokens[1]):
                return cmd, "invalid subcommand token"
            prefix = f"{cmd} {tokens[1]}"
            if prefix in UNSAFE_SUBCOMMAND_PREFIXES:
                return prefix, UNSAFE_SUBCOMMAND_PREFIXES[prefix]
            if (cmd, tokens[1]) in THREE_LEVEL_GROUPS:
                return prefix, "too broad (covers both read and write subcommands)"
            return prefix, None
        return cmd, "bare CLI without subcommand would match write subcommands"

    # 単体コマンド（ls, stat, jq 等）
    return cmd, None


def parse_rule(rule: str) -> tuple[str, str] | None:
    if not isinstance(rule, str):
        return None
    m = RULE_RE.match(rule.strip())
    if not m:
        return None
    return m.group(1), m.group(2)


def _split_regex_top_level_tokens(pattern: str) -> list[str]:
    """括弧 (...)・文字クラス [...] 内の空白では割らず、トップレベル空白のみで分割する。"""
    tokens: list[str] = []
    buf: list[str] = []
    paren_depth = 0
    in_bracket = False
    escaped = False
    for ch in pattern:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            buf.append(ch)
            escaped = True
            continue
        if in_bracket:
            buf.append(ch)
            if ch == "]":
                in_bracket = False
            continue
        if ch == "[":
            in_bracket = True
            buf.append(ch)
            continue
        if ch == "(":
            paren_depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            paren_depth = max(0, paren_depth - 1)
            buf.append(ch)
            continue
        if ch.isspace() and paren_depth == 0:
            if buf:
                tokens.append("".join(buf))
                buf.clear()
            continue
        buf.append(ch)
    if buf:
        tokens.append("".join(buf))
    return tokens


def _ends_with_unescaped_dollar(pattern: str) -> bool:
    if not pattern.endswith("$"):
        return False
    backslashes = 0
    i = len(pattern) - 2
    while i >= 0 and pattern[i] == "\\":
        backslashes += 1
        i -= 1
    return (backslashes % 2) == 0


def _split_top_level_alternation(pattern: str) -> list[str]:
    """括弧 (...)・文字クラス [...] 外のトップレベル `|` でパターンを分割する。"""
    branches: list[str] = []
    buf: list[str] = []
    paren_depth = 0
    in_bracket = False
    escaped = False
    for ch in pattern:
        if escaped:
            buf.append(ch)
            escaped = False
            continue
        if ch == "\\":
            buf.append(ch)
            escaped = True
            continue
        if in_bracket:
            buf.append(ch)
            if ch == "]":
                in_bracket = False
            continue
        if ch == "[":
            in_bracket = True
            buf.append(ch)
            continue
        if ch == "(":
            paren_depth += 1
            buf.append(ch)
            continue
        if ch == ")":
            paren_depth = max(0, paren_depth - 1)
            buf.append(ch)
            continue
        if ch == "|" and paren_depth == 0:
            branches.append("".join(buf))
            buf.clear()
            continue
        buf.append(ch)
    branches.append("".join(buf))
    return branches


def command_rule_matches_prefix(rule_target: str, candidate_prefix: str) -> bool:
    """Antigravity の command(...) ルールが候補プレフィックスに一致するか判定する。"""
    target = rule_target.strip()
    cand = candidate_prefix.strip()
    if not target or not cand:
        return False
    if target == "*":
        return True
    if target.startswith("regex:"):
        pattern = target[len("regex:"):].strip()
        if not pattern:
            return False
        if cand.startswith("regex:"):
            return pattern == cand[len("regex:"):].strip()
        try:
            compiled = re.compile(pattern)
        except re.error:
            return False
        cand_toks = cand.split()
        anchored_end = _ends_with_unescaped_dollar(pattern)
        # まず Antigravity のトークン単位アンカー仕様（例: regex:git log|diff）を優先評価する
        rule_toks = _split_regex_top_level_tokens(pattern)
        if rule_toks and len(rule_toks) <= len(cand_toks) and (not anchored_end or len(rule_toks) == len(cand_toks)):
            try:
                if all(re.fullmatch(rt, ct) for rt, ct in zip(rule_toks, cand_toks)):
                    return True
            except re.error:
                pass
        # 括弧外 `|` で片側だけ単一トークンになるパターン（例: regex:git log|diff）は
        # トークン単位指定とみなし、全体 fullmatch による単独 "diff" 誤一致を防ぐ
        top_branches = _split_top_level_alternation(pattern)
        if len(top_branches) > 1 and any(" " not in b.strip() for b in top_branches) and any(" " in b.strip() for b in top_branches):
            return False
        if compiled.fullmatch(cand):
            return True
        if not anchored_end:
            for k in range(1, len(cand_toks)):
                if compiled.fullmatch(" ".join(cand_toks[:k])):
                    return True
        return False

    if cand.startswith("regex:"):
        return False

    rule_toks = target.split()
    cand_toks = cand.split()
    if not rule_toks or len(rule_toks) > len(cand_toks):
        return False
    return cand_toks[: len(rule_toks)] == rule_toks


def mcp_rule_matches(rule_target: str, mcp_target: str) -> bool:
    target = rule_target.strip()
    cand = mcp_target.strip()
    if not target or not cand:
        return False
    if target in ("*", "*/*"):
        return True
    if target == cand:
        return True
    if target.endswith("/*"):
        server = target[:-2]
        return cand.startswith(server + "/")
    return False


def url_rule_matches(rule_target: str, domain: str) -> bool:
    target = rule_target.strip().lower()
    dom = domain.strip().lower()
    if not target or not dom:
        return False
    if target == "*":
        return True
    return dom == target or dom.endswith("." + target)


def _normalize_rule_path(path: str) -> str:
    norm = path.strip().replace("\\", "/")
    if not norm:
        return ""
    if norm == "~" or norm.startswith("~/"):
        norm = os.path.expanduser(norm).replace("\\", "/")
    normalized = posixpath.normpath(norm)
    # posixpath.normpath("//foo") は POSIX 仕様で "//foo" を残すため "/" へ正規化する
    if normalized.startswith("//"):
        normalized = "/" + normalized.lstrip("/")
    return normalized


def file_rule_matches(rule_target: str, candidate_path: str) -> bool:
    if rule_target.strip() == "*":
        return True
    target = _normalize_rule_path(rule_target)
    cand = _normalize_rule_path(candidate_path)
    if not target or not cand:
        return False
    if target == "/":
        return cand.startswith("/")
    if target == ".":
        return not cand.startswith("/") and cand != ".." and not cand.startswith("../")
    if cand == target:
        return True
    return cand.startswith(target + "/")


def is_sensitive_path(path: str) -> bool:
    """相対パス・絶対パス・チルダ表記・//や./・親ディレクトリを問わず機密ファイル・ディレクトリを検出する。"""
    raw = path.strip().replace("\\", "/").lower()
    if not raw:
        return False
    if raw.startswith("~/"):
        raw = raw[2:]
    norm = posixpath.normpath(raw)
    if norm.startswith("//"):
        norm = "/" + norm.lstrip("/")
    anchored = "/" + norm.lstrip("/")
    for pat in SENSITIVE_PATH_SEGMENT_PATTERNS:
        if pat in anchored:
            return True
        # 複数セグメントの機密パス（例: /.config/gcloud）の親ディレクトリ（例: ~/.config）も拒否
        parts = [p for p in pat.split("/") if p]
        for k in range(1, len(parts)):
            parent_pat = "/" + "/".join(parts[:k])
            if anchored == parent_pat or anchored.endswith(parent_pat):
                return True
    return any(pat in norm for pat in SENSITIVE_PATH_SUBSTR_PATTERNS)


def _is_overly_broad_file_path(path: str) -> bool:
    """ファイルシステム全体・ホーム全体/親・カレント/親参照を含む広域パスか判定する。"""
    raw = path.strip().replace("\\", "/")
    if raw in ("/", "~", "~/", ".", ".."):
        return True
    if ".." in raw.split("/"):
        return True
    if raw.startswith("~") and not raw.startswith("~/"):
        return True
    norm = _normalize_rule_path(raw)
    home = _normalize_rule_path("~")
    if norm in ("", "/", ".", "..", home):
        return True
    if home.startswith(norm + "/"):
        return True
    if ".." in norm.split("/"):
        return True
    return False


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
            # Antigravity 暗黙ルール: deny read_file は write_file もブロック、allow write_file は read_file も許可
            if action in ("read_file", "write_file"):
                matches_action = (
                    r_action == action
                    or (bucket == "deny" and action == "write_file" and r_action == "read_file")
                    or (bucket == "allow" and action == "read_file" and r_action == "write_file")
                )
                if matches_action and file_rule_matches(r_target, target):
                    return bucket
                continue
            if r_action != action:
                continue
            if action == "command" and command_rule_matches_prefix(r_target, target):
                return bucket
            if action == "mcp" and mcp_rule_matches(r_target, target):
                return bucket
            if action in ("read_url", "execute_url", "download_url") and url_rule_matches(r_target, target):
                return bucket
    return "none"


def _read_settings_json(settings_path: str) -> tuple[dict[str, Any], str]:
    """settings.json を読み込み (data, resolved_real_path) を返す。

    ファイルが本当に存在しない場合（FileNotFoundError）のみ空 dict を返す。
    壊れた symlink・PermissionError・破損 JSON・非 dict ルートは明示的に例外を送出する。
    """
    if os.path.islink(settings_path):
        try:
            os.stat(settings_path)
        except FileNotFoundError:
            raise ValueError(f"settings path is a broken symlink: {settings_path}") from None
    real_path = os.path.realpath(settings_path)
    try:
        with open(real_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {}, real_path
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValueError(f"failed to parse settings file ({settings_path}): {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"settings file root must be a JSON object: {settings_path}")
    return data, real_path


def _extract_validated_permissions(
    data: dict[str, Any],
    settings_path: str,
) -> tuple[dict[str, list[str]], list[str]]:
    """settings dict から型検証済みの permissions と既存ルール構文警告を返す。"""
    if "permissions" not in data:
        return {"allow": [], "ask": [], "deny": []}, []
    perms_raw = data["permissions"]
    if not isinstance(perms_raw, dict):
        raise ValueError(f"settings.permissions must be a JSON object: {settings_path}")

    permissions: dict[str, list[str]] = {}
    warnings: list[str] = []
    for bucket in ("allow", "ask", "deny"):
        raw_list = perms_raw.get(bucket)
        if raw_list is None:
            permissions[bucket] = []
            continue
        if not isinstance(raw_list, list) or not all(isinstance(x, str) for x in raw_list):
            raise ValueError(
                f"settings.permissions.{bucket} must be a list of strings: {settings_path}"
            )
        permissions[bucket] = list(raw_list)
        for rule in raw_list:
            parsed = parse_rule(rule)
            if not parsed:
                warnings.append(f"existing permissions.{bucket} contains invalid rule syntax: {rule!r}")
                continue
            r_action, r_target = parsed
            if r_action == "command" and r_target.strip().startswith("regex:"):
                pattern = r_target.strip()[len("regex:"):].strip()
                if not pattern:
                    warnings.append(f"existing permissions.{bucket} contains empty regex rule: {rule!r}")
                else:
                    try:
                        re.compile(pattern)
                    except re.error as exc:
                        warnings.append(
                            f"existing permissions.{bucket} contains invalid regex {rule!r}: {exc}"
                        )
    return permissions, warnings


def load_permissions(settings_path: str) -> tuple[dict[str, list[str]], list[str]]:
    data, _ = _read_settings_json(settings_path)
    return _extract_validated_permissions(data, settings_path)


def detect_rtk_hook_enabled(hooks_path: str) -> tuple[bool, list[str]]:
    """RTK PreToolUse フックが有効か判定する。読取異常や rtk 未検出は警告を返す。"""
    warnings: list[str] = []
    try:
        with open(hooks_path, encoding="utf-8") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return False, warnings
    except (OSError, UnicodeDecodeError) as exc:
        warnings.append(f"could not read hooks config ({hooks_path}): {exc}")
        return False, warnings
    if "rtk hook antigravity" not in raw:
        return False, warnings
    if not shutil.which("rtk"):
        warnings.append(
            f"RTK hook is configured in {hooks_path}, but 'rtk' binary was not found in PATH"
        )
        return False, warnings
    return True, warnings


def _build_rtk_probe_commands(
    prefix: str,
    sample_cmd: str | None = None,
    only_pipe_downstream: bool = False,
) -> list[str]:
    """rtk rewrite へ渡す検証コマンド候補を順に返す（フラグ途中で切らない）。"""
    if only_pipe_downstream:
        return []
    probes: list[str] = []
    if sample_cmd:
        segs = split_shell_segments(sample_cmd)
        if segs:
            toks, _, _ = unwrap_tokens(tokenize_segment(segs[0]))
            if toks and " ".join(toks).startswith(prefix) and len(toks) <= 12:
                probes.append(shlex.join(toks))
    if prefix not in probes:
        probes.append(prefix)
    if " " in prefix:
        probe_with_arg = f"{prefix} 1"
        if probe_with_arg not in probes:
            probes.append(probe_with_arg)
    return probes


def compute_rtk_prefix(
    prefix: str,
    sample_cmd: str | None = None,
    only_pipe_downstream: bool = False,
    warnings_out: list[str] | None = None,
) -> str | None:
    """rtk rewrite を実行し、安全分類を再適用した command(rtk ...) プレフィックスを返す。"""
    if prefix.startswith("rtk "):
        return None
    for test_cmd in _build_rtk_probe_commands(prefix, sample_cmd, only_pipe_downstream):
        try:
            res = subprocess.run(
                ["rtk", "rewrite", test_cmd],
                capture_output=True,
                text=True,
                timeout=2,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            if warnings_out is not None:
                warnings_out.append(f"rtk rewrite failed for {prefix!r}: {exc}")
            return None
        # rtk rewrite の正常終了コードは 0(allow書換), 1(未書換), 2(deny), 3(ask書換)
        if res.returncode not in (0, 1, 2, 3):
            if warnings_out is not None:
                stderr_snippet = (res.stderr or "").strip()[:100]
                suffix = f" ({stderr_snippet})" if stderr_snippet else ""
                warnings_out.append(
                    f"rtk rewrite exited with unexpected code {res.returncode} for {prefix!r}{suffix}"
                )
            return None
        rewritten = (res.stdout or "").strip()
        if not rewritten or not rewritten.startswith("rtk "):
            continue
        rw_toks = tokenize_segment(rewritten)
        if len(rw_toks) < 2 or rw_toks[0] != "rtk":
            continue
        # rtk 固有の危険サブコマンド（rtk read / rtk grep / rtk run 等）は提案しない
        if f"rtk {rw_toks[1]}" in UNSAFE_SUBCOMMAND_PREFIXES:
            return None
        # 書き換え後の実コマンドを classify_command_tokens で再分類し、--check / --noEmit 等の安全フラグを保持する
        inner_prefix, inner_reason = classify_command_tokens(rw_toks[1:])
        if inner_prefix is None or inner_reason is not None:
            return None
        return f"rtk {inner_prefix}"
    return None


def find_antigravity_transcripts(
    antigravity_dir: str,
    limit: int,
    warnings_out: list[str] | None = None,
    unreadable_out: list[str] | None = None,
) -> list[tuple[str, str]]:
    """直近 limit 件の (conversation_id, transcript_path) を新しい順に返す。

    brain/ の不存在や PermissionError は握り潰さず OSError を送出する。
    個別セッション配下の PermissionError 等は warnings_out / unreadable_out へ記録する。
    """
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    brain_dir = os.path.join(antigravity_dir, "brain")
    entries = os.listdir(brain_dir)
    found: list[tuple[float, str, str]] = []
    for entry in entries:
        if not UUID_RE.match(entry):
            continue
        logs_dir = os.path.join(brain_dir, entry, ".system_generated", "logs")
        chosen: tuple[float, str] | None = None
        for fname in ("transcript_full.jsonl", "transcript.jsonl"):
            candidate = os.path.join(logs_dir, fname)
            try:
                st = os.stat(candidate)
            except (FileNotFoundError, NotADirectoryError):
                continue
            except OSError as exc:
                if unreadable_out is not None:
                    unreadable_out.append(candidate)
                if warnings_out is not None:
                    warnings_out.append(f"could not stat transcript for session {entry}: {exc}")
                break
            if stat_mod.S_ISREG(st.st_mode):
                chosen = (st.st_mtime, candidate)
                break
        if chosen:
            found.append((chosen[0], entry, chosen[1]))
    found.sort(key=lambda item: item[0], reverse=True)
    return [(cid, path) for _, cid, path in found[:limit]]


def normalize_mcp_tool_name(tool_name: str) -> str:
    """MCP ツール名を Antigravity の server/tool 形式へ可能な範囲で正規化する。"""
    if "/" in tool_name:
        return tool_name
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
    # camelCase / PascalCase 境界を分割してから小文字化する（例: writeFile -> write_file）
    spaced = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", tool_name)
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", spaced)
    tokens = re.split(r"[^a-z0-9]+", spaced.lower())
    return any(tok in MCP_MUTATING_KEYWORDS for tok in tokens)


def scan_transcripts(
    antigravity_dir: str,
    settings_path: str,
    hooks_path: str,
    limit: int = 50,
    min_count: int = 2,
    check_rtk: bool | None = None,
) -> dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be a positive integer")
    if min_count <= 0:
        raise ValueError("min_count must be a positive integer")

    warnings: list[str] = []
    unreadable_stat_paths: list[str] = []
    transcripts = find_antigravity_transcripts(
        antigravity_dir,
        limit,
        warnings_out=warnings,
        unreadable_out=unreadable_stat_paths,
    )
    permissions, perm_warnings = load_permissions(settings_path)
    warnings.extend(perm_warnings)

    if check_rtk is None:
        rtk_enabled, rtk_warnings = detect_rtk_hook_enabled(hooks_path)
        warnings.extend(rtk_warnings)
    elif check_rtk:
        if not shutil.which("rtk"):
            raise ValueError("rtk binary not found in PATH (--check-rtk)")
        rtk_enabled = True
    else:
        rtk_enabled = False

    cmd_stats: dict[str, CommandStat] = {}
    rtk_seen_prefixes: set[str] = set()
    excluded_cmds: dict[str, tuple[CommandStat, str]] = {}
    mcp_stats: dict[str, SimpleStat] = {}
    excluded_mcp: dict[str, tuple[SimpleStat, str]] = {}
    url_stats: dict[str, SimpleStat] = {}

    total_run_commands = 0
    total_bypass_commands = 0
    sessions_scanned = 0
    unreadable_files = len(unreadable_stat_paths)
    malformed_lines = 0

    for conv_id, path in transcripts:
        try:
            fh = open(path, encoding="utf-8", errors="ignore")
        except OSError as exc:
            unreadable_files += 1
            warnings.append(f"could not open transcript for session {conv_id}: {exc}")
            continue
        file_has_valid_json = False
        file_line_count = 0
        with fh:
            for line in fh:
                stripped_line = line.strip()
                if not stripped_line:
                    continue
                file_line_count += 1
                # tool_calls を含まない巨大なツール出力行は json.loads を省くが、
                # 最初の有効 JSON 確認前・および {...} 形式でない行は破損検出のためパース検証する
                if '"tool_calls"' not in line:
                    if not file_has_valid_json or not (
                        stripped_line.startswith("{") and stripped_line.endswith("}")
                    ):
                        try:
                            probe_obj = json.loads(stripped_line)
                        except json.JSONDecodeError:
                            malformed_lines += 1
                            continue
                        if not isinstance(probe_obj, dict):
                            malformed_lines += 1
                            continue
                        file_has_valid_json = True
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines += 1
                    continue
                if not isinstance(obj, dict):
                    malformed_lines += 1
                    continue
                file_has_valid_json = True
                tool_calls = obj.get("tool_calls")
                if not isinstance(tool_calls, list):
                    continue
                for tc in tool_calls:
                    if not isinstance(tc, dict):
                        continue
                    name = tc.get("name")
                    args = tc.get("args")
                    if not isinstance(name, str) or not isinstance(args, dict):
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

                        for seg, is_pipe_downstream in split_shell_segments_with_meta(raw_cmd):
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
                                if was_rtk:
                                    rtk_seen_prefixes.add(prefix)
                                if prefix not in cmd_stats:
                                    cmd_stats[prefix] = CommandStat(prefix=prefix)
                                st = cmd_stats[prefix]
                            st.total_count += 1
                            if is_bypass:
                                st.bypass_count += 1
                            st.sessions.add(conv_id)
                            if exact_only:
                                st.exact_match_only_count += 1
                            if had_env:
                                st.has_env_prefix_count += 1
                            if not is_pipe_downstream:
                                st.non_pipe_downstream_count += 1
                            st.add_sample(seg)

                    elif name == "read_url_content":
                        raw_url = _decode_arg_value(args.get("Url") or args.get("url") or "")
                        if isinstance(raw_url, str) and raw_url.startswith(("http://", "https://")):
                            try:
                                host = (urllib.parse.urlparse(raw_url).hostname or "").lower()
                            except ValueError:
                                continue
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
        if file_line_count == 0 or file_has_valid_json:
            sessions_scanned += 1
        else:
            warnings.append(f"transcript for session {conv_id} contained no valid JSONL lines")

    if malformed_lines > 0:
        warnings.append(f"skipped {malformed_lines} malformed JSONL line(s) across transcripts")

    # RTK リライト判定を並列実行（min_count 通過後のユニークプレフィックスのみ）
    eligible_cmds = [(p, st) for p, st in cmd_stats.items() if st.total_count >= min_count]
    rtk_map: dict[str, str | None] = {}
    if rtk_enabled and eligible_cmds:
        def _probe_one(item: tuple[str, CommandStat]) -> tuple[str, str | None, list[str]]:
            p, st = item
            local_warn: list[str] = []
            res = compute_rtk_prefix(
                p,
                st.samples[0] if st.samples else None,
                only_pipe_downstream=(st.non_pipe_downstream_count == 0),
                warnings_out=local_warn,
            )
            return p, res, local_warn

        max_workers = min(8, len(eligible_cmds))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            for p, rtk_p, local_warn in pool.map(_probe_one, eligible_cmds):
                rtk_map[p] = rtk_p
                warnings.extend(local_warn)
    elif check_rtk is None and rtk_seen_prefixes:
        # RTK フック未検出でもトランスクリプトに rtk <cmd> が記録されていた安全なプレフィックスは保持する
        for p, _ in eligible_cmds:
            if p in rtk_seen_prefixes and not p.startswith("rtk "):
                rtk_map[p] = f"rtk {p}"

    candidates: list[dict[str, Any]] = []
    already_allowed: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []

    for prefix, st in eligible_cmds:
        status = check_rule_status("command", prefix, permissions)
        rtk_prefix = rtk_map.get(prefix)
        rtk_status = check_rule_status("command", rtk_prefix, permissions) if rtk_prefix else "n/a"

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

    # MCP・read_url 候補（いずれも既定 Ask のため高優先）
    for kind, stats_map in (("mcp", mcp_stats), ("read_url", url_stats)):
        for key, st in stats_map.items():
            if st.total_count < min_count:
                continue
            status = check_rule_status(kind, key, permissions)
            rule_str = f"{kind}({key})"
            item = {
                "kind": kind,
                "prefix": key,
                "rule": rule_str,
                "rtk_rule": None,
                "suggested_rules": [rule_str] if status == "none" else [],
                "status": status,
                "rtk_status": "n/a",
                "total_count": st.total_count,
                "bypass_count": st.total_count,
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
            "sessions_scanned": sessions_scanned,
            "sessions_found": len(transcripts),
            "unreadable_files": unreadable_files,
            "malformed_lines": malformed_lines,
            "total_run_commands": total_run_commands,
            "total_bypass_commands": total_bypass_commands,
            "settings_path": settings_path,
            "existing_allow_count": len(permissions["allow"]),
            "existing_ask_count": len(permissions["ask"]),
            "existing_deny_count": len(permissions["deny"]),
            "rtk_hook_detected": rtk_enabled,
        },
        "warnings": warnings,
        "candidates": candidates,
        "already_allowed": already_allowed,
        "conflicts": conflicts,
        "excluded": excluded_list[:20],
    }


def render_markdown(report: dict[str, Any], max_candidates: int = 30) -> str:
    if max_candidates <= 0:
        raise ValueError("max_candidates must be a positive integer")
    s = report["summary"]
    lines: list[str] = [
        "# Antigravity Permission Allowlist Analysis",
        "",
        f"- Scanned sessions: **{s['sessions_scanned']}**",
        f"- Total `run_command`: **{s['total_run_commands']}** (BypassSandbox: **{s['total_bypass_commands']}**)",
        f"- Settings: `{s['settings_path']}` (allow: {s['existing_allow_count']}, ask: {s['existing_ask_count']}, deny: {s['existing_deny_count']})",
        f"- RTK hook active: **{'yes' if s['rtk_hook_detected'] else 'no'}**",
        "",
    ]

    if report.get("warnings"):
        lines.extend(["## Warnings", ""])
        for w in report["warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    lines.extend(["## Candidates (Prioritized)", ""])

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
    if target != target_stripped:
        return f"rule target must not have leading or trailing whitespace: {rule}"
    if CONTROL_CHAR_RE.search(target_stripped):
        return f"rule target must not contain control characters: {rule}"
    if target_stripped == "*":
        return f"refusing global wildcard rule for safety: {rule}"

    if action in ("read_file", "write_file"):
        if _is_overly_broad_file_path(target_stripped):
            return f"refusing overly broad file path rule: {rule}"
        if is_sensitive_path(target_stripped):
            return f"refusing sensitive path rule: {rule}"
        return None

    if action in ("read_url", "execute_url", "download_url"):
        if (
            "://" in target_stripped
            or "/" in target_stripped
            or "@" in target_stripped
            or "*" in target_stripped
            or any(ch.isspace() for ch in target_stripped)
            or target_stripped.startswith(".")
            or target_stripped.endswith(".")
            or ".." in target_stripped
        ):
            return f"refusing invalid URL domain rule: {rule}"
        labels = target_stripped.split(".")
        if len(labels) < 2:
            if not (target_stripped.lower() == "localhost" and action in ("execute_url", "download_url")):
                return f"refusing overly broad single-label/TLD URL rule: {rule}"
        if not all(re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?", lbl) for lbl in labels):
            return f"refusing invalid domain label in URL rule: {rule}"
        return None

    if action == "mcp":
        if target_stripped == "*/*" or target_stripped.startswith("*/"):
            return f"refusing cross-server wildcard MCP rule: {rule}"
        if is_mcp_mutating(target_stripped):
            return f"refusing mutating/write-like MCP rule: {rule}"
        return None

    if action == "command":
        if target_stripped.startswith("regex:"):
            return (
                "refusing command(regex:...) in apply for safety "
                f"(configure regex rules manually via /permissions): {rule}"
            )
        if SHELL_META_IN_RULE_RE.search(target_stripped):
            return f"refusing command rule containing quotes or shell metacharacters: {rule}"
        try:
            toks = shlex.split(target_stripped, posix=True)
        except ValueError:
            return f"invalid command tokenization in rule: {rule}"
        if not toks:
            return f"refusing empty command rule: {rule}"
        # apply では環境変数代入・ラッパー（env/nohup/nice/timeout/command）・フルパス指定を禁止し、
        # 安全な先頭ラッパーは単独の rtk のみ許可する
        if ENV_ASSIGN_RE.match(toks[0]):
            return f"refusing command rule with leading environment assignment: {rule}"
        if "/" in toks[0]:
            return f"refusing command rule with path-qualified executable: {rule}"
        if toks[0] in WRAPPER_BINARIES:
            return f"refusing wrapper command rule: {rule}"
        if toks[0] == "rtk":
            if len(toks) < 2:
                return f"refusing bare rtk command rule: {rule}"
            if toks[1].startswith("-"):
                return f"refusing rtk flag rule: {rule}"
            if ENV_ASSIGN_RE.match(toks[1]) or "/" in toks[1] or toks[1] in WRAPPER_BINARIES or toks[1] == "rtk":
                return f"refusing wrapped or path-qualified rtk command rule: {rule}"
            if f"rtk {toks[1]}" in UNSAFE_SUBCOMMAND_PREFIXES:
                return (
                    f"refusing unsafe rtk command rule ({UNSAFE_SUBCOMMAND_PREFIXES[f'rtk {toks[1]}']}): {rule}"
                )
            if toks[1] in RTK_NATIVE_SAFE_SUBCOMMANDS:
                classify_target = toks
            else:
                classify_target = toks[1:]
        else:
            classify_target = toks
        prefix, reason = classify_command_tokens(classify_target)
        if prefix is None or reason is not None:
            detail = reason or "unrecognized or builtin command"
            return f"refusing unsafe or overly broad command rule ({detail}): {rule}"
    return None


REGEX_META_CHARS = frozenset(".^$*+?{}[]\\|()")


def _extract_regex_literal_prefix(pattern: str) -> str:
    """正規表現パターンの先頭から正規表現メタ文字を含まないリテラルトークン列を抽出する。"""
    cleaned = pattern.lstrip("^").strip()
    if not cleaned:
        return ""
    lit_toks: list[str] = []
    for tok in cleaned.split():
        stripped = tok.rstrip("$") if tok.endswith("$") and not tok.endswith("\\$") else tok
        if any(ch in REGEX_META_CHARS for ch in stripped):
            break
        if stripped:
            lit_toks.append(stripped)
    return " ".join(lit_toks)


def _find_reverse_deny_overlaps(
    action: str,
    target: str,
    deny_rules: list[str],
) -> list[str]:
    """新規 allow ルールが既存の狭い deny ルールを包含する場合、重複する deny ルール一覧を返す。"""
    overlaps: list[str] = []
    target_toks = target.split() if action == "command" else []
    inner_target = (
        " ".join(target_toks[1:])
        if len(target_toks) >= 2 and target_toks[0] == "rtk" and target_toks[1] not in RTK_NATIVE_SAFE_SUBCOMMANDS
        else None
    )
    for raw_deny in deny_rules:
        parsed = parse_rule(raw_deny)
        if not parsed:
            continue
        d_action, d_target = parsed
        matched = False
        if action == "command" and d_action == "command":
            if d_target.strip().startswith("regex:"):
                lit_prefix = _extract_regex_literal_prefix(d_target.strip()[len("regex:"):].strip())
                if lit_prefix:
                    matched = command_rule_matches_prefix(target, lit_prefix)
                    if not matched and inner_target:
                        matched = command_rule_matches_prefix(inner_target, lit_prefix)
            else:
                matched = command_rule_matches_prefix(target, d_target)
                if not matched and inner_target:
                    matched = command_rule_matches_prefix(inner_target, d_target)
        elif action == "mcp" and d_action == "mcp":
            matched = mcp_rule_matches(target, d_target)
        elif action in ("read_url", "execute_url", "download_url") and d_action == action:
            matched = url_rule_matches(target, d_target)
        elif action in ("read_file", "write_file") and d_action in ("read_file", "write_file"):
            if d_action == action or (action == "write_file" and d_action == "read_file"):
                matched = file_rule_matches(target, d_target)
        if matched:
            overlaps.append(raw_deny)
    return overlaps


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

    data, real_path = _read_settings_json(settings_path)
    existing_perms, perm_warnings = _extract_validated_permissions(data, settings_path)
    allow_list = list(existing_perms["allow"])

    added: list[str] = []
    skipped_existing: list[str] = []
    warnings: list[str] = list(perm_warnings)

    for rule in rules:
        rule = rule.strip()
        if rule in allow_list or rule in added:
            skipped_existing.append(rule)
            continue
        parsed = parse_rule(rule)
        assert parsed is not None
        action, target = parsed
        status = check_rule_status(action, target, existing_perms)
        # command(rtk <cmd>) は元の <cmd> に対する deny/ask とも照合する
        if action == "command" and status != "deny":
            toks = target.split()
            if len(toks) >= 2 and toks[0] == "rtk" and toks[1] not in RTK_NATIVE_SAFE_SUBCOMMANDS:
                inner_status = check_rule_status("command", " ".join(toks[1:]), existing_perms)
                if inner_status == "deny":
                    status = "deny"
                elif inner_status == "ask" and status == "none":
                    status = "ask"
        if status == "deny":
            raise ValueError(f"rule conflicts with existing permissions.deny: {rule}")
        if status == "ask":
            warnings.append(f"rule is shadowed by existing permissions.ask (Ask > Allow): {rule}")
        reverse_overlaps = _find_reverse_deny_overlaps(action, target, existing_perms["deny"])
        if reverse_overlaps:
            warnings.append(
                f"broader rule {rule} partially overlaps existing permissions.deny ({', '.join(reverse_overlaps)}); "
                "denied targets remain blocked by Deny > Allow"
            )
        allow_list.append(rule)
        added.append(rule)

    if not dry_run and added:
        perms = data.setdefault("permissions", {})
        perms["allow"] = allow_list
        parent = os.path.dirname(real_path)
        os.makedirs(parent, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix=".settings-", suffix=".json.tmp", dir=parent)
        try:
            os.chmod(tmp_path, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as out:
                json.dump(data, out, indent=2, ensure_ascii=False)
                out.write("\n")
            os.replace(tmp_path, real_path)
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


def _positive_int(raw: str) -> int:
    try:
        val = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"must be an integer: {raw}") from exc
    if val <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer: {raw}")
    return val


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="subcommand")

    default_agy_dir = os.environ.get("ANTIGRAVITY_APP_DATA_DIR") or DEFAULT_AGY_DIR

    p_scan = sub.add_parser("scan", help="トランスクリプトを分析して allowlist 候補を抽出する")
    p_scan.add_argument("--antigravity-dir", default=default_agy_dir)
    p_scan.add_argument("--settings", default=None, help="settings.json パス（既定: <antigravity-dir>/settings.json）")
    p_scan.add_argument("--hooks", default=DEFAULT_HOOKS_PATH, help="hooks.json パス")
    p_scan.add_argument("--limit", type=_positive_int, default=50, help="スキャンする最新セッション数（既定: 50）")
    p_scan.add_argument("--min-count", type=_positive_int, default=2, help="候補に含める最小出現回数（既定: 2）")
    rtk_grp = p_scan.add_mutually_exclusive_group()
    rtk_grp.add_argument("--check-rtk", dest="check_rtk", action="store_true", default=None)
    rtk_grp.add_argument("--no-check-rtk", dest="check_rtk", action="store_false")
    p_scan.add_argument("--format", choices=("markdown", "json"), default="markdown")
    p_scan.add_argument("--max-candidates", type=_positive_int, default=30, help="Markdown 表示する最大候補数（既定: 30）")

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
    if not args_list or (args_list[0].startswith("-") and args_list[0] not in ("-h", "--help")):
        args_list = ["scan"] + args_list

    ap = build_parser()
    args = ap.parse_args(args_list)

    if args.subcommand == "scan":
        agy_dir = os.path.abspath(os.path.expanduser(args.antigravity_dir))
        settings_path = os.path.abspath(
            os.path.expanduser(args.settings or os.path.join(agy_dir, "settings.json"))
        )
        hooks_path = os.path.abspath(os.path.expanduser(args.hooks))
        try:
            report = scan_transcripts(
                antigravity_dir=agy_dir,
                settings_path=settings_path,
                hooks_path=hooks_path,
                limit=args.limit,
                min_count=args.min_count,
                check_rtk=args.check_rtk,
            )
        except PermissionError as exc:
            print(f"error: {exc} (Antigravity sandbox では BypassSandbox: true で再実行してください)", file=sys.stderr)
            return 2
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if args.format == "json":
            print(json.dumps(report, indent=2, ensure_ascii=False))
        else:
            print(render_markdown(report, max_candidates=args.max_candidates))
        return 0

    if args.subcommand == "apply":
        settings_path = os.path.abspath(os.path.expanduser(args.settings))
        try:
            result = apply_rules(settings_path, args.add, dry_run=args.dry_run)
        except (OSError, ValueError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
