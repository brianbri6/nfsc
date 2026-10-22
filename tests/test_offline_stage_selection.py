"""Test offline stage isolation without the original copyrighted game files."""
import hashlib
import importlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
offline = importlib.import_module("prepare_offline")


def fake_pe(path, base, image_size):
    """Tiny test-only x86 PE header; it is not a real game or runnable binary."""
    raw = bytearray(4096)
    raw[:2] = b"MZ"
    struct.pack_into("<I", raw, 0x3C, 0x80)
    raw[0x80:0x84] = b"PE\0\0"
    struct.pack_into("<H", raw, 0x84, 0x14C)
    struct.pack_into("<H", raw, 0x98, 0x10B)
    struct.pack_into("<I", raw, 0x98 + 28, base)
    struct.pack_into("<I", raw, 0x98 + 56, image_size)
    path.write_bytes(raw)


class OfflineStageIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / "game"
        self.game.mkdir()
        (self.game / "SOUND").mkdir()
        (self.game / "SOUND" / "test.abk").write_bytes(b"TEST_ONLY")
        layouts = {
            "NFSC.exe": (0x400000, 0x82B34E),
            "d3dx9_30.dll": (0x400000, 0x260000),
            "msvcr71.dll": (0x7C340000, 0x56000),
            "msvcp71.dll": (0x7C3A0000, 0x7B000),
        }
        for name, (base, size) in layouts.items():
            fake_pe(self.game / name, base, size)
        self.reference = {
            "executable": "NFSC.exe",
            "sha256": hashlib.sha256((self.game / "NFSC.exe").read_bytes()).hexdigest(),
        }

    def simulate(self, stage):
        calls = []
        results = {"sound_banks": {
            "total_banks": 1, "unique_code_blocks": 1,
            "patched_call_references_verified": 0,
        }}
        with patch.object(offline, "ROOT", self.root), \
             patch.object(offline, "REFERENCE", self.reference), \
             patch.object(offline, "PCRECOMP_FILES", ()), \
             patch.object(offline, "verify_offline_assets", return_value=results), \
             patch.object(offline, "run", side_effect=lambda env, *args: calls.append(args)), \
             patch.object(sys, "argv", ["prepare_offline.py", "--game-root", str(self.game),
                                        "--stage", stage]):
            offline.main()
        return [str(call[1]) for call in calls]

    def test_only_game_stage_runs_main_lifter(self):
        commands = self.simulate("game")
        self.assertEqual(commands, ["scripts/analyze_binary.py",
                                    "scripts/data_seeds.py",
                                    "scripts/run_lift.py",
                                    "scripts/code_seeds.py",
                                    "scripts/run_lift.py",
                                    "scripts/run_lift.py"])

    def test_only_audio_stage_runs_abk(self):
        self.assertEqual(self.simulate("audio"),
                         ["scripts/abk_module.py", "scripts/run_lift.py",
                          "scripts/run_lift.py"])

    def test_only_dll_stage_runs_module_processor(self):
        self.assertEqual(self.simulate("dlls"), ["scripts/prepare_modules.py"])

    def test_all_stages_are_game_audio_dll(self):
        commands = self.simulate("all")
        self.assertEqual(len(commands), 10)
        self.assertEqual(commands[6:9],
                         ["scripts/abk_module.py", "scripts/run_lift.py", "scripts/run_lift.py"])
        self.assertEqual(commands[9], "scripts/prepare_modules.py")


if __name__ == "__main__":
    unittest.main()
