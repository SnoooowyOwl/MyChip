"""Build fixed-size SRAM initialization images from generated RV32 sources."""

from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from autogen.project_config import resolve_riscv_toolchain, riscv_toolchain_errors, toolchain_help

from .cnn_config import (
    DCACHE_BASE,
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


@dataclass(frozen=True)
class SourceText:
    name: str
    text: str


def configured_toolchain() -> Toolchain:
    tools = resolve_riscv_toolchain()
    return Toolchain(
        gcc=tools.gcc,
        objcopy=tools.objcopy,
        objdump=tools.objdump,
    )


def require_toolchain(tools: Toolchain) -> None:
    errors = riscv_toolchain_errors(tools)
    if errors:
        details = "\n".join(f"- {error}" for error in errors)
        raise FileNotFoundError(f"RISC-V toolchain is not configured correctly:\n{details}\n{toolchain_help()}\nRun `python3 autogen/check_env.py` for a full environment check.")


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
    *(.text.start .text.start.*)
    *(.text .text.*)
    *(.srodata .srodata.*)
    *(.rodata .rodata.*)
  }} > ICACHE

  .dcache_init : ALIGN(4)
  {{
    *(.dcache_init)
  }} > DCACHE

  .data : ALIGN(4)
  {{
    *(.sdata .sdata.*)
    *(.data .data.*)
  }} > DCACHE

  .bss (NOLOAD) : ALIGN(4)
  {{
    *(.sbss .sbss.*)
    *(.bss .bss.*)
    *(COMMON)
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
  ASSERT(SIZEOF(.data) == 0, "unexpected initialized .data; put constants in .dcache_init")
  ASSERT(SIZEOF(.bss) == 0, "unexpected .bss; use explicit D-cache addresses")
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


def common_riscv_flags() -> list[str]:
    return [
        f"-march={RISCV_ARCH}",
        "-mabi=ilp32",
        "-mcmodel=medany",
        "-ffreestanding",
        "-fno-builtin",
        "-fno-common",
        "-fno-pic",
        "-fno-stack-protector",
        "-fno-asynchronous-unwind-tables",
        "-fno-unwind-tables",
    ]


def link_riscv_sources(
    source_files: Sequence[SourceText],
    *,
    extra_cflags: Sequence[str] = (),
    include_dirs: Sequence[Path] = (),
) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
    tools = configured_toolchain()
    require_toolchain(tools)

    tmp = tempfile.TemporaryDirectory(prefix="cnn_accel_image_")
    tmpdir = Path(tmp.name)
    linker_path = tmpdir / "memory.ld"
    elf_path = tmpdir / "cnn_accel_one_sample.elf"

    linker_path.write_text(linker_script(), encoding="ascii")
    source_paths: list[Path] = []
    for source in source_files:
        path = tmpdir / source.name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source.text, encoding="ascii")
        source_paths.append(path)

    link_cmd = [
        str(tools.gcc),
        *common_riscv_flags(),
        *extra_cflags,
        "-nostdlib",
        "-nostartfiles",
        "-Wl,--no-relax",
        f"-Wl,-T,{linker_path}",
        "-Wl,-e,_start",
        *[f"-I{path}" for path in include_dirs],
        *[str(path) for path in source_paths],
        "-o",
        str(elf_path),
    ]
    run_checked(link_cmd, "RISC-V link")
    return elf_path, tmp


def extract_memory_images(elf_path: Path) -> MemoryImages:
    tools = configured_toolchain()
    require_toolchain(tools)
    tmpdir = elf_path.parent
    icache_bin = tmpdir / "icache.bin"
    dcache_bin = tmpdir / "dcache.bin"

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


def build_memory_images_from_sources(
    source_files: Sequence[SourceText],
    *,
    extra_cflags: Sequence[str] = (),
    include_dirs: Sequence[Path] = (),
) -> MemoryImages:
    elf_path, tmp = link_riscv_sources(source_files, extra_cflags=extra_cflags, include_dirs=include_dirs)
    try:
        return extract_memory_images(elf_path)
    finally:
        tmp.cleanup()


def compile_c_to_assembly(
    c_source: SourceText,
    *,
    extra_cflags: Sequence[str] = (),
    include_dirs: Sequence[Path] = (),
) -> str:
    tools = configured_toolchain()
    require_toolchain(tools)

    with tempfile.TemporaryDirectory(prefix="cnn_accel_asm_") as tmp:
        tmpdir = Path(tmp)
        c_path = tmpdir / c_source.name
        asm_path = tmpdir / f"{Path(c_source.name).stem}.S"
        c_path.write_text(c_source.text, encoding="ascii")

        asm_cmd = [
            str(tools.gcc),
            *common_riscv_flags(),
            *extra_cflags,
            *[f"-I{path}" for path in include_dirs],
            "-S",
            str(c_path),
            "-o",
            str(asm_path),
        ]
        run_checked(asm_cmd, "RISC-V C-to-assembly")
        return sanitize_compiler_assembly(asm_path.read_text(encoding="ascii"))


def sanitize_compiler_assembly(assembly: str) -> str:
    return re.sub(r'"/tmp/cnn_accel_asm_[^/]+/([^"]+)"', r'"\1"', assembly)


def build_memory_images(asm_text: str) -> MemoryImages:
    return build_memory_images_from_sources([SourceText("cnn_accel_one_sample.S", asm_text)])


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
