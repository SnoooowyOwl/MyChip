"""Shared accelerator register constants and data packing helpers."""

from __future__ import annotations

from typing import Sequence


ACC_BASE = 0x7000_0000
DCACHE_BASE = 0x9000_0000

CMD_START_CONV = 0x0000_FFFF
CMD_START_FC = 0x000F_FFFF
CMD_RESET_PSUMS = 0x0FFF_FFFF
CMD_GLOBAL_RESET = 0xFFFF_FFFF
CMD_SHIFT_LINES = 0x0000_0200

OFF_CTRL_STATUS = 0
OFF_SRC_ADDR = 4

OFF_W0_0_3 = 52
OFF_W0_4_7 = 56
OFF_W0_8 = 60
OFF_W1_0_3 = 64
OFF_W1_4_7 = 68
OFF_W1_8 = 72
OFF_W2_0_3 = 76
OFF_W2_4_7 = 80
OFF_W2_8 = 84
OFF_W3_0_3 = 88
OFF_W3_4_7 = 92
OFF_W3_8 = 96

OFF_RES_PACK_0 = 100
OFF_RES_PACK_1 = 104
OFF_RES_PACK_2 = 108
OFF_RES_PACK_3 = 112
OFF_RAW_BASE = 120

WEIGHT_REG_OFFSETS = (
    OFF_W0_0_3,
    OFF_W0_4_7,
    OFF_W0_8,
    OFF_W1_0_3,
    OFF_W1_4_7,
    OFF_W1_8,
    OFF_W2_0_3,
    OFF_W2_4_7,
    OFF_W2_8,
    OFF_W3_0_3,
    OFF_W3_4_7,
    OFF_W3_8,
)

IMPLEMENTED_ACCEL_OFFSETS = {
    OFF_CTRL_STATUS,
    OFF_SRC_ADDR,
    *WEIGHT_REG_OFFSETS,
    OFF_RES_PACK_0,
    OFF_RES_PACK_1,
    OFF_RES_PACK_2,
    OFF_RES_PACK_3,
    *[OFF_RAW_BASE + idx * 4 for idx in range(14)],
}


def u8(value: int) -> int:
    return value & 0xFF


def pack_i8_word(values: Sequence[int]) -> int:
    """Pack up to four signed/unsigned byte values little-endian into a word."""

    if len(values) > 4:
        raise ValueError("at most four byte values can be packed into one word")
    word = 0
    for idx, value in enumerate(values):
        word |= u8(int(value)) << (8 * idx)
    return word
