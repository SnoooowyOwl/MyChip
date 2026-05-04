# CV32E40P Accelerator Project File Architecture

This directory contains a CV32E40P-based FPGA system with a memory-mapped
convolution / fully-connected accelerator.

## Key Files

| Path | Role |
| --- | --- |
| `fpga/rtl/src/cv32e40p_xilinx.sv` | FPGA system top module and AXI bus integration. This file instantiates the CPU, debug module, memories, accelerator slave interface, and accelerator AXI read-master bridge. |
| `fpga/rtl/src/accelerator_sim.sv` | Accelerator RTL. Contains the `accelerator` memory-mapped module and the `conv_core` compute block. |
| `interface.txt` | Software-visible accelerator register/interface specification, aligned to `accelerator_sim.sv`. |
| `examples/testcode/conv_mode.S` | Example RISC-V assembly sequence for convolution mode. |
| `examples/testcode/fc_mode.S` | Example RISC-V assembly sequence for fully-connected mode. |
| `fpga/tb/cv32e40p_xilinx_tb.sv` | FPGA top-level testbench. |
| `fpga/tb/icache_initial.hex` | Instruction memory initialization image used by the FPGA testbench/system. |
| `fpga/tb/dcache_initial.hex` | Data memory initialization image used by the FPGA testbench/system. |

## Directory Layout

```text
cv32e40p/
|-- README.md
|-- README.pdf
|-- interface.txt
|-- examples/
|   `-- testcode/
|       |-- conv_mode.S
|       `-- fc_mode.S
|-- fpga/
|   |-- rtl/
|   |   |-- include/
|   |   `-- src/
|   |       |-- cv32e40p_xilinx.sv
|   |       |-- accelerator_sim.sv
|   |       |-- axi_*.sv
|   |       |-- axi2mem.sv
|   |       |-- bootram.sv
|   |       |-- dm_*.sv
|   |       |-- dmi_*.sv
|   |       |-- rstgen*.sv
|   |       `-- support cells and packages
|   `-- tb/
|       |-- cv32e40p_xilinx_tb.sv
|       |-- icache_initial.hex
|       |-- dcache_initial.hex
|       `-- deprecated/
|-- rtl/
|   |-- include/
|   |   |-- cv32e40p_pkg.sv
|   |   |-- cv32e40p_apu_core_pkg.sv
|   |   `-- cv32e40p_fpu_pkg.sv
|   |-- cv32e40p_top.sv
|   |-- cv32e40p_core.sv
|   |-- cv32e40p_*.sv
|   `-- vendor/
|       |-- pulp_platform_common_cells/
|       `-- pulp_platform_fpnew/
`-- bhv/
    |-- cv32e40p_tb_wrapper.sv
    |-- cv32e40p_tracer.sv
    |-- cv32e40p_rvfi*.sv
    `-- simulation and trace helpers
