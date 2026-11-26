#!/usr/bin/env python3
"""Unit tests for analyze_permissions.py."""

from __future__ import annotations

import contextlib
import io
import json
import os
import stat
import subprocess
import tempfile
import unittest
from unittest import mock

import analyze_permissions as ap


class ShellParsingTests(unittest.TestCase):
    def test_split_shell_segments_respects_quotes_and_pipe_meta(self) -> None:
        cmd = 'gh pr view 1 --json "a;b|c&&d" && git status; echo \'x && y\' | wc -l'
        segs_meta = ap.split_shell_segments_with_meta(cmd)
        self.assertEqual(
            segs_meta,
            [
                ('gh pr view 1 --json "a;b|c&&d"', False),
                ("git status", False),
                ("echo 'x && y'", False),
                ("wc -l", True),
            ],
        )
        # Subshell parentheses and background & split segments while preserving $(...) and &>
        self.assertEqual(
            ap.split_shell_segments("(git status && git diff) & ls -la"),
            ["git status", "git diff", "ls -la"],
        )
        self.assertEqual(
            ap.split_shell_segments("git log $(whoami) && git push&>/dev/null"),
            ["git log $(whoami)", "git push&>/dev/null"],
        )
        # Operators inside $(...) must NOT split the outer segment
        self.assertEqual(
            ap.split_shell_segments("echo $(git status && ls)"),
            ["echo $(git status && ls)"],
        )
        # Pipe downstream flag preserved across newline or subshell opening paren
        self.assertEqual(
            ap.split_shell_segments_with_meta("git log --oneline |\n  wc -l"),
            [("git log --oneline", False), ("wc -l", True)],
        )
        self.assertEqual(
            ap.split_shell_segments_with_meta("git log | (wc -l)"),
            [("git log", False), ("wc -l", True)],
        )

    def test_unwrap_tokens_strips_env_wrappers_and_safe_rtk(self) -> None:
        toks = ap.tokenize_segment(
            "GIT_CONFIG_GLOBAL=/dev/null /usr/bin/env -u PATH timeout 10 rtk git log -n 5 2>&1"
        )
        unwrapped, had_env, was_rtk = ap.unwrap_tokens(toks)
        self.assertEqual(unwrapped, ["git", "log", "-n", "5"])
        self.assertTrue(had_env)
        self.assertTrue(was_rtk)

        # command -v / -V is a query, not execution
        self.assertEqual(ap.unwrap_tokens(["command", "-v", "jq"])[0], [])
        self.assertEqual(ap.unwrap_tokens(["command", "-V", "git"])[0], [])
        self.assertEqual(ap.unwrap_tokens(["command", "-pv", "git"])[0], [])

        # Combined short value flags (-iu, -iC) and attached value forms (-uCC, -uPATH)
        self.assertEqual(
            ap.unwrap_tokens(ap.tokenize_segment("env -iu PATH rm -rf /tmp/foo"))[0],
            ["rm", "-rf", "/tmp/foo"],
        )
        self.assertEqual(
            ap.unwrap_tokens(ap.tokenize_segment("env -iC /tmp git status"))[0],
            ["git", "status"],
        )
        self.assertEqual(
            ap.unwrap_tokens(ap.tokenize_segment("env -uCC git push"))[0],
            ["git", "push"],
        )
        self.assertEqual(
            ap.unwrap_tokens(ap.tokenize_segment("env -uPATH git status"))[0],
            ["git", "status"],
        )

        # RTK native safe subcommands must NOT strip rtk
        unwrapped_gain, _, was_rtk_gain = ap.unwrap_tokens(["rtk", "gain", "--history"])
        self.assertEqual(unwrapped_gain, ["rtk", "gain", "--history"])
        self.assertFalse(was_rtk_gain)

    def test_unwrap_tokens_preserves_unsafe_rtk_subcommands(self) -> None:
        for raw in (
            "rtk",
            "rtk proxy rm -rf /",
            "rtk run ls",
            "rtk read /etc/passwd",
            "rtk grep foo bar",
            "rtk init",
            "rtk untrust",
            "rtk json a.json",
            "rtk env",
            "rtk -v git status",
        ):
            unwrapped, _, was_rtk = ap.unwrap_tokens(ap.tokenize_segment(raw))
            self.assertEqual(unwrapped[0], "rtk", f"should not unwrap {raw}")
            self.assertFalse(was_rtk)

    def test_unwrap_tokens_preserves_unsafe_env_and_wrapper_flags(self) -> None:
        for raw, expected0 in (
            ("env -S rm ls", "env"),
            ("env -iS rm ls", "env"),
            ("env --split-string=sh ls", "env"),
            ("env -P /bin rm -rf", "env"),
            ("env -iP /bin rm -rf", "env"),
            ("timeout -- rm ls", "timeout"),
            ("nice -n rm ls", "nice"),
        ):
            unwrapped, _, _ = ap.unwrap_tokens(ap.tokenize_segment(raw))
            self.assertEqual(unwrapped[0], expected0, f"should not unwrap {raw}")

    def test_unspaced_redirection_stripped_outside_quotes(self) -> None:
        toks = ap.tokenize_segment("git push>/dev/null 2>&1")
        self.assertEqual(toks, ["git", "push"])
        _, reason = ap.classify_command_tokens(toks)
        self.assertIsNotNone(reason)

        self.assertEqual(ap.tokenize_segment("git push&>/dev/null"), ["git", "push"])
        self.assertEqual(ap.tokenize_segment(">& /dev/null git push"), ["git", "push"])
        self.assertEqual(ap.tokenize_segment("git <<-EOF"), ["git"])
        self.assertEqual(ap.tokenize_segment("git status 2>&-"), ["git", "status"])

        quoted = ap.tokenize_segment('echo "a>b" >/tmp/out')
        self.assertEqual(quoted, ["echo", "a>b"])

    def test_exact_match_only_detection(self) -> None:
        self.assertTrue(ap.has_exact_match_only_construct("git log $(whoami)"))
        self.assertTrue(ap.has_exact_match_only_construct("ls {a,b}"))
        self.assertTrue(ap.has_exact_match_only_construct("git -c core.pager=cat log"))
        self.assertFalse(ap.has_exact_match_only_construct("git status && git log --oneline"))
        self.assertFalse(ap.has_exact_match_only_construct("grep '$(foo)' file.txt"))

    def test_strip_heredocs_comments_and_ignore_non_commands(self) -> None:
        cmd = "python3 - <<'PY'\nprint('hello')\ntest_files.append('a')\nPY\ngit status"
        self.assertEqual(ap.split_shell_segments(cmd), ["python3 - <<'PY'", "git status"])

        # Quoted <<EOF, here-string <<<, # comments, $((1 << 2)), and multi-line quotes must NOT start a heredoc
        edge = (
            "echo '<<EOF'\ngit diff\ncat <<< 'hello'\ngit status # see <<EOF\n"
            "echo $(( 1 << 2 ))\ngit log\n"
            "echo 'line1\n<<EOF\nline3'\ngit show"
        )
        self.assertEqual(
            ap.split_shell_segments(edge),
            [
                "echo '<<EOF'",
                "git diff",
                "cat <<< 'hello'",
                "git status",
                "echo $(( 1 << 2 ))",
                "git log",
                "echo 'line1\n<<EOF\nline3'",
                "git show",
            ],
        )
        # Hyphenated heredoc delimiter
        hyph = "cat <<END-OF-FILE\nrm -rf /\nEND-OF-FILE\ngit status"
        self.assertEqual(ap.split_shell_segments(hyph), ["cat <<END-OF-FILE", "git status"])

        # Array assignments and non-command tokens should not produce candidates
        toks, had_env, _ = ap.unwrap_tokens(ap.tokenize_segment("keep_paths+=($path)"))
        self.assertTrue(had_env)
        self.assertEqual(toks, [])
        self.assertEqual(ap.classify_command_tokens(["-C", "/repo"]), (None, None))
        self.assertEqual(ap.classify_command_tokens(["print(x)"]), (None, None))


