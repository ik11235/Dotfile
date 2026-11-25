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

    def test_unwrap_tokens_strips_env_wrappers_and_safe_rtk(self) -> None:
        toks = ap.tokenize_segment(
            "GIT_CONFIG_GLOBAL=/dev/null /usr/bin/env -u PATH timeout 10 rtk git log -n 5 2>&1"
        )
        unwrapped, had_env, was_rtk = ap.unwrap_tokens(toks)
        self.assertEqual(unwrapped, ["git", "log", "-n", "5"])
        self.assertTrue(had_env)
        self.assertTrue(was_rtk)

    def test_unwrap_tokens_preserves_unsafe_rtk_subcommands(self) -> None:
        for raw in (
            "rtk",
            "rtk proxy rm -rf /",
            "rtk run ls",
            "rtk read /etc/passwd",
            "rtk grep foo bar",
            "rtk -v git status",
        ):
            unwrapped, _, was_rtk = ap.unwrap_tokens(ap.tokenize_segment(raw))
            self.assertEqual(unwrapped[0], "rtk", f"should not unwrap {raw}")
            self.assertFalse(was_rtk)

    def test_unwrap_tokens_preserves_unsafe_env_and_wrapper_flags(self) -> None:
        for raw, expected0 in (
            ("env -S rm ls", "env"),
            ("env --split-string=sh ls", "env"),
            ("env -P /bin rm -rf", "env"),
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

        # Quoted <<EOF, here-string <<<, and # comments must NOT start a heredoc
        edge = "echo '<<EOF'\ngit diff\ncat <<< 'hello'\ngit status # see <<EOF\ngit log"
        self.assertEqual(
            ap.split_shell_segments(edge),
            ["echo '<<EOF'", "git diff", "cat <<< 'hello'", "git status", "git log"],
        )

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
            ["gh", "api", "repos/a/b"],
            ["gh", "-R", "a/b", "pr", "view", "1"],
            ["python3", "-c", "print(1)"],
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
            ["rtk"],
            ["rtk", "bypass", "git", "status"],
            ["rtk", "proxy", "git", "status"],
            ["rtk", "run", "ls"],
            ["rtk", "read", "a.txt"],
            ["rtk", "grep", "foo", "a.txt"],
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
            ["unzip", "archive.zip"],
            ["tar", "--overwrite", "-xf", "a.tar"],
            ["tar", "--delete", "-f", "a.tar", "x"],
            ["tar", "--update", "-f", "a.tar", "x"],
            ["tar", "-txf", "a.tar"],
            ["tar", "-tcf", "a.tar"],
            ["tar", "-tf", "a.tar", "--to-command=sh"],
            ["tar", "-tf", "a.tar", "--checkpoint-action=exec=sh"],
        ):
            _, reason = ap.classify_command_tokens(toks)
            self.assertIsNotNone(reason, f"expected exclusion for {toks}")

    def test_safe_flags_preserved(self) -> None:
        self.assertEqual(ap.classify_command_tokens(["git", "remote", "-v"]), ("git remote -v", None))
        self.assertEqual(ap.classify_command_tokens(["npx", "tsc", "--noEmit"]), ("npx tsc --noEmit", None))
        self.assertEqual(ap.classify_command_tokens(["npx", "prettier", "--check", "."]), ("npx prettier --check", None))
        self.assertEqual(ap.classify_command_tokens(["tsc", "--noEmit"]), ("tsc --noEmit", None))
        self.assertEqual(ap.classify_command_tokens(["prettier", "--check", "."]), ("prettier --check", None))
        self.assertEqual(ap.classify_command_tokens(["unzip", "-p", "a.zip", "b"]), ("unzip -p", None))
        self.assertEqual(ap.classify_command_tokens(["tar", "-tf", "a.tar"]), ("tar -tf", None))
        self.assertEqual(ap.classify_command_tokens(["tar", "--list", "-f", "a.tar"]), ("tar --list", None))

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
        self.assertFalse(ap.command_rule_matches_prefix("regex:^gh pr$", "gh pr view"))
        self.assertTrue(ap.command_rule_matches_prefix("regex:^gh pr$", "gh pr"))
        self.assertFalse(ap.command_rule_matches_prefix("regex:(gh pr|git push)", "git status"))

    def test_file_rule_matches_and_sensitive_path_edge_cases(self) -> None:
        # Root, sibling boundary, normalization, tilde expansion, wildcard
        self.assertTrue(ap.file_rule_matches("/", "/etc/hosts"))
        self.assertTrue(ap.file_rule_matches("///", "/etc/hosts"))
        self.assertTrue(ap.file_rule_matches("*", "/any/path"))
        self.assertTrue(ap.file_rule_matches("/etc/hosts", "/etc/./hosts"))
        self.assertTrue(ap.file_rule_matches("/etc/hosts", "/tmp/../etc/hosts"))
        self.assertTrue(ap.file_rule_matches("/etc/hosts", "/etc//hosts"))
        self.assertTrue(ap.file_rule_matches("~/docs", os.path.expanduser("~/docs/a.md")))
        self.assertTrue(ap.file_rule_matches("./src/", "src\\sub\\a.py"))
        self.assertFalse(ap.file_rule_matches("/workspace/src", "/workspace/src-secret/a.py"))
        self.assertFalse(ap.file_rule_matches("/", "relative/path"))

        # Sensitive path segment + substr patterns + case / slash / // normalization
        for sensitive in (
            "/workspace/server.key",
            "/workspace/cert.pem",
            "/workspace/credentials.json",
            "/workspace/id_ed25519",
            "./.ENV",
            r".\.ssh\config",
            "~/.config//gcloud",
            "~/.config/./gcloud",
            "/Users/me/.aws/config",
        ):
            self.assertTrue(ap.is_sensitive_path(sensitive), f"expected sensitive: {sensitive}")
        self.assertFalse(ap.is_sensitive_path("/workspace/src/app.py"))

    def test_mcp_and_file_and_url_matching_and_precedence(self) -> None:
        self.assertTrue(ap.mcp_rule_matches("todoist/*", "todoist/find-tasks"))
        self.assertTrue(ap.mcp_rule_matches("todoist/find-tasks", " todoist/find-tasks "))
        self.assertFalse(ap.mcp_rule_matches("todoist/*", "slack/search"))

        perms = {
            "allow": [
                "command(git status)",
                "command(gh pr view)",
                "read_url(google.com)",
                "write_file(/workspace/src)",
                "mcp(todoist/*)",
            ],
            "ask": ["command(gh pr view)", "execute_url(aws.amazon.com)"],
            "deny": [
                "command(git status)",
                "read_file(/etc/hosts)",
                "download_url(evil.example)",
                "mcp(todoist/delete-task)",
            ],
        }
        self.assertEqual(ap.check_rule_status("command", "git status", perms), "deny")
        self.assertEqual(ap.check_rule_status("command", "gh pr view", perms), "ask")
        self.assertEqual(ap.check_rule_status("read_url", "docs.google.com", perms), "allow")
        self.assertEqual(ap.check_rule_status("read_url", "example.com", perms), "none")
        self.assertEqual(ap.check_rule_status("execute_url", "console.aws.amazon.com", perms), "ask")
        self.assertEqual(ap.check_rule_status("download_url", "sub.evil.example", perms), "deny")
        # Implicit rules: deny read_file implies deny write_file; allow write_file implies allow read_file
        self.assertEqual(ap.check_rule_status("write_file", "/etc/hosts", perms), "deny")
        self.assertEqual(ap.check_rule_status("read_file", "/workspace/src/a.py", perms), "allow")
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
            # rtk read is unsafe and must not be suggested
            self.assertIsNone(ap.compute_rtk_prefix("cat", "cat a.txt"))
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
        self.assertTrue(any("101" in w for w in warnings2))

    def test_detect_rtk_hook_enabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hooks = os.path.join(tmp, "hooks.json")
            with mock.patch.object(ap.shutil, "which", return_value=None):
                self.assertEqual(ap.detect_rtk_hook_enabled(hooks), (False, []))

            with mock.patch.object(ap.shutil, "which", return_value="/usr/local/bin/rtk"):
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
                        {"name": "run_command", "args": {"CommandLine": "ls -la", "BypassSandbox": False}},
                        {"name": "run_command", "args": {"CommandLine": "stat foo", "BypassSandbox": True}},  # count=1 -> filtered by min_count=2
                        {"name": "mcp__todoist__find-tasks", "args": {"query": "today"}},
                        {"name": "mcp__todoist__create-task", "args": {"content": "x"}},
                        {"name": "read_url_content", "args": {"Url": "https://antigravity.google/docs/permissions"}},
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
                            {"name": "run_command", "args": {"CommandLine": '"ls -la"', "BypassSandbox": "false"}},
                            {"name": "mcp__todoist__find-tasks", "args": {"query": "tomorrow"}},
                            {"name": "mcp__todoist__create-task", "args": {"content": "y"}},
                            {"name": "read_url_content", "args": {"Url": '"https://antigravity.google/docs/sandbox"'}},
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

            def fake_rtk(prefix: str, _sample: str | None = None, **kw) -> str | None:
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

            # No double counting on Session 1
            self.assertEqual(cand_map["command(gh pr view)"]["total_count"], 2)
            self.assertEqual(cand_map["command(gh pr view)"]["bypass_count"], 2)
            self.assertEqual(
                cand_map["command(gh pr view)"]["suggested_rules"],
                ["command(gh pr view)", "command(rtk gh pr view)"],
            )
            # Original allowed, RTK companion missing
            self.assertEqual(cand_map["command(npm run lint)"]["suggested_rules"], ["command(rtk lint)"])
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

            # Warnings recorded for malformed JSONL + invalid existing rule syntax + parallel RTK warning
            self.assertTrue(any("bad rule syntax" in w for w in report["warnings"]))
            self.assertTrue(any("malformed JSONL" in w for w in report["warnings"]))
            self.assertTrue(any("simulated parallel rtk warning" in w for w in report["warnings"]))

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
                "read_file(/etc/./hosts)",
                "read_file(/tmp/../etc/hosts)",
                "write_file(/etc/hosts)",
                "download_url(sub.evil.example)",
            ):
                with self.assertRaisesRegex(ValueError, "permissions.deny", msg=denied_rule):
                    ap.apply_rules(settings_path, [denied_rule], dry_run=False)

            # Broader allow overlapping narrower deny emits a warning
            overlap_res = ap.apply_rules(settings_path, ["read_file(/etc)"], dry_run=True)
            self.assertTrue(any("partially overlaps existing permissions.deny" in w for w in overlap_res["warnings"]))

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

            # Comprehensive validate_rule_for_apply safety rejections
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
                "command(rtk proxy)",
                "command(rtk run)",
                "command(rtk read)",
                "command(rtk grep)",
                "command(rtk gh pr merge)",
                "command(env -u PATH rm -rf)",
                "command(/usr/bin/env rm -rf)",
                "command('rm')",
                "command(.)",
                "command(cat)",
                "command(grep)",
                "command(fd)",
                "command(yq)",
                "command(git)",
                "command(gh pr)",
                "command(tar --overwrite)",
                "command(tar -txf)",
                "command(npx -c)",
                "command(gh pr merge)",
                "command(git -C)",
                "command(gh api)",
                "command(git push>/dev/null)",
                "mcp(*)",
                "mcp(*/*)",
                "mcp( todoist/find-tasks )",
                "mcp(todoist/delete-task)",
                "mcp(fs/writeFile)",
                "mcp(github/deleteBranch)",
                "read_file(/)",
                "write_file(/)",
                "write_file(~)",
                "write_file(.)",
                "write_file(..)",
                "read_file(~/.ssh)",
                "read_file(~/.config//gcloud)",
                "read_file(.env)",
                "read_file(/workspace/server.key)",
                "write_file(.ssh/authorized_keys)",
                "read_file(secrets/prod.yaml)",
                "invalid syntax",
            ):
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
                    with self.assertRaises(ValueError, msg=f"expected failure for {content} dry={dry_flag}"):
                        ap.apply_rules(bad_file, ["command(gh pr view)"], dry_run=dry_flag)
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
