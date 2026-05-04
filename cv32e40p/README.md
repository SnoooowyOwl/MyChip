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

The CNN code generator lives outside this directory under `../autogen/`. It
maps the quantized model in `../python/network_structure.py` onto the fixed
accelerator RTL without changing hardware.

Important files:

| Path | Role |
| --- | --- |
| `../autogen/cnn_config.py` | CNN dimensions, memory layout, output address, DMA wait count, and toolchain paths. |
| `../autogen/accelerator_api.py` | Python API layer that emits RV32 accelerator register sequences. |
| `../autogen/cnn_top_emit.py` | Top-level CNN schedule emitter. |
| `../autogen/generate_cnn.py` | Code generation entry point. |
| `../autogen/verify_cnn.py` | Separate reference-model, codegen, SRAM-image, and toolchain verification. |
| `../autogen/out/cnn_accel_one_sample.S` | Generated raw RV32 assembly for sample 0. |
| `../autogen/out/icache_initial.hex` | Generated 2048-word instruction SRAM image. |
| `../autogen/out/dcache_initial.hex` | Generated 2048-word data SRAM image. |
| `../autogen/out/testcases/sample*/` | Five per-sample RTL test cases, each with assembly, I-cache hex, D-cache hex, and expected output metadata. |

The generator uses the installed RISC-V toolchain at:

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

## Current Software Optimizations

These optimizations are implemented in the generated RV32 code while keeping
the current RTL fixed:

- DMA wait for explicit row-load helpers is reduced to `10` nops in
  `cnn_config.py`.
- Conv1 and Conv2 overlap DMA prefetch with the current CONV computation:
  software writes the next DMA source address, starts CONV, handles current
  results, waits for `STATUS_DONE`, then issues `SHIFT_LINES`.
- Hot control paths inline `START_CONV`, `START_FC`, `SHIFT_LINES`, status
  polling, Conv1 packed stores, and Conv2 raw accumulation instead of calling
  small helper functions.
- Generated hot paths do not issue per-invocation `RESET_PSUMS`; `START_CONV`
  overwrites CONV result registers and `START_FC` clears the FC accumulator in
  the current RTL.
- Conv1 reads packed CONV outputs, so hardware already applies ReLU and low-8
  truncation.
- Conv2 reads raw signed 32-bit CONV outputs, accumulates across the 10 input
  channels in CPU memory, then CPU software applies ReLU and low-8 truncation.
- Conv2 uses a fixed 12-row unrolled schedule. The CPU accumulates the first 11
  raw outputs while later CONV columns are still being computed, then waits
  before mutating the line buffer.
- FC1 reuses each loaded 36-byte input chunk across all 10 output neurons. The
  four chunks by ten neurons are emitted directly, and FC1 postprocessing is
  unrolled.
- FC1 and FC2 scratch packing use generated fixed-offset loads/stores instead
  of runtime lookup-table loops; the old scratch-offset tables are not emitted
  into D-cache initialization data.
- The verifier checks both individual 8 KiB I-cache/D-cache image limits and
  the combined 16 KiB initialized-memory budget. The current generated sample 0
  link is about `0x1d5c` bytes of `.text` plus `0x16a0` bytes of initialized
  D-cache data, for `0x33fc` bytes total.

The final output byte address is controlled by `OUTPUT_ADDR` in
`../autogen/cnn_config.py`. The default is `0x90000b20`.

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
