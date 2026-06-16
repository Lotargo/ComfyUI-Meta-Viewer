from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageOps

from . import database as db


def get_cutout_path(cutout_dir: str | Path, image_id: int) -> Path:
    return Path(cutout_dir) / f"{image_id}.png"


def load_source_image(image_id: int) -> Image.Image | None:
    original = db.get_image_original_data(image_id)
    if original:
        return Image.open(BytesIO(original))

    image_path = db.get_image_path(image_id)
    if not image_path:
        return None

    path = Path(image_path)
    if not path.is_file():
        return None

    return Image.open(path)


def image_has_useful_alpha(img: Image.Image) -> bool:
    if img.mode not in ("RGBA", "LA"):
        return False
    alpha = img.getchannel("A")
    extrema = alpha.getextrema()
    return extrema[0] < 255


def estimate_background_color(rgb: Image.Image) -> tuple[int, int, int]:
    w, h = rgb.size
    step = max(1, min(w, h) // 80)
    samples: list[tuple[int, int, int]] = []

    for x in range(0, w, step):
        samples.append(rgb.getpixel((x, 0)))
        samples.append(rgb.getpixel((x, h - 1)))
    for y in range(0, h, step):
        samples.append(rgb.getpixel((0, y)))
        samples.append(rgb.getpixel((w - 1, y)))

    if not samples:
        return (255, 255, 255)

    channels = []
    for channel in range(3):
        values = sorted(pixel[channel] for pixel in samples)
        channels.append(values[len(values) // 2])
    return (channels[0], channels[1], channels[2])


def make_foreground_mask(img: Image.Image) -> Image.Image:
    rgb = img.convert("RGB")
    background = Image.new("RGB", rgb.size, estimate_background_color(rgb))
    diff = ImageChops.difference(rgb, background)
    mask = ImageOps.grayscale(diff)

    threshold = 28
    mask = mask.point(lambda p: 255 if p > threshold else 0, mode="L")
    mask = mask.filter(ImageFilter.MaxFilter(5))
    mask = mask.filter(ImageFilter.MinFilter(3))
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    return mask


def make_cutout_png(image_id: int, cutout_dir: str | Path) -> tuple[Path, bool]:
    cutout_path = get_cutout_path(cutout_dir, image_id)
    if cutout_path.exists():
        return cutout_path, True

    source = load_source_image(image_id)
    if source is None:
        raise FileNotFoundError("Image source not found")

    source.load()
    rgba = source.convert("RGBA")
    if image_has_useful_alpha(rgba):
        result = rgba
    else:
        alpha = make_foreground_mask(rgba)
        result = rgba.copy()
        result.putalpha(alpha)

    cutout_path.parent.mkdir(parents=True, exist_ok=True)
    result.save(cutout_path, format="PNG")
    return cutout_path, False


def clear_cutout(cutout_dir: str | Path, image_id: int) -> bool:
    cutout_path = get_cutout_path(cutout_dir, image_id)
    if not cutout_path.exists():
        return False
    cutout_path.unlink()
    return True
