#!/usr/bin/env python3
"""Build a handwritten freestanding C program into accelerator SRAM images."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autogen.compiler.cnn_config import ROOT
from autogen.compiler.config import COMPILER_CFLAGS, RUNTIME_INCLUDE_DIR
from autogen.compiler.memory_image import SourceText, build_memory_images_from_sources, compile_c_to_assembly, write_hex_image


EMPTY_DCACHE_INIT = '    .section .dcache_init,"aw"\n    .align 2\n    .word 0\n'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--c", required=True, type=Path, help="freestanding C source to compile")
    parser.add_argument(
        "--dcache-asm",
        type=Path,
        default=None,
        help="optional assembly file containing a .dcache_init section",
    )
    parser.add_argument("--out-dir", required=True, type=Path, help="directory for .S and hex outputs")
    parser.add_argument(
        "--cflag",
        action="append",
        default=[],
        help="extra GCC flag; may be provided multiple times",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    c_path = args.c.resolve()
    if not c_path.exists():
        raise FileNotFoundError(c_path)

    if args.dcache_asm is None:
        dcache_unit = SourceText("empty_dcache_init.S", EMPTY_DCACHE_INIT)
    else:
        data_path = args.dcache_asm.resolve()
        if not data_path.exists():
            raise FileNotFoundError(data_path)
        dcache_unit = SourceText(data_path.name, data_path.read_text(encoding="ascii"))

    c_unit = SourceText(c_path.name, c_path.read_text(encoding="ascii"))
    cflags = (*COMPILER_CFLAGS, *args.cflag)
    include_dirs = [RUNTIME_INCLUDE_DIR, c_path.parent]

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    asm_text = compile_c_to_assembly(c_unit, extra_cflags=cflags, include_dirs=include_dirs)
    asm_path = out_dir / f"{c_path.stem}.S"
    asm_path.write_text(asm_text, encoding="ascii")

    images = build_memory_images_from_sources(
        [c_unit, dcache_unit],
        extra_cflags=cflags,
        include_dirs=include_dirs,
    )
    icache_path = out_dir / "icache_initial.hex"
    dcache_path = out_dir / "dcache_initial.hex"
    write_hex_image(icache_path, images.icache_bytes)
    write_hex_image(dcache_path, images.dcache_bytes)

    print(f"wrote {asm_path.relative_to(ROOT) if asm_path.is_relative_to(ROOT) else asm_path}")
    print(f"wrote {icache_path.relative_to(ROOT) if icache_path.is_relative_to(ROOT) else icache_path}")
    print(f"wrote {dcache_path.relative_to(ROOT) if dcache_path.is_relative_to(ROOT) else dcache_path}")
    print(f"compiler C flags: {' '.join(cflags)}")


if __name__ == "__main__":
    main()
