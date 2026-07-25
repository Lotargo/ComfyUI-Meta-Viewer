from __future__ import annotations

from typing import Any


# Keep the order aligned with comfy.samplers.KSampler in the bundled ComfyUI.
CORE_SAMPLER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("euler", "Euler"),
    ("euler_cfg_pp", "Euler CFG++"),
    ("euler_ancestral", "Euler ancestral"),
    ("euler_ancestral_cfg_pp", "Euler ancestral CFG++"),
    ("heun", "Heun"),
    ("heunpp2", "Heun++ 2"),
    ("exp_heun_2_x0", "Exponential Heun 2 X0"),
    ("exp_heun_2_x0_sde", "Exponential Heun 2 X0 SDE"),
    ("dpm_2", "DPM 2"),
    ("dpm_2_ancestral", "DPM 2 ancestral"),
    ("lms", "LMS"),
    ("dpm_fast", "DPM fast"),
    ("dpm_adaptive", "DPM adaptive"),
    ("dpmpp_2s_ancestral", "DPM++ 2S ancestral"),
    ("dpmpp_2s_ancestral_cfg_pp", "DPM++ 2S ancestral CFG++"),
    ("dpmpp_sde", "DPM++ SDE"),
    ("dpmpp_sde_gpu", "DPM++ SDE GPU"),
    ("dpmpp_2m", "DPM++ 2M"),
    ("dpmpp_2m_cfg_pp", "DPM++ 2M CFG++"),
    ("dpmpp_2m_sde", "DPM++ 2M SDE"),
    ("dpmpp_2m_sde_gpu", "DPM++ 2M SDE GPU"),
    ("dpmpp_2m_sde_heun", "DPM++ 2M SDE Heun"),
    ("dpmpp_2m_sde_heun_gpu", "DPM++ 2M SDE Heun GPU"),
    ("dpmpp_3m_sde", "DPM++ 3M SDE"),
    ("dpmpp_3m_sde_gpu", "DPM++ 3M SDE GPU"),
    ("ddpm", "DDPM"),
    ("lcm", "LCM"),
    ("ipndm", "iPNDM"),
    ("ipndm_v", "iPNDM V"),
    ("deis", "DEIS"),
    ("res_multistep", "RES multistep"),
    ("res_multistep_cfg_pp", "RES multistep CFG++"),
    ("res_multistep_ancestral", "RES multistep ancestral"),
    ("res_multistep_ancestral_cfg_pp", "RES multistep ancestral CFG++"),
    ("gradient_estimation", "Gradient estimation"),
    ("gradient_estimation_cfg_pp", "Gradient estimation CFG++"),
    ("er_sde", "ER SDE"),
    ("seeds_2", "SEEDS 2"),
    ("seeds_3", "SEEDS 3"),
    ("sa_solver", "SA-Solver"),
    ("sa_solver_pece", "SA-Solver PECE"),
    ("ddim", "DDIM"),
    ("uni_pc", "UniPC"),
    ("uni_pc_bh2", "UniPC BH2"),
)

CORE_SCHEDULER_OPTIONS: tuple[tuple[str, str], ...] = (
    ("simple", "Simple"),
    ("sgm_uniform", "SGM uniform"),
    ("karras", "Karras"),
    ("exponential", "Exponential"),
    ("ddim_uniform", "DDIM uniform"),
    ("beta", "Beta"),
    ("normal", "Normal"),
    ("linear_quadratic", "Linear quadratic"),
    ("kl_optimal", "KL optimal"),
)


def apply_builtin_sampling_options(payload: dict[str, Any]) -> dict[str, Any]:
    """Replace abbreviated built-in manifest choices with the complete ComfyUI catalog."""
    fields = payload.get("fields")
    if not isinstance(fields, list):
        return payload

    catalogs = {
        "sampler": CORE_SAMPLER_OPTIONS,
        "scheduler": CORE_SCHEDULER_OPTIONS,
    }
    for field in fields:
        if not isinstance(field, dict):
            continue
        catalog = catalogs.get(field.get("id"))
        if catalog is None or field.get("kind") != "select":
            continue
        field["options"] = [
            {"value": value, "label": label}
            for value, label in catalog
        ]
    return payload


__all__ = [
    "CORE_SAMPLER_OPTIONS",
    "CORE_SCHEDULER_OPTIONS",
    "apply_builtin_sampling_options",
]
