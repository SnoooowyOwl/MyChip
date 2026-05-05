#!/usr/bin/env python3
"""Generate one random CNN input and build both software workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autogen.compiler.config import CNN_C_SOURCE, COMPILER_CFLAGS, RUNTIME_INCLUDE_DIR
from autogen.compiler.dcache_init_emit import emit_dcache_init_assembly
from autogen.compiler.memory_image import (
    SourceText,
    build_memory_images_from_sources,
    compile_c_to_assembly,
    write_hex_image as write_compiler_hex_image,
)
from autogen.compiler.cnn_model import CnnTensors as CompilerCnnTensors
from autogen.compiler.cnn_rodata import build_rodata as build_compiler_rodata
from autogen.compiler.cnn_config import OUT_DIR as COMPILER_OUT_DIR, ROOT
from autogen.compiler.testcase_metadata import expected_output_text as compiler_expected_output_text
from autogen.python.cnn_config import OUT_DIR as PYTHON_OUT_DIR
from autogen.python.cnn_model import (
    CnnTensors as PythonCnnTensors,
    compute_golden,
    load_cnn_tensors,
    validate_cnn_tensors,
)
from autogen.python.cnn_rodata import build_rodata as build_python_rodata
from autogen.python.cnn_top_emit import emit_assembly
from autogen.python.memory_image import build_memory_images, write_hex_image as write_python_hex_image
from autogen.python.testcase_metadata import expected_output_text as python_expected_output_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="random seed; default uses OS entropy",
    )
    parser.add_argument(
        "--name",
        default="random",
        help="output subdirectory name under each workflow out directory",
    )
    return parser.parse_args()


def make_random_tensors(seed: int | None) -> tuple[PythonCnnTensors, int]:
    base = load_cnn_tensors()
    rng = np.random.default_rng(seed)
    sample = rng.integers(0, 256, size=(1, 1, 16, 15), dtype=np.uint8)
    placeholder = np.zeros((1, 1), dtype=np.uint8)
    tensors = PythonCnnTensors(
        sample=sample,
        expected_output=placeholder,
        conv1_w=base.conv1_w,
        conv2_w=base.conv2_w,
        fc1_w=base.fc1_w,
        fc2_w=base.fc2_w,
    )
    _, _, _, fc2 = compute_golden(tensors)
    tensors = PythonCnnTensors(
        sample=sample,
        expected_output=fc2,
        conv1_w=base.conv1_w,
        conv2_w=base.conv2_w,
        fc1_w=base.fc1_w,
        fc2_w=base.fc2_w,
    )
    validate_cnn_tensors(tensors)
    return tensors, int(fc2[0, 0])


def to_compiler_tensors(tensors: PythonCnnTensors) -> CompilerCnnTensors:
    return CompilerCnnTensors(
        sample=tensors.sample,
        expected_output=tensors.expected_output,
        conv1_w=tensors.conv1_w,
        conv2_w=tensors.conv2_w,
        fc1_w=tensors.fc1_w,
        fc2_w=tensors.fc2_w,
    )


def input_text(tensors: PythonCnnTensors, seed: int | None, expected: int) -> str:
    rows = []
    for row in range(tensors.sample.shape[2]):
        values = ", ".join(str(int(v)) for v in tensors.sample[0, 0, row])
        rows.append(f"row{row:02d}: {values}")
    return "\n".join(
        [
            f"seed={seed if seed is not None else 'entropy'}",
            f"shape={tuple(tensors.sample.shape)}",
            f"expected_output_decimal={expected}",
            f"expected_output_hex=0x{expected:02X}",
            "input_rows:",
            *rows,
            "",
        ]
    )


def write_python_case(tensors: PythonCnnTensors, expected: int, out_dir: Path, seed: int | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    rodata = build_python_rodata(tensors, sample_index=0)
    asm = emit_assembly(rodata, sample_index=0, expected_output=expected)
    images = build_memory_images(asm)

    (out_dir / "cnn_accel_random.S").write_text(asm, encoding="ascii")
    write_python_hex_image(out_dir / "icache_initial.hex", images.icache_bytes)
    write_python_hex_image(out_dir / "dcache_initial.hex", images.dcache_bytes)
    (out_dir / "expected.txt").write_text(python_expected_output_text(0, expected), encoding="ascii")
    (out_dir / "input.txt").write_text(input_text(tensors, seed, expected), encoding="ascii")


def write_compiler_case(tensors: PythonCnnTensors, expected: int, out_dir: Path, seed: int | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    compiler_tensors = to_compiler_tensors(tensors)
    rodata = build_compiler_rodata(compiler_tensors, sample_index=0)
    data_asm = emit_dcache_init_assembly(rodata, global_labels=True)
    c_source = CNN_C_SOURCE.read_text(encoding="ascii")
    c_unit = SourceText(CNN_C_SOURCE.name, c_source)
    data_unit = SourceText("dcache_init_random.S", data_asm)

    compiler_asm = compile_c_to_assembly(c_unit, extra_cflags=COMPILER_CFLAGS, include_dirs=[RUNTIME_INCLUDE_DIR])
    images = build_memory_images_from_sources(
        [c_unit, data_unit],
        extra_cflags=COMPILER_CFLAGS,
        include_dirs=[RUNTIME_INCLUDE_DIR],
    )

    (out_dir / "dcache_init_random.S").write_text(data_asm, encoding="ascii")
    (out_dir / "cnn_accel.S").write_text(compiler_asm, encoding="ascii")
    write_compiler_hex_image(out_dir / "icache_initial.hex", images.icache_bytes)
    write_compiler_hex_image(out_dir / "dcache_initial.hex", images.dcache_bytes)
    (out_dir / "expected.txt").write_text(compiler_expected_output_text(0, expected), encoding="ascii")
    (out_dir / "input.txt").write_text(input_text(tensors, seed, expected), encoding="ascii")


def main() -> None:
    args = parse_args()
    tensors, expected = make_random_tensors(args.seed)
    python_out = PYTHON_OUT_DIR / args.name
    compiler_out = COMPILER_OUT_DIR / args.name

    write_python_case(tensors, expected, python_out, args.seed)
    write_compiler_case(tensors, expected, compiler_out, args.seed)

    print(f"random seed: {args.seed if args.seed is not None else 'entropy'}")
    print(f"expected output: {expected} / 0x{expected:02X}")
    print(f"manual workflow wrote {python_out.relative_to(ROOT)}")
    print(f"compiler workflow wrote {compiler_out.relative_to(ROOT)}")
    print(f"manual I-cache: {python_out.relative_to(ROOT)}/icache_initial.hex")
    print(f"manual D-cache: {python_out.relative_to(ROOT)}/dcache_initial.hex")
    print(f"compiler I-cache: {compiler_out.relative_to(ROOT)}/icache_initial.hex")
    print(f"compiler D-cache: {compiler_out.relative_to(ROOT)}/dcache_initial.hex")


if __name__ == "__main__":
    main()
