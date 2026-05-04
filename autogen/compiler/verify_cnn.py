#!/usr/bin/env python3
"""Verify the static C compiler CNN workflow."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from autogen.compiler.accelerator_regs import DCACHE_BASE
from autogen.compiler.cnn_config import (
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
    DMA_WAIT_NOPS,
    INPUT_H,
    LINK_TEXT_BASE,
    OUT_COMPILER_ASM,
    OUT_COMPILER_DATA_ASM,
    OUT_COMPILER_DCACHE_HEX,
    OUT_COMPILER_ICACHE_HEX,
    OUT_COMPILER_SOURCE_C,
    ROOT,
    ROW_STRIDE,
    SRAM_WINDOW_BYTES,
    compiler_testcase_paths,
)
from autogen.compiler.cnn_model import compute_golden, compute_mapped_golden, load_cnn_tensors, validate_cnn_tensors
from autogen.compiler.cnn_rodata import build_rodata
from autogen.compiler.config import CNN_C_SOURCE, COMPILER_CFLAGS, RUNTIME_INCLUDE_DIR
from autogen.compiler.dcache_init_emit import emit_dcache_init_assembly
from autogen.compiler.memory_image import (
    RISCV_ARCH,
    SourceText,
    build_memory_images_from_sources,
    compile_c_to_assembly,
    configured_toolchain,
    parse_hex_image,
)
from autogen.compiler.testcase_metadata import expected_output_text


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


def static_check_c_source(c_source: str, rodata: dict[str, list[int]]) -> None:
    if "ACC_OFF_SRC_ADDR + 4" in c_source or "BASE+8" in c_source:
        raise AssertionError("compiler C source appears to reference nonexistent accelerator BASE+8")
    if "acc_reset_psums(" in c_source:
        raise AssertionError("compiler C hot path should not call acc_reset_psums")
    if f"#define ACC_DMA_WAIT_NOPS {DMA_WAIT_NOPS}" not in c_source:
        raise AssertionError("compiler C source does not record the DMA wait contract")
    if "Auto-generated" in c_source:
        raise AssertionError("compiler C source should be a static checked-in program")
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


def verify_compiler_generated_files(
    c_source: str,
    data_asm: str,
    data_asm_path: Path,
    asm_path: Path,
    icache_path: Path,
    dcache_path: Path,
    expected_path: Path | None = None,
    expected_text: str | None = None,
) -> None:
    if not data_asm_path.exists() or data_asm_path.read_text(encoding="ascii") != data_asm:
        raise AssertionError(f"{data_asm_path.relative_to(ROOT)} is stale; rerun python3 autogen/compiler/build_current_cnn.py")

    c_unit = SourceText(CNN_C_SOURCE.name, c_source)
    data_unit = SourceText(data_asm_path.name, data_asm)
    compiler_asm = compile_c_to_assembly(c_unit, extra_cflags=COMPILER_CFLAGS, include_dirs=[RUNTIME_INCLUDE_DIR])
    if not asm_path.exists() or asm_path.read_text(encoding="ascii") != compiler_asm:
        raise AssertionError(f"{asm_path.relative_to(ROOT)} is stale; rerun python3 autogen/compiler/build_current_cnn.py")

    images = build_memory_images_from_sources([c_unit, data_unit], extra_cflags=COMPILER_CFLAGS, include_dirs=[RUNTIME_INCLUDE_DIR])
    check_linked_sections(images.objdump_header)
    check_no_compressed_instructions(images.objdump_disassembly)
    for path, expected_bytes in ((icache_path, images.icache_bytes), (dcache_path, images.dcache_bytes)):
        if not path.exists() or parse_hex_image(path) != expected_bytes:
            raise AssertionError(f"{path.relative_to(ROOT)} is stale; rerun python3 autogen/compiler/build_current_cnn.py")

    if expected_path is not None and expected_text is not None:
        if not expected_path.exists() or expected_path.read_text(encoding="ascii") != expected_text:
            raise AssertionError(f"{expected_path.relative_to(ROOT)} is stale; rerun python3 autogen/compiler/build_current_cnn.py")


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


def verify_compiler_case(tensors, sample_index: int, data_asm_path: Path, asm_path: Path, icache_path: Path, dcache_path: Path, expected_path: Path | None = None) -> None:
    expected = int(tensors.expected_output[sample_index, 0])
    rodata = build_rodata(tensors, sample_index=sample_index)
    if not OUT_COMPILER_SOURCE_C.exists():
        raise AssertionError(f"{OUT_COMPILER_SOURCE_C.relative_to(ROOT)} is missing")
    c_source = OUT_COMPILER_SOURCE_C.read_text(encoding="ascii")
    data_asm = emit_dcache_init_assembly(rodata, global_labels=True)
    static_check_c_source(c_source, rodata)
    expected_text = expected_output_text(sample_index, expected) if expected_path is not None else None
    verify_compiler_generated_files(c_source, data_asm, data_asm_path, asm_path, icache_path, dcache_path, expected_path, expected_text)


def verify_compiler_static() -> int:
    tensors = load_cnn_tensors()
    sample_count = tensors.sample.shape[0]
    for sample_index in range(sample_count):
        verify_compiler_case(tensors, sample_index, *compiler_testcase_paths(sample_index))
    verify_compiler_case(tensors, 0, OUT_COMPILER_DATA_ASM, OUT_COMPILER_ASM, OUT_COMPILER_ICACHE_HEX, OUT_COMPILER_DCACHE_HEX)
    return sample_count


def main() -> None:
    fc1, fc2 = verify_reference_and_mapping()
    sample_count = verify_compiler_static()
    tools = configured_toolchain()
    print("compiler workflow verification passed")
    print(f"C source checked: {OUT_COMPILER_SOURCE_C.relative_to(ROOT)}")
    print(f"assembly checked: {OUT_COMPILER_ASM.relative_to(ROOT)}")
    print(f"I-cache image checked: {OUT_COMPILER_ICACHE_HEX.relative_to(ROOT)}")
    print(f"D-cache image checked: {OUT_COMPILER_DCACHE_HEX.relative_to(ROOT)}")
    print(f"testcase directories checked: {sample_count}")
    print(f"toolchain checked: {tools.gcc}")
    print(f"golden output all samples: {fc2.reshape(-1).tolist()}")
    print(f"sample 0 expected FC1: {fc1[0].tolist()}")


if __name__ == "__main__":
    main()
