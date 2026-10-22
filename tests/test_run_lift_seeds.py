"""Regression tests for low-memory seed coverage; no proprietary game data."""
from pathlib import Path
import sys
import unittest
import tempfile
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from run_lift import missing_seed_coverage, restore_seeds, invalidate_previous_lift_manifest  # noqa: E402


def make_function(address, instructions, calls=()):
    block = SimpleNamespace(
        instructions=[SimpleNamespace(address=a, size=size) for a, size in instructions])
    return SimpleNamespace(address=address, blocks={address: block},
                           calls_to=set(calls), entry_kind="prologue")


class FakeDisassembler:
    def __init__(self):
        self.decoded = []

    def disassemble_function(self, va, iat):
        self.decoded.append(va)
        return make_function(va, [(va, 2)])


class MissingSeedCoverageTests(unittest.TestCase):
    def test_only_missing_seed_bytes_are_recorded(self):
        funcs = {
            0x1000: make_function(0x1000, [(0x1000, 5), (0x1010, 7)]),
            0x2000: make_function(0x2000, [(0x1001, 4), (0x2010, 2)]),
        }
        result = missing_seed_coverage(funcs, [0x1000, 0x1001, 0x1002, 0x1016, 0x2011, 0x9000])
        self.assertEqual(result, {
            0x1001: {0x1000},
            0x1002: {0x1000, 0x2000},
            0x1016: {0x1000},
            0x2011: {0x2000},
        })
        self.assertEqual(missing_seed_coverage(funcs, []), {})

    def test_coverage_matches_prior_algorithm_for_overlapping_decoders(self):
        funcs = {
            k: make_function(k, [(k + step, 1 + ((k + step) % 9))
                                  for step in range(0, 100, 10)])
            for k in range(0x4000, 0x6000, 31)
        }
        candidates = set(range(0x3FF0, 0x6020, 17))
        old = {}
        for address, function in funcs.items():
            for block in function.blocks.values():
                for ins in block.instructions:
                    for interior in range(ins.address + 1, ins.address + ins.size):
                        old.setdefault(interior, set()).add(address)
        expected = {address: covering for address, covering in old.items()
                    if address in candidates}
        self.assertEqual(missing_seed_coverage(funcs, candidates), expected)

    def test_uncalled_bogus_start_removed_and_seed_restored(self):
        funcs = {0x1000: make_function(0x1000, [(0x1000, 5)])}
        dis = FakeDisassembler()
        restore_seeds(dis, {}, funcs, {0x1002})
        self.assertEqual(set(funcs), {0x1002})
        self.assertEqual(funcs[0x1002].entry_kind, "start")
        self.assertEqual(dis.decoded, [0x1002])

    def test_called_real_function_wins_over_inside_seed(self):
        funcs = {
            0x1000: make_function(0x1000, [(0x1000, 5)]),
            0x2000: make_function(0x2000, [(0x2000, 5)], calls=[0x1000]),
        }
        dis = FakeDisassembler()
        restore_seeds(dis, {}, funcs, {0x1002})
        self.assertEqual(set(funcs), {0x1000, 0x2000})
        self.assertEqual(dis.decoded, [])

    def test_restarting_lift_invalidates_old_success_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = Path(tmp) / "d3dx_lift_stats.json"
            generated = Path(tmp) / "d3dx_recomp_0000.c"
            stats.write_text('{"functions": 100, "files": 1, "lift_failures": 0}')
            generated.write_text("incomplete function body")
            invalidate_previous_lift_manifest(tmp, "d3dx_")
            self.assertFalse(stats.exists())
            self.assertTrue(generated.exists())  # generator removes/replaces it next
            invalidate_previous_lift_manifest(tmp, "d3dx_")  # safe to retry

    def test_existing_seed_function_wins_over_inside_seed(self):
        funcs = {0x1000: make_function(0x1000, [(0x1000, 5)])}
        dis = FakeDisassembler()
        restore_seeds(dis, {}, funcs, {0x1000, 0x1002})
        self.assertEqual(set(funcs), {0x1000})
        self.assertEqual(dis.decoded, [])


if __name__ == "__main__":
    unittest.main()
