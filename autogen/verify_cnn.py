#!/usr/bin/env python3
"""Standalone verification for the generated CNN mapping and SRAM images."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autogen.accelerator_api import DCACHE_BASE, IMPLEMENTED_ACCEL_OFFSETS
from autogen.cnn_config import (
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
    FC1_IN,
    FC_CHUNK,
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
from autogen.cnn_model import compute_golden, compute_mapped_golden, load_cnn_tensors, validate_cnn_tensors
from autogen.cnn_rodata import build_rodata
from autogen.cnn_top_emit import emit_assembly
from autogen.memory_image import RISCV_ARCH, build_memory_images, configured_toolchain, parse_hex_image
from autogen.testcase_metadata import expected_output_text


def align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def static_check_assembly(asm: str, rodata: dict[str, list[int]]) -> None:
    if re.search(r"(?<!\d)8\(s0\)", asm):
        raise AssertionError("generated assembly appears to access nonexistent accelerator BASE+8")
    if ".section .rodata" in asm:
        raise AssertionError("generated assembly still places initialized data in I-cache .rodata")

    for match in re.finditer(r"\b(\d+)\(s0\)", asm):
        offset = int(match.group(1))
        if offset not in IMPLEMENTED_ACCEL_OFFSETS:
            raise AssertionError(f"unexpected accelerator offset {offset}(s0)")

    runtime_ranges = dcache_runtime_ranges()
    max_runtime_addr = max(end for _, _, end in runtime_ranges)
    if max_runtime_addr - DCACHE_BASE > SRAM_WINDOW_BYTES:
        raise AssertionError(f"D-cache runtime layout exceeds 8 KiB window: max {max_runtime_addr:#x}")
    check_no_overlaps(runtime_ranges)

    if len(rodata["fc_scratch_offsets"]) != FC_CHUNK:
        raise AssertionError("bad FC scratch offset table length")
    if len(rodata["conv2_flat_offsets"]) != FC1_IN:
        raise AssertionError("bad Conv2 flat offset table length")
    check_dcache_const_layout(rodata)


def dcache_runtime_ranges() -> list[tuple[str, int, int]]:
    return [
        ("input", D_INPUT, D_INPUT + INPUT_H * ROW_STRIDE),
        ("Conv1 activations", D_CONV1, D_CONV1 + CONV1_COUT * CONV1_CH_BYTES),
        ("Conv2 activations", D_CONV2, D_CONV2 + CONV2_H * CONV2_ROW_STRIDE),
        ("FC1 activations", D_FC1, D_FC1 + 10),
        ("final output", D_OUTPUT, D_OUTPUT + 1),
        ("FC scratch", D_SCRATCH, D_SCRATCH + 3 * ROW_STRIDE),
        ("accum scratch", D_ACCUM, D_ACCUM + CONV2_W * 4),
        ("stack guard", D_STACK_TOP + 4 - D_STACK_GUARD_BYTES, D_STACK_TOP + 4),
    ]


def check_no_overlaps(ranges: list[tuple[str, int, int]]) -> None:
    for name, start, end in ranges:
        if start < DCACHE_BASE or end > DCACHE_BASE + SRAM_WINDOW_BYTES:
            raise AssertionError(f"{name} [{start:#x}, {end:#x}) is outside the 8 KiB D-cache window")
        if start >= end:
            raise AssertionError(f"{name} has an invalid range [{start:#x}, {end:#x})")

    for idx, (name_a, start_a, end_a) in enumerate(ranges):
        for name_b, start_b, end_b in ranges[idx + 1 :]:
            if start_a < end_b and start_b < end_a:
                raise AssertionError(
                    f"{name_a} [{start_a:#x}, {end_a:#x}) overlaps "
                    f"{name_b} [{start_b:#x}, {end_b:#x})"
                )


def check_dcache_const_layout(rodata: dict[str, list[int]]) -> None:
    addr = D_CONST
    const_ranges: list[tuple[str, int, int]] = []

    for name in ("conv1_w_packed", "conv2_w_packed", "fc1_w_packed", "fc2_w_packed"):
        addr = align_up(addr, 4)
        end = addr + len(rodata[name]) * 4
        const_ranges.append((name, addr, end))
        addr = end

    addr = align_up(addr, 2)
    end = addr + len(rodata["fc_scratch_offsets"])
    const_ranges.append(("fc_scratch_offsets", addr, end))
    addr = end

    addr = align_up(addr, 2)
    end = addr + len(rodata["conv2_flat_offsets"]) * 2
    const_ranges.append(("conv2_flat_offsets", addr, end))
    addr = end

    if addr - DCACHE_BASE > SRAM_WINDOW_BYTES:
        raise AssertionError(f"D-cache constants exceed 8 KiB window: end {addr:#x}")

    runtime_ranges = dcache_runtime_ranges()
    for const_name, const_start, const_end in const_ranges:
        for runtime_name, runtime_start, runtime_end in runtime_ranges:
            if const_start < runtime_end and runtime_start < const_end:
                raise AssertionError(
                    f"{const_name} [{const_start:#x}, {const_end:#x}) overlaps "
                    f"{runtime_name} [{runtime_start:#x}, {runtime_end:#x})"
                )


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
    if not asm_path.exists():
        raise AssertionError(f"{asm_path.relative_to(ROOT)} is missing; rerun python3 autogen/generate_cnn.py")
    generated = asm_path.read_text(encoding="ascii")
    if generated != asm:
        raise AssertionError(f"{asm_path.relative_to(ROOT)} is stale; rerun python3 autogen/generate_cnn.py")

    images = build_memory_images(asm)
    check_linked_sections(images.objdump_header)
    check_no_compressed_instructions(images.objdump_disassembly)

    expected = {
        icache_path: images.icache_bytes,
        dcache_path: images.dcache_bytes,
    }
    for path, expected_bytes in expected.items():
        if not path.exists():
            raise AssertionError(f"{path.relative_to(ROOT)} is missing; rerun python3 autogen/generate_cnn.py")
        actual_bytes = parse_hex_image(path)
        if actual_bytes != expected_bytes:
            raise AssertionError(f"{path.relative_to(ROOT)} is stale; rerun python3 autogen/generate_cnn.py")

    if expected_path is not None and expected_text is not None:
        if not expected_path.exists():
            raise AssertionError(f"{expected_path.relative_to(ROOT)} is missing; rerun python3 autogen/generate_cnn.py")
        actual_text = expected_path.read_text(encoding="ascii")
        if actual_text != expected_text:
            raise AssertionError(f"{expected_path.relative_to(ROOT)} is stale; rerun python3 autogen/generate_cnn.py")


def verify_reference_and_mapping() -> tuple[np.ndarray, np.ndarray]:
    tensors = load_cnn_tensors()
    validate_cnn_tensors(tensors)

    conv1, conv2, fc1, fc2 = compute_golden(tensors)
    if tensors.expected_output.tolist() != fc2.tolist():
        raise AssertionError(
            f"sample_io output {tensors.expected_output.tolist()} != golden {fc2.tolist()}"
        )

    for sample_index in range(tensors.sample.shape[0]):
        mapped_conv1, mapped_conv2, mapped_fc1, mapped_fc2 = compute_mapped_golden(
            tensors.sample[sample_index : sample_index + 1], tensors
        )
        if not np.array_equal(mapped_conv1, conv1[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped Conv1 golden does not match direct Conv1 golden for sample {sample_index}")
        if not np.array_equal(mapped_conv2, conv2[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped Conv2 golden does not match direct Conv2 golden for sample {sample_index}")
        if not np.array_equal(mapped_fc1, fc1[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped FC1 golden does not match direct FC1 golden for sample {sample_index}")
        if not np.array_equal(mapped_fc2, fc2[sample_index : sample_index + 1]):
            raise AssertionError(f"mapped FC2 golden does not match direct FC2 golden for sample {sample_index}")
    if fc2.reshape(-1).tolist() != [180, 237, 188, 156, 0]:
        raise AssertionError(f"unexpected golden output {fc2.reshape(-1).tolist()}")
    if fc1[0].tolist() != [0, 45, 0, 170, 0, 0, 0, 0, 0, 158]:
        raise AssertionError(f"unexpected sample 0 FC1 golden {fc1[0].tolist()}")

    return fc1, fc2


def verify_codegen_case(
    tensors,
    sample_index: int,
    asm_path: Path,
    icache_path: Path,
    dcache_path: Path,
    expected_path: Path | None = None,
) -> None:
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
    print("verification passed")
    print(f"assembly checked: {OUT_ASM.relative_to(ROOT)}")
    print(f"I-cache image checked: {OUT_ICACHE_HEX.relative_to(ROOT)}")
    print(f"D-cache image checked: {OUT_DCACHE_HEX.relative_to(ROOT)}")
    print(f"testcase directories checked: {sample_count}")
    print(f"toolchain checked: {tools.gcc}")
    print(f"golden output all samples: {fc2.reshape(-1).tolist()}")
    print(f"sample 0 expected output byte: {int(fc2.reshape(-1)[0])}")
    print(f"sample 0 expected FC1: {fc1[0].tolist()}")


if __name__ == "__main__":
    main()
