"""Project-wide paths and environment configuration.

The RISC-V toolchain can be configured either with RISCV_TOOLCHAIN_ROOT or with
the individual RISCV_GCC, RISCV_OBJCOPY, and RISCV_OBJDUMP environment
variables. Individual tool variables take precedence over RISCV_TOOLCHAIN_ROOT.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RISCV_TOOLCHAIN_ROOT = Path(
    "/data/yxx/tools/riscv/xpack-riscv-none-elf-gcc/xpack-riscv-none-elf-gcc-15.2.0-1"
)
RISCV_PREFIX = "riscv-none-elf"
DEFAULT_RISCV_GCC = DEFAULT_RISCV_TOOLCHAIN_ROOT / "bin" / f"{RISCV_PREFIX}-gcc"
DEFAULT_RISCV_OBJCOPY = DEFAULT_RISCV_TOOLCHAIN_ROOT / "bin" / f"{RISCV_PREFIX}-objcopy"
DEFAULT_RISCV_OBJDUMP = DEFAULT_RISCV_TOOLCHAIN_ROOT / "bin" / f"{RISCV_PREFIX}-objdump"

PYTHON_MODEL_DIR = PROJECT_ROOT / "python"
CNN_DATA_FILES = (
    PYTHON_MODEL_DIR / "network_structure.py",
    PYTHON_MODEL_DIR / "sample_io.txt",
    PYTHON_MODEL_DIR / "data" / "conv1_weight.txt",
    PYTHON_MODEL_DIR / "data" / "conv2_weight.txt",
    PYTHON_MODEL_DIR / "data" / "fc1_weight.txt",
    PYTHON_MODEL_DIR / "data" / "fc2_weight.txt",
)


@dataclass(frozen=True)
class RiscvToolchain:
    root: Path
    gcc: Path
    objcopy: Path
    objdump: Path


def _env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if value:
        return Path(os.path.expandvars(value)).expanduser()
    return default


def resolve_riscv_toolchain() -> RiscvToolchain:
    root = _env_path("RISCV_TOOLCHAIN_ROOT", DEFAULT_RISCV_TOOLCHAIN_ROOT)
    bin_dir = root / "bin"
    return RiscvToolchain(
        root=root,
        gcc=_env_path("RISCV_GCC", bin_dir / f"{RISCV_PREFIX}-gcc"),
        objcopy=_env_path("RISCV_OBJCOPY", bin_dir / f"{RISCV_PREFIX}-objcopy"),
        objdump=_env_path("RISCV_OBJDUMP", bin_dir / f"{RISCV_PREFIX}-objdump"),
    )


def riscv_toolchain_errors(tools: RiscvToolchain | None = None) -> list[str]:
    tools = tools or resolve_riscv_toolchain()
    errors: list[str] = []
    for label, path in (
        ("RISCV_GCC", tools.gcc),
        ("RISCV_OBJCOPY", tools.objcopy),
        ("RISCV_OBJDUMP", tools.objdump),
    ):
        if not path.exists():
            errors.append(f"{label} not found: {path}")
        elif not path.is_file():
            errors.append(f"{label} is not a file: {path}")
        elif not os.access(path, os.X_OK):
            errors.append(f"{label} is not executable: {path}")
    return errors


def project_file_errors() -> list[str]:
    errors: list[str] = []
    for path in CNN_DATA_FILES:
        if not path.exists():
            errors.append(f"required project file not found: {path}")
        elif not path.is_file():
            errors.append(f"required project path is not a file: {path}")
    return errors


def project_env_errors() -> list[str]:
    return [*project_file_errors(), *riscv_toolchain_errors()]


def toolchain_help() -> str:
    return (
        "Set RISCV_TOOLCHAIN_ROOT to the xPack RISC-V toolchain root, or set "
        "RISCV_GCC, RISCV_OBJCOPY, and RISCV_OBJDUMP individually."
    )
