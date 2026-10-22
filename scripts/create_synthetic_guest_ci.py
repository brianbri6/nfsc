#!/usr/bin/env python3
"""Generate small public-domain stand-in guest C sources for CI validation.

This is NOT Carbon code and does NOT create a playable game.
Only run in GitHub Actions, never alongside private original game inputs.
Run with NFSC_SYNTHETIC_CI=1 to acknowledge the non-playable artifact.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "src/recomp"
SYMBOLS = {
    "gen": ("", 0x0087E926),
    "gen_d3dx": ("d3dx_", 0x00D01000),
    "gen_msvcr": ("msvcr_", 0x00F61000),
    "gen_msvcp": ("msvcp_", 0x00FC1000),
    "gen_abk": ("abk_", 0x10001000),
}


def create():
    if os.getenv("NFSC_SYNTHETIC_CI") != "1" or not os.getenv("GITHUB_ACTIONS"):
        raise SystemExit("Synthetic guest C fixture requires GitHub Actions and NFSC_SYNTHETIC_CI=1")
    for folder, (prefix, address) in SYMBOLS.items():
        directory = BASE / folder
        if directory.exists() and any(directory.iterdir()):
            raise SystemExit(f"Refusing to overwrite existing game C or other files: {directory}")
        directory.mkdir(parents=True, exist_ok=True)
        func = f"sub_{address:08X}"
        header = f"{prefix}recomp_funcs.h"
        (directory / header).write_text(
            f"/* Synthetic CI only; no game functions */\nvoid {func}(void);\n",
            encoding="utf-8")
        (directory / f"{prefix}recomp_0000.c").write_text(
            "#define RECOMP_GENERATED_CODE\n"
            '#include "recomp_types.h"\n'
            f'#include "{header}"\n'
            f"void {func}(void) {{}}\n",
            encoding="utf-8")
        (directory / f"{prefix}recomp_dispatch.c").write_text(
            '#include "recomp_types.h"\n'
            f'#include "{header}"\n'
            f"const recomp_dispatch_entry_t {prefix}recomp_dispatch_table[] = "
            f"{{{{0x{address:08X}u, {func}}}}};\n"
            f"const uint32_t {prefix}recomp_dispatch_count = 1u;\n",
            encoding="utf-8")
    (BASE / "gen_abk/abk_blocks.c").write_text(
        '#include "nfs_abk.h"\n'
        "static const uint8_t ci_data[2] = {0x90, 0xC3};\n"
        "static const uint16_t ci_rels[1] = {0};\n"
        "const nfs_abk_block_t nfs_abk_blocks[] = "
        "{{0x10001000u, ci_data, 2u, ci_rels, 0u}};\n"
        "const unsigned nfs_abk_block_count = 1u;\n",
        encoding="utf-8")
    (BASE / "gen/SYNTHETIC_CI_ONLY").write_text(
        "NON-PLAYABLE synthetic build fixtures. Never ship this APK.\n",
        encoding="utf-8")
    print("Synthetic generated-source fixtures created; no original game assets used.")


if __name__ == "__main__":
    create()
