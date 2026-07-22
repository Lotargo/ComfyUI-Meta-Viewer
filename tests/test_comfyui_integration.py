from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.comfyui.client import ComfyUIClient, ComfyUIClientError
from app.comfyui.detector import ComfyUIDetectionResult, detect_comfyui, find_python_interpreter
from app.comfyui.launcher import generate_launcher_script
from app.comfyui.manager import ComfyUIMode, ComfyUIStatus, ComfyUIManager
from app.config_store import ConfigStore
from app.main import app


class ComfyUIDetectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_detect_root_main_py(self) -> None:
        main_py = self.base_path / "main.py"
        main_py.write_text("print('comfy')", encoding="utf-8")

        # Fake python_embeded
        py_exe = self.base_path / "python_embeded" / ("python.exe" if sys.platform == "win32" else "python")
        py_exe.parent.mkdir(parents=True, exist_ok=True)
        py_exe.write_text("fake python", encoding="utf-8")

        res = detect_comfyui(self.base_path)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.comfy_dir, self.base_path)
        self.assertEqual(res.main_py, main_py)
        self.assertEqual(res.interpreter, py_exe)
        self.assertTrue(res.is_portable)

    def test_detect_nested_comfyui_main_py(self) -> None:
        nested_dir = self.base_path / "ComfyUI"
        nested_dir.mkdir(parents=True, exist_ok=True)
        main_py = nested_dir / "main.py"
        main_py.write_text("print('comfy')", encoding="utf-8")

        # Create venv python
        venv_py = nested_dir / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
        venv_py.parent.mkdir(parents=True, exist_ok=True)
        venv_py.write_text("fake python", encoding="utf-8")

        res = detect_comfyui(self.base_path)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.comfy_dir, nested_dir)
        self.assertEqual(res.main_py, main_py)
        self.assertEqual(res.interpreter, venv_py)
        self.assertFalse(res.is_portable)

    def test_detect_ambiguous_main_py_error(self) -> None:
        (self.base_path / "main.py").write_text("root", encoding="utf-8")
        nested_dir = self.base_path / "ComfyUI"
        nested_dir.mkdir(parents=True, exist_ok=True)
        (nested_dir / "main.py").write_text("nested", encoding="utf-8")

        res = detect_comfyui(self.base_path)
        self.assertFalse(res.is_valid)
        self.assertIn("Ambiguous", res.error or "")

    def test_detect_invalid_missing_main_py(self) -> None:
        res = detect_comfyui(self.base_path)
        self.assertFalse(res.is_valid)
        self.assertIn("main.py not found", res.error or "")


class ComfyUILauncherTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_generate_launcher_script(self) -> None:
        comfy_dir = self.base_path / "ComfyUI with space"
        comfy_dir.mkdir(parents=True, exist_ok=True)
        main_py = comfy_dir / "main.py"
        py_exe = comfy_dir / "python.exe"

        detection = ComfyUIDetectionResult(
            root_path=self.base_path,
            comfy_dir=comfy_dir,
            main_py=main_py,
            interpreter=py_exe,
            is_valid=True,
        )

        script_path = generate_launcher_script(
            detection=detection,
            extra_args="--lowvram --xformers",
            host="127.0.0.1",
            port=8188,
        )

        self.assertTrue(script_path.exists())
        content = script_path.read_text(encoding="utf-8")
        self.assertIn("--listen 127.0.0.1", content)
        self.assertIn("--port 8188", content)
        self.assertIn("--lowvram", content)


class ComfyUIClientTest(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_check_health_success(self, mock_urlopen) -> None:
        stats_response = MagicMock()
        stats_response.status = 200
        stats_response.read.return_value = json.dumps({"system": {"os": "nt"}}).encode("utf-8")
        stats_cm = MagicMock()
        stats_cm.__enter__.return_value = stats_response

        queue_response = MagicMock()
        queue_response.status = 200
        queue_response.read.return_value = json.dumps({
            "queue_running": [],
            "queue_pending": [],
        }).encode("utf-8")
        queue_cm = MagicMock()
        queue_cm.__enter__.return_value = queue_response

        mock_urlopen.side_effect = [stats_cm, queue_cm]

        client = ComfyUIClient(host="127.0.0.1", port=8188)
        res = client.check_health()

        self.assertTrue(res["online"])
        self.assertIn("system", res["system_stats"])
        self.assertFalse(res["queue_info"]["is_busy"])

    @patch("urllib.request.urlopen")
    def test_check_health_unreachable(self, mock_urlopen) -> None:
        mock_urlopen.side_effect = OSError("Connection refused")
        client = ComfyUIClient(host="127.0.0.1", port=8188)
        with self.assertRaises(ComfyUIClientError):
            client.check_health()


class ComfyUIManagerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        (self.base_path / "main.py").write_text("import time; time.sleep(10)", encoding="utf-8")

        # Fake interpreter script that runs python
        py_exe = Path(sys.executable)
        self.mgr = ComfyUIManager()

    def tearDown(self) -> None:
        self.mgr.stop_managed()
        self.temp_dir.cleanup()

    @patch("app.comfyui.manager.detect_comfyui")
    def test_start_and_stop_managed_process(self, mock_detect) -> None:
        detection = ComfyUIDetectionResult(
            root_path=self.base_path,
            comfy_dir=self.base_path,
            main_py=self.base_path / "main.py",
            interpreter=Path(sys.executable),
            is_valid=True,
        )
        mock_detect.return_value = detection

        info = self.mgr.start_managed(install_path=self.base_path)
        self.assertEqual(info["mode"], "managed")
        self.assertEqual(info["status"], "starting")
        self.assertIsNotNone(info["pid"])

        self.mgr.stop_managed()
        self.assertEqual(self.mgr.mode, ComfyUIMode.NONE)
        self.assertEqual(self.mgr.status, ComfyUIStatus.STOPPED)

    @patch("app.comfyui.client.ComfyUIClient.check_health")
    def test_check_external_mode(self, mock_health) -> None:
        mock_health.return_value = {
            "online": True,
            "system_stats": {"system": {}},
            "queue_info": {"is_busy": False},
        }

        res = self.mgr.check_external_or_status(host="127.0.0.1", port=8188)
        self.assertEqual(res["mode"], "external")
        self.assertEqual(res["status"], "external")
        self.assertTrue(res["online"])


class ComfyUIRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        config_path = Path(self.temp_dir.name) / "config.json"
        self.config_store = ConfigStore(config_path)

        app.config["TESTING"] = True
        app.config["CONFIG_STORE"] = self.config_store
        self.client = app.test_client()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_settings_page_route(self) -> None:
        resp = self.client.get("/settings/comfyui")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"ComfyUI Integration", resp.data)

    def test_config_api(self) -> None:
        resp = self.client.get("/api/comfyui/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["port"], 8188)

        post_resp = self.client.post(
            "/api/comfyui/config",
            json={"host": "127.0.0.1", "port": 8189, "extra_args": "--lowvram"},
        )
        self.assertEqual(post_resp.status_code, 200)
        updated = post_resp.get_json()
        self.assertEqual(updated["port"], 8189)
        self.assertEqual(updated["extra_args"], "--lowvram")

    def test_detect_api(self) -> None:
        resp = self.client.post("/api/comfyui/detect", json={"path": self.temp_dir.name})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertFalse(data["is_valid"])

    def test_status_api(self) -> None:
        resp = self.client.get("/api/comfyui/status")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("mode", data)
        self.assertIn("status", data)


if __name__ == "__main__":
    unittest.main()
