import json
from pathlib import Path
import tempfile
import unittest
from urllib.parse import parse_qs, urlparse

from tools.nav import add_pdf_links, nav_target, offset_latlon, stop_target


class NavTargetTests(unittest.TestCase):
    def test_default_is_subject_position(self):
        t = nav_target({"subject_latlon": [35.62645, 139.77502]})
        q = parse_qs(urlparse(t["url"]).query)
        self.assertEqual(q["travelmode"], ["walking"])
        self.assertEqual(q["destination"], ["35.626450,139.775020"])
        self.assertEqual(t["label"], "人物站位")

    def test_camera_target_offsets_along_bearing(self):
        lat, lon = offset_latlon(35.0, 139.0, 90, 100)
        self.assertAlmostEqual(lat, 35.0, places=6)
        self.assertGreater(lon, 139.0)
        t = nav_target({"subject_latlon": [35.0, 139.0], "cam_bearing": 0, "cam_dist": 111.2, "walk_to": {"to": "camera"}})
        self.assertAlmostEqual(t["latlon"][0], 35.001, places=3)

    def test_place_id_and_indoor_label(self):
        t = nav_target({"subject_latlon": [35.69, 139.70], "walk_to": {"place_id": "ChIJtest", "label": "店铺 4F"}})
        self.assertIn("destination_place_id=ChIJtest", t["url"])
        self.assertEqual(t["label"], "店铺 4F")
        self.assertEqual(nav_target({"subject_latlon": [35.69, 139.70], "indoor": True})["label"], "室内站位（导航到所在建筑）")

    def test_missing_coordinates_and_stop_fallback(self):
        self.assertIsNone(nav_target({"title": "无坐标"}))
        shots = {"01": {"title": "无坐标"}, "02": {"subject_latlon": [35.1, 139.1]}}
        self.assertEqual(stop_target({"shots": ["01", "02"]}, shots)["latlon"], [35.1, 139.1])

    def test_pdf_links_skip_without_links_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(add_pdf_links(Path(tmp) / "x.pdf", [], Path(tmp) / "links.json"), 0)


if __name__ == "__main__":
    unittest.main()
