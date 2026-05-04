# Manual Python Workflow

This folder contains the low-level Python codegen workflow for the CNN in
`../../python/network_structure.py`.

## Environment

Project-wide environment defaults live in `../project_config.py`. On a new
machine, set the RISC-V toolchain root and run the environment check from the
repository root:

```sh
export RISCV_TOOLCHAIN_ROOT=/path/to/xpack-riscv-none-elf-gcc
python3 autogen/check_env.py
```

You can also set `RISCV_GCC`, `RISCV_OBJCOPY`, and `RISCV_OBJDUMP`
individually; those override `RISCV_TOOLCHAIN_ROOT`.

Run from the repository root:

```sh
python3 autogen/python/generate_cnn.py
python3 autogen/python/verify_cnn.py
```

Generated files are written under `autogen/python/out/`:

| Path | Purpose |
| --- | --- |
| `out/cnn_accel_one_sample.S` | Raw RV32 assembly for sample 0. |
| `out/icache_initial.hex` | I-cache SRAM initialization image for sample 0. |
| `out/dcache_initial.hex` | D-cache SRAM initialization image for sample 0. |
| `out/testcases/sample*/` | Per-sample assembly, SRAM images, and expected output metadata. |

Important source files:

| Path | Purpose |
| --- | --- |
| `../project_config.py` | Project-wide path defaults and RISC-V toolchain environment resolution. |
| `../check_env.py` | Environment checker for required model files and RISC-V toolchain executables. |
| `cnn_config.py` | CNN dimensions, D-cache layout, output address, DMA wait count, and toolchain paths. |
| `accelerator_api.py` | APIs that emit RV32 accelerator register sequences. |
| `cnn_top_emit.py` | Hand-scheduled CNN mapping using the accelerator APIs. |
| `mapping_plan.md` | Layer mapping strategy and optimization notes. |

This workflow emits RV32IM only; compressed instructions are disabled. It is the
highest-control path and contains the hand scheduling used to overlap row DMA
with CONV computation where the fixed RTL allows it.
