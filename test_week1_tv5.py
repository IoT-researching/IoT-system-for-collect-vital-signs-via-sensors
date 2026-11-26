
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from signal_processing.ppg_algorithm import process_ppg  # noqa: E402


class Week1PpgTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = json.loads((ROOT / "data" / "sample_input.json").read_text(encoding="utf-8"))
        cls.expected = {
            item["case"]: item
            for item in json.loads((ROOT / "data" / "sample_output.json").read_text(encoding="utf-8"))
        }

    def test_fixture_shape_and_channel_lengths(self):
        self.assertEqual(len(self.cases), 5)
        for case in self.cases:
            with self.subTest(case=case["case"]):
                self.assertEqual(case["fs"], 100)
                self.assertEqual(len(case["red"]), 400)
                self.assertEqual(len(case["ir"]), 400)
                self.assertTrue(all(math.isfinite(v) for v in case["red"] + case["ir"]))

    def test_clean_target_rates_are_within_two_bpm(self):
        for target in (60, 75, 90):
            case = next(c for c in self.cases if c["case"] == f"Clean {target} bpm")
            result = process_ppg(case["red"], case["ir"], case["fs"])
            with self.subTest(target=target):
                self.assertTrue(result["is_valid"])
                self.assertEqual(result["error_code"], 0)
                self.assertAlmostEqual(result["hr"], target, delta=2.0)

    def test_no_finger_is_invalid_with_error_code_one(self):
        case = next(c for c in self.cases if c["case"] == "No Finger")
        result = process_ppg(case["red"], case["ir"], case["fs"])
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["error_code"], 1)
        self.assertEqual(result["spo2"], 0.0)

    def test_noisy_reference_case_is_processed(self):
        case = next(c for c in self.cases if c["case"] == "Noisy 75 bpm")
        result = process_ppg(case["red"], case["ir"], case["fs"])
        expected = self.expected[case["case"]]
        self.assertEqual(result["is_valid"], expected["is_valid"])
        self.assertEqual(result["error_code"], expected["error_code"])
        if result["is_valid"]:
            self.assertAlmostEqual(result["hr"], 75.0, delta=3.0)

    def test_zero_channels_are_invalid(self):
        zeros = [0] * 400
        result = process_ppg(zeros, zeros)
        self.assertFalse(result["is_valid"])
        self.assertEqual(result["error_code"], 1)

    def test_missing_or_mismatched_samples_are_rejected_without_crash(self):
        self.assertFalse(process_ppg([], [])["is_valid"])
        self.assertFalse(process_ppg([90000] * 400, [100000] * 399)["is_valid"])
        self.assertFalse(process_ppg([90000] * 20, [100000] * 20)["is_valid"])

    def test_non_finite_samples_and_invalid_sample_rate_are_rejected(self):
        red = [95000.0] * 400
        ir = [100000.0] * 400
        red[10] = float("nan")
        self.assertFalse(process_ppg(red, ir)["is_valid"])
        self.assertFalse(process_ppg([95000] * 400, [100000] * 400, fs=0)["is_valid"])
        self.assertFalse(process_ppg([95000] * 400, [100000] * 400, fs=4)["is_valid"])

    def test_wokwi_firmware_json_fixtures(self):
        firmware_dir = ROOT.parents[1] / "tv2-wokwi-esp32" / "firmware" / "wokwi_esp32"
        fixtures = sorted(firmware_dir.glob("ppg_tv2_*.json"))
        self.assertEqual(len(fixtures), 5, f"Expected five Wokwi JSON fixtures in {firmware_dir}")
        for path in fixtures:
            case = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(fixture=path.name):
                self.assertEqual(case["fs"], 100)
                self.assertEqual(len(case["red"]), len(case["ir"]))
                self.assertEqual(len(case["red"]), 400)
                result = process_ppg(case["red"], case["ir"], case["fs"])
                if "no_finger" in path.name:
                    self.assertFalse(result["is_valid"])
                    self.assertEqual(result["error_code"], 1)
                elif "clean_" in path.name:
                    target = int(path.name.split("clean_")[1].split("bpm")[0])
                    self.assertTrue(result["is_valid"])
                    self.assertAlmostEqual(result["hr"], target, delta=2.0)
                elif "noisy_" in path.name:
                    self.assertTrue(result["is_valid"])
                    self.assertAlmostEqual(result["hr"], 75.0, delta=3.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
