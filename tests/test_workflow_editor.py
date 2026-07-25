from __future__ import annotations

import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database
from app.comfyui.workflow_compiler import (
    WorkflowCompiler,
    WorkflowCompilerError,
    WorkflowDependencyValidator,
    default_field_values,
)
from app.comfyui.workflow_execution import WorkflowExecutionService
from app.comfyui.workflow_models import RuntimeInventory, WorkflowTemplateManifest
from app.comfyui.workflow_registry import WorkflowTemplateRegistry
from app.comfyui.sampling_options import CORE_SAMPLER_OPTIONS, CORE_SCHEDULER_OPTIONS
from app.comfyui.workflow_store import WorkflowStore
from app.config_store import ConfigStore
from app.main import app


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z1XcAAAAASUVORK5CYII="
)


def ready_inventory(template) -> RuntimeInventory:
    return RuntimeInventory(
        online=True,
        node_types=sorted(set(template.manifest.required_nodes) | {"LoraLoader"}),
        models={
            "checkpoints": ["models/base-xl.safetensors", "models/refiner-xl.safetensors"],
            "loras": ["styles/ink.safetensors", "styles/light.safetensors"],
            "vae": ["video_vae.safetensors"],
            "diffusion_models": ["hunyuan_video.safetensors"],
            "text_encoders": ["clip_l.safetensors", "llava_llama3_fp8.safetensors"],
        },
        source="api",
    )


