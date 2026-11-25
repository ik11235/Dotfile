#!/usr/bin/env python3
"""Unit tests for analyze_permissions.py."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from unittest import mock

import analyze_permissions as ap


class ShellParsingTests(unittest.TestCase):
    def test_split_shell_segments_respects_quotes(self) -> None:
        cmd = 'gh pr view 1 --json "a;b|c&&d" && git status; echo \'x && y\' | head -n 5'
        segs = ap.split_shell_segments(cmd)
        self.assertEqual(
            segs,
            [
                'gh pr view 1 --json "a;b|c&&d"',
                "git status",
                "echo 'x && y'",
                "head -n 5",
            ],
        )

    def test_unwrap_tokens_strips_env_wrappers_and_rtk(self) -> None:
        toks = ap.tokenize_segment("GIT_CONFIG_GLOBAL=/dev/null timeout 10 rtk git log -n 5 2>&1")
        unwrapped, had_env, was_rtk = ap.unwrap_tokens(toks)
        self.assertEqual(unwrapped, ["git", "log", "-n", "5"])
        self.assertTrue(had_env)
        self.assertTrue(was_rtk)

    def test_exact_match_only_detection(self) -> None:
        self.assertTrue(ap.has_exact_match_only_construct("git log $(whoami)"))
        self.assertTrue(ap.has_exact_match_only_construct("ls {a,b}"))
        self.assertTrue(ap.has_exact_match_only_construct("git -c core.pager=cat log"))
        self.assertFalse(ap.has_exact_match_only_construct("git status && git log --oneline"))
        # Single-quoted literal should not trigger command substitution detection
        self.assertFalse(ap.has_exact_match_only_construct("grep '$(foo)' file.txt"))

    def test_strip_heredocs_and_ignore_non_commands(self) -> None:
        cmd = "python3 - <<'PY'\nprint('hello')\ntest_files.append('a')\nPY\ngit status"
        segs = ap.split_shell_segments(cmd)
        self.assertEqual(segs, ["python3 - <<'PY'", "git status"])

        # Quoted <<EOF and here-string <<< must NOT swallow subsequent lines
        quoted_cmd = "echo '<<EOF'\ngit diff\ncat <<< 'hello'\ngit log"
        self.assertEqual(
            ap.split_shell_segments(quoted_cmd),
            ["echo '<<EOF'", "git diff", "cat <<< 'hello'", "git log"],
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

    def test_unsafe_flags_and_commands_excluded(self) -> None:
        for toks in (
            ["git", "-C", "/repo", "status"],
            ["git", "-c", "core.pager=cat", "log"],
            ["gh", "api", "repos/a/b"],
            ["gh", "-R", "a/b", "pr", "view", "1"],
            ["python3", "-c", "print(1)"],
            ["node", "-e", "1+1"],
            ["rm", "-rf", "tmp"],
            ["rtk", "bypass", "git", "status"],
            ["npx", "prettier", "--write", "."],
            ["npx", "tsc"],
            ["unzip", "archive.zip"],
        ):
            _, reason = ap.classify_command_tokens(toks)
            self.assertIsNotNone(reason, f"expected exclusion for {toks}")

    def test_safe_npx_and_unzip_flags(self) -> None:
        self.assertEqual(ap.classify_command_tokens(["npx", "tsc", "--noEmit"]), ("npx tsc --noEmit", None))
        self.assertEqual(ap.classify_command_tokens(["npx", "prettier", "--check", "."]), ("npx prettier --check", None))
        self.assertEqual(ap.classify_command_tokens(["unzip", "-p", "a.zip", "b"]), ("unzip -p", None))

    def test_rtk_probe_commands_never_slice_flag_pairs(self) -> None:
        probes = ap._build_rtk_probe_commands(
            "gh pr view",
            "gh pr view 171 --repo owner/repo --comments",
        )
        self.assertEqual(probes[0], "gh pr view 171 --repo owner/repo --comments")
        self.assertIn("gh pr view", probes)
        self.assertIn("gh pr view 1", probes)


class RuleMatchingTests(unittest.TestCase):
    def test_word_boundary_prefix_matching(self) -> None:
        self.assertTrue(ap.command_rule_matches_prefix("git status", "git status"))
        self.assertTrue(ap.command_rule_matches_prefix("git", "git status"))
        self.assertFalse(ap.command_rule_matches_prefix("ls", "lsof"))
        self.assertFalse(ap.command_rule_matches_prefix("gh pr view", "gh pr list"))

    def test_regex_matching(self) -> None:
        self.assertTrue(ap.command_rule_matches_prefix("regex:npm run (build|lint|test)", "npm run lint"))
        self.assertFalse(ap.command_rule_matches_prefix("regex:npm run (build|lint|test)", "npm run deploy"))

    def test_precedence_deny_ask_allow(self) -> None:
        perms = {
            "allow": ["command(git status)", "command(gh pr view)", "read_url(google.com)"],
            "ask": ["command(gh pr view)"],
            "deny": ["command(git status)"],
        }
        self.assertEqual(ap.check_rule_status("command", "git status", perms), "deny")
        self.assertEqual(ap.check_rule_status("command", "gh pr view", perms), "ask")
        self.assertEqual(ap.check_rule_status("read_url", "docs.google.com", perms), "allow")
        self.assertEqual(ap.check_rule_status("read_url", "example.com", perms), "none")


class ScanAndApplyIntegrationTests(unittest.TestCase):
    def _write_transcript(self, root: str, uuid: str, filename: str, entries: list[dict]) -> None:
        logs = os.path.join(root, "brain", uuid, ".system_generated", "logs")
        os.makedirs(logs, exist_ok=True)
        with open(os.path.join(logs, filename), "w", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")

    def test_scan_handles_full_and_compact_transcripts_and_rtk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = os.path.join(tmp, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "permissions": {
                            "allow": ["command(git status)", "command(rtk git status)"],
                            "ask": ["command(gh run view)"],
                            "deny": ["command(rm -rf)"],
                        }
                    },
                    fh,
                )

            # Session 1: transcript_full.jsonl (native types)
            self._write_transcript(
                tmp,
                "11111111-1111-1111-1111-111111111111",
                "transcript_full.jsonl",
                [
                    {
                        "type": "PLANNER_RESPONSE",
                        "tool_calls": [
                            {
                                "name": "run_command",
                                "args": {"CommandLine": "gh pr view 10 && git status", "BypassSandbox": True},
                            },
                            {
                                "name": "run_command",
                                "args": {"CommandLine": "gh run view 99", "BypassSandbox": True},
                            },
                            {
                                "name": "run_command",
                                "args": {"CommandLine": "gh api repos/o/r", "BypassSandbox": True},
                            },
                            {
                                "name": "mcp__todoist__find-tasks",
                                "args": {"query": "today"},
                            },
                            {
                                "name": "mcp__todoist__create-task",
                                "args": {"content": "x"},
                            },
                            {
                                "name": "read_url_content",
                                "args": {"Url": "https://antigravity.google/docs/permissions"},
                            },
                        ],
                    }
                ],
            )
            # Session 2: compact transcript.jsonl (stringified args)
            self._write_transcript(
                tmp,
                "22222222-2222-2222-2222-222222222222",
                "transcript.jsonl",
                [
                    {
                        "type": "PLANNER_RESPONSE",
                        "tool_calls": [
                            {
                                "name": "run_command",
                                "args": {"CommandLine": '"gh pr view 20"', "BypassSandbox": "true"},
                            },
                            {
                                "name": "run_command",
                                "args": {"CommandLine": '"gh run view 100"', "BypassSandbox": "true"},
                            },
                            {
                                "name": "run_command",
                                "args": {"CommandLine": '"gh api repos/o/r"', "BypassSandbox": "true"},
                            },
                            {
                                "name": "mcp__todoist__find-tasks",
                                "args": {"query": "tomorrow"},
                            },
                            {
                                "name": "read_url_content",
                                "args": {"Url": '"https://antigravity.google/docs/sandbox"'},
                            },
                        ],
                    }
                ],
            )

            def fake_rtk(prefix: str, _sample: str | None = None) -> str | None:
                if prefix in ("gh pr view", "git status"):
                    return f"rtk {prefix}"
                return None

            with mock.patch.object(ap, "compute_rtk_prefix", side_effect=fake_rtk):
                report = ap.scan_transcripts(
                    antigravity_dir=tmp,
                    settings_path=settings_path,
                    hooks_path=os.path.join(tmp, "missing-hooks.json"),
                    limit=10,
                    min_count=2,
                    check_rtk=True,
                )

            self.assertEqual(report["summary"]["sessions_scanned"], 2)
            cand_map = {c["rule"]: c for c in report["candidates"]}
            self.assertIn("command(gh pr view)", cand_map)
            self.assertEqual(
                cand_map["command(gh pr view)"]["suggested_rules"],
                ["command(gh pr view)", "command(rtk gh pr view)"],
            )
            self.assertEqual(cand_map["command(gh pr view)"]["bypass_count"], 2)
            self.assertIn("mcp(todoist/find-tasks)", cand_map)
            self.assertIn("read_url(antigravity.google)", cand_map)

            # Conflict with ask
            conflict_rules = {c["rule"] for c in report["conflicts"]}
            self.assertIn("command(gh run view)", conflict_rules)

            # Excluded unsafe commands / mutating MCP
            excl_prefixes = {e["prefix"] for e in report["excluded"]}
            self.assertIn("gh api", excl_prefixes)

            # Markdown rendering succeeds
            md = ap.render_markdown(report)
            self.assertIn("command(gh pr view)", md)
            self.assertIn("command(rtk gh pr view)", md)

    def test_apply_rules_validates_dedupes_preserves_keys_and_mode_0600(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings_path = os.path.join(tmp, "settings.json")
            with open(settings_path, "w", encoding="utf-8") as fh:
                json.dump(
                    {
                        "$schema": "https://antigravity.google/schemas/v1/settings.json",
                        "permissions": {
                            "allow": ["command(git status)"],
                            "deny": ["command(rm -rf)"],
                        },
                        "trustedWorkspaces": ["/tmp/demo"],
                    },
                    fh,
                )

            # Dry run does not write
            dry = ap.apply_rules(
                settings_path,
                ["command(git status)", "command(gh pr view)", "command(rtk gh pr view)"],
                dry_run=True,
            )
            self.assertEqual(dry["added"], ["command(gh pr view)", "command(rtk gh pr view)"])
            self.assertEqual(dry["skipped_existing"], ["command(git status)"])
            with open(settings_path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh)["permissions"]["allow"], ["command(git status)"])

            # Real apply writes atomically with 0600 and preserves other keys
            res = ap.apply_rules(
                settings_path,
                ["command(git status)", "command(gh pr view)", "command(rtk gh pr view)"],
                dry_run=False,
            )
            self.assertEqual(res["total_allow"], 3)
            mode = stat.S_IMODE(os.stat(settings_path).st_mode)
            self.assertEqual(mode, 0o600)
            with open(settings_path, encoding="utf-8") as fh:
                saved = json.load(fh)
            self.assertEqual(saved["$schema"], "https://antigravity.google/schemas/v1/settings.json")
            self.assertEqual(saved["trustedWorkspaces"], ["/tmp/demo"])
            self.assertEqual(
                saved["permissions"]["allow"],
                ["command(git status)", "command(gh pr view)", "command(rtk gh pr view)"],
            )

            # Unsafe / wildcard / deny-conflicting rules are rejected
            for bad in (
                "command(*)",
                "command(gh pr merge)",
                "command(rtk gh pr merge)",
                "command(git -C)",
                "command(gh api)",
                "read_file(~/.ssh)",
                "invalid syntax",
            ):
                with self.assertRaises(ValueError, msg=f"expected rejection for {bad}"):
                    ap.apply_rules(settings_path, [bad], dry_run=True)


if __name__ == "__main__":
    unittest.main()
