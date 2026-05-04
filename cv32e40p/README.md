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