class ClassificationTests(unittest.TestCase):
    def test_three_level_read_vs_write(self) -> None:
        self.assertEqual(ap.classify_command_tokens(["gh", "pr", "view", "123"]), ("gh pr view", None))
        prefix, reason = ap.classify_command_tokens(["gh", "pr", "merge", "123"])
        self.assertEqual(prefix, "gh pr merge")
        self.assertIsNotNone(reason)

        self.assertEqual(ap.classify_command_tokens(["git", "worktree", "list"]), ("git worktree list", None))
        _, wt_reason = ap.classify_command_tokens(["git", "worktree", "remove", "foo"])
        self.assertIsNotNone(wt_reason)

        self.assertEqual(ap.classify_command_tokens(["nix", "store", "ls"]), ("nix store ls", None))
        self.assertIn("nix store ls", ap.SAFE_READONLY_PREFIXES)

    def test_unsafe_flags_commands_and_file_readers_excluded(self) -> None:
        for toks in (
            ["git", "-C", "/repo", "status"],
            ["git", "-c", "core.pager=cat", "log"],
            ["git", "status", "-c", "core.fsmonitor=evil"],
            ["git", "status", "--exec-path=/tmp/evil"],
            ["gh", "api", "repos/a/b"],
            ["gh", "-R", "a/b", "pr", "view", "1"],
            ["gh", "auth", "token"],
            ["python3", "-c", "print(1)"],
            ["python3.12", "-c", "print(1)"],
            ["pip", "install", "evil-pkg"],
            ["pip3", "install", "evil-pkg"],
            ["node", "-e", "1+1"],
            ["bun", "run", "lint"],
            ["rm", "-rf", "tmp"],
            ["."],
            ["fd", ".", "-x", "sh"],
            ["yq", "-i", ".a=1", "f.yml"],
            ["cat", "/etc/passwd"],
            ["head", "-n", "10", "a.txt"],
            ["tail", "-n", "10", "a.txt"],
            ["grep", "foo", "a.txt"],
            ["rg", "foo", "a.txt"],
            ["sort", "-o", "out.txt", "in.txt"],
            ["uniq", "in.txt", "out.txt"],
            ["xxd", "-r", "a.hex"],
            ["strings", "/etc/passwd"],
            ["hexdump", "/etc/passwd"],
            ["cut", "-d:", "-f1", "/etc/passwd"],
            ["diff", "a", "b"],
            ["comm", "a", "b"],
            ["jq", ".", "secrets.json"],
            ["tar", "-tf", "a.tar"],
            ["tar", "--list", "-f", "a.tar"],
            ["tar", "--overwrite", "-xf", "a.tar"],
            ["uv", "run", "python"],
            ["uv", "sync"],
            ["uv", "add", "requests"],
            ["uv", "remove", "requests"],
            ["uv", "publish"],
            ["uv", "python"],
            ["uv", "python", "install", "3.12"],
            ["uv", "tool"],
            ["uv", "tool", "run", "ruff"],
            ["uv", "pip"],
            ["uv", "pip", "install", "evil"],
            ["uvx", "ruff"],
            ["pipx", "run", "cowsay"],
            ["npm", "exec", "evil"],
            ["npm", "run-script"],
            ["pnpm", "dlx", "evil"],
            ["pnpm", "exec", "evil"],
            ["yarn", "dlx", "evil"],
            ["yarn", "exec", "evil"],
            ["wrangler", "d1"],
            ["wrangler", "d1", "execute", "db"],
            ["wrangler", "d1", "time-travel", "info", "db"],
            ["wrangler", "kv", "key", "put"],
            ["wrangler", "r2", "object", "put"],
            ["wrangler", "pages", "deployment", "list"],
            ["wrangler", "queues", "list"],
            ["wrangler", "vectorize", "list"],
            ["wrangler", "hyperdrive", "list"],
            ["mise", "exec", "--", "sh"],
            ["mise", "x", "--", "sh"],
            ["cargo", "run"],
            ["go", "run", "main.go"],
            ["docker", "compose", "run", "app"],
            ["docker", "container", "exec", "c1", "sh"],
            ["docker", "container", "run", "alpine"],
            ["kubectl", "run", "pod"],
            ["kubectl", "cp", "a", "b"],
            ["terraform", "apply"],
            ["terraform", "destroy"],
            ["rtk"],
            ["rtk", "bypass", "git", "status"],
            ["rtk", "proxy", "git", "status"],
            ["rtk", "run", "ls"],
            ["rtk", "read", "a.txt"],
            ["rtk", "grep", "foo", "a.txt"],
            ["rtk", "init"],
            ["rtk", "untrust"],
            ["rtk", "json", "a.json"],
            ["rtk", "log", "a.log"],
            ["rtk", "smart", "a.py"],
            ["rtk", "ast-grep", "foo"],
            ["rtk", "plugins"],
            ["rtk", "pipeline", "add", "foo"],
            ["rtk", "learn", "--write-rules"],
            ["rtk", "llm-proxy"],
            ["rtk", "telemetry"],
            ["rtk", "env"],
            ["rtk", "-v", "git", "status"],
            ["git"],
            ["gh", "pr"],
            ["gh", "pr", "--help"],
            ["npx", "prettier", "--write", "."],
            ["npx", "tsc"],
            ["prettier", "--write", "."],
            ["tsc"],
            ["npx", "-c", "rm -rf /"],
            ["npx", "-p", "evil-pkg"],
            ["npx", "sh"],
            ["npx", "bash"],
            ["npx", "env"],
            ["npx", "npx", "bash"],
            ["npx", "wrangler", "deploy"],
            ["npx", "git", "push"],
            ["npx", "unzip", "a.zip"],
            ["npx", "./evil.js"],
            ["npx", "/usr/bin/id"],
            ["unzip", "archive.zip"],
        ):
            _, reason = ap.classify_command_tokens(toks)
            self.assertIsNotNone(reason, f"expected exclusion for {toks}")

    def test_safe_flags_preserved(self) -> None:
        self.assertEqual(ap.classify_command_tokens(["git", "remote", "-v"]), ("git remote -v", None))
        self.assertEqual(ap.classify_command_tokens(["npx", "tsc", "--noEmit"]), ("npx tsc --noEmit", None))
        self.assertEqual(ap.classify_command_tokens(["npx", "prettier", "--check", "."]), ("npx prettier --check", None))
        self.assertEqual(ap.classify_command_tokens(["npx", "git", "status"]), ("npx git status", None))
        self.assertEqual(ap.classify_command_tokens(["npx", "@biomejs/biome", "check"]), ("npx @biomejs/biome", None))
        self.assertEqual(ap.classify_command_tokens(["tsc", "--noEmit"]), ("tsc --noEmit", None))
        self.assertEqual(ap.classify_command_tokens(["prettier", "--check", "."]), ("prettier --check", None))
        self.assertEqual(ap.classify_command_tokens(["unzip", "-p", "a.zip", "b"]), ("unzip -p", None))
        self.assertEqual(ap.classify_command_tokens(["unzip", "-Z", "a.zip"]), ("unzip -Z", None))
        self.assertEqual(ap.classify_command_tokens(["rtk", "gain"]), ("rtk gain", None))

    def test_is_mcp_mutating_handles_camel_case_and_read_only(self) -> None:
        for mut in (
            "fs/writeFile",
            "github/deleteBranch",
            "slack/postMessage",
            "linear/createIssue",
            "db/executeQuery",
            "todoist/delete-task",
        ):
            self.assertTrue(ap.is_mcp_mutating(mut), f"expected mutating for {mut}")
        for ro in ("todoist/findTasks", "github/listPullRequests", "notion/fetchPage"):
            self.assertFalse(ap.is_mcp_mutating(ro), f"expected read-only for {ro}")


