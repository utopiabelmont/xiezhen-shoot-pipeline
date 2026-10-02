import unittest

import tools.checklist as checklist
import tools.make_cards as make_cards


VIDEO = {"id": "02", "medium": "video", "lens": "1× 主摄 24mm", "shutter": "录像 4K 60 fps · 运动模式",
         "camera": "胸口高度", "kind": "全身",
         "clip": {"mode": "sq60", "move": "侧跟", "dur_s": 3, "start": "a", "end": "b", "nd": "—", "exposure": "锁 AE/AF"}}
STILL = {"id": "01", "medium": "still", "lens": "0.5× 超广角 13mm", "shutter": "自动 · 曝光 0", "camera": "低机位",
         "kind": "环境远景", "flash": "关",
         "look": "iPhone 原相机，摄影风格「标准」全天固定，HEIF 最大 48MP；不加滤镜"}
BURST = {"id": "03", "medium": "burst", "lens": "1× 主摄 24mm", "shutter": "连拍 · 自动", "camera": "胸口高度",
         "kind": "全身", "burst": {"fps": 10, "precap_s": 0, "action": "走过来"}}


class PhoneWordingTests(unittest.TestCase):
    def tearDown(self):
        make_cards.PHONE = False
        checklist.PHONE[0] = False

    def test_is_phone(self):
        self.assertTrue(make_cards.is_phone("iPhone 16 Pro Max"))
        self.assertFalse(make_cards.is_phone("Sony α7 V（a7M5）"))
        self.assertFalse(make_cards.is_phone(None))

    def test_phone_settings_rows(self):
        make_cards.PHONE = True
        video = dict(make_cards.settings_rows(VIDEO, "video"))
        self.assertIn("录像 4K 60 fps", video["模式"])
        self.assertIn("运动模式", video["模式"])
        self.assertNotIn("曝光 ND", video)
        still = dict(make_cards.settings_rows(STILL, "still"))
        self.assertEqual(still["摄影风格"], "标准（全组固定） · HEIF 最大 48MP")
        burst = dict(make_cards.settings_rows(BURST, "burst"))
        self.assertIn("快门键向左滑住", burst["连拍"])

    def test_camera_rows_unchanged(self):
        make_cards.PHONE = False
        video = dict(make_cards.settings_rows(VIDEO, "video"))
        self.assertIn("S&Q 60→24p", video["模式快门"])
        self.assertIn("曝光 ND", video)

    def test_checklist_gear_items(self):
        shots = [STILL, VIDEO, BURST]
        meta = {"forecast": "阴，16 时阵雨"}
        checklist.PHONE[0] = True
        items = [k for k, _ in checklist.gear_items({"body": "iPhone 16 Pro Max", "gear": "iPhone 16 Pro Max"}, shots, meta)]
        self.assertTrue(any(k.startswith("短片：录像 4K 24 fps") for k in items))
        self.assertFalse(any("ND" in k or "电池" in k for k in items))
        checklist.PHONE[0] = False
        items = [k for k, _ in checklist.gear_items({"body": "Sony α7 V", "gear": "24-105mm F4"}, shots, meta)]
        self.assertTrue(any(k.startswith("可变 ND") for k in items))
        detail = dict(checklist.shot_detail(VIDEO))
        self.assertEqual(detail["曝光"], "锁 AE/AF")


if __name__ == "__main__":
    unittest.main()
