from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

from app import database
from app.config_store import ConfigStore

from .detector import detect_comfyui


class ModelRecommendationError(RuntimeError):
    """Raised when a local model cannot be safely prepared for lookup."""


class CivitaiModelRecommendationService:
    """Find and cache sampling defaults from Civitai image metadata.

    The Civitai endpoint accepts SHA-256, so no third-party hash dependency is
    needed.  File hashes are cached by path, size and mtime to avoid repeatedly
    reading multi-gigabyte checkpoints.
    """

    API_URL = "https://civitai.com/api/v1/model-versions/by-hash/{hash_value}"
    TIMEOUT_SECONDS = 18

    def __init__(self, store: ConfigStore):
        self.store = store

    def recommend(self, *, folder: str, name: str) -> dict[str, Any]:
        path = self._resolve_model_path(folder, name)
        sha256 = self._file_hash(path)
        cached = self._cached_recommendation(sha256)
        if cached is not None:
            return {**cached, "cached": True}

        try:
            payload = self._fetch(sha256)
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                payload = self._manual_result(
                    "Civitai не нашёл эту модель по хешу. Настройте параметры вручную.",
                )
            else:
                raise ModelRecommendationError(
                    f"Civitai returned HTTP {exc.code}. Try again later."
                ) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ModelRecommendationError(
                "Не удалось обратиться к Civitai. Проверьте интернет-соединение и повторите попытку."
            ) from exc

        if payload.get("matched"):
            result = self._recommendation_from_civitai(payload)
        else:
            result = payload
        self._save_recommendation(sha256, result)
        return {**result, "cached": False}

    def _resolve_model_path(self, folder: str, name: str) -> Path:
        config = self.store.comfyui_settings()
        detection = detect_comfyui(
            str(config.get("install_path") or ""),
            custom_python=config.get("custom_python"),
        )
        if not detection.is_valid or detection.comfy_dir is None:
            raise ModelRecommendationError("ComfyUI installation path is not configured.")
        if not folder or not name:
            raise ModelRecommendationError("Select a local model first.")

        # The values originate in the local ComfyUI inventory, but validate them
        # again because this endpoint is callable directly.
        relative = PurePosixPath(name.replace("\\", "/"))
        if relative.is_absolute() or ".." in relative.parts or "/" in folder or "\\" in folder:
            raise ModelRecommendationError("Invalid model location.")
        model_root = (Path(detection.comfy_dir) / "models").resolve()
        path = (model_root / folder / Path(*relative.parts)).resolve()
        try:
            path.relative_to(model_root)
        except ValueError as exc:
            raise ModelRecommendationError("Invalid model location.") from exc
        if not path.is_file():
            raise ModelRecommendationError("The selected model file is no longer available.")
        return path

    def _file_hash(self, path: Path) -> str:
        stat = path.stat()
        conn = database.get_conn()
        try:
            row = conn.execute(
                """SELECT sha256 FROM model_file_hashes
                WHERE file_path=? AND file_size=? AND file_mtime=?""",
                (str(path), int(stat.st_size), float(stat.st_mtime)),
            ).fetchone()
        finally:
            conn.close()
        if row is not None:
            return str(row["sha256"])

        digest = hashlib.sha256()
        with path.open("rb") as file:
            for block in iter(lambda: file.read(4 * 1024 * 1024), b""):
                digest.update(block)
        sha256 = digest.hexdigest()
        conn = database.get_conn()
        try:
            conn.execute(
                """INSERT INTO model_file_hashes (file_path, file_size, file_mtime, sha256)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_size=excluded.file_size,
                    file_mtime=excluded.file_mtime,
                    sha256=excluded.sha256,
                    updated_at=datetime('now')""",
                (str(path), int(stat.st_size), float(stat.st_mtime), sha256),
            )
            conn.commit()
        finally:
            conn.close()
        return sha256

    def _cached_recommendation(self, sha256: str) -> dict[str, Any] | None:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT result_json FROM model_recommendations WHERE sha256=?", (sha256,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        try:
            result = json.loads(str(row["result_json"]))
        except (TypeError, json.JSONDecodeError):
            return None
        return result if isinstance(result, dict) else None

    def _save_recommendation(self, sha256: str, result: dict[str, Any]) -> None:
        conn = database.get_conn()
        try:
            conn.execute(
                """INSERT INTO model_recommendations (sha256, result_json)
                VALUES (?, ?)
                ON CONFLICT(sha256) DO UPDATE SET
                    result_json=excluded.result_json,
                    updated_at=datetime('now')""",
                (sha256, json.dumps(result, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

    def _fetch(self, sha256: str) -> dict[str, Any]:
        url = self.API_URL.format(hash_value=urllib.parse.quote(sha256, safe=""))
        request = urllib.request.Request(url, headers={"User-Agent": "ComfyUI-Meta-Viewer/1.0"})
        with urllib.request.urlopen(request, timeout=self.TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ModelRecommendationError("Civitai returned an invalid model response.")
        data["matched"] = True
        return data

    @classmethod
    def _recommendation_from_civitai(cls, payload: dict[str, Any]) -> dict[str, Any]:
        images = payload.get("images") if isinstance(payload.get("images"), list) else []
        samples = [item.get("meta") for item in images if isinstance(item, dict) and isinstance(item.get("meta"), dict)]
        values: dict[str, list[Any]] = {"steps": [], "cfg": [], "clip_skip": [], "sampler": [], "scheduler": []}
        for meta in samples:
            assert isinstance(meta, dict)
            normalized = {re.sub(r"[^a-z0-9]", "", str(key).casefold()): value for key, value in meta.items()}
            cls._append_number(values["steps"], cls._meta_value(normalized, "steps"), integer=True)
            cls._append_number(values["cfg"], cls._meta_value(normalized, "cfgscale", "cfg"))
            cls._append_number(values["clip_skip"], cls._meta_value(normalized, "clipskip"), integer=True)
            sampler, scheduler = cls._normalize_sampler(cls._meta_value(normalized, "sampler"))
            explicit_scheduler = cls._normalize_scheduler(cls._meta_value(normalized, "scheduletype", "scheduler"))
            if sampler:
                values["sampler"].append(sampler)
            if explicit_scheduler or scheduler:
                values["scheduler"].append(explicit_scheduler or scheduler)

        recommended = {
            key: cls._mode(value)
            for key, value in values.items()
            if cls._mode(value) is not None
        }
        model = payload.get("model") if isinstance(payload.get("model"), dict) else {}
        return {
            "matched": True,
            "source": "civitai",
            "model_name": str(model.get("name") or payload.get("name") or "Civitai model"),
            "model_version": str(payload.get("name") or ""),
            "model_url": f"https://civitai.com/models/{payload.get('modelId')}" if payload.get("modelId") else None,
            "sample_count": len(samples),
            "recommended_values": recommended,
            "message": (
                "Рекомендации собраны по параметрам примеров Civitai."
                if recommended else "Civitai нашёл модель, но у её примеров нет параметров генерации."
            ),
        }

    @staticmethod
    def _manual_result(message: str) -> dict[str, Any]:
        return {
            "matched": False,
            "source": "manual",
            "sample_count": 0,
            "recommended_values": {},
            "message": message,
        }

    @staticmethod
    def _meta_value(meta: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if key in meta:
                return meta[key]
        return None

    @staticmethod
    def _append_number(target: list[Any], value: Any, *, integer: bool = False) -> None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        if not math.isfinite(number):
            return
        target.append(int(round(number)) if integer else round(number, 3))

    @staticmethod
    def _mode(values: list[Any]) -> Any | None:
        if not values:
            return None
        counts = Counter(values)
        return max(counts, key=lambda value: (counts[value], values.index(value)))

    @staticmethod
    def _normalize_sampler(raw: Any) -> tuple[str | None, str | None]:
        value = re.sub(r"[^a-z0-9+]+", "", str(raw or "").casefold())
        scheduler = "karras" if "karras" in value else None
        aliases = (
            ("dpm++2msde", "dpmpp_2m_sde"), ("dpmpp2msde", "dpmpp_2m_sde"),
            ("dpm++2m", "dpmpp_2m"), ("dpmpp2m", "dpmpp_2m"),
            ("eulera", "euler_ancestral"), ("eulerancestral", "euler_ancestral"),
            ("euler", "euler"),
        )
        for alias, canonical in aliases:
            if alias in value:
                return canonical, scheduler
        return None, scheduler

    @staticmethod
    def _normalize_scheduler(raw: Any) -> str | None:
        value = str(raw or "").casefold().replace(" ", "_")
        return value if value in {"normal", "karras", "exponential", "sgm_uniform"} else None


__all__ = ["CivitaiModelRecommendationService", "ModelRecommendationError"]
