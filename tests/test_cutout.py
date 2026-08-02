import unittest
from PIL import Image
from app.cutout import image_has_useful_alpha


class ImageHasUsefulAlphaTests(unittest.TestCase):
    def test_unsupported_modes_return_false(self) -> None:
        # RGB has no alpha channel
        img_rgb = Image.new("RGB", (2, 2), color=(255, 0, 0))
        self.assertFalse(image_has_useful_alpha(img_rgb))

        # L is single-channel grayscale (no alpha)
        img_l = Image.new("L", (2, 2), color=128)
        self.assertFalse(image_has_useful_alpha(img_l))

        # CMYK has four channels but no alpha channel
        img_cmyk = Image.new("CMYK", (2, 2), color=(0, 255, 255, 0))
        self.assertFalse(image_has_useful_alpha(img_cmyk))

    def test_rgba_opaque_returns_false(self) -> None:
        # Every pixel has alpha = 255 (completely opaque)
        img = Image.new("RGBA", (2, 2), color=(255, 0, 0, 255))
        self.assertFalse(image_has_useful_alpha(img))

    def test_rgba_fully_transparent_returns_true(self) -> None:
        # Every pixel has alpha = 0 (completely transparent)
        img = Image.new("RGBA", (2, 2), color=(255, 0, 0, 0))
        self.assertTrue(image_has_useful_alpha(img))

    def test_rgba_partially_transparent_returns_true(self) -> None:
        # Create an RGBA image where only one pixel is transparent/semi-transparent
        img = Image.new("RGBA", (2, 2), color=(255, 0, 0, 255))
        # Modify one pixel's alpha to 128
        img.putpixel((0, 0), (255, 0, 0, 128))
        self.assertTrue(image_has_useful_alpha(img))

    def test_la_opaque_returns_false(self) -> None:
        # LA mode: L (Luminance) and A (Alpha)
        # Every pixel has alpha = 255
        img = Image.new("LA", (2, 2), color=(128, 255))
        self.assertFalse(image_has_useful_alpha(img))

    def test_la_transparent_returns_true(self) -> None:
        # LA mode where at least one pixel is semi-transparent
        img = Image.new("LA", (2, 2), color=(128, 255))
        img.putpixel((1, 1), (128, 0))
        self.assertTrue(image_has_useful_alpha(img))


if __name__ == "__main__":
    unittest.main()
