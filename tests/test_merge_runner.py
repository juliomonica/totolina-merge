"""Validate the gate itself, especially error output with process exit code 0."""
from pathlib import Path
import sys
import tempfile
import unittest

from run_kitchen_regressions import checked_run


class ErrorDetectionTests(unittest.TestCase):
    def test_errors_cannot_pass_with_zero_exit(self):
        for error in ["SCRIPT ERROR: Invalid access to previously freed instance",
                      "ERROR: null CreationDefinition", "ERROR: Failed loading resource",
                      "Assertion failed: duplicate result", "FATAL: SIGSEGV"]:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(RuntimeError):
                    checked_run([sys.executable, "-c", f"print({error!r})"], Path(directory) / "log.txt")

    def test_nonzero_exit_and_missing_completion_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "log.txt"
            with self.assertRaises(RuntimeError):
                checked_run([sys.executable, "-c", "raise SystemExit(2)"], log)
            with self.assertRaises(RuntimeError):
                checked_run([sys.executable, "-c", "print('started')"], log, expected_marker="complete")
            checked_run([sys.executable, "-c", "print('complete')"], log, expected_marker="complete")


if __name__ == "__main__":
    unittest.main()
