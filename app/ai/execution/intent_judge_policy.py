from __future__ import annotations

from typing import Any


_PRODUCT_POLICY = """PRODUCT-OBJECT BENCHMARK POLICY
- Preserve an explicit advertising, commercial, packshot, or product-photography purpose when the original request asks for one. A product description without that medium is incomplete intent fidelity.
- Shallow depth of field alone is not a camera or composition strategy. A score above 6/10 for composition_and_camera requires an explicit shot size, framing, viewpoint, angle, centering, symmetry, or three-quarter presentation.
- If the user supplied no brand name or label text, do not reward invented readable branding, logos, names, or lettering. Generic packaging structure is acceptable, but fabricated text should be listed as a weakness because diffusion models may render it as gibberish.
- Judge material behavior concretely: glass edges, liquid colour, reflections, refraction, cap finish, contact shadow, surface, and background should serve the advertising concept rather than merely decorate it.
"""


def install_intent_judge_policy(executor_class: Any) -> None:
    """Add benchmark-specific judge guidance without changing the public executor API."""

    if getattr(executor_class, "_cmv_policy_installed", False):
        return

    original = executor_class._render_judge_package

    def render_with_policy(
        cls: Any,
        *,
        family: str,
        user_request: str,
        candidate: Any,
        required_intents: tuple[str, ...] = (),
    ) -> str:
        package = original(
            family=family,
            user_request=user_request,
            candidate=candidate,
            required_intents=required_intents,
        )
        if "clean_minimal" not in required_intents:
            return package
        marker = "ORIGINAL HUMAN REQUEST\n"
        return package.replace(marker, _PRODUCT_POLICY + "\n" + marker, 1)

    executor_class._render_judge_package = classmethod(render_with_policy)
    executor_class._cmv_policy_installed = True
