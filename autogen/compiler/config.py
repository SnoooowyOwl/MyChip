"""Compiler workflow configuration."""

from __future__ import annotations

from pathlib import Path


COMPILER_DIR = Path(__file__).resolve().parent
RUNTIME_INCLUDE_DIR = COMPILER_DIR
CNN_C_SOURCE = COMPILER_DIR / "cnn_accel.c"
COMPILER_CFLAGS = (
    "-Os",
    "-fno-jump-tables",
    "-fno-tree-loop-distribute-patterns",
)