class WorkflowTemplateRegistryTest(unittest.TestCase):
    def test_builtin_templates_cover_initial_categories(self) -> None:
        templates = WorkflowTemplateRegistry().list_templates()

        self.assertEqual(
            {item.manifest.category.value for item in templates},
            {"simple", "reference", "video", "advanced"},
        )
        self.assertTrue(all(item.manifest.resource_slots for item in templates))
        self.assertTrue(all(item.workflow for item in templates))
        self.assertTrue(all(item.manifest.schema_version == "2" for item in templates))
        self.assertTrue(all(item.manifest.supported_ecosystems for item in templates))

    def test_builtin_templates_expose_complete_comfyui_sampling_catalog(self) -> None:
        expected_samplers = [value for value, _label in CORE_SAMPLER_OPTIONS]
        expected_schedulers = [value for value, _label in CORE_SCHEDULER_OPTIONS]

        for template in WorkflowTemplateRegistry().list_templates():
            fields = {field.id: field for field in template.manifest.fields}
            self.assertEqual(
                [option.value for option in fields["sampler"].options],
                expected_samplers,
            )
            self.assertEqual(
                [option.value for option in fields["scheduler"].options],
                expected_schedulers,
            )

    def test_json_bundle_import_is_immediately_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowTemplateRegistry(user_root=temp_dir)
            source = registry.get("core-image")
            manifest = source.manifest.model_dump(mode="json")
            manifest.update({"id": "custom-image", "name": "Custom image", "version": "2.0.0"})
            bundle = json.dumps({"manifest": manifest, "workflow": source.workflow}).encode("utf-8")

            imported = registry.import_bundle("custom.json", bundle)

            self.assertEqual(imported.manifest.id, "custom-image")
            self.assertEqual(registry.get("custom-image").source, "user")
            self.assertTrue((Path(temp_dir) / "custom-image" / "manifest.json").is_file())

    def test_v1_bundle_is_migrated_and_persisted_as_schema_v2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowTemplateRegistry(user_root=temp_dir)
            source = registry.get("core-image")
            manifest = source.manifest.model_dump(mode="json")
            manifest.update({
                "schema_version": "1",
                "id": "legacy-v1-image",
                "name": "Legacy v1 image",
                "version": "1.0.0",
            })
            for key in (
                "supported_ecosystems",
                "loader_family",
                "component_policy",
                "capability_notes",
                "limitation_notes",
            ):
                manifest.pop(key)
            bundle = json.dumps({"manifest": manifest, "workflow": source.workflow}).encode("utf-8")

            imported = registry.import_bundle("legacy.json", bundle)
            stored = json.loads(
                (Path(temp_dir) / "legacy-v1-image" / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(imported.manifest.schema_version, "2")
            self.assertEqual(imported.manifest.loader_family.value, "checkpoint")
            self.assertEqual(imported.manifest.component_policy.clip.value, "embedded")
            self.assertEqual(stored["schema_version"], "2")
            self.assertIn("ecosystem compatibility", stored["limitation_notes"][0])

    def test_v2_manifest_rejects_component_policy_without_matching_slot(self) -> None:
        source = WorkflowTemplateRegistry().get("core-image")
        payload = source.manifest.model_dump(mode="json")
        payload["component_policy"]["clip"] = "required"

        with self.assertRaisesRegex(ValueError, "required clip policy"):
            WorkflowTemplateManifest.model_validate(payload)

    def test_resource_options_filter_standard_and_gguf_files_by_slot(self) -> None:
        from app.comfyui.editor_routes import _resource_options

        source = WorkflowTemplateRegistry().get("core-image")
        manifest = WorkflowTemplateManifest.model_validate({
            "id": "taxonomy-filter",
            "name": "Taxonomy filter",
            "version": "1.0.0",
            "category": "simple",
            "media_type": "image",
            "supported_ecosystems": ["flux_1"],
            "loader_family": "custom",
            "component_policy": {"clip": "embedded", "vae": "embedded"},
            "resource_slots": {
                "standard": {"label": "Standard", "accepts": ["diffusion_model"]},
                "gguf": {"label": "GGUF", "accepts": ["diffusion_model_gguf"]},
            },
            "output_nodes": ["7"],
        })
        template = source.model_copy(update={"manifest": manifest})
        inventory = RuntimeInventory(
            online=True,
            models={
                "diffusion_models": ["flux.safetensors", "flux.Q4_K_M.gguf"],
                "unet": ["legacy.ckpt", "legacy.Q5_K_S.GGUF"],
            },
            source="api",
        )

        options = _resource_options(template, inventory)

        self.assertEqual(
            [item["name"] for item in options["standard"]],
            ["flux.safetensors", "legacy.ckpt"],
        )
        self.assertEqual(
            [item["name"] for item in options["gguf"]],
            ["flux.Q4_K_M.gguf", "legacy.Q5_K_S.GGUF"],
        )


class WorkflowCompilerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.template = WorkflowTemplateRegistry().get("core-image")

    def test_fields_and_generic_lora_chain_are_compiled(self) -> None:
        graph = WorkflowCompiler().compile(
            self.template,
            values={"positive_prompt": "A glass observatory", "width": 768, "seed": 42},
            resource_selections={
                "checkpoint": "models/base-xl.safetensors",
                "loras": [
                    {"name": "styles/ink.safetensors", "strength_model": 0.7, "strength_clip": 0.6},
                    "styles/light.safetensors",
                ],
            },
        )

        self.assertEqual(graph["1"]["inputs"]["ckpt_name"], "models/base-xl.safetensors")
        self.assertEqual(graph["2"]["inputs"]["text"], "A glass observatory")
        self.assertEqual(graph["4"]["inputs"]["width"], 768)
        self.assertEqual(graph["5"]["inputs"]["seed"], 42)
        self.assertEqual(graph["cmv_lora_1"]["inputs"]["strength_model"], 0.7)
        self.assertEqual(graph["cmv_lora_2"]["inputs"]["model"], ["cmv_lora_1", 0])
        self.assertEqual(graph["5"]["inputs"]["model"], ["cmv_lora_2", 0])
        self.assertEqual(graph["2"]["inputs"]["clip"], ["cmv_lora_2", 1])
        self.assertEqual(graph["6"]["inputs"]["vae"], ["1", 2])

    def test_extended_sampler_and_scheduler_are_compiled(self) -> None:
        graph = WorkflowCompiler().compile(
            self.template,
            values={
                "sampler": "sa_solver_pece",
                "scheduler": "kl_optimal",
            },
            resource_selections={"checkpoint": "models/base-xl.safetensors"},
        )

        self.assertEqual(graph["5"]["inputs"]["sampler_name"], "sa_solver_pece")
        self.assertEqual(graph["5"]["inputs"]["scheduler"], "kl_optimal")

    def test_ambiguous_auto_binding_requires_declarative_binding(self) -> None:
        template = self.template.model_copy(deep=True)
        template.workflow["8"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ""},
        }
        slot = template.manifest.resource_slots["checkpoint"]
        template.manifest.resource_slots["checkpoint"] = slot.model_copy(
            update={"binding": slot.binding.model_copy(update={"kind": "auto", "node_id": None, "input": None})}
        )

        with self.assertRaisesRegex(WorkflowCompilerError, "exactly one"):
            WorkflowCompiler().compile(
                template,
                resource_selections={"checkpoint": "models/base-xl.safetensors"},
            )

    def test_dependency_report_separates_nodes_and_models(self) -> None:
        report = WorkflowDependencyValidator().validate(
            self.template,
            resource_selections={"checkpoint": "missing.safetensors"},
            inventory=RuntimeInventory(
                online=True,
                node_types=["CheckpointLoaderSimple"],
                models={"checkpoints": []},
                source="api",
            ),
        )

        self.assertIn("KSampler", report.missing_nodes)
        self.assertEqual(report.missing_resources[0].slot, "checkpoint")
        self.assertFalse(report.ready)

    def test_dependency_report_is_ready_for_resolved_runtime(self) -> None:
        report = WorkflowDependencyValidator().validate(
            self.template,
            resource_selections={
                "checkpoint": "models/base-xl.safetensors",
                "loras": ["styles/ink.safetensors"],
            },
            inventory=ready_inventory(self.template),
        )

        self.assertTrue(report.ready)


class WorkflowEditorRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.old_upload_folder = app.config.get("UPLOAD_FOLDER")
        self.old_config_store = app.config.get("CONFIG_STORE")
        app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=str(Path(self.temp_dir.name) / "uploads"),
            CONFIG_STORE=ConfigStore(Path(self.temp_dir.name) / "config.json"),
        )
        Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
        self.client = app.test_client()
        self.template = WorkflowTemplateRegistry().get("core-image")
        self.inventory = ready_inventory(self.template)
        self.inventory.models["checkpoints"] = ["models/base-xl.safetensors"]

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        app.config["UPLOAD_FOLDER"] = self.old_upload_folder
        app.config["CONFIG_STORE"] = self.old_config_store
        self.temp_dir.cleanup()

    def test_editor_page_uses_beginner_path_and_separate_advanced_settings(self) -> None:
        response = self.client.get("/editor")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("What will you create?", html)
        self.assertIn("Describe your idea in everyday language", html)
        self.assertIn('id="advanced-settings-dialog"', html)
        self.assertIn('id="advanced-fields"', html)
        self.assertIn("Check dependencies and preview graph", html)
        self.assertNotIn("Manifest controls", html)

    @patch("app.comfyui.editor_routes._inventory")
    def test_manifest_driven_draft_preview_round_trip(self, inventory_mock) -> None:
        inventory_mock.return_value = self.inventory
        bootstrap = self.client.get("/api/editor/bootstrap")
        self.assertEqual(bootstrap.status_code, 200)
        self.assertEqual(len(bootstrap.get_json()["templates"]), 4)

        created = self.client.post(
            "/api/editor/drafts",
            json={
                "template_id": "core-image",
                "values": {"positive_prompt": "A copper automaton"},
                "resource_selections": {"checkpoint": "models/base-xl.safetensors"},
            },
        )
        self.assertEqual(created.status_code, 201)
        draft = created.get_json()["draft"]

        updated = self.client.patch(
            f"/api/editor/drafts/{draft['id']}",
            json={"values": {"steps": 36}},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["draft"]["values"]["positive_prompt"], "A copper automaton")
        self.assertEqual(updated.get_json()["draft"]["values"]["steps"], 36)

        preview = self.client.post(f"/api/editor/drafts/{draft['id']}/preview")
        self.assertEqual(preview.status_code, 200)
        payload = preview.get_json()
        self.assertTrue(payload["dependencies"]["ready"])
        self.assertEqual(payload["workflow"]["5"]["inputs"]["steps"], 36)

    @patch("app.comfyui.editor_routes._inventory")
    def test_run_is_blocked_when_runtime_dependencies_are_missing(self, inventory_mock) -> None:
        inventory_mock.return_value = RuntimeInventory(online=False, error="offline")
        draft = WorkflowStore().create_draft(
            template_id="core-image",
            template_version="1.0.0",
            values=default_field_values(self.template),
            resource_selections={},
        )

        response = self.client.post(f"/api/editor/drafts/{draft.id}/run")

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "workflow_dependencies_missing")
        self.assertTrue(payload["dependencies"]["missing_nodes"])
        self.assertTrue(payload["dependencies"]["missing_resources"])

    def test_run_results_exclude_assets_deleted_from_library(self) -> None:
        store = WorkflowStore()
        draft = store.create_draft(
            template_id="core-image",
            template_version="1.0.0",
            values=default_field_values(self.template),
            resource_selections={"checkpoint": "models/base-xl.safetensors"},
        )
        run = store.create_run(
            draft_id=draft.id,
            prompt_id="prompt-deleted-output",
            client_id="editor-test",
        )
        asset_id, _ = database.insert_upload_asset(
            "temporary-result.png",
            PNG_1X1,
            media_type="image",
            has_generation_metadata=True,
        )
        store.update_run(
            run.id,
            status="completed",
            output_asset_ids=[asset_id],
        )

        self.assertTrue(database.delete_image(asset_id))
        response = self.client.get("/api/editor/runs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["runs"][0]["output_asset_ids"], [])
        self.assertEqual(store.get_run(run.id).output_asset_ids, [asset_id])

    @patch("app.comfyui.editor_routes.client_from_store")
    def test_remix_creates_manual_reference_draft_without_running(self, client_mock) -> None:
        runtime = client_mock.return_value
        runtime.upload_image.return_value = {
            "name": "source.png",
            "subfolder": "cmv/remix",
            "type": "input",
        }
        asset_id, _ = database.insert_upload_asset(
            "source.png",
            PNG_1X1,
            media_type="image",
            has_generation_metadata=True,
            embedded_metadata={
                "prompt_parameters": {
                    "positive_prompt": "A lantern floating over a frozen lake",
                    "negative_prompt": "blurry",
                }
            },
        )

        response = self.client.post("/api/editor/remix", json={"asset_id": asset_id})

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["draft"]["template_id"], "core-reference")
        self.assertEqual(payload["draft"]["status"], "editing")
        self.assertEqual(payload["draft"]["source_asset_id"], asset_id)
        self.assertEqual(
            payload["draft"]["values"]["positive_prompt"],
            "A lantern floating over a frozen lake",
        )
        self.assertEqual(payload["draft"]["values"]["reference_image"], "cmv/remix/source.png")
        self.assertEqual(WorkflowStore().list_runs(), [])


