from app.comfyui.workflow_registry import WorkflowTemplateRegistry


def test_builtin_workflow_templates_load_and_validate(tmp_path):
    registry = WorkflowTemplateRegistry(user_root=tmp_path / "templates")

    templates = registry.list_templates()
    template_ids = {t.manifest.id for t in templates}

    expected_ids = {
        "core-image",
        "core-flux",
        "core-flux-gguf",
        "core-pony-gguf",
        "core-reference",
        "core-two-stage",
        "core-video",
        "core-inpaint",
        "core-controlnet",
        "core-upscale",
    }
    for tid in expected_ids:
        assert tid in template_ids, f"Expected template '{tid}' not found in registry"

    for template in templates:
        assert template.manifest.schema_version == "2"
        assert template.manifest.id
        assert template.manifest.name
        assert template.manifest.category
        assert template.manifest.media_type in ("image", "video")
        assert len(template.manifest.output_nodes) > 0
