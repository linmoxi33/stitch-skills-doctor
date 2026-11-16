#!/usr/bin/env python3
"""Behavior tests for stitch-skills-doctor.

Run: python3 tests/run.py   (prints "N passed, M failed", exit code 0 only when M == 0)
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "bin", "stitch-skills-doctor")
CLEAN = os.path.join(ROOT, "examples", "in", "clean-pack")
BROKEN = os.path.join(ROOT, "examples", "in", "broken-pack")


def run(*args, cwd=None):
    proc = subprocess.run(
        [sys.executable, BIN] + list(args), capture_output=True, text=True, cwd=cwd or ROOT
    )
    return proc.returncode, proc.stdout, proc.stderr


def report(*args):
    rc, out, err = run("--json", *args)
    return rc, json.loads(out), err


class FixtureTests(unittest.TestCase):
    def test_01_clean_pack_passes(self):
        rc, data, _ = report("--pack", CLEAN)
        self.assertEqual(rc, 0)
        self.assertEqual(data["summary"]["findings"], 0)
        self.assertEqual(data["verdict"], "pass")

    def test_02_clean_pack_probes_scripts(self):
        _, data, _ = report("--pack", CLEAN)
        self.assertEqual(data["summary"]["scripts"], 1)
        self.assertEqual(data["summary"]["executed_probes"], 1)

    def test_03_broken_pack_fails_with_error(self):
        rc, data, _ = report("--pack", BROKEN)
        self.assertEqual(rc, 1)
        self.assertGreater(data["summary"]["by_severity"]["error"], 0)
        self.assertEqual(data["verdict"], "fail")

    def test_04_broken_pack_finds_all_rule_families(self):
        _, data, _ = report("--pack", BROKEN)
        rules = set(data["summary"]["by_rule"])
        for expected in (
            "DOC_FLAG_UNSUPPORTED",
            "DOC_PATH_MISSING",
            "DOC_PATH_CLONE_DEPENDENT",
            "SCRIPT_SYNTAX_ERROR",
            "SCRIPT_ORPHAN",
            "SCRIPT_DEP_MISSING",
            "SCRIPT_UNDECLARED_DEP",
        ):
            self.assertIn(expected, rules)

    def test_05_documented_flag_not_parsed_is_caught(self):
        _, data, _ = report("--pack", BROKEN)
        flags = {f["path"] for f in data["findings"] if f["rule"] == "DOC_FLAG_UNSUPPORTED"}
        self.assertIn("--mode", flags)
        self.assertNotIn("--input", flags)  # report.py really does parse --input

    def test_06_syntax_error_reports_interpreter_output(self):
        _, data, _ = report("--pack", BROKEN)
        errs = [f for f in data["findings"] if f["rule"] == "SCRIPT_SYNTAX_ERROR"]
        self.assertEqual(len(errs), 1)
        self.assertIn("SyntaxError", errs[0]["message"])

    def test_07_clone_dependent_path_is_error(self):
        _, data, _ = report("--pack", BROKEN)
        f = [x for x in data["findings"] if x["rule"] == "DOC_PATH_CLONE_DEPENDENT"]
        self.assertEqual(len(f), 1)
        self.assertEqual(f[0]["severity"], "error")

    def test_08_json_is_deterministic(self):
        _, a, _ = report("--pack", BROKEN)
        _, b, _ = report("--pack", BROKEN)
        self.assertEqual(a["deterministic_sha256"], b["deterministic_sha256"])
        self.assertEqual(
            [(f["rule"], f["path"]) for f in a["findings"]],
            [(f["rule"], f["path"]) for f in b["findings"]],
        )

    def test_09_no_exec_suppresses_probes(self):
        _, data, _ = report("--pack", BROKEN, "--no-exec")
        self.assertEqual(data["summary"]["executed_probes"], 0)
        self.assertNotIn("SCRIPT_SYNTAX_ERROR", data["summary"]["by_rule"])

    def test_10_fail_on_warning_flags_warnings_only_pack(self):
        tmp = tempfile.mkdtemp(prefix="ssd-test-")
        try:
            skill = os.path.join(tmp, "plugins", "p", "skills", "s")
            os.makedirs(os.path.join(skill, "scripts"))
            with open(os.path.join(skill, "SKILL.md"), "w") as fh:
                fh.write("---\nname: s\ndescription: d\n---\n\nNo commands here.\n")
            with open(os.path.join(skill, "scripts", "orphan.sh"), "w") as fh:
                fh.write("#!/bin/bash\necho hi\n")
            rc_error, _, _ = run("--pack", tmp)
            rc_warn, _, _ = run("--pack", tmp, "--fail-on", "warning")
            rc_never, _, _ = run("--pack", tmp, "--fail-on", "never")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(rc_error, 0)
        self.assertEqual(rc_warn, 1)
        self.assertEqual(rc_never, 0)


class CliTests(unittest.TestCase):
    def test_11_missing_pack_is_usage_error(self):
        rc, _, err = run()
        self.assertEqual(rc, 2)
        self.assertIn("--pack", err)

    def test_12_nonexistent_dir_is_usage_error(self):
        rc, _, err = run("--pack", os.path.join(ROOT, "does-not-exist"))
        self.assertEqual(rc, 2)
        self.assertIn("not a directory", err)

    def test_13_pack_without_skills_is_usage_error(self):
        tmp = tempfile.mkdtemp(prefix="ssd-empty-")
        try:
            rc, _, err = run("--pack", tmp)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(rc, 2)
        self.assertIn("no SKILL.md", err)

    def test_14_json_output_parses_and_has_contract_fields(self):
        rc, data, _ = report("--pack", CLEAN)
        self.assertEqual(rc, 0)
        for key in ("summary", "findings", "verdict", "deterministic_sha256"):
            self.assertIn(key, data)
        self.assertEqual(
            set(data["summary"]["by_severity"]), {"error", "warning", "info"}
        )

    def test_15_human_output_mentions_verdict_and_counts(self):
        rc, out, _ = run("--pack", CLEAN)
        self.assertEqual(rc, 0)
        self.assertIn("verdict=pass", out)
        self.assertIn("findings=0", out)

    def test_16_relative_pack_path_works_from_any_cwd(self):
        rc, out, _ = run("--pack", "examples/in/clean-pack", cwd=ROOT)
        self.assertEqual(rc, 0)
        self.assertIn("verdict=pass", out)


if __name__ == "__main__":
    prog = unittest.main(exit=False, verbosity=1)
    total = prog.result.testsRun
    failed = len(prog.result.failures) + len(prog.result.errors)
    print("%d passed, %d failed (%d cases)" % (total - failed, failed, total))
    sys.exit(0 if failed == 0 else 1)