```

## FPGA System Integration

`fpga/rtl/src/cv32e40p_xilinx.sv` is the system-level integration point.

Main address regions:

| Region | Base | Purpose |
| --- | --- | --- |
| ROM | `0x00010000` | Boot/instruction memory region. |
| SRAM / I-cache region | `0x80000000` | Main SRAM-mapped region. |
| Accelerator | `0x70000000` | Memory-mapped accelerator slave registers. |
| D-cache data region | `0x90000000` | Data memory region used by examples and DMA source reads. |
| Debug module | `0x00000000` to `0x00001000` | Debug module access region. |

The accelerator is connected in two ways:

- As an AXI slave through `axi2mem`, exposing its software-visible registers.
- As an AXI read master through the custom bridge around `acc_axi_m_req`, so the
  accelerator can fetch input rows from memory after software writes `SRC_ADDR`.

## Accelerator RTL

`fpga/rtl/src/accelerator_sim.sv` contains:

- `conv_core`: one 3x3 MAC datapath. Inputs are unsigned int8; weights are
  signed int8; raw output is signed int32; packed output applies ReLU and keeps
  the low 8 bits.
- `accelerator`: memory-mapped control/status, weight registers, result
  registers, line buffers, prefetch buffer, compute state machine, and AXI
  read-DMA state machine.

Important implemented behavior:

- Register base is `0x70000000`.
- `SRC_ADDR` is at offset `0x004`.
- There is no implemented `BASE+8` read-length register.
- DMA reads are fixed at 4 AXI beats, 4 bytes per beat, for 16 bytes total.
- Convolution mode uses weight group 0 and computes 14 adjacent 3x3 windows.
- FC mode uses weight groups 0, 1, 2, and 3 across four cycles and returns a
  single signed 32-bit result.

See `interface.txt` for the full software-visible register map.

## Software Examples

Example assembly lives under `examples/testcode/`.

- `conv_mode.S` writes weight group 0, streams rows through the line buffer,
  starts convolution mode, polls `STATUS`, and stores packed convolution results.
- `fc_mode.S` writes all four weight groups, streams rows through the line
  buffer, starts FC mode, polls `STATUS`, and stores the 32-bit FC result.

## CNN Autogen Flow

The CNN software framework lives outside this directory under `../autogen/`.
That directory contains two workflow folders plus shared environment helpers:

- `../autogen/python/`: manual Python codegen that emits low-level RV32
  assembly and SRAM images.
- `../autogen/compiler/`: C/compiler workflow that compiles a checked-in
  freestanding C schedule for the current CNN.
- `../autogen/project_config.py` and `../autogen/check_env.py`: shared
  environment configuration and validation.

Both workflows map the quantized model in `../python/network_structure.py` onto
the fixed accelerator RTL without changing hardware.

Important files:

| Path | Role |
| --- | --- |
| `../autogen/project_config.py` | Project-wide path defaults and RISC-V toolchain environment resolution. |
| `../autogen/check_env.py` | Environment checker for required model files and RISC-V toolchain executables. |
| `../autogen/python/cnn_config.py` | Manual workflow CNN dimensions, memory layout, output address, DMA wait count, and toolchain paths. |
| `../autogen/python/accelerator_api.py` | Python API layer that emits manual RV32 accelerator register sequences. |
| `../autogen/python/cnn_top_emit.py` | Manual low-level CNN schedule emitter. |
| `../autogen/python/generate_cnn.py` | Manual low-level assembly generation entry point. |
| `../autogen/python/verify_cnn.py` | Manual workflow reference-model, codegen, SRAM-image, and toolchain verification. |
| `../autogen/python/mapping_plan.md` | CNN-to-accelerator mapping strategy and optimization notes. |
| `../autogen/python/out/cnn_accel_one_sample.S` | Manual generated raw RV32 assembly for sample 0. |
| `../autogen/python/out/icache_initial.hex` | Manual workflow instruction SRAM image. |
| `../autogen/python/out/dcache_initial.hex` | Manual workflow data SRAM image. |
| `../autogen/python/out/testcases/sample*/` | Five manual per-sample RTL test cases. |
| `../autogen/compiler/cnn_config.py` | Compiler workflow CNN dimensions, memory layout, output address, DMA wait count, and toolchain paths. |
| `../autogen/compiler/accel_runtime.h` | Freestanding C accelerator MMIO API. |
| `../autogen/compiler/cnn_accel.c` | Checked-in raw C implementation of the current CNN accelerator schedule. |
| `../autogen/compiler/memory.ld` | Linker script for direct RISC-V GCC calls. |
| `../autogen/compiler/build_current_cnn.py` | C/compiler workflow build entry point for the current CNN. |
| `../autogen/compiler/build_c_program.py` | Utility for compiling handwritten freestanding C into raw assembly and SRAM hex images. |
| `../autogen/compiler/verify_cnn.py` | Compiler workflow reference-model, C-build, SRAM-image, and toolchain verification. |
| `../autogen/compiler/out/cnn_accel.S` | GCC-generated RV32 assembly for compiler workflow sample 0. |
| `../autogen/compiler/out/dcache_init.S` | Compiler workflow D-cache initialization assembly for sample 0. |
| `../autogen/compiler/out/icache_initial.hex` | Compiler workflow instruction SRAM image. |
| `../autogen/compiler/out/dcache_initial.hex` | Compiler workflow data SRAM image. |

Project-wide environment defaults live in `../autogen/project_config.py`. On a new
machine, set the RISC-V toolchain root and run the environment check from the
repository root:

```sh
export RISCV_TOOLCHAIN_ROOT=/path/to/xpack-riscv-none-elf-gcc
python3 autogen/check_env.py
```

If the tools are installed in nonstandard locations, set the individual paths:

```sh
export RISCV_GCC=/path/to/riscv-none-elf-gcc
export RISCV_OBJCOPY=/path/to/riscv-none-elf-objcopy
export RISCV_OBJDUMP=/path/to/riscv-none-elf-objdump
python3 autogen/check_env.py
```

The default fallback RISC-V toolchain root is:

```text
/data/yxx/tools/riscv/xpack-riscv-none-elf-gcc/xpack-riscv-none-elf-gcc-15.2.0-1
```

It builds for `rv32im` with compressed instructions disabled. The current
generated sample outputs are:

| Case | Expected word at default `OUTPUT_ADDR = 0x90000b20` |
| --- | --- |
| sample0 | `0x000000b4` |
| sample1 | `0x000000ed` |
| sample2 | `0x000000bc` |
| sample3 | `0x0000009c` |
| sample4 | `0x00000000` |

Manual workflow commands:

```sh
python3 autogen/python/generate_cnn.py
python3 autogen/python/verify_cnn.py
```

C/compiler workflow commands:

```sh
python3 autogen/compiler/build_current_cnn.py
python3 autogen/compiler/verify_cnn.py
```

The compiler workflow is intended for programmability and still uses the
accelerator for CONV and FC work. The default C flags are `-Os
-fno-jump-tables -fno-tree-loop-distribute-patterns` so the image fits the
8 KiB I-cache SRAM. Handwritten C can be compiled through
`python3 autogen/compiler/build_c_program.py`.

The raw C source is `../autogen/compiler/cnn_accel.c`. To call the RISC-V
compiler directly from the repository root:

```sh
RISCV_GCC=${RISCV_GCC:-${RISCV_TOOLCHAIN_ROOT:-/data/yxx/tools/riscv/xpack-riscv-none-elf-gcc/xpack-riscv-none-elf-gcc-15.2.0-1}/bin/riscv-none-elf-gcc}

