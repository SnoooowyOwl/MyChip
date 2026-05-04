#!/usr/bin/env python3
"""Build the static C implementation for the current CNN test cases."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autogen.compiler.cnn_config import (
    DMA_WAIT_NOPS,
    OUT_COMPILER_ASM,
    OUT_COMPILER_DATA_ASM,
    OUT_COMPILER_DCACHE_HEX,
    OUT_COMPILER_ICACHE_HEX,
    ROOT,
    compiler_testcase_paths,
)
from autogen.compiler.cnn_model import load_cnn_tensors
from autogen.compiler.cnn_rodata import build_rodata
from autogen.compiler.config import CNN_C_SOURCE, COMPILER_CFLAGS, RUNTIME_INCLUDE_DIR
from autogen.compiler.dcache_init_emit import emit_dcache_init_assembly
from autogen.compiler.memory_image import SourceText, build_memory_images_from_sources, compile_c_to_assembly, write_hex_image
from autogen.compiler.testcase_metadata import expected_output_text


def build_case_sources(tensors, sample_index: int) -> tuple[int, str]:
    expected = int(tensors.expected_output[sample_index, 0])
    rodata = build_rodata(tensors, sample_index=sample_index)
    data_asm = emit_dcache_init_assembly(rodata, global_labels=True)
    return expected, data_asm


def write_case(
    tensors,
    sample_index: int,
    data_asm_path: Path,
    asm_path: Path,
    icache_path: Path,
    dcache_path: Path,
    expected_path: Path | None,
) -> None:
    expected, data_asm = build_case_sources(tensors, sample_index)
    c_source = CNN_C_SOURCE.read_text(encoding="ascii")
    data_asm_path.parent.mkdir(parents=True, exist_ok=True)
    data_asm_path.write_text(data_asm, encoding="ascii")

    c_unit = SourceText(CNN_C_SOURCE.name, c_source)
    data_unit = SourceText(data_asm_path.name, data_asm)
    compiler_asm = compile_c_to_assembly(c_unit, extra_cflags=COMPILER_CFLAGS, include_dirs=[RUNTIME_INCLUDE_DIR])
    asm_path.write_text(compiler_asm, encoding="ascii")

    images = build_memory_images_from_sources(
        [c_unit, data_unit],
        extra_cflags=COMPILER_CFLAGS,
        include_dirs=[RUNTIME_INCLUDE_DIR],
    )
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
        help="build only this sample index; default builds every sample",
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
        write_case(tensors, sample_index, *compiler_testcase_paths(sample_index))

    write_case(
        tensors,
        legacy_index,
        OUT_COMPILER_DATA_ASM,
        OUT_COMPILER_ASM,
        OUT_COMPILER_ICACHE_HEX,
        OUT_COMPILER_DCACHE_HEX,
        None,
    )

    for sample_index in sample_indices:
        data_asm_path, asm_path, icache_path, dcache_path, expected_path = compiler_testcase_paths(sample_index)
        print(f"wrote {data_asm_path.relative_to(ROOT)}")
        print(f"wrote {asm_path.relative_to(ROOT)}")
        print(f"wrote {icache_path.relative_to(ROOT)}")
        print(f"wrote {dcache_path.relative_to(ROOT)}")
        print(f"wrote {expected_path.relative_to(ROOT)}")
    print(f"compiled C source {CNN_C_SOURCE.relative_to(ROOT)}")
    print(f"mirrored sample {legacy_index} to {OUT_COMPILER_DATA_ASM.relative_to(ROOT)}")
    print(f"mirrored sample {legacy_index} to {OUT_COMPILER_ASM.relative_to(ROOT)}")
    print(f"mirrored sample {legacy_index} to {OUT_COMPILER_ICACHE_HEX.relative_to(ROOT)}")
    print(f"mirrored sample {legacy_index} to {OUT_COMPILER_DCACHE_HEX.relative_to(ROOT)}")
    print(f"compiler C flags: {' '.join(COMPILER_CFLAGS)}")
    print(f"DMA wait nops per row load: {DMA_WAIT_NOPS}")
    print("run python3 autogen/compiler/verify_cnn.py for compiler workflow checks")


if __name__ == "__main__":
    main()
