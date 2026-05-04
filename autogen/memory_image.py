"""Build fixed-size SRAM initialization images from generated RV32 assembly."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .cnn_config import (
    DCACHE_BASE,
    DEFAULT_RISCV_GCC,
    DEFAULT_RISCV_OBJCOPY,
    DEFAULT_RISCV_OBJDUMP,
    LINK_TEXT_BASE,
    SRAM_WINDOW_BYTES,
)


WORD_BYTES = 4
SRAM_WORDS = SRAM_WINDOW_BYTES // WORD_BYTES
ICACHE_SECTION = ".text"
DCACHE_SECTION = ".dcache_init"
RISCV_ARCH = "rv32im"


@dataclass(frozen=True)
class Toolchain:
    gcc: Path
    objcopy: Path
    objdump: Path


@dataclass(frozen=True)
class MemoryImages:
    icache_bytes: bytes
    dcache_bytes: bytes
    objdump_header: str
    objdump_disassembly: str


def configured_toolchain() -> Toolchain:
    return Toolchain(
        gcc=Path(os.environ.get("RISCV_GCC", str(DEFAULT_RISCV_GCC))),
        objcopy=Path(os.environ.get("RISCV_OBJCOPY", str(DEFAULT_RISCV_OBJCOPY))),
        objdump=Path(os.environ.get("RISCV_OBJDUMP", str(DEFAULT_RISCV_OBJDUMP))),
    )


def require_toolchain(tools: Toolchain) -> None:
    for name, path in (("RISC-V GCC", tools.gcc), ("RISC-V objcopy", tools.objcopy), ("RISC-V objdump", tools.objdump)):
        if not path.exists():
            raise FileNotFoundError(f"{name} not found: {path}")


def linker_script() -> str:
    return f"""OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{{
  ICACHE (rx)  : ORIGIN = 0x{LINK_TEXT_BASE:08x}, LENGTH = 8K
  DCACHE (rw)  : ORIGIN = 0x{DCACHE_BASE:08x}, LENGTH = 8K
}}

SECTIONS
{{
  .text : ALIGN(4)
  {{
    *(.text .text.*)
  }} > ICACHE

  .dcache_init : ALIGN(4)
  {{
    *(.dcache_init)
  }} > DCACHE

  /DISCARD/ :
  {{
    *(.riscv.attributes)
    *(.comment)
    *(.note*)
    *(.eh_frame*)
  }}

  ASSERT(SIZEOF(.text) <= LENGTH(ICACHE), "I-cache image exceeds 8 KiB")
  ASSERT(SIZEOF(.dcache_init) <= LENGTH(DCACHE), "D-cache image exceeds 8 KiB")
}}
"""


def run_checked(cmd: list[str], what: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(cmd, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"{what} failed\n"
            f"command: {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def build_memory_images(asm_text: str) -> MemoryImages:
    tools = configured_toolchain()
    require_toolchain(tools)

    with tempfile.TemporaryDirectory(prefix="cnn_accel_image_") as tmp:
        tmpdir = Path(tmp)
        asm_path = tmpdir / "cnn_accel_one_sample.S"
        linker_path = tmpdir / "memory.ld"
        elf_path = tmpdir / "cnn_accel_one_sample.elf"
        icache_bin = tmpdir / "icache.bin"
        dcache_bin = tmpdir / "dcache.bin"

        asm_path.write_text(asm_text, encoding="ascii")
        linker_path.write_text(linker_script(), encoding="ascii")

        link_cmd = [
            str(tools.gcc),
            f"-march={RISCV_ARCH}",
            "-mabi=ilp32",
            "-nostdlib",
            "-nostartfiles",
            "-Wl,--no-relax",
            f"-Wl,-T,{linker_path}",
            "-Wl,-e,_start",
            str(asm_path),
            "-o",
            str(elf_path),
        ]
        run_checked(link_cmd, "RISC-V link")

        dump_cmd = [
            str(tools.objcopy),
            "--dump-section",
            f"{ICACHE_SECTION}={icache_bin}",
            "--dump-section",
            f"{DCACHE_SECTION}={dcache_bin}",
            str(elf_path),
        ]
        run_checked(dump_cmd, "RISC-V section extraction")

        objdump_cmd = [str(tools.objdump), "-h", str(elf_path)]
        objdump = run_checked(objdump_cmd, "RISC-V objdump")
        disasm_cmd = [str(tools.objdump), "-d", str(elf_path)]
        disasm = run_checked(disasm_cmd, "RISC-V disassembly")

        return MemoryImages(
            icache_bytes=pad_sram_image(icache_bin.read_bytes(), "I-cache"),
            dcache_bytes=pad_sram_image(dcache_bin.read_bytes(), "D-cache"),
            objdump_header=objdump.stdout,
            objdump_disassembly=disasm.stdout,
        )


def pad_sram_image(data: bytes, name: str) -> bytes:
    if len(data) > SRAM_WINDOW_BYTES:
        raise ValueError(f"{name} image exceeds {SRAM_WINDOW_BYTES} bytes: {len(data)}")
    return data + bytes(SRAM_WINDOW_BYTES - len(data))


def bytes_to_hex_words(data: bytes) -> str:
    if len(data) != SRAM_WINDOW_BYTES:
        raise ValueError(f"expected exactly {SRAM_WINDOW_BYTES} bytes, got {len(data)}")
    lines: list[str] = []
    for offset in range(0, SRAM_WINDOW_BYTES, WORD_BYTES):
        word = int.from_bytes(data[offset : offset + WORD_BYTES], byteorder="little", signed=False)
        lines.append(f"{word:08X}")
    return "\n".join(lines) + "\n"


def write_hex_image(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(bytes_to_hex_words(data), encoding="ascii")


def parse_hex_image(path: Path) -> bytes:
    lines = path.read_text(encoding="ascii").splitlines()
    if len(lines) != SRAM_WORDS:
        raise ValueError(f"{path} has {len(lines)} lines, expected {SRAM_WORDS}")
    data = bytearray()
    for line_no, line in enumerate(lines, start=1):
        token = line.strip()
        if len(token) != 8:
            raise ValueError(f"{path}:{line_no}: expected 8 hex digits")
        try:
            word = int(token, 16)
        except ValueError as exc:
            raise ValueError(f"{path}:{line_no}: invalid hex word {token!r}") from exc
        data.extend(word.to_bytes(WORD_BYTES, byteorder="little", signed=False))
    return bytes(data)
