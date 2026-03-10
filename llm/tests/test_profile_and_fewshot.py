import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LLM_DIR = ROOT / "llm"
if str(LLM_DIR) not in sys.path:
    sys.path.insert(0, str(LLM_DIR))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import llm_offline_extract as loe  # noqa: E402
import window_to_text as wtt  # noqa: E402


class ProfileAndFewshotTests(unittest.TestCase):
    def test_profile_resolution_hi7_and_mc1(self):
        hi7_features = [x.strip() for x in (ROOT / "pyloader/features_erg/hi7_all.txt").read_text().splitlines() if x.strip()]
        _, hi7_meta = wtt.resolve_rule_profile_payload(
            "auto",
            str(ROOT / "llm/rules/profiles"),
            "auto",
            "Hitachi HDS722020ALA330",
            hi7_features,
        )
        self.assertEqual("hdd", hi7_meta["rule_medium"])
        self.assertEqual("hitachi", hi7_meta["rule_vendor"])
        self.assertEqual("hitachi_hds722020ala330", hi7_meta["rule_model_key"])
        self.assertNotIn("workload", hi7_meta["recommended_fewshot_required_causes"])

        mc1_features = [x.strip() for x in (ROOT / "pyloader/features_erg/mc1_all.txt").read_text().splitlines() if x.strip()]
        _, mc1_meta = wtt.resolve_rule_profile_payload(
            "auto",
            str(ROOT / "llm/rules/profiles"),
            "auto",
            "MC1",
            mc1_features,
        )
        self.assertEqual("ssd", mc1_meta["rule_medium"])
        self.assertEqual("alibaba", mc1_meta["rule_vendor"])
        self.assertEqual("mc1", mc1_meta["rule_model_key"])
        self.assertIn("workload", mc1_meta["recommended_fewshot_required_causes"])

    def test_build_reference_examples_quality(self):
        records = []
        causes = ["media", "interface", "temperature", "power", "unknown"]
        for i, cause in enumerate(causes):
            records.append(
                {
                    "disk_id": f"d{i%2}",
                    "window_end_time": f"2014-08-{10+i:02d}",
                    "summary_text": f"summary-{cause}",
                    "n_rows": 30,
                    "target": {
                        "root_cause": cause,
                        "confidence": 0.9,
                        "risk_hint": 0.8,
                        "events": [{"feature": "SMART_5", "type": "monotonic_increase", "severity": 0.9}],
                    },
                }
            )
        refs, quality = wtt.build_reference_examples(
            records,
            per_cause=1,
            strategy="stratified",
            min_per_cause=1,
            min_non_unknown=2,
        )
        self.assertGreaterEqual(len(refs), 2)
        self.assertGreaterEqual(quality["coverage_by_cause"]["media"], 1)
        self.assertGreaterEqual(quality["coverage_by_cause"]["unknown"], 1)
        self.assertGreaterEqual(quality["non_unknown_ratio"], 0.5)

    def test_choose_references_gate_and_required_source(self):
        unknown_only = [
            {"target": {"root_cause": "unknown"}},
            {"target": {"root_cause": "unknown"}},
        ]
        required = loe.parse_required_causes("media,unknown")
        refs_auto, _, missing_auto = loe.choose_references(unknown_only, "auto", required, 1)
        self.assertEqual([], refs_auto)
        self.assertIn("media", missing_auto)

        refs_force, _, _ = loe.choose_references(unknown_only, "force", required, 1)
        self.assertEqual(2, len(refs_force))

        refs_off, _, _ = loe.choose_references(unknown_only, "off", required, 1)
        self.assertEqual([], refs_off)

        raw, source = loe.resolve_required_causes_arg(
            "media,interface,temperature,power,workload,unknown",
            "hi7",
            {},
            explicit_cli=False,
        )
        self.assertEqual("dataset:hi7", source)
        self.assertEqual(["media", "interface", "temperature", "power", "unknown"], loe.parse_required_causes(raw))

        raw2, source2 = loe.resolve_required_causes_arg(
            "media,interface,temperature,power,workload,unknown",
            "auto",
            {"recommended_fewshot_required_causes": ["media", "unknown"]},
            explicit_cli=False,
        )
        self.assertEqual("reference", source2)
        self.assertEqual(["media", "unknown"], loe.parse_required_causes(raw2))


if __name__ == "__main__":
    unittest.main()
