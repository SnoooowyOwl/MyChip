"""CNN dimensions and generated-program memory map."""

from __future__ import annotations

from pathlib import Path

from autogen.project_config import (
    DEFAULT_RISCV_GCC,
    DEFAULT_RISCV_OBJCOPY,
    DEFAULT_RISCV_OBJDUMP,
    DEFAULT_RISCV_TOOLCHAIN_ROOT,
)

from .accelerator_regs import DCACHE_BASE


ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = ROOT / "python"
DATA_DIR = PYTHON_DIR / "data"
OUT_DIR = ROOT / "autogen" / "python" / "out"
OUT_ASM = OUT_DIR / "cnn_accel_one_sample.S"
OUT_ICACHE_HEX = OUT_DIR / "icache_initial.hex"
OUT_DCACHE_HEX = OUT_DIR / "dcache_initial.hex"
OUT_TESTCASES_DIR = OUT_DIR / "testcases"

DEFAULT_TOOLCHAIN_ROOT = DEFAULT_RISCV_TOOLCHAIN_ROOT
LINK_TEXT_BASE = 0x8000_0000

INPUT_H = 16
INPUT_W = 15
ROW_STRIDE = 16

CONV1_COUT = 10
CONV1_H = 14
CONV1_W = 13
CONV1_ROW_STRIDE = 16
CONV1_CH_BYTES = CONV1_H * CONV1_ROW_STRIDE

CONV2_H = 12
CONV2_W = 11
CONV2_ROW_STRIDE = 16

FC1_IN = 132
FC1_OUT = 10
FC_CHUNK = 36
FC1_CHUNKS = 4

D_INPUT = DCACHE_BASE + 0x000
D_CONV1 = DCACHE_BASE + 0x100
D_CONV2 = DCACHE_BASE + 0xA00
D_FC1 = DCACHE_BASE + 0xB00

# User-configurable final-result byte address.
# The generated program stores the final uint8 CNN result here with `sb`.
# Keep it inside the 8 KiB D-cache window and away from the buffers below.
OUTPUT_ADDR = DCACHE_BASE + 0xB20
D_OUTPUT = OUTPUT_ADDR

D_SCRATCH = DCACHE_BASE + 0xB40
D_ACCUM = DCACHE_BASE + 0xB80
D_CONST = DCACHE_BASE + 0xE00
D_STACK_TOP = DCACHE_BASE + 0x1FFC
D_STACK_GUARD_BYTES = 0x100

SRAM_WINDOW_BYTES = 0x2000
COMBINED_SRAM_WINDOW_BYTES = 0x4000
DMA_WAIT_NOPS = 10


def testcase_dir(sample_index: int) -> Path:
    return OUT_TESTCASES_DIR / f"sample{sample_index}"


def testcase_paths(sample_index: int) -> tuple[Path, Path, Path, Path]:
    case_dir = testcase_dir(sample_index)
    return (
        case_dir / f"cnn_accel_sample{sample_index}.S",
        case_dir / "icache_initial.hex",
        case_dir / "dcache_initial.hex",
        case_dir / "expected.txt",
    )
