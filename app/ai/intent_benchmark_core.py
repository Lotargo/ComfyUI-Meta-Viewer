from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..config_store import ConfigStoreError
from ..paths import PathValidationError, build_runtime_paths, normalize_path
from .execution import (
    OpenCodeIntentJudgeExecutionError,
    OpenCodeIntentJudgeExecutionResult,
    OpenCodeIntentJudgeExecutor,
    OpenCodePromptExecutionError,
    OpenCodePromptExecutionResult,
    OpenCodePromptExecutor,
)
from .opencode_smoke import resolve_opencode_profile
from .profiles import AIProfileStore, AIProfileStoreError
from .prompting import (
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
)
from .secrets import SecretStoreError
from .smoke import SmokeRunnerError


IntentStatus = Literal["pass", "warn", "fail"]
_WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+(?:[-'][A-Za-zА-Яа-яЁё0-9]+)*")
_SENTENCE_RE = re.compile(r"[.!?](?:\s|$)")

_GENERIC_BUZZWORDS = (
    "masterpiece",
    "best quality",
    "8k",
    "uhd",
    "award-winning",
    "stunning",
    "perfect face",
    "ultra detailed",
)


@dataclass(frozen=True)
class IntentCoverageRule:
    metric_id: str
    label: str
    markers: tuple[str, ...]
    maximum: int


@dataclass(frozen=True)
class IntentBenchmark:
    benchmark_id: str
    title: str
    description: str
    task: PromptTask
    input_text: str
    core_groups: dict[str, tuple[str, ...]]
    coverage_rules: tuple[IntentCoverageRule, ...]
    expansion_groups: dict[str, tuple[str, ...]]
    required_intents: dict[str, tuple[str, ...]]


@dataclass(frozen=True)
class IntentHeuristicMetric:
    metric_id: str
    status: IntentStatus
    points: int
    maximum: int
    detail: str


@dataclass(frozen=True)
class IntentBenchmarkReport:
    benchmark: IntentBenchmark
    generator_profile: dict[str, Any]
    judge_profile: dict[str, Any]
    generation: OpenCodePromptExecutionResult
    judge: OpenCodeIntentJudgeExecutionResult
    heuristic_metrics: tuple[IntentHeuristicMetric, ...]

    @property
    def heuristic_score(self) -> int:
        return sum(metric.points for metric in self.heuristic_metrics)

    @property
    def heuristic_maximum(self) -> int:
        return sum(metric.maximum for metric in self.heuristic_metrics)

    @property
    def heuristic_percentage(self) -> int:
        if self.heuristic_maximum == 0:
            return 0
        return round(self.heuristic_score * 100 / self.heuristic_maximum)

    @property
    def judge_score(self) -> int:
        return self.judge.result.total

    @property
    def same_model_judge(self) -> bool:
        return (
            self.generator_profile.get("id") == self.judge_profile.get("id")
            and self.generator_profile.get("model") == self.judge_profile.get("model")
        )

    @property
    def score_weights(self) -> tuple[float, float]:
        return (0.60, 0.40) if self.same_model_judge else (0.50, 0.50)

    @property
    def combined_score(self) -> int:
        heuristic_weight, judge_weight = self.score_weights
        return round(
            self.heuristic_percentage * heuristic_weight
            + self.judge_score * judge_weight
        )

    @property
    def score_gap(self) -> int:
        return abs(self.heuristic_percentage - self.judge_score)

    @property
    def missing_required_intents(self) -> tuple[str, ...]:
        prompt = self.generation.result.positive_prompt
        return tuple(
            name
            for name, markers in self.benchmark.required_intents.items()
            if not _contains_any(prompt, markers)
        )

    def to_dict(self) -> dict[str, Any]:
        heuristic_weight, judge_weight = self.score_weights
        return {
            "schema_version": "3",
            "benchmark": {
                "id": self.benchmark.benchmark_id,
                "title": self.benchmark.title,
                "description": self.benchmark.description,
                "input_text": self.benchmark.input_text,
                "required_intents": list(self.benchmark.required_intents),
                "task": self.benchmark.task.model_dump(mode="json"),
            },
            "profiles": {
                "generator": _public_profile(self.generator_profile),
                "judge": _public_profile(self.judge_profile),
                "same_model_judge": self.same_model_judge,
            },
            "candidate": self.generation.result.model_dump(mode="json"),
            "scores": {
                "heuristic": self.heuristic_percentage,
                "judge": self.judge_score,
                "combined": self.combined_score,
                "gap": self.score_gap,
                "weights": {
                    "heuristic": heuristic_weight,
                    "judge": judge_weight,
                },
            },
            "missing_required_intents": list(self.missing_required_intents),
            "heuristic_metrics": [
                {
                    "id": metric.metric_id,
                    "status": metric.status,
                    "points": metric.points,
                    "maximum": metric.maximum,
                    "detail": metric.detail,
                }
                for metric in self.heuristic_metrics
            ],
            "judge": {
                **self.judge.result.model_dump(mode="json"),
                "computed_total": self.judge_score,
                "computed_verdict": self.judge.result.verdict,
            },
            "execution": {
                "generation": self.generation.metadata(),
                "judge": self.judge.metadata(),
            },
        }


_CAMERA_MARKERS = (
    "close-up",
    "close up",
    "medium shot",
    "medium portrait",
    "three-quarter",
    "eye-level",
    "eye level",
    "low angle",
    "high angle",
    "lens",
    "framing",
    "camera",
    "hero shot",
    "macro",
    "крупный план",
    "средний план",
    "ракурс",
    "объектив",
    "кадрирование",
)

_LIGHTING_MARKERS = (
    "window light",
    "side light",
    "key light",
    "fill light",
    "rim light",
    "diffused light",
    "soft light",
    "warm light",
    "backlight",
    "gradient light",
    "specular highlight",
    "shadow",
    "golden-hour",
    "golden hour",
    "оконный свет",
    "боковой свет",
    "мягкий свет",
    "контровой",
    "блик",
    "тень",
)

_DEPTH_COLOUR_MEDIUM_MARKERS = (
    "depth of field",
    "bokeh",
    "foreground",
    "background",
    "earth tones",
    "muted palette",
    "restrained palette",
    "colour palette",
    "color palette",
    "editorial photography",
    "product photography",
    "commercial photography",
    "photographic",
    "film grain",
    "negative space",
    "глубина резкости",
    "боке",
    "передний план",
    "фон",
    "палитра",
    "фотография",
    "негативное пространство",
)

_PORTRAIT_CORE = {
    "adult": (
        "adult",
        "grown woman",
        "woman in her twenties",
        "woman in her thirties",
        "взрослая",
        "взрослой",
    ),
    "female": ("woman", "female", "young woman", "девушка", "женщина"),
    "ceramic_artist": (
        "ceramic artist",
        "ceramist",
        "ceramicist",
        "potter",
        "pottery artist",
        "керамист",
        "гончар",
    ),
    "workshop": (
        "workshop",
        "pottery studio",
        "ceramic studio",
        "atelier",
        "мастерская",
        "студия керамики",
    ),
}

_PORTRAIT_ENVIRONMENT = (
    "pottery wheel",
    "kiln",
    "shelves",
    "ceramic tools",
    "pottery tools",
    "bowls",
    "vessels",
    "clay",
    "workbench",
    "studio shelves",
    "handmade ceramics",
    "гончарный круг",
    "печь",
    "полки",
    "инструменты",
    "глина",
    "верстак",
)

_PORTRAIT_MATERIALS = (
    "skin texture",
    "linen",
    "clay dust",
    "matte ceramic",
    "glazed ceramic",
    "wood grain",
    "fabric texture",
    "handmade surface",
    "material response",
    "текстура кожи",
    "лён",
    "глиняная пыль",
    "матовая керамика",
    "фактура ткани",
)

_PORTRAIT_DIRECTION = (
    "gaze",
    "looks",
    "looking",
    "off-camera",
    "off camera",
    "expression",
    "pose",
    "posture",
    "holds",
    "holding",
    "works",
    "working",
    "взгляд",
    "смотрит",
    "выражение",
    "поза",
    "держит",
    "работает",
)

_SINGLE_CHARACTER_CORE = {
    "adult": (
        "adult",
        "grown woman",
        "woman in her twenties",
        "woman in her thirties",
        "взрослая",
        "взрослой",
    ),
    "female": ("woman", "female", "young woman", "девушка", "женщина"),
    "ranger": (
        "ranger",
        "tracker",
        "scout",
        "pathfinder",
        "следопыт",
        "разведчица",
    ),
    "single_subject": (
        "single character",
        "one character",
        "solo",
        "alone",
        "solitary",
        "одна героиня",
        "один персонаж",
        "в одиночестве",
    ),
    "forest_trail": (
        "forest trail",
        "woodland trail",
        "forest path",
        "woodland path",
        "лесная тропа",
        "лесной тропе",
    ),
}

_SINGLE_CHARACTER_FRAMING = _CAMERA_MARKERS + (
    "full-body",
    "full body",
    "head-to-toe",
    "head to toe",
    "wide shot",
    "long shot",
    "three-quarter body",
    "entire silhouette",
    "полный рост",
    "в полный рост",
    "ростовой кадр",
)

_SINGLE_CHARACTER_COSTUME = (
    "layered clothing",
    "leather armor",
    "leather armour",
    "sturdy tunic",
    "weathered cloak",
    "wool cloak",
    "hooded cloak",
    "leather boots",
    "sturdy boots",
    "weathered boots",
    "utility belt",
    "belt pouches",
    "satchel",
    "backpack",
    "bracers",
    "gloves",
    "map case",
    "field gear",
    "practical clothing",
    "worn leather",
    "woven fabric",
    "многослойная одежда",
    "плащ",
    "кожаные сапоги",
    "прочные ботинки",
    "поясные сумки",
    "рюкзак",
    "полевое снаряжение",
)

_SINGLE_CHARACTER_ACTION = (
    "walking",
    "striding",
    "standing",
    "pausing",
    "scanning",
    "studying tracks",
    "reading tracks",
    "holding a map",
    "hand on",
    "weight shifted",
    "feet planted",
    "confident stance",
    "purposeful stance",
    "идёт",
    "шагает",
    "стоит",
    "изучает следы",
    "держит карту",
    "уверенная поза",
)

_SINGLE_CHARACTER_ENVIRONMENT = (
    "moss",
    "fern",
    "ferns",
    "roots",
    "fallen leaves",
    "mud",
    "mist",
    "fog",
    "tree trunks",
    "canopy",
    "footprints",
    "contact shadow",
    "ground contact",
    "dappled light",
    "мох",
    "папоротник",
    "корни",
    "опавшие листья",
    "грязь",
    "туман",
    "стволы деревьев",
    "следы",
    "контактная тень",
)

_PRACTICAL_INTENT = (
    "practical",
    "functional",
    "utilitarian",
    "weather-ready",
    "travel-worn",
    "field-ready",
    "sturdy",
    "purpose-built",
    "практич",
    "функциональ",
    "утилитар",
    "походн",
)

_CONFIDENT_INTENT = (
    "confident",
    "self-assured",
    "assured",
    "steady",
    "composed",
    "purposeful",
    "decisive",
    "уверен",
    "собран",
    "решительн",
)

_MYSTERIOUS_INTENT = (
    "mysterious",
    "enigmatic",
    "secretive",
    "elusive",
    "subtle mystery",
    "veiled",
    "shadowed",
    "misty",
    "fog-shrouded",
    "partly obscured",
    "таинствен",
    "загадочн",
)

_ARCHITECTURE_CORE = {
    "library": (
        "library",
        "reading library",
        "community library",
        "neighborhood library",
        "neighbourhood library",
        "библиотек",
    ),
    "interior": (
        "interior",
        "indoor space",
        "room",
        "designed space",
        "интерьер",
        "помещение",
        "пространство",
    ),
    "reading_area": (
        "reading area",
        "reading zone",
        "reading nook",
        "reading lounge",
        "reading space",
        "seating area",
        "зона чтения",
        "читальная зона",
        "место для чтения",
    ),
    "small_scale": (
        "small",
        "compact",
        "intimate scale",
        "modest scale",
        "neighborhood scale",
        "neighbourhood scale",
        "небольш",
        "компактн",
        "камерн",
    ),
}

_ARCHITECTURE_PERSPECTIVE = _CAMERA_MARKERS + (
    "wide-angle",
    "wide angle",
    "architectural lens",
    "one-point perspective",
    "two-point perspective",
    "perspective",
    "vanishing point",
    "straight verticals",
    "level verticals",
    "eye-height",
    "eye height",
    "corner view",
    "axial view",
    "точка схода",
    "перспектива",
    "вертикали",
)

_ARCHITECTURE_LIGHTING = _LIGHTING_MARKERS + (
    "daylight",
    "natural light",
    "skylight",
    "clerestory",
    "pendant light",
    "pendant lights",
    "task lighting",
    "reading light",
    "indirect lighting",
    "recessed lighting",
    "ambient lighting",
    "дневной свет",
    "естественный свет",
    "подвесные светильники",
    "локальное освещение",
)

_ARCHITECTURE_LAYOUT = (
    "reading area",
    "reading zone",
    "reading nook",
    "reading lounge",
    "bookshelves",
    "book shelves",
    "built-in shelves",
    "built-in shelving",
    "floor-to-ceiling shelves",
    "perimeter shelving",
    "central aisle",
    "clear aisle",
    "circulation path",
    "open circulation",
    "zoning",
    "alcove",
    "threshold",
    "зона чтения",
    "книжные полки",
    "встроенные стеллажи",
    "проход",
    "маршрут движения",
)

_ARCHITECTURE_MATERIALS = (
    "timber",
    "wood",
    "oak",
    "birch",
    "walnut",
    "plywood",
    "plaster",
    "concrete",
    "brick",
    "stone",
    "glass",
    "metal",
    "wool",
    "felt",
    "carpet",
    "upholstery",
    "acoustic panel",
    "матовое дерево",
    "дуб",
    "штукатурка",
    "бетон",
    "кирпич",
    "камень",
    "стекло",
    "текстиль",
)

_ARCHITECTURE_FUNCTION = (
    "human scale",
    "ergonomic",
    "accessible",
    "clear aisle",
    "unobstructed",
    "integrated storage",
    "book storage",
    "task lighting",
    "reading light",
    "comfortable seating",
    "lounge chair",
    "armchair",
    "reading chair",
    "reading table",
    "side table",
    "organized",
    "organised",
    "modular",
    "гуманн",
    "эргономич",
    "доступн",
    "свободный проход",
    "удобное кресло",
    "места хранения",
)

_ARCHITECTURE_DEPTH = (
    "foreground",
    "middle ground",
    "midground",
    "background",
    "layered depth",
    "spatial depth",
    "receding",
    "leading lines",
    "sightline",
    "vista",
    "ceiling height",
    "double height",
    "threshold",
    "depth of the room",
    "передний план",
    "средний план",
    "фон",
    "глубина пространства",
    "линии перспективы",
)

_CALM_INTENT = (
    "calm",
    "quiet",
    "serene",
    "tranquil",
    "restful",
    "peaceful",
    "subdued",
    "unhurried",
    "soft atmosphere",
    "soft wool",
    "soft rug",
    "soft upholstery",
    "diffused daylight",
    "diffused light",
    "gentle shadow",
    "gentle shadows",
    "uncluttered",
    "спокойн",
    "тих",
    "умиротвор",
)

_FUNCTIONAL_INTENT = (
    "functional",
    "practical",
    "efficient",
    "ergonomic",
    "well-organized",
    "well organised",
    "organized",
    "organised",
    "task area",
    "reading lamp",
    "floor lamp",
    "purposeful",
    "usable",
    "функциональ",
    "практич",
    "эргономич",
    "организован",
)

_LANDSCAPE_CORE = {
    "landscape": (
        "landscape",
        "environment",
        "scenic view",
        "natural vista",
        "establishing view",
        "environmental vista",
        "пейзаж",
        "природная сцена",
    ),
    "northern_valley": (
        "northern valley",
        "nordic valley",
        "boreal valley",
        "arctic valley",
        "subarctic valley",
        "tundra valley",
        "северная долина",
        "северной долины",
    ),
    "river": (
        "river",
        "river channel",
        "watercourse",
        "река",
        "рекой",
    ),
    "mountains": (
        "mountain",
        "mountains",
        "mountain range",
        "peaks",
        "гор",
        "вершины",
    ),
    "dawn": (
        "dawn",
        "sunrise",
        "daybreak",
        "first light",
        "early morning",
        "рассвет",
        "на рассвете",
        "раннее утро",
    ),
}

_LANDSCAPE_COMPOSITION = (
    "wide landscape",
    "wide view",
    "wide-angle",
    "wide angle",
    "panoramic",
    "panorama",
    "sweeping view",
    "elevated viewpoint",
    "low viewpoint",
    "horizon",
    "leading line",
    "leading lines",
    "foreground",
    "middle ground",
    "midground",
    "background",
    "rule of thirds",
    "широкий пейзаж",
    "панорам",
    "горизонт",
    "передний план",
    "средний план",
    "фон",
)

_LANDSCAPE_ATMOSPHERE = _LIGHTING_MARKERS + (
    "dawn light",
    "sunrise light",
    "first light",
    "low-angle light",
    "low angle light",
    "cool light",
    "blue hour",
    "mist",
    "fog",
    "haze",
    "atmospheric haze",
    "low cloud",
    "cloud cover",
    "overcast sky",
    "clear sky",
    "рассветный свет",
    "утренний свет",
    "туман",
    "дымка",
    "облака",
)

_LANDSCAPE_TERRAIN = (
    "valley floor",
    "mountain slope",
    "mountain slopes",
    "ridge",
    "ridges",
    "rocky",
    "rock outcrop",
    "boulder",
    "boulders",
    "tundra",
    "moss",
    "lichen",
    "heather",
    "grassland",
    "grasses",
    "conifer",
    "pine",
    "birch",
    "snow patch",
    "дно долины",
    "склоны",
    "хребет",
    "скалы",
    "валуны",
    "тундра",
    "мох",
    "лишайник",
)

_LANDSCAPE_WATER = (
    "winding river",
    "river winding",
    "winding through",
    "meandering river",
    "river bends",
    "river channel",
    "riverbank",
    "river bank",
    "banks",
    "current",
    "flowing water",
    "glacial water",
    "clear water",
    "reflective water",
    "reflective path",
    "reflection",
    "ripples",
    "surface shimmer",
    "water's edge",
    "water edge",
    "извилистая река",
    "русло",
    "берег",
    "течение",
    "отражение",
    "рябь",
)

_LANDSCAPE_SCALE = (
    "vast",
    "expansive",
    "immense",
    "monumental scale",
    "grand scale",
    "sense of scale",
    "distant",
    "far distance",
    "tiny trees",
    "small trees",
    "scattered trees",
    "tiny cabin",
    "small cabin",
    "scale reference",
    "towering",
    "простор",
    "масштаб",
    "вдали",
    "далёк",
)

_SPACIOUS_INTENT = (
    "spacious",
    "expansive",
    "vast",
    "open",
    "broad",
    "wide",
    "sweeping",
    "unbounded",
    "простор",
    "обширн",
    "широк",
    "открыт",
)

_COOL_INTENT = (
    "cool",
    "cold",
    "crisp",
    "chill",
    "icy",
    "blue-grey",
    "blue-gray",
    "blue tones",
    "cool palette",
    "cool light",
    "прохлад",
    "холодн",
    "синев",
)

_MAJESTIC_INTENT = (
    "majestic",
    "monumental",
    "grand",
    "awe-inspiring",
    "awe inspiring",
    "sublime",
    "towering",
    "imposing",
    "dramatic scale",
    "epic scale",
    "величествен",
    "монументаль",
    "грандиозн",
)

_ILLUSTRATION_CORE = {
    "storybook_illustration": (
        "storybook illustration",
        "children's book illustration",
        "childrens book illustration",
        "book illustration",
        "narrative illustration",
        "illustrated story",
        "книжная иллюстрация",
        "иллюстрация для книги",
        "сказочная иллюстрация",
    ),
    "teapot_house": (
        "teapot-shaped house",
        "teapot shaped house",
        "house shaped like a teapot",
        "teapot house",
        "teapot cottage",
        "kettle-shaped house",
        "kettle shaped house",
        "домик в форме чайника",
        "дом-чайник",
        "чайник-домик",
    ),
    "autumn": (
        "autumn",
        "autumnal",
        "fall foliage",
        "fall leaves",
        "осенн",
    ),
    "forest": (
        "forest",
        "woodland",
        "woods",
        "лес",
        "лесной",
    ),
}

_ILLUSTRATION_COMPOSITION = (
    "focal point",
    "focal hierarchy",
    "visual hierarchy",
    "centered composition",
    "off-center",
    "off center",
    "rule of thirds",
    "foreground",
    "middle ground",
    "midground",
    "background",
    "overlap",
    "eye path",
    "leading path",
    "framed by",
    "silhouette",
    "thumbnail",
    "точка фокуса",
    "визуальная иерархия",
    "передний план",
    "средний план",
    "фон",
    "силуэт",
)

_ILLUSTRATION_MEDIUM = (
    "gouache",
    "watercolor",
    "watercolour",
    "colored pencil",
    "coloured pencil",
    "ink line",
    "ink outline",
    "cut paper",
    "paper cut",
    "screen print",
    "linocut",
    "digital painting",
    "digital illustration",
    "matte paint",
    "opaque paint",
    "visible brush",
    "brushstroke",
    "paper texture",
    "pigment",
    "grainy texture",
    "гуашь",
    "акварель",
    "цветные карандаши",
    "бумажная текстура",
    "мазки",
)

_ILLUSTRATION_SHAPE_LANGUAGE = (
    "shape language",
    "rounded shape",
    "rounded forms",
    "soft shapes",
    "curved silhouette",
    "exaggerated",
    "stylized",
    "stylised",
    "simplified",
    "squat",
    "bulbous",
    "tapered",
    "asymmetrical",
    "whimsical architecture",
    "spout",
    "handle",
    "lid roof",
    "lid-shaped roof",
    "язык форм",
    "округлые формы",
    "стилизован",
    "носик чайника",
    "ручка чайника",
)

_ILLUSTRATION_PALETTE_LIGHT = (
    "warm palette",
    "autumn palette",
    "earthy palette",
    "limited palette",
    "amber",
    "ochre",
    "rust orange",
    "burnt orange",
    "golden yellow",
    "deep red",
    "teal shadow",
    "value contrast",
    "warm glow",
    "glowing window",
    "window glow",
    "dappled light",
    "soft light",
    "golden light",
    "long shadow",
    "тёплая палитра",
    "осенняя палитра",
    "охра",
    "янтарный",
    "светящиеся окна",
)

_ILLUSTRATION_STORY_DETAIL = (
    "winding path",
    "curving path",
    "stepping stones",
    "fallen leaves",
    "leaf-strewn",
    "leaf strewn",
    "leaf litter",
    "mushroom",
    "acorn",
    "fern",
    "moss",
    "lantern",
    "tiny window",
    "glowing window",
    "chimney smoke",
    "curling smoke",
    "wooden door",
    "doorstep",
    "entrance",
    "balcony",
    "garden",
    "footprints",
    "inviting entrance",
    "извилистая тропинка",
    "опавшие листья",
    "грибы",
    "мох",
    "фонарь",
    "дым из трубы",
)

_COZY_INTENT = (
    "cozy",
    "cosy",
    "warm",
    "intimate",
    "inviting",
    "welcoming",
    "snug",
    "comforting",
    "уют",
    "тёпл",
    "тепл",
    "камерн",
)

_WHIMSICAL_INTENT = (
    "whimsical",
    "playful",
    "quirky",
    "fanciful",
    "charming",
    "eccentric",
    "oddly shaped",
    "причудлив",
    "игрив",
    "фантазийн",
)

_MAGICAL_INTENT = (
    "magical",
    "enchanted",
    "fairy-tale",
    "fairytale",
    "storybook magic",
    "subtle magic",
    "glowing motes",
    "fireflies",
    "sparkles",
    "волшебн",
    "зачарован",
    "сказочн",
)

_PRODUCT_CORE = {
    "perfume_bottle": (
        "perfume bottle",
        "fragrance bottle",
        "perfume flacon",
        "fragrance flacon",
        "bottle of perfume",
        "флакон духов",
        "флакон парфюма",
        "духи",
        "парфюм",
    ),
    "commercial_product_image": (
        "product photograph",
        "product photography",
        "advertising photograph",
        "advertising image",
        "commercial photograph",
        "commercial campaign",
        "campaign image",
        "packshot",
        "рекламная фотография",
        "рекламный кадр",
        "предметная съёмка",
    ),
}

_PRODUCT_SET = (
    "seamless background",
    "gradient background",
    "studio background",
    "studio set",
    "backdrop",
    "pedestal",
    "plinth",
    "reflective surface",
    "acrylic surface",
    "stone slab",
    "glass platform",
    "soft fabric",
    "декорация",
    "подиум",
    "фон",
    "градиент",
    "отражающая поверхность",
)

_PRODUCT_MATERIALS = (
    "glass",
    "transparent glass",
    "translucent glass",
    "liquid",
    "metal cap",
    "gold cap",
    "silver cap",
    "reflection",
    "refraction",
    "specular highlight",
    "glass edge",
    "embossed label",
    "etched label",
    "стекло",
    "жидкость",
    "металлическая крышка",
    "отражение",
    "преломление",
    "блик",
    "этикетка",
)

_PRODUCT_PRESENTATION = (
    "centered",
    "upright",
    "hero product",
    "hero shot",
    "label visible",
    "front-facing",
    "front facing",
    "three-quarter view",
    "symmetrical",
    "negative space",
    "grounded shadow",
    "base contact",
    "по центру",
    "вертикально",
    "этикетка видна",
    "симметрич",
    "негативное пространство",
)

_PREMIUM_REFINED_INTENT = (
    "refined",
    "editorial",
    "elegant",
    "polished",
    "sophisticated",
    "premium",
    "luxury",
    "luxurious",
    "high-end",
    "art-directed",
    "restrained",
    "дорог",
    "премиаль",
    "элегант",
    "изыскан",
    "редакцион",
)

_WARM_INTENT = (
    "warm",
    "amber",
    "golden",
    "honey",
    "soft warmth",
    "warm beige",
    "тёпл",
    "тепл",
    "янтар",
    "золотист",
    "медов",
)


def _rule(
    metric_id: str,
    label: str,
    markers: tuple[str, ...],
    maximum: int,
) -> IntentCoverageRule:
    return IntentCoverageRule(metric_id, label, markers, maximum)


BENCHMARKS: dict[str, IntentBenchmark] = {
    "flux-portrait-intent-basic": IntentBenchmark(
        benchmark_id="flux-portrait-intent-basic",
        title="Short human portrait intent",
        description=(
            "Measures whether the model can turn a short Russian user request into a coherent, "
            "visually specific FLUX portrait prompt without a ready-made production brief."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PORTRAIT,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-intent-benchmark-v3-portrait",
        ),
        input_text=(
            "Сделай атмосферный портрет взрослой девушки-керамиста в её мастерской. "
            "Хочется, чтобы кадр выглядел естественно, дорого и немного уютно."
        ),
        core_groups=_PORTRAIT_CORE,
        coverage_rules=(
            _rule("invented_camera_language", "Camera or framing language", _CAMERA_MARKERS, 8),
            _rule("invented_lighting", "Motivated lighting", _LIGHTING_MARKERS, 8),
            _rule("invented_environment_detail", "Workshop detail", _PORTRAIT_ENVIRONMENT, 8),
            _rule("tactile_materials", "Tactile material language", _PORTRAIT_MATERIALS, 8),
            _rule("subject_direction", "Subject pose, gaze, or action", _PORTRAIT_DIRECTION, 6),
        ),
        expansion_groups={
            "camera": _CAMERA_MARKERS,
            "lighting": _LIGHTING_MARKERS,
            "environment": _PORTRAIT_ENVIRONMENT,
            "materials": _PORTRAIT_MATERIALS,
            "subject_direction": _PORTRAIT_DIRECTION,
            "depth_colour_medium": _DEPTH_COLOUR_MEDIUM_MARKERS,
        },
        required_intents={
            "natural": (
                "natural",
                "authentic",
                "unposed",
                "candid",
                "relaxed",
                "realistic",
                "естествен",
                "аутентич",
                "непостановоч",
            ),
            "premium_refined": _PREMIUM_REFINED_INTENT,
            "cozy": (
                "cozy",
                "warm",
                "intimate",
                "inviting",
                "softly lit",
                "уют",
                "тёпл",
                "тепл",
                "камерн",
            ),
        },
    ),
    "flux-single-character-intent-basic": IntentBenchmark(
        benchmark_id="flux-single-character-intent-basic",
        title="Short human single-character intent",
        description=(
            "Measures whether the model can turn a short Russian character request into "
            "a coherent, visually specific FLUX full-body character prompt."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.SINGLE_CHARACTER,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-intent-benchmark-v3-single-character",
        ),
        input_text=(
            "Нарисуй одного персонажа — взрослую девушку-следопыта в полный рост "
            "на лесной тропе. Образ должен быть практичным, уверенным и немного загадочным."
        ),
        core_groups=_SINGLE_CHARACTER_CORE,
        coverage_rules=(
            _rule(
                "character_framing",
                "Full-body framing or camera language",
                _SINGLE_CHARACTER_FRAMING,
                8,
            ),
            _rule("invented_lighting", "Motivated lighting", _LIGHTING_MARKERS, 8),
            _rule(
                "coherent_costume",
                "Functional clothing, equipment, or material detail",
                _SINGLE_CHARACTER_COSTUME,
                8,
            ),
            _rule(
                "character_action",
                "Character stance, action, or gesture",
                _SINGLE_CHARACTER_ACTION,
                8,
            ),
            _rule(
                "environment_relationship",
                "Physical relationship to the forest environment",
                _SINGLE_CHARACTER_ENVIRONMENT,
                6,
            ),
        ),
        expansion_groups={
            "framing": _SINGLE_CHARACTER_FRAMING,
            "lighting": _LIGHTING_MARKERS,
            "costume_equipment": _SINGLE_CHARACTER_COSTUME,
            "pose_action": _SINGLE_CHARACTER_ACTION,
            "environment_relationship": _SINGLE_CHARACTER_ENVIRONMENT,
            "depth_colour_medium": _DEPTH_COLOUR_MEDIUM_MARKERS,
        },
        required_intents={
            "practical": _PRACTICAL_INTENT,
            "confident": _CONFIDENT_INTENT,
            "mysterious": _MYSTERIOUS_INTENT,
        },
    ),
    "flux-architecture-interior-intent-basic": IntentBenchmark(
        benchmark_id="flux-architecture-interior-intent-basic",
        title="Short human library interior intent",
        description=(
            "Measures whether the model can turn a short Russian interior request into "
            "a coherent, visually specific FLUX architectural prompt."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.ARCHITECTURE_INTERIOR,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-intent-benchmark-v3-architecture-interior",
        ),
        input_text=(
            "Создай светлый интерьер небольшой современной библиотеки с зоной чтения. "
            "Пространство должно выглядеть спокойным, тёплым и функциональным."
        ),
        core_groups=_ARCHITECTURE_CORE,
        coverage_rules=(
            _rule(
                "architectural_perspective",
                "Camera position or coherent perspective",
                _ARCHITECTURE_PERSPECTIVE,
                8,
            ),
            _rule(
                "architectural_lighting",
                "Natural or artificial lighting strategy",
                _ARCHITECTURE_LIGHTING,
                8,
            ),
            _rule(
                "spatial_layout",
                "Zoning, shelving, or circulation",
                _ARCHITECTURE_LAYOUT,
                8,
            ),
            _rule(
                "surface_materials",
                "Surface-specific architectural materials",
                _ARCHITECTURE_MATERIALS,
                8,
            ),
            _rule(
                "human_scale_function",
                "Human scale, furnishing, or functional clearance",
                _ARCHITECTURE_FUNCTION,
                6,
            ),
        ),
        expansion_groups={
            "perspective": _ARCHITECTURE_PERSPECTIVE,
            "lighting": _ARCHITECTURE_LIGHTING,
            "layout_circulation": _ARCHITECTURE_LAYOUT,
            "materials": _ARCHITECTURE_MATERIALS,
            "scale_function": _ARCHITECTURE_FUNCTION,
            "depth_medium": _ARCHITECTURE_DEPTH + _DEPTH_COLOUR_MEDIUM_MARKERS,
        },
        required_intents={
            "calm": _CALM_INTENT,
            "warm": _WARM_INTENT,
            "functional": _FUNCTIONAL_INTENT,
        },
    ),
    "flux-landscape-environment-intent-basic": IntentBenchmark(
        benchmark_id="flux-landscape-environment-intent-basic",
        title="Short human northern landscape intent",
        description=(
            "Measures whether the model can turn a short Russian landscape request into "
            "a coherent, visually specific FLUX environment prompt."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.LANDSCAPE_ENVIRONMENT,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-intent-benchmark-v3-landscape-environment",
        ),
        input_text=(
            "Создай широкий пейзаж северной долины с рекой и далёкими горами на рассвете. "
            "Атмосфера должна быть просторной, прохладной и немного величественной."
        ),
        core_groups=_LANDSCAPE_CORE,
        coverage_rules=(
            _rule(
                "landscape_composition",
                "Viewpoint, horizon, or foreground-to-background composition",
                _LANDSCAPE_COMPOSITION,
                8,
            ),
            _rule(
                "weather_lighting",
                "Dawn lighting, sky, or atmospheric weather",
                _LANDSCAPE_ATMOSPHERE,
                8,
            ),
            _rule(
                "terrain_ecology",
                "Terrain, geology, or climate-consistent vegetation",
                _LANDSCAPE_TERRAIN,
                8,
            ),
            _rule(
                "water_geography",
                "River course, banks, flow, or reflections",
                _LANDSCAPE_WATER,
                8,
            ),
            _rule(
                "environmental_scale",
                "Distance progression or environmental scale reference",
                _LANDSCAPE_SCALE,
                6,
            ),
        ),
        expansion_groups={
            "composition": _LANDSCAPE_COMPOSITION,
            "weather_lighting": _LANDSCAPE_ATMOSPHERE,
            "terrain_ecology": _LANDSCAPE_TERRAIN,
            "water": _LANDSCAPE_WATER,
            "scale": _LANDSCAPE_SCALE,
            "depth_colour_medium": _DEPTH_COLOUR_MEDIUM_MARKERS,
        },
        required_intents={
            "spacious": _SPACIOUS_INTENT,
            "cool": _COOL_INTENT,
            "majestic": _MAJESTIC_INTENT,
        },
    ),
    "flux-illustration-art-intent-basic": IntentBenchmark(
        benchmark_id="flux-illustration-art-intent-basic",
        title="Short human storybook illustration intent",
        description=(
            "Measures whether the model can turn a short Russian storybook request into "
            "a coherent, visually specific FLUX illustration prompt."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.ILLUSTRATION_ART,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-intent-benchmark-v3-illustration-art",
        ),
        input_text=(
            "Нарисуй сказочную книжную иллюстрацию маленького домика в форме чайника "
            "в осеннем лесу. Настроение должно быть уютным, причудливым и немного волшебным."
        ),
        core_groups=_ILLUSTRATION_CORE,
        coverage_rules=(
            _rule(
                "illustration_composition",
                "Focal hierarchy, silhouette, or layered composition",
                _ILLUSTRATION_COMPOSITION,
                8,
            ),
            _rule(
                "coherent_medium",
                "Coherent illustration medium or mark-making",
                _ILLUSTRATION_MEDIUM,
                8,
            ),
            _rule(
                "shape_language",
                "Stylised shape language or teapot construction",
                _ILLUSTRATION_SHAPE_LANGUAGE,
                8,
            ),
            _rule(
                "palette_and_light",
                "Palette, value, or motivated illustration lighting",
                _ILLUSTRATION_PALETTE_LIGHT,
                8,
            ),
            _rule(
                "narrative_environment",
                "Story-supporting forest or habitation detail",
                _ILLUSTRATION_STORY_DETAIL,
                6,
            ),
        ),
        expansion_groups={
            "composition": _ILLUSTRATION_COMPOSITION,
            "medium_marks": _ILLUSTRATION_MEDIUM,
            "shape_language": _ILLUSTRATION_SHAPE_LANGUAGE,
            "palette_light": _ILLUSTRATION_PALETTE_LIGHT,
            "story_detail": _ILLUSTRATION_STORY_DETAIL,
            "depth_colour_medium": _DEPTH_COLOUR_MEDIUM_MARKERS,
        },
        required_intents={
            "cozy": _COZY_INTENT,
            "whimsical": _WHIMSICAL_INTENT,
            "magical": _MAGICAL_INTENT,
        },
    ),
    "flux-product-intent-basic": IntentBenchmark(
        benchmark_id="flux-product-intent-basic",
        title="Short human perfume advertising intent",
        description=(
            "Measures whether the model can turn a short Russian product request into a "
            "specific FLUX advertising prompt with coherent art direction."
        ),
        task=PromptTask(
            family=PromptFamily.FLUX,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.PRODUCT_OBJECT,
            modifiers=(PromptModifier.SAFE,),
            checkpoint_profile="flux-intent-benchmark-v3-product",
        ),
        input_text=(
            "Сделай красивую рекламную фотографию флакона духов. "
            "Нужен дорогой, чистый и немного тёплый образ."
        ),
        core_groups=_PRODUCT_CORE,
        coverage_rules=(
            _rule("invented_camera_language", "Camera or framing language", _CAMERA_MARKERS, 8),
            _rule("invented_lighting", "Motivated lighting", _LIGHTING_MARKERS, 8),
            _rule("invented_product_set", "Product set or background", _PRODUCT_SET, 8),
            _rule("product_materials", "Glass, liquid, or reflective material language", _PRODUCT_MATERIALS, 8),
            _rule("product_presentation", "Product placement and readability", _PRODUCT_PRESENTATION, 6),
        ),
        expansion_groups={
            "camera": _CAMERA_MARKERS,
            "lighting": _LIGHTING_MARKERS,
            "set_background": _PRODUCT_SET,
            "materials_reflections": _PRODUCT_MATERIALS,
            "product_presentation": _PRODUCT_PRESENTATION,
            "depth_colour_medium": _DEPTH_COLOUR_MEDIUM_MARKERS,
        },
        required_intents={
            "premium_refined": _PREMIUM_REFINED_INTENT,
            "clean_minimal": (
                "clean",
                "minimal",
                "minimalist",
                "uncluttered",
                "seamless",
                "crisp",
                "pure",
                "negative space",
                "simple composition",
                "чист",
                "минимал",
                "лаконич",
                "без лишних деталей",
            ),
            "warm": _WARM_INTENT,
        },
    ),
}


def _public_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": profile.get("id"),
        "name": profile.get("name"),
        "kind": profile.get("kind"),
        "cli_type": profile.get("cli_type"),
        "model": profile.get("model"),
    }


def _contains_any(text: str, markers: tuple[str, ...]) -> list[str]:
    lowered = text.casefold()
    return [marker for marker in markers if marker.casefold() in lowered]


def _coverage_metric(rule: IntentCoverageRule, prompt: str) -> IntentHeuristicMetric:
    found = _contains_any(prompt, rule.markers)
    if found:
        return IntentHeuristicMetric(
            rule.metric_id,
            "pass",
            rule.maximum,
            rule.maximum,
            f"{rule.label}: " + ", ".join(found[:4]),
        )
    return IntentHeuristicMetric(
        rule.metric_id,
        "fail",
        0,
        rule.maximum,
        f"No concrete {rule.label.lower()} was found.",
    )


def _core_intent_metric(benchmark: IntentBenchmark, prompt: str) -> IntentHeuristicMetric:
    covered = [
        name
        for name, markers in benchmark.core_groups.items()
        if _contains_any(prompt, markers)
    ]
    total = len(benchmark.core_groups)
    points = round(16 * len(covered) / max(1, total))
    status: IntentStatus = (
        "pass"
        if len(covered) == total
        else "warn"
        if len(covered) >= max(1, total - 1)
        else "fail"
    )
    return IntentHeuristicMetric(
        "core_intent",
        status,
        points,
        16,
        f"Preserved {len(covered)}/{total} core groups: "
        + (", ".join(covered) or "none"),
    )


def _requested_intent_metric(
    benchmark: IntentBenchmark,
    prompt: str,
) -> IntentHeuristicMetric:
    covered = [
        name
        for name, markers in benchmark.required_intents.items()
        if _contains_any(prompt, markers)
    ]
    missing = [name for name in benchmark.required_intents if name not in covered]
    maximum = 24
    points = round(maximum * len(covered) / max(1, len(benchmark.required_intents)))
    status: IntentStatus = "pass" if not missing else "warn" if covered else "fail"
    return IntentHeuristicMetric(
        "requested_intent_coverage",
        status,
        points,
        maximum,
        "Covered: "
        + (", ".join(covered) or "none")
        + "; Missing: "
        + (", ".join(missing) or "none"),
    )


def _expansion_metric(
    benchmark: IntentBenchmark,
    prompt: str,
) -> IntentHeuristicMetric:
    output_words = _WORD_RE.findall(prompt)
    covered = [
        name
        for name, markers in benchmark.expansion_groups.items()
        if _contains_any(prompt, markers)
    ]
    total = len(benchmark.expansion_groups)
    count = len(covered)
    pass_groups = max(1, total - 1)
    warn_groups = max(2, total // 2)
    if len(output_words) >= 60 and count >= pass_groups:
        return IntentHeuristicMetric(
            "non_trivial_expansion",
            "pass",
            12,
            12,
            f"{len(output_words)} words; {count}/{total} independent visual decision groups: "
            + ", ".join(covered),
        )
    if len(output_words) >= 35 and count >= warn_groups:
        return IntentHeuristicMetric(
            "non_trivial_expansion",
            "warn",
            7,
            12,
            f"{len(output_words)} words; {count}/{total} visual decision groups: "
            + ", ".join(covered),
        )
    return IntentHeuristicMetric(
        "non_trivial_expansion",
        "fail",
        0,
        12,
        f"{len(output_words)} words; only {count}/{total} visual decision groups. "
        "The result is likely a paraphrase or shallow expansion.",
    )


def evaluate_intent_heuristics(
    benchmark: IntentBenchmark,
    result: PromptResult,
) -> tuple[IntentHeuristicMetric, ...]:
    prompt = result.positive_prompt.strip()
    metrics: list[IntentHeuristicMetric] = [_core_intent_metric(benchmark, prompt)]
    metrics.extend(_coverage_metric(rule, prompt) for rule in benchmark.coverage_rules)
    metrics.append(_requested_intent_metric(benchmark, prompt))
    metrics.append(_expansion_metric(benchmark, prompt))

    output_words = _WORD_RE.findall(prompt)
    sentence_count = len(_SENTENCE_RE.findall(prompt))
    if sentence_count >= 3:
        metrics.append(
            IntentHeuristicMetric(
                "coherent_structure",
                "pass",
                4,
                4,
                f"{sentence_count} developed sentences found.",
            )
        )
    elif sentence_count == 2:
        metrics.append(
            IntentHeuristicMetric(
                "coherent_structure",
                "warn",
                3,
                4,
                "Two coherent sentences found.",
            )
        )
    else:
        metrics.append(
            IntentHeuristicMetric(
                "coherent_structure",
                "warn" if len(output_words) >= 50 else "fail",
                2 if len(output_words) >= 50 else 0,
                4,
                "The result is compressed into one sentence or fragment.",
            )
        )

    if benchmark.task.family == PromptFamily.FLUX:
        negative_ok = result.negative_prompt == ""
        negative_detail = (
            "FLUX negative_prompt is correctly empty."
            if negative_ok
            else "FLUX benchmark expects an empty negative_prompt."
        )
    else:
        negative_ok = True
        negative_detail = "No family-specific negative prompt policy is enforced."
    metrics.append(
        IntentHeuristicMetric(
            "family_negative_policy",
            "pass" if negative_ok else "fail",
            3 if negative_ok else 0,
            3,
            negative_detail,
        )
    )

    buzzwords = [item for item in _GENERIC_BUZZWORDS if item in prompt.casefold()]
    metrics.append(
        IntentHeuristicMetric(
            "anti_buzzword",
            "pass" if not buzzwords else "fail",
            3 if not buzzwords else 0,
            3,
            "No generic quality slogans found."
            if not buzzwords
            else "Generic slogans found: " + ", ".join(buzzwords),
        )
    )
    return tuple(metrics)


def intent_status(
    report: IntentBenchmarkReport,
    minimum_score: int,
) -> IntentStatus:
    hard_failures = {
        metric.metric_id
        for metric in report.heuristic_metrics
        if metric.status == "fail"
        and metric.metric_id in {"core_intent", "family_negative_policy"}
    }
    if hard_failures:
        return "fail"
    if report.combined_score >= minimum_score:
        if report.missing_required_intents or report.score_gap > 25:
            return "warn"
        return "pass"
    if report.combined_score >= max(0, minimum_score - 15):
        return "warn"
    return "fail"


def run_intent_benchmark(
    *,
    benchmark: IntentBenchmark,
    generator_profile: dict[str, Any],
    judge_profile: dict[str, Any],
    generator: OpenCodePromptExecutor | None = None,
    judge: OpenCodeIntentJudgeExecutor | None = None,
) -> IntentBenchmarkReport:
    generation = (generator or OpenCodePromptExecutor()).execute(
        profile=generator_profile,
        task=benchmark.task,
        user_input=benchmark.input_text,
    )
    judge_execution = (judge or OpenCodeIntentJudgeExecutor()).execute(
        profile=judge_profile,
        family=benchmark.task.family.value,
        user_request=benchmark.input_text,
        candidate=generation.result,
        required_intents=tuple(benchmark.required_intents),
    )
    return IntentBenchmarkReport(
        benchmark=benchmark,
        generator_profile=generator_profile,
        judge_profile=judge_profile,
        generation=generation,
        judge=judge_execution,
        heuristic_metrics=evaluate_intent_heuristics(benchmark, generation.result),
    )


def _status_style(status: IntentStatus) -> str:
    return {"pass": "bold green", "warn": "bold yellow", "fail": "bold red"}[status]


def _print_benchmarks(console: Console) -> None:
    table = Table(title="Prompt intent benchmarks")
    table.add_column("ID", style="bold cyan")
    table.add_column("Family")
    table.add_column("Scenario")
    table.add_column("Input language")
    table.add_column("Required intents")
    table.add_column("Purpose")
    for benchmark in BENCHMARKS.values():
        table.add_row(
            benchmark.benchmark_id,
            benchmark.task.family.value,
            benchmark.task.scenario.value,
            "Russian",
            ", ".join(benchmark.required_intents),
            benchmark.description,
        )
    console.print(table)


def _print_report(
    console: Console,
    report: IntentBenchmarkReport,
    *,
    minimum_score: int,
    show_bundle: bool,
) -> None:
    console.print(
        Panel(
            Text(report.benchmark.input_text),
            title="Raw human request",
            border_style="blue",
        )
    )

    candidate = Table(title="Generated PromptResult", show_header=False)
    candidate.add_column("Field", style="bold cyan", no_wrap=True)
    candidate.add_column("Value", overflow="fold")
    candidate.add_row("positive_prompt", report.generation.result.positive_prompt)
    candidate.add_row(
        "negative_prompt", report.generation.result.negative_prompt or "<empty>"
    )
    console.print(candidate)

    heuristic = Table(title="Deterministic intent checks")
    heuristic.add_column("Status")
    heuristic.add_column("Metric")
    heuristic.add_column("Points")
    heuristic.add_column("Detail")
    for metric in report.heuristic_metrics:
        heuristic.add_row(
            Text(metric.status.upper(), style=_status_style(metric.status)),
            metric.metric_id,
            f"{metric.points}/{metric.maximum}",
            metric.detail,
        )
    console.print(heuristic)

    scores = report.judge.result.scores
    judge_table = Table(title="Model judge rubric")
    judge_table.add_column("Criterion")
    judge_table.add_column("Points")
    for name, maximum in (
        ("intent_fidelity", 20),
        ("useful_visual_expansion", 20),
        ("atmosphere_translation", 15),
        ("composition_and_camera", 10),
        ("lighting", 10),
        ("environment_and_materials", 10),
        ("coherence_and_model_fit", 10),
        ("restraint_and_consistency", 5),
    ):
        judge_table.add_row(name, f"{getattr(scores, name)}/{maximum}")
    console.print(judge_table)

    if report.judge.result.strengths:
        console.print(
            Panel(
                "\n".join(f"• {item}" for item in report.judge.result.strengths),
                title="Judge strengths",
                border_style="green",
            )
        )
    if report.judge.result.weaknesses:
        console.print(
            Panel(
                "\n".join(f"• {item}" for item in report.judge.result.weaknesses),
                title="Judge weaknesses",
                border_style="yellow",
            )
        )
    console.print(
        Panel(
            report.judge.result.rationale,
            title="Judge rationale",
            border_style="magenta",
        )
    )

    status = intent_status(report, minimum_score)
    heuristic_weight, judge_weight = report.score_weights
    summary = Table(show_header=False, box=None)
    summary.add_column(style="bold cyan")
    summary.add_column()
    summary.add_row("Heuristic score", f"{report.heuristic_percentage}/100")
    summary.add_row("Judge score", f"{report.judge_score}/100")
    summary.add_row("Combined score", f"{report.combined_score}/100")
    summary.add_row(
        "Score weights",
        f"heuristic {heuristic_weight:.0%} · judge {judge_weight:.0%}",
    )
    summary.add_row("Score gap", f"{report.score_gap} points")
    summary.add_row(
        "Missing required intents",
        ", ".join(report.missing_required_intents) or "none",
    )
    summary.add_row("Minimum", f"{minimum_score}/100")
    summary.add_row("Same-model judge", "yes" if report.same_model_judge else "no")
    summary.add_row("Generation latency", f"{report.generation.latency_ms} ms")
    summary.add_row("Judge latency", f"{report.judge.latency_ms} ms")
    summary.add_row("Result", status.upper())
    console.print(
        Panel(
            summary,
            title="Intent benchmark summary",
            border_style={"pass": "green", "warn": "yellow", "fail": "red"}[
                status
            ],
        )
    )

    if show_bundle:
        console.print(
            Panel(
                Text(report.generation.bundle.render()),
                title="Generator InstructionBundle",
                border_style="magenta",
            )
        )


def _write_json(path_value: str, report: IntentBenchmarkReport) -> Path:
    path = normalize_path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.ai.intent_benchmark",
        description=(
            "Evaluate prompt intent expansion through generation plus an isolated model judge."
        ),
    )
    parser.add_argument("--no-color", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List intent benchmarks.")

    run = subparsers.add_parser("run", help="Run one intent benchmark through OpenCode.")
    run.add_argument("benchmark", choices=tuple(BENCHMARKS))
    run.add_argument("--profile", help="Generator OpenCode profile ID or exact name.")
    run.add_argument(
        "--judge-profile",
        help="Judge OpenCode profile ID or exact name. Defaults to the generator profile.",
    )
    run.add_argument("--config", help="Override the application config.json path.")
    run.add_argument("--minimum-score", type=int, default=80)
    run.add_argument("--timeout", type=int)
    run.add_argument("--show-bundle", action="store_true")
    run.add_argument("--json-out")
    run.add_argument("--debug", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    console = Console(no_color=args.no_color)
    if args.command == "list":
        _print_benchmarks(console)
        return 0

    try:
        if not 0 <= args.minimum_score <= 100:
            raise SmokeRunnerError(
                "Minimum score must be between 0 and 100.",
                code="invalid_minimum_score",
            )
        config_path = (
            normalize_path(args.config) if args.config else build_runtime_paths().config
        )
        store = AIProfileStore(config_path)
        generator_resolved = resolve_opencode_profile(
            store,
            selector=args.profile,
            requires_image=False,
        )
        judge_resolved = (
            resolve_opencode_profile(
                store,
                selector=args.judge_profile,
                requires_image=False,
            )
            if args.judge_profile
            else generator_resolved
        )
        generator_profile = dict(generator_resolved.profile)
        judge_profile = dict(judge_resolved.profile)
        if args.timeout is not None:
            if not 5 <= args.timeout <= 600:
                raise SmokeRunnerError(
                    "Timeout must be between 5 and 600 seconds.",
                    code="invalid_timeout",
                )
            generator_profile["timeout_seconds"] = args.timeout
            judge_profile["timeout_seconds"] = args.timeout

        benchmark = BENCHMARKS[args.benchmark]
        header = Table(show_header=False, box=None)
        header.add_column(style="bold cyan")
        header.add_column()
        header.add_row("Benchmark", f"{benchmark.benchmark_id} · {benchmark.title}")
        header.add_row("Scenario", benchmark.task.scenario.value)
        header.add_row(
            "Generator", f"{generator_profile['name']} · {generator_profile['model']}"
        )
        header.add_row("Judge", f"{judge_profile['name']} · {judge_profile['model']}")
        header.add_row(
            "Judge mode",
            "same model"
            if generator_profile["id"] == judge_profile["id"]
            else "separate profile",
        )
        header.add_row("Required intents", ", ".join(benchmark.required_intents))
        header.add_row("Minimum score", f"{args.minimum_score}/100")
        console.print(Panel(header, title="Prompt intent benchmark", border_style="cyan"))

        with console.status("Generating prompt from raw intent…", spinner="dots"):
            generation = OpenCodePromptExecutor().execute(
                profile=generator_profile,
                task=benchmark.task,
                user_input=benchmark.input_text,
            )
        with console.status("Evaluating candidate with model judge…", spinner="dots"):
            judge_execution = OpenCodeIntentJudgeExecutor().execute(
                profile=judge_profile,
                family=benchmark.task.family.value,
                user_request=benchmark.input_text,
                candidate=generation.result,
                required_intents=tuple(benchmark.required_intents),
            )
        report = IntentBenchmarkReport(
            benchmark=benchmark,
            generator_profile=generator_profile,
            judge_profile=judge_profile,
            generation=generation,
            judge=judge_execution,
            heuristic_metrics=evaluate_intent_heuristics(benchmark, generation.result),
        )
        _print_report(
            console,
            report,
            minimum_score=args.minimum_score,
            show_bundle=args.show_bundle,
        )
        if args.json_out:
            console.print(f"JSON report: {_write_json(args.json_out, report)}")
        return 0 if intent_status(report, args.minimum_score) == "pass" else 3
    except (OpenCodePromptExecutionError, OpenCodeIntentJudgeExecutionError) as exc:
        detail = f"stage={exc.stage} · code={exc.code}\n{exc}"
        if args.debug and exc.technical_error:
            detail += f"\n\nTechnical detail:\n{exc.technical_error}"
        console.print(
            Panel(
                Text(detail),
                title="Intent benchmark execution failed",
                border_style="red",
            )
        )
        return 1
    except (
        SmokeRunnerError,
        AIProfileStoreError,
        ConfigStoreError,
        SecretStoreError,
        PathValidationError,
        OSError,
        ValueError,
    ) as exc:
        code = getattr(exc, "code", "configuration_error")
        console.print(
            Panel(
                Text(f"code={code}\n{exc}"),
                title="Intent benchmark configuration error",
                border_style="red",
            )
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
