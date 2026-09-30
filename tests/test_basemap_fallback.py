import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image
from tools.make_cards import load_basemaps


class BasemapFallbackTests(unittest.TestCase):
    def test_osm_fallback_and_styled_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp)
            maps = plan / "basemaps"
            maps.mkdir()
            metadata = {"lat_min": 35, "lat_max": 36, "lon_min": 139, "lon_max": 140}
            (maps / "main_meta.json").write_text(json.dumps(metadata), encoding="utf-8")
            Image.new("RGB", (12, 12), "red").save(maps / "main_osm.png")
            loaded = load_basemaps(plan)
            self.assertEqual(loaded["main"][0].getpixel((0, 0)), (255, 0, 0))
            self.assertEqual(loaded["main"][1], metadata)
            Image.new("RGB", (12, 12), "blue").save(maps / "main_styled.png")
            loaded = load_basemaps(plan)
            self.assertEqual(loaded["main"][0].getpixel((0, 0)), (0, 0, 255))

    def test_missing_image_and_legacy_map(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = Path(tmp)
            (plan / "basemaps").mkdir()
            (plan / "basemaps/empty_meta.json").write_text("{}", encoding="utf-8")
            self.assertEqual(load_basemaps(plan), {})
            Image.new("RGB", (8, 8), "white").save(plan / "basemap_styled.png")
            (plan / "basemap_meta.json").write_text("{}", encoding="utf-8")
            self.assertEqual(load_basemaps(plan)["main"][0].size, (8, 8))


if __name__ == "__main__":
    unittest.main()
