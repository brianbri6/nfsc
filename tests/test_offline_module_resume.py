"""Fast checkpoint regression tests; no copyrighted Carbon inputs required."""
import importlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
module = importlib.import_module("prepare_modules")


class ResumableDllLiftTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "d3dx9_30.dll"
        self.source.write_bytes(b"dummy dll bytes for checkpoints")
        (self.root / "src/recomp").mkdir(parents=True)
        self.calls = []
        self.fail_catalog = False
        self.fingerprint = "test-fingerprint-a"
        self.config = patch.multiple(module,
                                     ROOT=self.root,
                                     MODULES={"d3dx9_30.dll": (self.source, 0x00D00000, "d3dx_")})
        self.config.start()
        self.addCleanup(self.config.stop)
        self.fingerprint_patch = patch.object(module, "_checkpoint_id",
                                              side_effect=lambda *_: self.fingerprint)
        self.fingerprint_patch.start()
        self.addCleanup(self.fingerprint_patch.stop)
        self.run_patch = patch.object(module, "run", side_effect=self.fake_run)
        self.run_patch.start()
        self.addCleanup(self.run_patch.stop)
        self.probe_patch = patch.object(module, "probe_seeds", side_effect=self.fake_probe)
        self.probe_patch.start()
        self.addCleanup(self.probe_patch.stop)
        self.classify_patch = patch.object(module, "not_code", side_effect=self.fake_classify)
        self.classify_patch.start()
        self.addCleanup(self.classify_patch.stop)

    def fake_run(self, script, *args):
        if script == "prepare_module.py":
            self.calls.append("relocated")
            Path(args[2]).write_bytes(b"relocated bytes")
            Path(args[3]).write_text("[]", encoding="utf-8")
        elif script == "run_lift.py" and args[0] == "catalog":
            self.calls.append("catalogued")
            if self.fail_catalog:
                raise RuntimeError("injected catalog failure")
            Path(args[3]).write_text('{"functions": [{"address": 13631488}]}',
                                     encoding="utf-8")
        elif script == "run_lift.py" and args[0] == "lift":
            self.calls.append("lifted")
            out = Path(args[3])
            out.mkdir(parents=True, exist_ok=True)
            (out / "d3dx_recomp_0000.c").write_text("void example(void) {}\n",
                                                     encoding="utf-8")
            (out / "d3dx_recomp_dispatch.c").write_text("/* dispatch */\n",
                                                         encoding="utf-8")
            (out / "d3dx_lift_stats.json").write_text(
                '{"functions": 1, "files": 1, "lift_failures": 0}\n', encoding="utf-8")
        else:
            raise AssertionError(f"Unexpected fake subprocess: {script} {args}")

    def fake_probe(self, image, seeds, probed):
        self.calls.append("probed")
        Path(probed).write_text("[]", encoding="utf-8")

    def fake_classify(self, image, catalog, base, name, excluded):
        self.calls.append("classified")
        Path(excluded).write_text("[]", encoding="utf-8")

    def run_lift(self, resume=True):
        module.lift("d3dx9_30.dll", resume=resume)

    def manifest(self):
        path = self.root / "work/modules/d3dx/pipeline_checkpoint.json"
        return json.loads(path.read_text(encoding="utf-8"))

    def test_completed_pipeline_is_skipped(self):
        self.run_lift()
        self.assertEqual(self.calls, ["relocated", "probed", "catalogued",
                                      "classified", "lifted"])
        self.calls.clear()
        self.run_lift()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.manifest()["completed"],
                         ["relocated", "probed", "catalogued", "classified", "lifted"])

    def test_resume_after_catalog_crash(self):
        self.fail_catalog = True
        with self.assertRaisesRegex(RuntimeError, "injected catalog failure"):
            self.run_lift()
        self.assertEqual(self.manifest()["completed"], ["relocated", "probed"])
        self.calls.clear()
        self.fail_catalog = False
        self.run_lift()
        self.assertEqual(self.calls, ["catalogued", "classified", "lifted"])

    def test_corrupted_probe_reprocesses_dependent_stages(self):
        self.run_lift()
        self.calls.clear()
        (self.root / "work/modules/d3dx/seeds_probed.json").write_text("{broken",
                                                                       encoding="utf-8")
        self.run_lift()
        self.assertEqual(self.calls, ["probed", "catalogued", "classified", "lifted"])

    def test_generator_fingerprint_change_invalidates_all_stages(self):
        self.run_lift()
        self.calls.clear()
        self.fingerprint = "test-fingerprint-b"
        self.run_lift()
        self.assertEqual(self.calls, ["relocated", "probed", "catalogued",
                                      "classified", "lifted"])
        self.assertEqual(self.manifest()["fingerprint"], "test-fingerprint-b")


if __name__ == "__main__":
    unittest.main()
