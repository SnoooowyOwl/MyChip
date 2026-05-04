"""Accelerator register API and reusable accelerator runtime helpers."""

from __future__ import annotations

from typing import Sequence

try:
    from .rv32_emit import Rv32Emitter, u8
except ImportError:  # Allows direct imports from the autogen directory.
    from rv32_emit import Rv32Emitter, u8  # type: ignore


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


def pack_i8_word(values: Sequence[int]) -> int:
    """Pack up to four signed/unsigned byte values little-endian into a word."""

    if len(values) > 4:
        raise ValueError("at most four byte values can be packed into one word")
    word = 0
    for idx, value in enumerate(values):
        word |= u8(int(value)) << (8 * idx)
    return word


class AcceleratorAPI:
    """Python-side API that emits RV32 sequences for accelerator operations."""

    def __init__(self, emitter: Rv32Emitter, acc_reg: str = "s0") -> None:
        self.e = emitter
        self.acc = acc_reg

    def write_command(self, command: int, tmp: str = "t0", comment: str | None = None) -> None:
        self.e.li(tmp, command, comment=comment)
        self.e.inst("sw", tmp, f"{OFF_CTRL_STATUS}({self.acc})")

    def global_reset(self) -> None:
        self.write_command(CMD_GLOBAL_RESET, comment="GLOBAL_RESET")

    def reset_psums(self) -> None:
        self.write_command(CMD_RESET_PSUMS, comment="RESET_PSUMS")

    def shift_lines(self) -> None:
        self.write_command(CMD_SHIFT_LINES, comment="SHIFT_LINES")

    def start_conv(self) -> None:
        self.write_command(CMD_START_CONV, comment="START_CONV")

    def start_fc(self) -> None:
        self.write_command(CMD_START_FC, comment="START_FC")

    def set_dma_addr(self, addr_reg: str) -> None:
        self.e.inst("sw", addr_reg, f"{OFF_SRC_ADDR}({self.acc})", comment="SET_DMA_ADDR")

    def read_conv_packed(self, dst_reg: str, pack_idx: int) -> None:
        offsets = (OFF_RES_PACK_0, OFF_RES_PACK_1, OFF_RES_PACK_2, OFF_RES_PACK_3)
        self.e.inst("lw", dst_reg, f"{offsets[pack_idx]}({self.acc})")

    def read_conv_raw(self, dst_reg: str, raw_idx: int) -> None:
        if not 0 <= raw_idx < 14:
            raise ValueError("raw convolution result index must be 0..13")
        self.e.inst("lw", dst_reg, f"{OFF_RAW_BASE + raw_idx * 4}({self.acc})")

    def read_fc_raw(self, dst_reg: str) -> None:
        self.e.inst("lw", dst_reg, f"{OFF_RES_PACK_0}({self.acc})")

    def write_conv_weights_from_ptr(self, ptr_reg: str) -> None:
        self.e.inst("lw", "t0", f"0({ptr_reg})")
        self.e.inst("sw", "t0", f"{OFF_W0_0_3}({self.acc})")
        self.e.inst("lw", "t0", f"4({ptr_reg})")
        self.e.inst("sw", "t0", f"{OFF_W0_4_7}({self.acc})")
        self.e.inst("lw", "t0", f"8({ptr_reg})")
        self.e.inst("sw", "t0", f"{OFF_W0_8}({self.acc})")

    def write_fc_weights_from_ptr(self, ptr_reg: str) -> None:
        for idx, offset in enumerate(WEIGHT_REG_OFFSETS):
            self.e.inst("lw", "t0", f"{idx * 4}({ptr_reg})")
            self.e.inst("sw", "t0", f"{offset}({self.acc})")

    def wait_done_inline(self, label: str = "acc_wait_done_inline") -> None:
        self.e.label(label)
        self.e.inst("lw", "t0", f"{OFF_CTRL_STATUS}({self.acc})")
        self.e.inst("li", "t1", "1")
        self.e.inst("bne", "t0", "t1", label)

    def emit_runtime_helpers(self, dma_wait_nops: int = 16) -> None:
        """Emit accelerator-only helper labels used by the top schedule."""

        e = self.e
        acc = self.acc
        e.comment(f"Accelerator runtime helpers. {acc} must hold ACCELERATOR_BASE.")

        e.label("acc_wait_done")
        e.inst("lw", "t0", f"{OFF_CTRL_STATUS}({acc})")
        e.inst("li", "t1", "1")
        e.inst("bne", "t0", "t1", "acc_wait_done")
        e.ret()
        e.emit()

        e.label("acc_reset_psums")
        self.reset_psums()
        e.ret()
        e.emit()

        e.label("acc_start_conv")
        self.start_conv()
        e.ret()
        e.emit()

        e.label("acc_start_fc")
        self.start_fc()
        e.ret()
        e.emit()

        e.label("acc_shift_lines")
        self.shift_lines()
        e.ret()
        e.emit()

        e.label("acc_set_dma_addr")
        self.set_dma_addr("a0")
        e.ret()
        e.emit()

        e.label("acc_dma_shift")
        self.set_dma_addr("a0")
        for _ in range(dma_wait_nops):
            e.inst("nop")
        self.shift_lines()
        e.ret()
        e.emit()

        e.label("acc_load_three_rows")
        e.inst("addi", "sp", "sp", "-16")
        e.inst("sw", "ra", "12(sp)")
        e.inst("sw", "a0", "0(sp)")
        e.inst("sw", "a1", "4(sp)")
        e.inst("lw", "a0", "0(sp)")
        e.call("acc_dma_shift")
        e.inst("lw", "t0", "0(sp)")
        e.inst("lw", "t1", "4(sp)")
        e.inst("add", "a0", "t0", "t1")
        e.call("acc_dma_shift")
        e.inst("lw", "t0", "0(sp)")
        e.inst("lw", "t1", "4(sp)")
        e.inst("add", "a0", "t0", "t1")
        e.inst("add", "a0", "a0", "t1")
        e.call("acc_dma_shift")
        e.inst("lw", "ra", "12(sp)")
        e.inst("addi", "sp", "sp", "16")
        e.ret()
        e.emit()

        e.label("acc_write_conv_w0")
        self.write_conv_weights_from_ptr("a0")
        e.ret()
        e.emit()

        e.label("acc_write_fc_weights")
        self.write_fc_weights_from_ptr("a0")
        e.ret()
        e.emit()
