#!/usr/bin/env python3
"""Generate RV32 assembly and SRAM images for quantized CNN test cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autogen.cnn_config import DMA_WAIT_NOPS, OUT_ASM, OUT_DCACHE_HEX, OUT_ICACHE_HEX, ROOT, testcase_paths
from autogen.cnn_model import load_cnn_tensors
from autogen.cnn_rodata import build_rodata
from autogen.cnn_top_emit import emit_assembly
from autogen.memory_image import build_memory_images, write_hex_image
from autogen.testcase_metadata import expected_output_text


def write_case(
    tensors,
    sample_index: int,
    asm_path: Path,
    icache_path: Path,
    dcache_path: Path,
    expected_path: Path | None,
) -> None:
    expected = int(tensors.expected_output[sample_index, 0])
    rodata = build_rodata(tensors, sample_index=sample_index)
    asm = emit_assembly(rodata, sample_index=sample_index, expected_output=expected)
    asm_path.parent.mkdir(parents=True, exist_ok=True)
    asm_path.write_text(asm, encoding="ascii")
    images = build_memory_images(asm)
    write_hex_image(icache_path, images.icache_bytes)
    write_hex_image(dcache_path, images.dcache_bytes)
    if expected_path is not None:
        expected_path.write_text(expected_output_text(sample_index, expected), encoding="ascii")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sample",
        type=int,
        default=None,
        help="generate only this sample index; default generates every sample",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tensors = load_cnn_tensors()
    sample_count = tensors.sample.shape[0]
    if args.sample is None:
        sample_indices = list(range(sample_count))
        legacy_index = 0
    else:
        if not 0 <= args.sample < sample_count:
            raise ValueError(f"sample index {args.sample} outside sample count {sample_count}")
        sample_indices = [args.sample]
        legacy_index = args.sample

    for sample_index in sample_indices:
        write_case(tensors, sample_index, *testcase_paths(sample_index))

    write_case(tensors, legacy_index, OUT_ASM, OUT_ICACHE_HEX, OUT_DCACHE_HEX, None)
    for sample_index in sample_indices:
        asm_path, icache_path, dcache_path, expected_path = testcase_paths(sample_index)
        print(f"wrote {asm_path.relative_to(ROOT)}")
        print(f"wrote {icache_path.relative_to(ROOT)}")
        print(f"wrote {dcache_path.relative_to(ROOT)}")
        print(f"wrote {expected_path.relative_to(ROOT)}")
    print(f"mirrored sample {legacy_index} to {OUT_ASM.relative_to(ROOT)}")
    print(f"mirrored sample {legacy_index} to {OUT_ICACHE_HEX.relative_to(ROOT)}")
    print(f"mirrored sample {legacy_index} to {OUT_DCACHE_HEX.relative_to(ROOT)}")
    print(f"DMA wait nops per row load: {DMA_WAIT_NOPS}")
    print("run python3 autogen/verify_cnn.py for mapping, image, and toolchain checks")


if __name__ == "__main__":
    main()
