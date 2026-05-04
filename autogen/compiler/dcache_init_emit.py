"""Emit D-cache initialization assembly for preloaded input and packed weights."""

from __future__ import annotations

from collections.abc import Iterable

from .accelerator_regs import DCACHE_BASE, u8
from .cnn_config import D_CONST, D_INPUT


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFF_FFFF:08x}"


def emit_byte_values(values: Iterable[int], per_line: int = 16) -> list[str]:
    vals = [u8(v) for v in values]
    lines: list[str] = []
    for idx in range(0, len(vals), per_line):
        chunk = vals[idx : idx + per_line]
        lines.append("    .byte " + ", ".join(f"0x{v:02x}" for v in chunk))
    return lines


def emit_word_values(values: Iterable[int], per_line: int = 4) -> list[str]:
    vals = [int(v) & 0xFFFF_FFFF for v in values]
    lines: list[str] = []
    for idx in range(0, len(vals), per_line):
        chunk = vals[idx : idx + per_line]
        lines.append("    .word " + ", ".join(hex32(v) for v in chunk))
    return lines


def emit_dcache_init_assembly(rodata: dict[str, list[int]], *, global_labels: bool = True) -> str:
    lines: list[str] = [
        '    .section .dcache_init,"aw"',
        "    .align 2",
        f"    .org 0x{D_INPUT - DCACHE_BASE:x}",
    ]
    if global_labels:
        lines.append("    .globl input0_padded")
    lines.append("input0_padded:")
    lines.extend(emit_byte_values(rodata["input0_padded"]))
    lines.extend(["", "    .align 2", f"    .org 0x{D_CONST - DCACHE_BASE:x}"])

    for label in ("conv1_w_packed", "conv2_w_packed", "fc1_w_packed", "fc2_w_packed"):
        if global_labels:
            lines.append(f"    .globl {label}")
        lines.append(f"{label}:")
        lines.extend(emit_word_values(rodata[label]))
        lines.extend(["", "    .align 2"])

    return "\n".join(lines).rstrip() + "\n"
