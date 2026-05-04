#!/usr/bin/env python3
"""Check project paths and RISC-V toolchain environment."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from autogen.project_config import PROJECT_ROOT, project_env_errors, resolve_riscv_toolchain, toolchain_help


def version_line(path) -> str:
    result = subprocess.run([str(path), "--version"], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return f"version check failed: {result.stderr.strip() or result.stdout.strip()}"
    return result.stdout.splitlines()[0]


def main() -> int:
    tools = resolve_riscv_toolchain()
    print(f"project root: {PROJECT_ROOT}")
    print(f"RISCV_TOOLCHAIN_ROOT: {tools.root}")
    print(f"RISCV_GCC: {tools.gcc}")
    print(f"RISCV_OBJCOPY: {tools.objcopy}")
    print(f"RISCV_OBJDUMP: {tools.objdump}")

    errors = project_env_errors()
    if errors:
        print("environment check failed:")
        for error in errors:
            print(f"- {error}")
        print(toolchain_help())
        return 1

    print(f"GCC version: {version_line(tools.gcc)}")
    print("environment check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
