#!/usr/bin/env python3
"""Verify the manual Python-to-RV32 CNN workflow."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autogen.python.accelerator_regs import DCACHE_BASE, IMPLEMENTED_ACCEL_OFFSETS
from autogen.python.cnn_config import (
    COMBINED_SRAM_WINDOW_BYTES,
    CONV1_CH_BYTES,
    CONV1_COUT,
    CONV2_H,
    CONV2_ROW_STRIDE,
    CONV2_W,
    D_ACCUM,
    D_CONST,
    D_CONV1,
    D_CONV2,
    D_FC1,
    D_INPUT,
    D_OUTPUT,
    D_SCRATCH,
    D_STACK_GUARD_BYTES,
    D_STACK_TOP,
    INPUT_H,
    LINK_TEXT_BASE,
    OUT_ASM,
    OUT_DCACHE_HEX,
    OUT_ICACHE_HEX,
    ROOT,
    ROW_STRIDE,
    SRAM_WINDOW_BYTES,
    testcase_paths,
)
from autogen.python.cnn_model import compute_golden, compute_mapped_golden, load_cnn_tensors, validate_cnn_tensors
from autogen.python.cnn_rodata import build_rodata
from autogen.python.cnn_top_emit import emit_assembly
from autogen.python.memory_image import RISCV_ARCH, build_memory_images, configured_toolchain, parse_hex_image
from autogen.python.testcase_metadata import expected_output_text


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def dcache_runtime_ranges() -> list[tuple[str, int, int]]:
    return [
        ("input", D_INPUT, D_INPUT + INPUT_H * ROW_STRIDE),
        ("Conv1 activations", D_CONV1, D_CONV1 + CONV1_COUT * CONV1_CH_BYTES),
        ("Conv2 activations", D_CONV2, D_CONV2 + CONV2_H * CONV2_ROW_STRIDE),
        ("FC1 activations", D_FC1, D_FC1 + 10),
        ("final output", D_OUTPUT, D_OUTPUT + 1),
        ("FC scratch", D_SCRATCH, D_SCRATCH + 3 * ROW_STRIDE),
        ("accum scratch", D_ACCUM, D_ACCUM + CONV2_H * CONV2_W * 4),
        ("stack guard", D_STACK_TOP + 4 - D_STACK_GUARD_BYTES, D_STACK_TOP + 4),
    ]


def check_no_overlaps(ranges: list[tuple[str, int, int]]) -> None:
    for name, start, end in ranges:
        if start < DCACHE_BASE or end > DCACHE_BASE + SRAM_WINDOW_BYTES:
            raise AssertionError(f"{name} [{start:#x}, {end:#x}) is outside the 8 KiB D-cache window")
        if start >= end:
            raise AssertionError(f"{name} has invalid range [{start:#x}, {end:#x})")

    for idx, (name_a, start_a, end_a) in enumerate(ranges):
        for name_b, start_b, end_b in ranges[idx + 1 :]:
            if start_a < end_b and start_b < end_a:
                raise AssertionError(f"{name_a} overlaps {name_b}")


def check_dcache_const_layout(rodata: dict[str, list[int]]) -> None:
    addr = D_CONST
    const_ranges: list[tuple[str, int, int]] = []
    for name in ("conv1_w_packed", "conv2_w_packed", "fc1_w_packed", "fc2_w_packed"):
        addr = align_up(addr, 4)
        end = addr + len(rodata[name]) * 4
        const_ranges.append((name, addr, end))
        addr = end

    if addr - DCACHE_BASE > SRAM_WINDOW_BYTES:
        raise AssertionError(f"D-cache constants exceed 8 KiB window: end {addr:#x}")

    for const_name, const_start, const_end in const_ranges:
        for runtime_name, runtime_start, runtime_end in dcache_runtime_ranges():
            if const_start < runtime_end and runtime_start < const_end:
                raise AssertionError(f"{const_name} overlaps {runtime_name}")


def static_check_assembly(asm: str, rodata: dict[str, list[int]]) -> None:
    if re.search(r"(?<!\d)8\(s0\)", asm):
        raise AssertionError("generated assembly appears to access nonexistent accelerator BASE+8")
    if ".section .rodata" in asm:
        raise AssertionError("generated assembly still places initialized data in I-cache .rodata")
    for forbidden in (
        "call acc_reset_psums",
        "call acc_wait_done",
        "call acc_store_packed_13",
        "call acc_accumulate_raw_11",
        "call fill_fc_scratch_conv2",
        "call fill_fc_scratch_linear",
    ):
        if forbidden in asm:
            raise AssertionError(f"generated assembly still contains hot helper call: {forbidden}")

    for match in re.finditer(r"\b(\d+)\(s0\)", asm):
        offset = int(match.group(1))
        if offset not in IMPLEMENTED_ACCEL_OFFSETS:
            raise AssertionError(f"unexpected accelerator offset {offset}(s0)")

    check_no_overlaps(dcache_runtime_ranges())
    check_dcache_const_layout(rodata)


def check_linked_sections(objdump_header: str) -> None:
    sections: dict[str, tuple[int, int]] = {}
    for line in objdump_header.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[1] in {".text", ".dcache_init"}:
            sections[parts[1]] = (int(parts[2], 16), int(parts[3], 16))

    for section, base in ((".text", LINK_TEXT_BASE), (".dcache_init", DCACHE_BASE)):
        if section not in sections:
            raise AssertionError(f"linked ELF is missing {section}")
        size, vma = sections[section]
        if vma != base:
            raise AssertionError(f"{section} linked at {vma:#x}, expected {base:#x}")
        if size > SRAM_WINDOW_BYTES:
            raise AssertionError(f"{section} exceeds 8 KiB SRAM window: {size} bytes")

    total = sum(size for size, _ in sections.values())
    if total > COMBINED_SRAM_WINDOW_BYTES:
        raise AssertionError(f"combined I/D SRAM image exceeds 16 KiB: {total} bytes")


def check_no_compressed_instructions(objdump_disassembly: str) -> None:
    for line in objdump_disassembly.splitlines():
        match = re.match(r"\s*[0-9a-f]+:\s+([0-9a-f]+)\s+", line)
        if match and len(match.group(1)) != 8:
            raise AssertionError(f"{RISCV_ARCH} build emitted a non-32-bit instruction: {line.strip()}")


def verify_generated_files(
    asm: str,
    asm_path: Path,
    icache_path: Path,
    dcache_path: Path,
    expected_path: Path | None = None,
    expected_text: str | None = None,
) -> None:
    if not asm_path.exists() or asm_path.read_text(encoding="ascii") != asm:
        raise AssertionError(f"{asm_path.relative_to(ROOT)} is stale; rerun python3 autogen/python/generate_cnn.py")

    images = build_memory_images(asm)
    check_linked_sections(images.objdump_header)
    check_no_compressed_instructions(images.objdump_disassembly)

    for path, expected_bytes in ((icache_path, images.icache_bytes), (dcache_path, images.dcache_bytes)):
        if not path.exists() or parse_hex_image(path) != expected_bytes:
            raise AssertionError(f"{path.relative_to(ROOT)} is stale; rerun python3 autogen/python/generate_cnn.py")

    if expected_path is not None and expected_text is not None:
        if not expected_path.exists() or expected_path.read_text(encoding="ascii") != expected_text:
            raise AssertionError(f"{expected_path.relative_to(ROOT)} is stale; rerun python3 autogen/python/generate_cnn.py")


def verify_reference_and_mapping() -> tuple[np.ndarray, np.ndarray]:
    tensors = load_cnn_tensors()
    validate_cnn_tensors(tensors)
    conv1, conv2, fc1, fc2 = compute_golden(tensors)
    if tensors.expected_output.tolist() != fc2.tolist():
        raise AssertionError(f"sample_io output {tensors.expected_output.tolist()} != golden {fc2.tolist()}")

    for sample_index in range(tensors.sample.shape[0]):
        mapped = compute_mapped_golden(tensors.sample[sample_index : sample_index + 1], tensors)
        if not np.array_equal(mapped[0], conv1[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped Conv1 golden mismatch for sample {sample_index}")
        if not np.array_equal(mapped[1], conv2[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped Conv2 golden mismatch for sample {sample_index}")
        if not np.array_equal(mapped[2], fc1[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped FC1 golden mismatch for sample {sample_index}")
        if not np.array_equal(mapped[3], fc2[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped FC2 golden mismatch for sample {sample_index}")
    return fc1, fc2


def verify_codegen_case(tensors, sample_index: int, asm_path: Path, icache_path: Path, dcache_path: Path, expected_path: Path | None = None) -> None:
    expected = int(tensors.expected_output[sample_index, 0])
    rodata = build_rodata(tensors, sample_index=sample_index)
    asm = emit_assembly(rodata, sample_index=sample_index, expected_output=expected)
    static_check_assembly(asm, rodata)
    expected_text = expected_output_text(sample_index, expected) if expected_path is not None else None
    verify_generated_files(asm, asm_path, icache_path, dcache_path, expected_path, expected_text)


def verify_codegen_static() -> int:
    tensors = load_cnn_tensors()
    sample_count = tensors.sample.shape[0]
    for sample_index in range(sample_count):
        verify_codegen_case(tensors, sample_index, *testcase_paths(sample_index))
    verify_codegen_case(tensors, 0, OUT_ASM, OUT_ICACHE_HEX, OUT_DCACHE_HEX)
    return sample_count


def main() -> None:
    fc1, fc2 = verify_reference_and_mapping()
    sample_count = verify_codegen_static()
    tools = configured_toolchain()
    print("manual workflow verification passed")
    print(f"assembly checked: {OUT_ASM.relative_to(ROOT)}")
    print(f"I-cache image checked: {OUT_ICACHE_HEX.relative_to(ROOT)}")
    print(f"D-cache image checked: {OUT_DCACHE_HEX.relative_to(ROOT)}")
    print(f"testcase directories checked: {sample_count}")
    print(f"toolchain checked: {tools.gcc}")
    print(f"golden output all samples: {fc2.reshape(-1).tolist()}")
    print(f"sample 0 expected FC1: {fc1[0].tolist()}")


if __name__ == "__main__":
    main()
