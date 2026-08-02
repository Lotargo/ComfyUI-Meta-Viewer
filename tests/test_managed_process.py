from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.ai.cli import CLIIntegrationError
from app.ai.execution import opencode as opencode_module
from app.ai.execution import opencode_judge as judge_module
from app.ai.managed_process import run_managed_command


class ManagedProcessBindingTest(unittest.TestCase):
    def test_opencode_executors_use_managed_runner(self) -> None:
        self.assertIs(opencode_module.run_command, run_managed_command)
        self.assertIs(judge_module.run_command, run_managed_command)

    def test_normal_command_returns_output(self) -> None:
        result = run_managed_command(
            [sys.executable, "-c", "print('CMV_MANAGED_OK')"],
            timeout=10,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "CMV_MANAGED_OK")

    @mock.patch("app.ai.managed_process.os.name", "nt")
    @mock.patch("app.ai.managed_process.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True)
    @mock.patch("app.ai.managed_process.subprocess.run")
    @mock.patch.dict("app.ai.managed_process.os.environ", {"SystemRoot": "C:\\MySystemRoot"})
    def test_fallback_terminate_process_tree_windows_resolves_taskkill(self, mock_run: mock.MagicMock) -> None:
        from app.ai.managed_process import _fallback_terminate_process_tree
        mock_process = mock.MagicMock()
        mock_process.pid = 1234
        mock_process.poll.return_value = 0

        _fallback_terminate_process_tree(mock_process)

        expected_path = os.path.join("C:\\MySystemRoot", "System32", "taskkill.exe")
        mock_run.assert_called_once_with(
            [expected_path, "/PID", "1234", "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            creationflags=0x08000000,
        )

    @mock.patch("app.ai.managed_process.os.name", "nt")
    @mock.patch("app.ai.managed_process.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True)
    @mock.patch("app.ai.managed_process.subprocess.run")
    @mock.patch.dict("app.ai.managed_process.os.environ", {}, clear=True)
    def test_fallback_terminate_process_tree_windows_fallback_path(self, mock_run: mock.MagicMock) -> None:
        from app.ai.managed_process import _fallback_terminate_process_tree
        mock_process = mock.MagicMock()
        mock_process.pid = 5678
        mock_process.poll.return_value = 0

        _fallback_terminate_process_tree(mock_process)

        expected_path = os.path.join("C:\\Windows", "System32", "taskkill.exe")
        mock_run.assert_called_once_with(
            [expected_path, "/PID", "5678", "/T", "/F"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
            creationflags=0x08000000,
        )


@unittest.skipUnless(os.name == "nt", "Windows Job Object regression test")
class WindowsManagedProcessTimeoutTest(unittest.TestCase):
    def test_timeout_kills_child_after_parent_exits_and_releases_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="cmv-managed-process-test-") as temp_dir:
            workspace = Path(temp_dir)
            lock_path = workspace / "child-lock.txt"
            child_code = (
                "from pathlib import Path; import time; "
                f"handle=Path({str(lock_path)!r}).open('w', encoding='utf-8'); "
                "handle.write('locked'); handle.flush(); time.sleep(60)"
            )
            parent_code = (
                "import subprocess, sys, time; from pathlib import Path; "
                f"subprocess.Popen([sys.executable, '-c', {child_code!r}], "
                "stdout=sys.stdout, stderr=sys.stderr); "
                f"deadline=time.time()+2; path=Path({str(lock_path)!r}); "
                "\nwhile not path.exists() and time.time() < deadline: time.sleep(0.02)"
            )

            with self.assertRaises(CLIIntegrationError) as captured:
                run_managed_command(
                    [sys.executable, "-c", parent_code],
                    timeout=2,
                    cwd=workspace,
                )

            self.assertEqual(captured.exception.code, "timeout")
            self.assertTrue(lock_path.exists())
            lock_path.unlink()
            probe = workspace / "cleanup-probe.txt"
            probe.write_text("released", encoding="utf-8")
            probe.unlink()


if __name__ == "__main__":
    unittest.main()