class RuleMatchingTests(unittest.TestCase):
    def test_word_boundary_prefix_matching(self) -> None:
        self.assertTrue(ap.command_rule_matches_prefix("*", "git status"))
        self.assertTrue(ap.command_rule_matches_prefix("git status", "git status"))
        self.assertTrue(ap.command_rule_matches_prefix("git", "git status"))
        self.assertFalse(ap.command_rule_matches_prefix("ls", "lsof"))
        self.assertFalse(ap.command_rule_matches_prefix("gh pr view", "gh pr list"))

    def test_regex_matching_including_empty_and_grouped_spaces(self) -> None:
        self.assertTrue(ap.command_rule_matches_prefix("regex:npm run (build|lint|test)", "npm run lint"))
        self.assertFalse(ap.command_rule_matches_prefix("regex:npm run (build|lint|test)", "npm run deploy"))
        # Empty regex must NEVER match
        self.assertFalse(ap.command_rule_matches_prefix("regex:", "git status"))
        self.assertFalse(ap.command_rule_matches_prefix("regex:   ", "git status"))
        # Grouped spaces, unparenthesized top-level alternation, per-token alternation, and $ anchor
        self.assertTrue(ap.command_rule_matches_prefix("regex:(gh pr|git push)", "gh pr view"))
        self.assertTrue(ap.command_rule_matches_prefix("regex:git worktree|gh pr", "gh pr view"))
        self.assertTrue(ap.command_rule_matches_prefix("regex:rtk (gh pr|git worktree)", "rtk gh pr view"))
        self.assertTrue(ap.command_rule_matches_prefix("regex:npm run build|lint", "npm run lint"))
        self.assertTrue(ap.command_rule_matches_prefix("regex:git log|diff", "git diff"))
        self.assertFalse(ap.command_rule_matches_prefix("regex:git log|diff", "diff"))
        self.assertFalse(ap.command_rule_matches_prefix("regex:^gh pr$", "gh pr view"))
        self.assertTrue(ap.command_rule_matches_prefix("regex:^gh pr$", "gh pr"))
        self.assertFalse(ap.command_rule_matches_prefix("regex:(gh pr|git push)", "git status"))

    def test_file_rule_matches_and_sensitive_path_edge_cases(self) -> None:
        # Root, ".", sibling boundary, leading // normalization, tilde expansion, wildcard
        self.assertTrue(ap.file_rule_matches("/", "/etc/hosts"))
        self.assertTrue(ap.file_rule_matches("///", "/etc/hosts"))
        self.assertTrue(ap.file_rule_matches(".", "src/app.py"))
        self.assertFalse(ap.file_rule_matches(".", "/etc/hosts"))
        self.assertFalse(ap.file_rule_matches(".", "../outside.py"))
        self.assertTrue(ap.file_rule_matches("*", "/any/path"))
        self.assertTrue(ap.file_rule_matches("/etc/hosts", "//etc/hosts"))
        self.assertTrue(ap.file_rule_matches("/etc/hosts", "/etc/./hosts"))
        self.assertTrue(ap.file_rule_matches("/etc/hosts", "/tmp/../etc/hosts"))
        self.assertTrue(ap.file_rule_matches("/etc/hosts", "/etc//hosts"))
        self.assertTrue(ap.file_rule_matches("~/docs", os.path.expanduser("~/docs/a.md")))
        self.assertTrue(ap.file_rule_matches("./src/", "src\\sub\\a.py"))
        self.assertFalse(ap.file_rule_matches("/workspace/src", "/workspace/src-secret/a.py"))
        self.assertFalse(ap.file_rule_matches("/", "relative/path"))

        # Sensitive path segment + parent directory + substr patterns + case / slash / // normalization
        for sensitive in (
            "/workspace/server.key",
            "/workspace/cert.pem",
            "/workspace/credentials.json",
            "/workspace/id_ed25519",
            "./.ENV",
            r".\.ssh\config",
            "~/.config",
            "/Users/me/.config",
            "~/.config//gcloud",
            "~/.config/./gcloud",
            "/Users/me/.aws/config",
        ):
            self.assertTrue(ap.is_sensitive_path(sensitive), f"expected sensitive: {sensitive}")
        self.assertFalse(ap.is_sensitive_path("/workspace/src/app.py"))
        self.assertFalse(ap.is_sensitive_path("~/.config/nvim/init.lua"))

    def test_mcp_and_file_and_url_matching_and_precedence(self) -> None:
        # Wildcards and boundary negations
        self.assertTrue(ap.mcp_rule_matches("*", "todoist/find-tasks"))
        self.assertTrue(ap.mcp_rule_matches("*/*", "todoist/find-tasks"))
        self.assertTrue(ap.mcp_rule_matches("todoist/*", "todoist/find-tasks"))
        self.assertTrue(ap.mcp_rule_matches("todoist/find-tasks", " todoist/find-tasks "))
        self.assertFalse(ap.mcp_rule_matches("todoist/*", "slack/search"))
        self.assertFalse(ap.mcp_rule_matches("todoist/*", "todoist-admin/read"))

        self.assertTrue(ap.url_rule_matches("*", "example.com"))
        self.assertTrue(ap.url_rule_matches("google.com", "docs.google.com"))
        self.assertFalse(ap.url_rule_matches("google.com", "evilgoogle.com"))

        perms = {
            "allow": [
                "command(git status)",
                "command(gh pr view)",
                "read_url(google.com)",
                "write_file(/workspace/src)",
                "read_file(/workspace/docs)",
                "mcp(todoist/*)",
            ],
            "ask": ["command(git)", "command(gh pr view)", "execute_url(aws.amazon.com)"],
            "deny": [
                "command(git status)",
                "command(git log)",
                "read_file(/etc/hosts)",
                "write_file(/workspace/locked)",
                "download_url(evil.example)",
                "mcp(todoist/delete-task)",
            ],
        }
        # Deny > Ask > Allow precedence (including ask(git) vs deny(git log))
        self.assertEqual(ap.check_rule_status("command", "git status", perms), "deny")
        self.assertEqual(ap.check_rule_status("command", "git log", perms), "deny")
        self.assertEqual(ap.check_rule_status("command", "gh pr view", perms), "ask")
        self.assertEqual(ap.check_rule_status("read_url", "docs.google.com", perms), "allow")
        self.assertEqual(ap.check_rule_status("read_url", "example.com", perms), "none")
        self.assertEqual(ap.check_rule_status("execute_url", "console.aws.amazon.com", perms), "ask")
        self.assertEqual(ap.check_rule_status("download_url", "sub.evil.example", perms), "deny")
        # Implicit rules: deny read_file implies deny write_file; allow write_file implies allow read_file
        self.assertEqual(ap.check_rule_status("write_file", "/etc/hosts", perms), "deny")
        self.assertEqual(ap.check_rule_status("read_file", "/workspace/src/a.py", perms), "allow")
        # Reverse directions must NOT apply
        self.assertEqual(ap.check_rule_status("write_file", "/workspace/docs/a.md", perms), "none")
        self.assertEqual(ap.check_rule_status("read_file", "/workspace/locked/a.txt", perms), "none")
        self.assertEqual(ap.check_rule_status("mcp", "todoist/delete-task", perms), "deny")
        self.assertEqual(ap.check_rule_status("mcp", "todoist/find-tasks", perms), "allow")


