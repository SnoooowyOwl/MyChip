"""Expected-output metadata for generated RTL simulation test cases."""

from __future__ import annotations

from .accelerator_regs import DCACHE_BASE
from .cnn_config import D_OUTPUT


def expected_output_metadata(sample_index: int, expected_byte: int) -> dict[str, int]:
    if not 0 <= expected_byte <= 0xFF:
        raise ValueError(f"expected byte out of uint8 range: {expected_byte}")

    byte_offset = D_OUTPUT - DCACHE_BASE
    byte_lane = byte_offset % 4
    word_addr = D_OUTPUT - byte_lane
    word_index = (word_addr - DCACHE_BASE) // 4
    expected_word = expected_byte << (byte_lane * 8)
    return {
        "sample_index": sample_index,
        "output_addr": D_OUTPUT,
        "dcache_word_addr": word_addr,
        "dcache_word_index": word_index,
        "dcache_hex_line_1_based": word_index + 1,
        "byte_lane": byte_lane,
        "expected_output_decimal": expected_byte,
        "expected_output_byte_hex": expected_byte,
        "expected_word_if_other_bytes_zero": expected_word,
    }


def expected_output_text(sample_index: int, expected_byte: int) -> str:
    meta = expected_output_metadata(sample_index, expected_byte)
    return "\n".join(
        [
            f"sample_index={meta['sample_index']}",
            f"output_addr=0x{meta['output_addr']:08X}",
            f"dcache_word_addr=0x{meta['dcache_word_addr']:08X}",
            f"dcache_word_index={meta['dcache_word_index']}",
            f"dcache_hex_line_1_based={meta['dcache_hex_line_1_based']}",
            f"byte_lane={meta['byte_lane']}",
            f"expected_output_decimal={meta['expected_output_decimal']}",
            f"expected_output_byte_hex=0x{meta['expected_output_byte_hex']:02X}",
            f"expected_word_if_other_bytes_zero=0x{meta['expected_word_if_other_bytes_zero']:08X}",
            "note=the program stores one byte with sb; the expected word assumes neighboring bytes are zero",
            "",
        ]
    )
