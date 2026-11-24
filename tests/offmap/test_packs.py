# CHANGE 2026-11-24 OFFMAP-TOOL-01: new test (no previous version). Validates the Romania pack config.
import json, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "offmap"))
import build_packs as bp
CFG = os.path.join(os.path.dirname(__file__), "..", "..", "tools", "offmap", "packs_romania.json")
class T(unittest.TestCase):
    def test_valid(self): bp.load(CFG)
    def test_unordered_rejected(self):
        c = json.load(open(CFG)); c["packs"][2]["firstDay"] = 0
        with self.assertRaises(AssertionError): bp.validate(c)
    def test_base_required_first(self):
        c = json.load(open(CFG)); c["packs"][0]["required"] = False
        with self.assertRaises(AssertionError): bp.validate(c)
    def test_bad_bbox(self):
        c = json.load(open(CFG)); c["packs"][1]["bbox"] = "26.3,44.3,25.9,44.6"
        with self.assertRaises(AssertionError): bp.validate(c)
if __name__ == "__main__": unittest.main()