class FakeCompletedClient:
    def get_job(self, prompt_id):
        return {
            "status": "completed",
            "workflow": {"prompt": {"1": {"class_type": "SaveImage", "inputs": {}}}},
            "outputs": {
                "7": {
                    "images": [{"filename": "result.png", "subfolder": "", "type": "output"}],
                }
            },
        }

    def download_output(self, output):
        return PNG_1X1


class WorkflowExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_completed_output_is_imported_into_library(self) -> None:
        store = WorkflowStore()
        template = WorkflowTemplateRegistry().get("core-image")
        draft = store.create_draft(
            template_id=template.manifest.id,
            template_version=template.manifest.version,
            values=default_field_values(template),
            resource_selections={"checkpoint": "models/base-xl.safetensors"},
        )
        run = store.create_run(draft_id=draft.id, prompt_id="prompt-1", client_id="client-1")

        completed = WorkflowExecutionService(store=store, client=FakeCompletedClient()).refresh(run.id)

        self.assertEqual(completed.status, "completed")
        self.assertEqual(len(completed.output_asset_ids), 1)
        detail = database.get_asset_detail(completed.output_asset_ids[0])
        self.assertIsNotNone(detail)
        self.assertEqual(detail.media_type, "image")
        self.assertEqual(detail.embedded_metadata["generation"]["template_id"], "core-image")


if __name__ == "__main__":
    unittest.main()
