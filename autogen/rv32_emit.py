"""Plain RV32 assembly text emitter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


def u8(value: int) -> int:
    return value & 0xFF


def hex32(value: int) -> str:
    return f"0x{value & 0xFFFF_FFFF:08x}"


@dataclass
class Rv32Emitter:
    lines: list[str] = field(default_factory=list)

    def emit(self, line: str = "") -> None:
        self.lines.append(line)

    def comment(self, text: str) -> None:
        self.emit(f"    # {text}" if text else "")

    def label(self, name: str) -> None:
        self.emit(f"{name}:")

    def inst(self, op: str, *args: object, comment: str | None = None) -> None:
        body = f"    {op}"
        if args:
            body += " " + ", ".join(str(arg) for arg in args)
        if comment:
            body = f"{body:<40} # {comment}"
        self.emit(body)

    def li(self, rd: str, imm: int | str, comment: str | None = None) -> None:
        self.inst("li", rd, imm if isinstance(imm, str) else hex32(imm), comment=comment)

    def la(self, rd: str, label: str, comment: str | None = None) -> None:
        self.inst("la", rd, label, comment=comment)

    def call(self, label: str, comment: str | None = None) -> None:
        self.inst("call", label, comment=comment)

    def ret(self) -> None:
        self.inst("ret")

    def section(self, name: str) -> None:
        self.emit(f"    .section {name}")

    def align(self, value: int) -> None:
        self.emit(f"    .align {value}")

    def globl(self, name: str) -> None:
        self.emit(f"    .globl {name}")

    def byte_values(self, values: Iterable[int], per_line: int = 16) -> None:
        vals = [u8(v) for v in values]
        for idx in range(0, len(vals), per_line):
            chunk = vals[idx : idx + per_line]
            self.emit("    .byte " + ", ".join(f"0x{v:02x}" for v in chunk))

    def half_values(self, values: Iterable[int], per_line: int = 8) -> None:
        vals = [int(v) & 0xFFFF for v in values]
        for idx in range(0, len(vals), per_line):
            chunk = vals[idx : idx + per_line]
            self.emit("    .half " + ", ".join(f"0x{v:04x}" for v in chunk))

    def word_values(self, values: Iterable[int], per_line: int = 4) -> None:
        vals = [int(v) & 0xFFFF_FFFF for v in values]
        for idx in range(0, len(vals), per_line):
            chunk = vals[idx : idx + per_line]
            self.emit("    .word " + ", ".join(hex32(v) for v in chunk))

    def text(self) -> str:
        return "\n".join(self.lines).rstrip() + "\n"

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.text(), encoding="ascii")