class RtkIntegrationTests(unittest.TestCase):
    def test_compute_rtk_prefix_preserves_safety_flags_and_blocks_unsafe(self) -> None:
        called: list[str] = []

        def fake_run(argv, **_kwargs):
            cmd = argv[2]
            called.append(cmd)
            mapping = {
                "npx prettier --check .": (3, "rtk prettier --check ."),
                "npx tsc --noEmit": (3, "rtk tsc --noEmit"),
                "gh pr view 171 --repo owner/repo": (3, "rtk gh pr view 171 --repo owner/repo"),
                "npm run lint": (3, "rtk lint"),
                "wc -l": (3, "rtk wc -l"),
                "wc": (3, "rtk wc"),
                "cat a.txt": (3, "rtk read a.txt"),
                "jq . a.json": (3, "rtk json a.json"),
                "npx prettier --bad": (3, "rtk prettier ."),
            }
            rc, out = mapping.get(cmd, (1, ""))
            return subprocess.CompletedProcess(argv, rc, stdout=out, stderr="")

        with mock.patch.object(subprocess, "run", side_effect=fake_run):
            self.assertEqual(
                ap.compute_rtk_prefix("npx prettier --check", "npx prettier --check ."),
                "rtk prettier --check",
            )
            self.assertEqual(
                ap.compute_rtk_prefix("npx tsc --noEmit", "npx tsc --noEmit"),
                "rtk tsc --noEmit",
            )
            self.assertEqual(
                ap.compute_rtk_prefix("gh pr view", "gh pr view 171 --repo owner/repo"),
                "rtk gh pr view",
            )
            self.assertEqual(ap.compute_rtk_prefix("npm run lint", "npm run lint"), "rtk lint")
            # Pipe-downstream only must NOT even invoke rtk rewrite (even though standalone wc -l rewrites)
            called.clear()
            self.assertIsNone(ap.compute_rtk_prefix("wc", "wc -l", only_pipe_downstream=True))
            self.assertEqual(called, [])
            # rtk read / rtk json are unsafe and must not be suggested (rtk json exercises UNSAFE_SUBCOMMAND_PREFIXES directly)
            self.assertIsNone(ap.compute_rtk_prefix("cat", "cat a.txt"))
            self.assertIsNone(ap.compute_rtk_prefix("jq", "jq . a.json"))
            # Re-classification guard rejects rewritten command that drops required safety flag
            self.assertIsNone(ap.compute_rtk_prefix("npx prettier --bad", "npx prettier --bad"))

    def test_compute_rtk_prefix_records_warning_on_error_and_unexpected_rc(self) -> None:
        warnings: list[str] = []
        with mock.patch.object(
            subprocess, "run", side_effect=subprocess.TimeoutExpired(cmd=["rtk"], timeout=2)
        ):
            self.assertIsNone(ap.compute_rtk_prefix("gh pr view", warnings_out=warnings))
        self.assertEqual(len(warnings), 1)

        warnings2: list[str] = []
        with mock.patch.object(
            subprocess, "run", return_value=subprocess.CompletedProcess(["rtk"], 101, stdout="", stderr="panic")
        ):
            self.assertIsNone(ap.compute_rtk_prefix("gh pr view", warnings_out=warnings2))
        self.assertTrue(any("101" in w and "panic" in w for w in warnings2))

    def test_detect_rtk_hook_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hooks = os.path.join(tmp, "hooks.json")
            with mock.patch.object(ap.shutil, "which", return_value=None):
                # Missing file + missing rtk -> False without warning
                self.assertEqual(ap.detect_rtk_hook_enabled(hooks), (False, []))
                # Hook configured but rtk binary missing -> False WITH warning
                with open(hooks, "w", encoding="utf-8") as fh:
                    fh.write('{"rtk": "rtk hook antigravity"}')
                enabled, warns = ap.detect_rtk_hook_enabled(hooks)
                self.assertFalse(enabled)
                self.assertTrue(any("not found in PATH" in w for w in warns))

            with mock.patch.object(ap.shutil, "which", return_value="/usr/local/bin/rtk"):
                os.unlink(hooks)
                # Missing file -> False without warning
                self.assertEqual(ap.detect_rtk_hook_enabled(hooks), (False, []))

                with open(hooks, "w", encoding="utf-8") as fh:
                    fh.write('{"rtk": "rtk hook antigravity"}')
                self.assertEqual(ap.detect_rtk_hook_enabled(hooks), (True, []))

                with open(hooks, "w", encoding="utf-8") as fh:
                    fh.write('{"other": "noop"}')
                self.assertEqual(ap.detect_rtk_hook_enabled(hooks), (False, []))

                # PermissionError records warning instead of silent failure
                with mock.patch("builtins.open", side_effect=PermissionError("denied")):
                    enabled, warns = ap.detect_rtk_hook_enabled(hooks)
                    self.assertFalse(enabled)
                    self.assertEqual(len(warns), 1)

                # Non-UTF-8 hooks.json records warning instead of crashing
                with open(hooks, "wb") as fh:
                    fh.write(b"\xff\xfe")
                enabled_bad, warns_bad = ap.detect_rtk_hook_enabled(hooks)
                self.assertFalse(enabled_bad)
                self.assertEqual(len(warns_bad), 1)

                # Broken symlink hooks.json records warning instead of silent False
                broken_hooks = os.path.join(tmp, "broken_hooks.json")
                os.symlink(os.path.join(tmp, "nonexistent_hooks.json"), broken_hooks)
                enabled_brk, warns_brk = ap.detect_rtk_hook_enabled(broken_hooks)
                self.assertFalse(enabled_brk)
                self.assertTrue(any("broken symlink" in w for w in warns_brk))


