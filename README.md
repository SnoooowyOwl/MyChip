# MyChip CV32E40P Accelerator Project

This repository contains a CV32E40P-based FPGA system with a memory-mapped
convolution / fully-connected accelerator, plus software workflows that map the
target CNN onto the fixed RTL.

## What Is Here

| Path | Purpose |
| --- | --- |
| `cv32e40p/` | CV32E40P RTL project, FPGA top, accelerator RTL, interface spec, testbench files, and assembly examples. |
| `cv32e40p/fpga/rtl/src/cv32e40p_xilinx.sv` | FPGA system top module. It instantiates the CPU, accelerator, SRAM regions, debug module, and bus integration. |
| `cv32e40p/fpga/rtl/src/accelerator_sim.sv` | Accelerator RTL implementation. |
| `cv32e40p/interface.txt` | Software-visible accelerator register interface, aligned to the RTL. |
| `python/network_structure.py` | Target quantized CNN structure. |
| `python/data/` and `python/sample_io.txt` | Quantized weights and sample input/output data. |
| `autogen/` | CNN software generation, compiler workflow, shared environment config, and generated SRAM images. |

More detailed RTL architecture notes are in `cv32e40p/README.md`.

## Environment

The RISC-V toolchain path is configured centrally in `autogen/project_config.py`.
On a new machine, set the xPack RISC-V toolchain root:

```sh
export RISCV_TOOLCHAIN_ROOT=/path/to/xpack-riscv-none-elf-gcc
python3 autogen/check_env.py
```

If the tool binaries are not under one common root, set them individually:

```sh
export RISCV_GCC=/path/to/riscv-none-elf-gcc
export RISCV_OBJCOPY=/path/to/riscv-none-elf-objcopy
export RISCV_OBJDUMP=/path/to/riscv-none-elf-objdump
python3 autogen/check_env.py
```

The current fallback default is:

```text
/data/yxx/tools/riscv/xpack-riscv-none-elf-gcc/xpack-riscv-none-elf-gcc-15.2.0-1
```

## Software Workflows

There are two supported workflows under `autogen/`.

### Manual Python Workflow

This path emits hand-scheduled RV32 assembly and SRAM initialization images:

```sh
python3 autogen/python/generate_cnn.py
python3 autogen/python/verify_cnn.py
```

Main outputs:

```text
autogen/python/out/cnn_accel_one_sample.S
autogen/python/out/icache_initial.hex
autogen/python/out/dcache_initial.hex
autogen/python/out/testcases/sample*/
```

Use this workflow when exact instruction scheduling and accelerator/DMA overlap
matter most.

### C Compiler Workflow

This path compiles the checked-in raw C CNN schedule:

```sh
python3 autogen/compiler/build_current_cnn.py
python3 autogen/compiler/verify_cnn.py
```

Main source and outputs:

```text
autogen/compiler/cnn_accel.c
autogen/compiler/accel_runtime.h
autogen/compiler/memory.ld
autogen/compiler/out/cnn_accel.S
autogen/compiler/out/icache_initial.hex
autogen/compiler/out/dcache_initial.hex
autogen/compiler/out/testcases/sample*/
```

Use this workflow for programmability. Handwritten freestanding C can be built
with:

```sh
python3 autogen/compiler/build_c_program.py \
  --c path/to/program.c \
  --dcache-asm autogen/compiler/out/dcache_init.S \
  --out-dir autogen/compiler/out/user_c
```

## RTL Simulation Inputs

The generated SRAM images are `$readmemh`-style files with one 32-bit word per
line and 2048 lines per 8 KiB SRAM image.

For the current generated sample 0, initialize:

```text
I-cache SRAM: autogen/python/out/icache_initial.hex
D-cache SRAM: autogen/python/out/dcache_initial.hex
```

or, for the C/compiler workflow:

```text
I-cache SRAM: autogen/compiler/out/icache_initial.hex
D-cache SRAM: autogen/compiler/out/dcache_initial.hex
```

The default final result byte address is `0x90000b20`. Current expected output
words are:

| Case | Expected word |
| --- | --- |
| sample0 | `0x000000b4` |
| sample1 | `0x000000ed` |
| sample2 | `0x000000bc` |
| sample3 | `0x0000009c` |
| sample4 | `0x00000000` |

## Useful Checks

Run these from the repository root:

```sh
python3 autogen/check_env.py
python3 autogen/python/verify_cnn.py
python3 autogen/compiler/verify_cnn.py
```

The verifiers check the Python golden model, accelerator mapping assumptions,
generated file freshness, SRAM image bounds, and that generated code is RV32IM
without compressed instructions.