$RISCV_GCC \
  -march=rv32im -mabi=ilp32 -mcmodel=medany \
  -ffreestanding -fno-builtin -fno-common -fno-pic \
  -fno-stack-protector -fno-asynchronous-unwind-tables -fno-unwind-tables \
  -Os -fno-jump-tables -fno-tree-loop-distribute-patterns \
  -Iautogen/compiler \
  -S autogen/compiler/cnn_accel.c \
  -o autogen/compiler/out/cnn_accel.S
```

To link it with the generated sample data:

```sh
python3 autogen/compiler/build_current_cnn.py --sample 0

RISCV_GCC=${RISCV_GCC:-${RISCV_TOOLCHAIN_ROOT:-/data/yxx/tools/riscv/xpack-riscv-none-elf-gcc/xpack-riscv-none-elf-gcc-15.2.0-1}/bin/riscv-none-elf-gcc}

$RISCV_GCC \
  -march=rv32im -mabi=ilp32 -mcmodel=medany \
  -ffreestanding -fno-builtin -fno-common -fno-pic \
  -fno-stack-protector -fno-asynchronous-unwind-tables -fno-unwind-tables \
  -Os -fno-jump-tables -fno-tree-loop-distribute-patterns \
  -nostdlib -nostartfiles -Wl,--no-relax \
  -Wl,-T,autogen/compiler/memory.ld -Wl,-e,_start \
  -Iautogen/compiler \
  autogen/compiler/cnn_accel.c autogen/compiler/out/dcache_init.S \
  -o autogen/compiler/out/cnn_accel.elf
```

## Current Software Optimizations

These optimizations are implemented while keeping the current RTL fixed:

- Explicit DMA waits are reduced to `10` nops in each workflow's
  `cnn_config.py`.
- Conv1 and Conv2 overlap DMA prefetch with the current CONV computation:
  software writes the next DMA source address, starts CONV, handles current
  results, waits for `STATUS_DONE`, then issues `SHIFT_LINES`.
- Hot manual control paths inline `START_CONV`, `START_FC`, `SHIFT_LINES`,
  status polling, Conv1 packed stores, and Conv2 raw accumulation.
- Generated hot paths do not issue per-invocation `RESET_PSUMS`; `START_CONV`
  overwrites CONV result registers and `START_FC` clears the FC accumulator in
  the current RTL.
- Conv1 reads packed CONV outputs, so hardware already applies ReLU and low-8
  truncation.
- Conv2 reads raw signed 32-bit CONV outputs, accumulates across the 10 input
  channels in CPU memory, then CPU software applies ReLU and low-8 truncation.
- Conv2 uses a fixed 12-row unrolled schedule. The CPU accumulates raw outputs
  while later CONV columns are still being computed, then waits before mutating
  the line buffer.
- FC1 reuses each loaded 36-byte input chunk across all 10 output neurons.
- FC1 and FC2 scratch packing use fixed-offset loads/stores instead of runtime
  lookup-table loops.
- The verifiers check both individual 8 KiB I-cache/D-cache image limits and
  the combined 16 KiB initialized-memory budget.

The final output byte address is controlled by `OUTPUT_ADDR` in the selected
workflow config, either `../autogen/python/cnn_config.py` or
`../autogen/compiler/cnn_config.py`. The default is `0x90000b20`.

## CPU RTL and Support Files

`rtl/` contains the CV32E40P core RTL:

- `rtl/cv32e40p_top.sv` is the CPU top-level module.
- `rtl/cv32e40p_core.sv` and `rtl/cv32e40p_*.sv` are the pipeline, LSU, decoder,
  controller, ALU, register file, interrupt, debug-facing, and support modules.
- `rtl/include/` contains CV32E40P package definitions.
- `rtl/vendor/` contains third-party common cells and floating-point support
  dependencies.

`bhv/` contains simulation and tracing helpers for behavioral simulation,
instruction tracing, RVFI tracing, and testbench wrapping.
