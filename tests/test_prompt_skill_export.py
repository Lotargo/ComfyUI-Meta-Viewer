from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.ai.prompting.registry import FAMILY_PROFILES
from app.integrations.skill_export import (
    PromptSkillExportError,
    PromptSkillExporter,
    SkillExportHost,
)


class PromptSkillExporterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.exporter = PromptSkillExporter()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_all_hosts_export_identical_canonical_references(self) -> None:
        manifests = {}
        skill_texts = {}
        for host in SkillExportHost:
            package = self.exporter.export(self.root / host.value, host=host)
            manifest = json.loads(
                (package.path / "manifest.json").read_text(encoding="utf-8")
            )
            manifests[host] = manifest["references"]
            skill_texts[host] = (package.path / "SKILL.md").read_text(
                encoding="utf-8"
            )
            self.assertEqual(manifest["host"], host.value)
            self.assertRegex(package.manifest_sha256, r"^[0-9a-f]{64}$")

        first_references = next(iter(manifests.values()))
        self.assertTrue(first_references)
        for references in manifests.values():
            self.assertEqual(references, first_references)
        for host, skill_text in skill_texts.items():
            self.assertIn(f"host: {host.value}", skill_text)
            self.assertIn("SceneSpec", skill_text)
            self.assertIn("strict `PromptResult` JSON", skill_text)

    def test_family_reference_is_a_byte_exact_canonical_copy(self) -> None:
        package = self.exporter.export(
            self.root / "package", host=SkillExportHost.OPENCODE
        )
        for family, profile in FAMILY_PROFILES.items():
            exported = package.path / "references" / "families" / f"{family.value}-base.md"
            self.assertEqual(exported.read_bytes(), profile.path.read_bytes())
            manifest = json.loads(
                (package.path / "manifest.json").read_text(encoding="utf-8")
            )
            key = f"references/families/{family.value}-base.md"
            self.assertEqual(
                manifest["references"][key]["sha256"],
                hashlib.sha256(profile.path.read_bytes()).hexdigest(),
            )

    def test_export_refuses_to_merge_into_an_existing_package(self) -> None:
        target = self.root / "existing"
        target.mkdir()
        (target / "user-file.txt").write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(PromptSkillExportError, "must be empty"):
            self.exporter.export(target, host=SkillExportHost.CODEX)
        self.assertEqual((target / "user-file.txt").read_text(encoding="utf-8"), "keep")

    def test_exported_validator_accepts_only_prompt_result_v1(self) -> None:
        package = self.exporter.export(
            self.root / "package", host=SkillExportHost.CLAUDE_CODE
        )
        valid = self.root / "valid.json"
        invalid = self.root / "invalid.json"
        valid.write_text(
            json.dumps({
                "schema_version": "1",
                "positive_prompt": "portrait",
                "negative_prompt": "",
            }),
            encoding="utf-8",
        )
        invalid.write_text(
            json.dumps({
                "schema_version": "1",
                "positive_prompt": "portrait",
                "negative_prompt": "",
                "commentary": "not allowed",
            }),
            encoding="utf-8",
        )
        validator = package.path / "scripts" / "validate_prompt_result.py"
        accepted = subprocess.run(
            [sys.executable, str(validator), str(valid)],
            capture_output=True,
            text=True,
            check=False,
        )
        rejected = subprocess.run(
            [sys.executable, str(validator), str(invalid)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(rejected.returncode, 1)


if __name__ == "__main__":
    unittest.main()