class ScanAndApplyIntegrationTests(unittest.TestCase):
    def _write_transcript(
        self, root: str, uuid: str, filename: str, lines: list[str | dict], mtime: float | None = None
    ) -> str:
        logs = os.path.join(root, "brain", uuid, ".system_generated", "logs")
        os.makedirs(logs, exist_ok=True)
        path = os.path.join(logs, filename)
        with open(path, "w", encoding="utf-8") as fh:
            for item in lines:
                fh.write((item if isinstance(item, str) else json.dumps(item)) + "\n")
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def test_scan_covers_allowed_excluded_min_count_rtk_conflicts_and_ordering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = os.path.join(tmp, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "permissions": {
                            "allow": [
                                "command(git status)",
                                "command(rtk git status)",
                                "command(npm run lint)",
                                "command(regex:[unclosed)",
                                "bad rule syntax",
                            ],
                            "ask": ["command(gh run view)"],
                            "deny": ["command(rm -rf)", "command(rtk gh issue view)"],
                        }
                    },
                    fh,
                )

            # Session 1 (newest, has BOTH transcript_full.jsonl and transcript.jsonl -> must NOT double count)
            s1_entries = [
                {
                    "type": "PLANNER_RESPONSE",
                    "tool_calls": [
                        {"name": "run_command", "args": {"CommandLine": "gh pr view 10 && git status", "BypassSandbox": True}},
                        {"name": "run_command", "args": {"CommandLine": "npm run lint", "BypassSandbox": True}},
                        {"name": "run_command", "args": {"CommandLine": "gh run view 99", "BypassSandbox": True}},
                        {"name": "run_command", "args": {"CommandLine": "gh issue view 1", "BypassSandbox": True}},
                        {"name": "run_command", "args": {"CommandLine": "gh api repos/o/r", "BypassSandbox": True}},
                        {"name": "run_command", "args": {"CommandLine": "ls -la | wc -l", "BypassSandbox": False}},
                        {"name": "run_command", "args": {"CommandLine": "rtk next build", "BypassSandbox": True}},
                        {"name": "run_command", "args": {"CommandLine": "stat foo", "BypassSandbox": True}},  # count=1 -> filtered by min_count=2
                        {"name": "mcp__todoist__find-tasks", "args": {"query": "today"}},
                        {"name": "mcp__todoist__create-task", "args": {"content": "x"}},
                        {"name": "read_url_content", "args": {"Url": "https://antigravity.google/docs/permissions"}},
                        {"name": "read_url_content", "args": {"Url": "http://intranet:8080/docs"}},  # single-label -> filtered out
                        {"name": "read_url_content", "args": {"Url": "https://example.com./docs"}},  # trailing dot -> filtered out
                        {"name": "read_url_content", "args": {"Url": "https://[invalid/path"}},  # must not crash
                    ],
                },
                "null",
                "[]",
                "{not-json \"tool_calls\"",
            ]
            self._write_transcript(tmp, "11111111-1111-1111-1111-111111111111", "transcript_full.jsonl", s1_entries, mtime=3000)
            self._write_transcript(tmp, "11111111-1111-1111-1111-111111111111", "transcript.jsonl", s1_entries, mtime=3000)

            # Session 2 (second newest, compact transcript.jsonl)
            self._write_transcript(
                tmp,
                "22222222-2222-2222-2222-222222222222",
                "transcript.jsonl",
                [
                    {
                        "type": "PLANNER_RESPONSE",
                        "tool_calls": [
                            {"name": "run_command", "args": {"CommandLine": '"gh pr view 20 && git status"', "BypassSandbox": "true"}},
                            {"name": "run_command", "args": {"CommandLine": '"npm run lint"', "BypassSandbox": "true"}},
                            {"name": "run_command", "args": {"CommandLine": '"gh run view 100"', "BypassSandbox": "true"}},
                            {"name": "run_command", "args": {"CommandLine": '"gh issue view 2"', "BypassSandbox": "true"}},
                            {"name": "run_command", "args": {"CommandLine": '"gh api repos/o/r"', "BypassSandbox": "true"}},
                            {"name": "run_command", "args": {"CommandLine": '"ls -la | wc -l"', "BypassSandbox": "false"}},
                            {"name": "run_command", "args": {"CommandLine": '"rtk next build"', "BypassSandbox": "true"}},
                            {"name": "mcp__todoist__find-tasks", "args": {"query": "tomorrow"}},
                            {"name": "mcp__todoist__create-task", "args": {"content": "y"}},
                            {"name": "read_url_content", "args": {"Url": '"https://antigravity.google/docs/sandbox"'}},
                            {"name": "read_url_content", "args": {"Url": '"http://intranet:8080/guide"'}},
                            {"name": "read_url_content", "args": {"Url": '"https://example.com./guide"'}},
                        ],
                    }
                ],
                mtime=2000,
            )

            # Session 3 (oldest -> excluded by limit=2)
            self._write_transcript(
                tmp,
                "33333333-3333-3333-3333-333333333333",
                "transcript_full.jsonl",
                [
                    {
                        "type": "PLANNER_RESPONSE",
                        "tool_calls": [
                            {"name": "run_command", "args": {"CommandLine": "uname -a", "BypassSandbox": True}},
                            {"name": "run_command", "args": {"CommandLine": "uname -a", "BypassSandbox": True}},
                        ],
                    }
                ],
                mtime=1000,
            )

            rtk_calls: dict[str, tuple[str | None, bool]] = {}

            def fake_rtk(prefix: str, sample_cmd: str | None = None, **kw) -> str | None:
                rtk_calls[prefix] = (sample_cmd, bool(kw.get("only_pipe_downstream")))
                if prefix in ("gh pr view", "git status", "gh issue view"):
                    return f"rtk {prefix}"
                if prefix == "npm run lint":
                    if kw.get("warnings_out") is not None:
                        kw["warnings_out"].append("simulated parallel rtk warning")
                    return "rtk lint"
                return None

            with mock.patch.object(ap.shutil, "which", return_value="/usr/local/bin/rtk"), \
                 mock.patch.object(ap, "compute_rtk_prefix", side_effect=fake_rtk):
                report = ap.scan_transcripts(
                    antigravity_dir=tmp,
                    settings_path=settings_path,
                    hooks_path=os.path.join(tmp, "missing-hooks.json"),
                    limit=2,
                    min_count=2,
                    check_rtk=True,
                )

            self.assertEqual(report["summary"]["sessions_scanned"], 2)
            # null + [] + broken json line = 3 malformed lines (not skipped by tool_calls filter)
            self.assertEqual(report["summary"]["malformed_lines"], 3)
            cand_rules = [c["rule"] for c in report["candidates"]]
            cand_map = {c["rule"]: c for c in report["candidates"]}

            # Oldest session (uname) excluded by limit=2; count=1 (stat) filtered by min_count=2
            self.assertNotIn("command(uname)", cand_map)
            self.assertNotIn("command(stat)", cand_map)

            # MCP and read_url candidates verified
            self.assertIn("mcp(todoist/find-tasks)", cand_map)
            self.assertEqual(cand_map["mcp(todoist/find-tasks)"]["total_count"], 2)
            self.assertIn("read_url(antigravity.google)", cand_map)
            self.assertEqual(cand_map["read_url(antigravity.google)"]["total_count"], 2)
            self.assertNotIn("read_url(intranet)", cand_map)
            self.assertNotIn("read_url(example.com.)", cand_map)

            # No double counting on Session 1
            self.assertEqual(cand_map["command(gh pr view)"]["total_count"], 2)
            self.assertEqual(cand_map["command(gh pr view)"]["bypass_count"], 2)
            self.assertEqual(
                cand_map["command(gh pr view)"]["suggested_rules"],
                ["command(gh pr view)", "command(rtk gh pr view)"],
            )
            # Original allowed, RTK companion missing
            self.assertEqual(cand_map["command(npm run lint)"]["suggested_rules"], ["command(rtk lint)"])
            # rtk-prefixed command in transcript preserves command(rtk ...) even when compute_rtk_prefix returns None
            self.assertIn("command(rtk next)", cand_map["command(next)"]["suggested_rules"])
            # Sandbox-only command sorted below bypass commands
            self.assertIn("command(ls)", cand_map)
            self.assertEqual(cand_map["command(ls)"]["bypass_count"], 0)
            self.assertLess(cand_rules.index("command(gh pr view)"), cand_rules.index("command(ls)"))

            # Already allowed verified
            allowed_rules = {a["rule"] for a in report["already_allowed"]}
            self.assertIn("command(git status)", allowed_rules)

            # Conflicts verified (both orig ask AND rtk-only deny)
            conflict_rules = {c["rule"] for c in report["conflicts"]}
            self.assertIn("command(gh run view)", conflict_rules)
            self.assertIn("command(gh issue view)", conflict_rules)
            self.assertNotIn("command(gh issue view)", cand_map)

            # Both unsafe command AND mutating MCP verified in excluded
            excl_prefixes = {e["prefix"] for e in report["excluded"]}
            self.assertIn("gh api", excl_prefixes)
            self.assertIn("todoist/create-task", excl_prefixes)
            self.assertNotIn("mcp(todoist/create-task)", cand_map)

            # Warnings recorded for malformed JSONL + invalid existing rule syntax + invalid regex + parallel RTK warning
            self.assertTrue(any("bad rule syntax" in w for w in report["warnings"]))
            self.assertTrue(any("invalid regex" in w for w in report["warnings"]))
            self.assertTrue(any("malformed JSONL" in w for w in report["warnings"]))
            self.assertTrue(any("simulated parallel rtk warning" in w for w in report["warnings"]))
            # Verify sample_cmd and only_pipe_downstream passed to compute_rtk_prefix
            self.assertEqual(rtk_calls["wc"][1], True)
            self.assertEqual(rtk_calls["gh pr view"][1], False)
            self.assertIsNotNone(rtk_calls["gh pr view"][0])

            md = ap.render_markdown(report)
            self.assertIn("sandbox-only", md)
            self.assertIn("orig allowed; RTK rule missing", md)
            self.assertIn("## Warnings", md)

    def test_scan_missing_brain_raises_and_unreadable_or_corrupt_files_warned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = os.path.join(tmp, "settings.json")
            with self.assertRaises(FileNotFoundError):
                ap.scan_transcripts(tmp, settings_path, os.path.join(tmp, "hooks.json"), check_rtk=False)

            # Plain-text corrupt file without "tool_calls" must NOT count as valid scanned session
            self._write_transcript(
                tmp,
                "44444444-4444-4444-4444-444444444444",
                "transcript_full.jsonl",
                ["hello plain text", "not json at all"],
            )
            p = self._write_transcript(
                tmp, "11111111-1111-1111-1111-111111111111", "transcript_full.jsonl", []
            )
            # Unreadable session subdirectory (stat fails with PermissionError)
            locked_dir = os.path.join(tmp, "brain", "55555555-5555-5555-5555-555555555555")
            os.makedirs(os.path.join(locked_dir, ".system_generated", "logs"), exist_ok=True)
            os.chmod(p, 0o000)
            os.chmod(locked_dir, 0o000)
            try:
                report = ap.scan_transcripts(tmp, settings_path, os.path.join(tmp, "hooks.json"), check_rtk=False)
                self.assertEqual(report["summary"]["sessions_scanned"], 0)
                self.assertEqual(report["summary"]["unreadable_files"], 2)
                self.assertEqual(report["summary"]["malformed_lines"], 2)
                self.assertTrue(any("no valid JSONL lines" in w for w in report["warnings"]))
                self.assertTrue(any("could not stat" in w for w in report["warnings"]))
            finally:
                os.chmod(p, 0o600)
                os.chmod(locked_dir, 0o700)

    def test_apply_rules_validation_conflicts_errors_symlink_and_new_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = os.path.join(tmp, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "$schema": "https://antigravity.google/schemas/v1/settings.json",
                        "permissions": {
                            "allow": ["command(git status)"],
                            "ask": ["command(gh pr checks)"],
                            "deny": [
                                "command(git log)",
                                "command(regex:git diff --stat)",
                                "mcp(todoist/*)",
                                "read_file(/etc/hosts)",
                                "download_url(evil.example)",
                            ],
                        },
                        "trustedWorkspaces": ["/tmp/demo"],
                    },
                    fh,
                )

            # Dry run does not write, warns on ask conflict
            dry = ap.apply_rules(
                settings_path,
                ["command(git status)", "command(gh pr view)", "command(gh pr checks)"],
                dry_run=True,
            )
            self.assertEqual(dry["added"], ["command(gh pr view)", "command(gh pr checks)"])
            self.assertEqual(dry["skipped_existing"], ["command(git status)"])
            self.assertTrue(any("permissions.ask" in w for w in dry["warnings"]))
            with open(settings_path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["permissions"]["allow"], ["command(git status)"])

            # Partial failure with dry_run=False must leave settings.json completely untouched
            with self.assertRaisesRegex(ValueError, "permissions.deny"):
                ap.apply_rules(
                    settings_path,
                    ["command(gh pr view)", "command(git log)"],
                    dry_run=False,
                )
            with open(settings_path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["permissions"]["allow"], ["command(git status)"])

            # All action-type deny conflicts are rejected (including rtk-wrapped and normalized path)
            for denied_rule in (
                "command(git log)",
                "command(rtk git log)",
                "mcp(todoist/find-tasks)",
                "read_file(/etc/hosts)",
                "read_file(//etc/hosts)",
                "read_file(/etc/./hosts)",
                "write_file(/etc/hosts)",
                "download_url(sub.evil.example)",
            ):
                with self.assertRaisesRegex(ValueError, "permissions.deny", msg=denied_rule):
                    ap.apply_rules(settings_path, [denied_rule], dry_run=False)

            # Broader allow overlapping narrower deny (including regex deny) emits a warning
            overlap_res = ap.apply_rules(settings_path, ["read_file(/etc)", "command(git diff)"], dry_run=True)
            self.assertTrue(any("read_file(/etc/hosts)" in w for w in overlap_res["warnings"]))
            self.assertTrue(any("command(regex:git diff --stat)" in w for w in overlap_res["warnings"]))

            # Valid RTK native safe subcommand and valid URL rules pass apply --dry-run
            ok_dry = ap.apply_rules(
                settings_path,
                ["command(rtk gain)", "read_url(docs.github.com)", "execute_url(localhost)"],
                dry_run=True,
            )
            self.assertEqual(len(ok_dry["added"]), 3)

            # Atomic write failure rolls back cleanly: original untouched and no .tmp left behind
            with open(settings_path, encoding="utf-8") as fh:
                before_content = fh.read()
            with mock.patch.object(ap.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    ap.apply_rules(settings_path, ["command(gh pr view)"], dry_run=False)
            with open(settings_path, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before_content)
            self.assertFalse(any(f.endswith(".json.tmp") for f in os.listdir(tmp)))

            # Real apply writes atomically with 0600 and preserves other keys
            res = ap.apply_rules(
                settings_path,
                ["command(git status)", "command(gh pr view)", "command(rtk gh pr view)"],
                dry_run=False,
            )
            self.assertEqual(res["total_allow"], 3)
            self.assertEqual(stat.S_IMODE(os.stat(settings_path).st_mode), 0o600)
            with open(settings_path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["$schema"], "https://antigravity.google/schemas/v1/settings.json")
            self.assertEqual(saved["trustedWorkspaces"], ["/tmp/demo"])

            # Comprehensive validate_rule_for_apply safety rejections (tested directly so deny rules cannot mask guards)
            for bad in (
                "command(*)",
                "command(   )",
                "command(regex:.*)",
                "command(regex:)",
                "command(regex:[unclosed)",
                "command(env)",
                "command(env -S rm ls)",
                "command(env -P /bin rm -rf)",
                "command(LD_PRELOAD=/tmp/evil.so ls)",
                "command(GIT_EXTERNAL_DIFF=/tmp/evil git diff)",
                "command(nohup)",
                "command(nohup git log)",
                "command(timeout 10)",
                "command(timeout -- rm ls)",
                "command(nice -n rm ls)",
                "command(command)",
                "command(/usr/bin/git log)",
                "command(rtk)",
                "command(rtk /tmp/attacker/git status)",
                "command(rtk\tgit status)",
                "command(rtk proxy)",
                "command(rtk run)",
                "command(rtk read)",
                "command(rtk grep)",
                "command(rtk init)",
                "command(rtk pipeline)",
                "command(rtk learn)",
                "command(rtk env)",
                "command(python3.12)",
                "command(pip)",
                "command(uv tool)",
                "command(npm run-script)",
                "command(wrangler d1)",
                "command(wrangler kv)",
                "command(rtk gh pr merge)",
                "command(env -u PATH rm -rf)",
                "command(/usr/bin/env rm -rf)",
                "command('rm')",
                "command('git' status)",
                "command(git status && rm -rf /)",
                "command(git status; id)",
                "command(git status $(whoami))",
                "command(pipx)",
                "command(uv sync)",
                "command(uv python)",
                "command(wrangler pages)",
                "command(wrangler d1 time-travel)",
                "command(.)",
                "command(cat)",
                "command(grep)",
                "command(sort)",
                "command(jq)",
                "command(tar -tf)",
                "command(uvx)",
                "command(npm exec)",
                "command(pnpm dlx)",
                "command(yarn dlx)",
                "command(fd)",
                "command(yq)",
                "command(git)",
                "command(gh pr)",
                "command(tar --overwrite)",
                "command(tar -txf)",
                "command(npx -c)",
                "command(npx sh)",
                "command(npx npx)",
                "command(npx wrangler)",
                "command(npx unzip)",
                "command(npx ./evil.js)",
                "command(uv run)",
                "command(gh pr merge)",
                "command(git -C)",
                "command(gh api)",
                "command(git push>/dev/null)",
                "read_url(com)",
                "read_url(*.com)",
                "read_url(https://example.com/path)",
                "read_url(example.com.)",
                "read_url(example.com:8080)",
                "read_url(-evil.com)",
                "read_url(localhost)",
                "mcp(*)",
                "mcp(*/*)",
                "mcp( github/list-prs )",
                "mcp(todoist/delete-task)",
                "mcp(fs/writeFile)",
                "mcp(github/deleteBranch)",
                "read_file(/)",
                "write_file(/)",
                "write_file(//)",
                "write_file(/**)",
                "read_file(~/*)",
                "read_file(~/.s*h)",
                "write_file(~)",
                "write_file(~/.)",
                f"write_file({os.path.expanduser('~')})",
                "write_file(~/..)",
                "write_file(~/sub/..)",
                "write_file(~root)",
                f"write_file({os.path.dirname(os.path.expanduser('~'))})",
                "read_file(/workspace/a/../b)",
                "write_file(.)",
                "write_file(..)",
                "read_file(~/.ssh)",
                "read_file(~/.config)",
                "read_file(~/.config//gcloud)",
                "write_file(~/.gemini/antigravity-cli/settings.json)",
                "write_file(~/.gemini/config/hooks.json)",
                "write_file(~/.agents/hooks/remind-lessons.sh)",
                "write_file(~/.agents)",
                "read_file(~/.claude)",
                "write_file(~/.claude/settings.json)",
                "read_file(.env)",
                "read_file(/workspace/server.key)",
                "write_file(.ssh/authorized_keys)",
                "read_file(secrets/prod.yaml)",
                "invalid syntax",
            ):
                self.assertIsNotNone(ap.validate_rule_for_apply(bad), f"expected validate_rule_for_apply rejection for {bad}")
                with self.assertRaises(ValueError, msg=f"expected rejection for {bad}"):
                    ap.apply_rules(settings_path, [bad], dry_run=True)

            # PermissionError on settings.json must propagate and leave file untouched
            os.chmod(settings_path, 0o000)
            try:
                with self.assertRaises(PermissionError):
                    ap.apply_rules(settings_path, ["command(gh pr view)"], dry_run=False)
                with self.assertRaises(PermissionError):
                    ap.load_permissions(settings_path)
            finally:
                os.chmod(settings_path, 0o600)

            # Symlink target is preserved and updated
            real_target = os.path.join(tmp, "real_settings.json")
            link_path = os.path.join(tmp, "link_settings.json")
            with open(real_target, "w", encoding="utf-8") as fh:
                json.dump({"permissions": {"allow": []}}, fh)
            os.symlink(real_target, link_path)
            ap.apply_rules(link_path, ["command(gh pr view)"], dry_run=False)
            self.assertTrue(os.path.islink(link_path))
            with open(real_target, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["permissions"]["allow"], ["command(gh pr view)"])

            # Broken symlink is rejected
            broken_link = os.path.join(tmp, "broken.json")
            os.symlink(os.path.join(tmp, "nonexistent.json"), broken_link)
            with self.assertRaisesRegex(ValueError, "broken symlink"):
                ap.apply_rules(broken_link, ["command(gh pr view)"], dry_run=False)

            # Symlink into unreadable directory propagates PermissionError (not misreported as broken symlink)
            locked_parent = os.path.join(tmp, "locked_parent")
            os.makedirs(locked_parent, exist_ok=True)
            locked_target = os.path.join(locked_parent, "settings.json")
            with open(locked_target, "w", encoding="utf-8") as fh:
                json.dump({"permissions": {"allow": []}}, fh)
            perm_link = os.path.join(tmp, "perm_link.json")
            os.symlink(locked_target, perm_link)
            os.chmod(locked_parent, 0o000)
            try:
                with self.assertRaises(PermissionError):
                    ap.load_permissions(perm_link)
            finally:
                os.chmod(locked_parent, 0o700)

            # Corrupted JSON & bad schema types (including permissions: null) are rejected without mutating file
            for content in (
                "{broken",
                "[]",
                '{"permissions": null}',
                '{"permissions": []}',
                '{"permissions": {"allow": "command(ls)"}}',
                '{"permissions": {"allow": [123]}}',
            ):
                bad_file = os.path.join(tmp, "bad_settings.json")
                with open(bad_file, "w", encoding="utf-8") as fh:
                    fh.write(content)
                for dry_flag in (True, False):
                    with self.assertRaises(ValueError, msg=f"expected failure for {content} dry={dry_flag}") as cm:
                        ap.apply_rules(bad_file, ["command(gh pr view)"], dry_run=dry_flag)
                    self.assertIn(bad_file, str(cm.exception))
                with open(bad_file, encoding="utf-8") as fh:
                    self.assertEqual(fh.read(), content)

            # New file creation in non-existent parent directory sets 0600
            new_path = os.path.join(tmp, "nested", "dir", "settings.json")
            ap.apply_rules(new_path, ["command(gh pr view)"], dry_run=False)
            self.assertEqual(stat.S_IMODE(os.stat(new_path).st_mode), 0o600)
            with open(new_path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["permissions"]["allow"], ["command(gh pr view)"])


class CliMainTests(unittest.TestCase):
    def test_main_scan_and_apply_cli_wiring(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "brain"))
            settings = os.path.join(tmp, "settings.json")

            # --help shows top-level help (including apply subcommand), not rewritten to scan --help
            help_out = io.StringIO()
            with contextlib.redirect_stdout(help_out):
                with self.assertRaises(SystemExit) as cm_help:
                    ap.main(["--help"])
                self.assertEqual(cm_help.exception.code, 0)
            self.assertIn("apply", help_out.getvalue())

            # Implicit scan subcommand + --format json + --no-check-rtk
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                rc = ap.main(["--antigravity-dir", tmp, "--settings", settings, "--no-check-rtk", "--format", "json"])
            self.assertEqual(rc, 0)
            parsed = json.loads(out.getvalue())
            self.assertEqual(parsed["summary"]["sessions_scanned"], 0)

            # Negative --limit is rejected by argparse
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as cm:
                    ap.main(["scan", "--limit", "-1"])
                self.assertNotEqual(cm.exception.code, 0)

            # apply --dry-run returns 0 and does not create file
            out_dry = io.StringIO()
            with contextlib.redirect_stdout(out_dry):
                rc = ap.main(["apply", "--settings", settings, "--add", "command(gh pr view)", "--dry-run"])
            self.assertEqual(rc, 0)
            self.assertFalse(os.path.exists(settings))

            # apply invalid rule returns exit code 2 with error on stderr
            err_buf = io.StringIO()
            with contextlib.redirect_stderr(err_buf):
                rc = ap.main(["apply", "--settings", settings, "--add", "command(env)"])
            self.assertEqual(rc, 2)
            self.assertIn("error:", err_buf.getvalue())

            # scan on missing brain dir returns exit code 2
            err_scan = io.StringIO()
            with contextlib.redirect_stderr(err_scan):
                rc = ap.main(["scan", "--antigravity-dir", os.path.join(tmp, "missing"), "--no-check-rtk"])
            self.assertEqual(rc, 2)
            self.assertIn("error:", err_scan.getvalue())

            # scan encountering PermissionError prints BypassSandbox hint and exits 2
            err_perm = io.StringIO()
            with mock.patch.object(ap, "scan_transcripts", side_effect=PermissionError("Operation not permitted")):
                with contextlib.redirect_stderr(err_perm):
                    rc = ap.main(["scan", "--antigravity-dir", tmp, "--no-check-rtk"])
            self.assertEqual(rc, 2)
            self.assertIn("BypassSandbox: true", err_perm.getvalue())


if __name__ == "__main__":
    unittest.main()
