# Autogen CNN Accelerator Framework

This directory contains a small code generation framework for mapping the CNN in
`../python/network_structure.py` onto the current accelerator RTL.

## Files

| Path | Purpose |
| --- | --- |
| `rv32_emit.py` | Generic RV32 assembly text emitter. |
| `accelerator_api.py` | Accelerator register constants, packing helpers, and accelerator API emitters. |
| `cnn_config.py` | CNN dimensions, D-cache memory layout, and output paths. |
| `cnn_model.py` | Pure Python/NumPy reference model and input/weight parsing. |
| `cnn_rodata.py` | Input/weight packing for generated D-cache initialization data. |
| `cnn_top_emit.py` | Top-level CNN schedule and CPU helper emission. |
| `memory_image.py` | Toolchain link/extract helpers for SRAM init hex images. |
| `generate_cnn.py` | Code generation entry point only. |
| `verify_cnn.py` | Reference-model, mapping, generated-image, and toolchain verification. |
| `testcase_metadata.py` | Expected-output address and value metadata for RTL test cases. |
| `accel_codegen.py` | Compatibility wrapper for older imports. |
| `mapping_plan.md` | Design plan and mapping rationale. |
| `out/cnn_accel_one_sample.S` | Generated RV32 assembly for sample 0. |
| `out/icache_initial.hex` | 2048-word I-cache SRAM image for base `0x80000000`. |
| `out/dcache_initial.hex` | 2048-word D-cache SRAM image for base `0x90000000`. |
| `out/testcases/sample*/` | Per-sample assembly, I-cache image, D-cache image, and expected output metadata. |

## Generate

Run from the repository root:

```sh
python3 autogen/generate_cnn.py
```

The generator:

- parses `python/data/conv1_weight.txt`;
- parses `python/data/conv2_weight.txt`;
- parses `python/data/fc1_weight.txt`;
- parses `python/data/fc2_weight.txt`;
- parses all samples from `python/sample_io.txt`;
- emits one RTL test directory per sample under `autogen/out/testcases/`;
- mirrors sample 0 to `autogen/out/cnn_accel_one_sample.S`;
- mirrors sample 0 to `autogen/out/icache_initial.hex`;
- mirrors sample 0 to `autogen/out/dcache_initial.hex`;
- builds for `rv32im` with compressed instructions disabled;
- does not run golden-model verification.

Expected generator summary:

```text
wrote autogen/out/testcases/sample0/cnn_accel_sample0.S
wrote autogen/out/testcases/sample0/icache_initial.hex
wrote autogen/out/testcases/sample0/dcache_initial.hex
wrote autogen/out/testcases/sample0/expected.txt
...
mirrored sample 0 to autogen/out/cnn_accel_one_sample.S
mirrored sample 0 to autogen/out/icache_initial.hex
mirrored sample 0 to autogen/out/dcache_initial.hex
DMA wait nops per row load: 10
run python3 autogen/verify_cnn.py for mapping, image, and toolchain checks
```

Each generated case directory contains:

```text
cnn_accel_sampleN.S
icache_initial.hex
dcache_initial.hex
expected.txt
```

The current five expected output bytes are:

| Case | Expected byte | Expected word at `0x90000b20` |
| --- | --- | --- |
| sample0 | `0xb4` / 180 | `0x000000b4` |
| sample1 | `0xed` / 237 | `0x000000ed` |
| sample2 | `0xbc` / 188 | `0x000000bc` |
| sample3 | `0x9c` / 156 | `0x0000009c` |
| sample4 | `0x00` / 0 | `0x00000000` |

## Verify

Run from the repository root:

```sh
python3 autogen/verify_cnn.py
```

The verifier is separate from code generation. It:

- computes the direct NumPy reference tensors;
- computes a mapped golden model that mirrors accelerator calls plus CPU
  accumulation;
- checks the mapped model against the direct model for every sample;
- checks `python/sample_io.txt` expected outputs against the direct model;
- emits assembly in memory and checks accelerator register offsets and D-cache
  bounds;
- links the generated RV32 code into separate I-cache and D-cache memory
  regions;
- checks that linked instructions are all 32-bit RV32IM instructions;
- checks that the top-level and per-sample generated hex files are current
  2048-word SRAM images.

By default the verifier uses:

```text
/data/yxx/tools/riscv/xpack-riscv-none-elf-gcc/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc
```

Override the tools with `RISCV_GCC`, `RISCV_OBJCOPY`, and `RISCV_OBJDUMP`
environment variables if needed.

Expected verifier summary:

```text
verification passed
assembly checked: autogen/out/cnn_accel_one_sample.S
I-cache image checked: autogen/out/icache_initial.hex
D-cache image checked: autogen/out/dcache_initial.hex
testcase directories checked: 5
toolchain checked: /data/yxx/tools/riscv/xpack-riscv-none-elf-gcc/xpack-riscv-none-elf-gcc-15.2.0-1/bin/riscv-none-elf-gcc
golden output all samples: [180, 237, 188, 156, 0]
sample 0 expected output byte: 180
sample 0 expected FC1: [0, 45, 0, 170, 0, 0, 0, 0, 0, 158]
```

## Generated Assembly Contract

The generated assembly assumes:

- `s0` holds `ACCELERATOR_BASE = 0x70000000`;
- generated code is RV32IM only; RVC/compressed instructions are disabled;
- I-cache SRAM is initialized from `autogen/out/icache_initial.hex`;
- D-cache SRAM is initialized from `autogen/out/dcache_initial.hex`;
- the final one-byte output is stored at `OUTPUT_ADDR` from `cnn_config.py`;
- stack is placed near the top of the 8 KiB D-cache window at `0x90001ffc`;
- accelerator DMA reads use fixed 16-byte rows;
- FC row loads still use explicit DMA waits because FC compute is only 4 cycles;
- Conv1 and Conv2 prefetch the next activation row during the current CONV
  computation, then issue `SHIFT_LINES` after the computation and result
  handling have completed.
- generated hot loops do not issue per-invocation `RESET_PSUMS`; `START_CONV`
  overwrites the CONV result registers before they are consumed, and `START_FC`
  clears the FC accumulator in the current RTL.

D-cache layout:

| Address | Buffer |
| --- | --- |
| `0x90000000` | padded input rows |
| `0x90000100` | padded Conv1 activations |
| `0x90000a00` | padded Conv2 activations |
| `0x90000b00` | FC1 activations |
| `OUTPUT_ADDR` from `cnn_config.py` | final output byte |
| `0x90000b40` | FC scratch rows |
| `0x90000b80` | full 12x11 int32 Conv2 accumulation scratch |
| `0x90000e00` | preloaded weights and lookup tables |

The default `OUTPUT_ADDR` is `0x90000b20`. You may change it in
`cnn_config.py`, but it must remain inside the 8 KiB D-cache window and must not
overlap input, activation buffers, scratch buffers, constants, or the stack
guard. `verify_cnn.py` checks this.

## Accelerator API Layer

`accelerator_api.py` provides Python APIs that emit RV32 sequences for:

- `global_reset`
- `reset_psums`
- `set_dma_addr`
- `shift_lines`
- `start_conv`
- `start_fc`
- `wait_done`
- `write_conv_weights`
- `write_fc_weights`
- `read_conv_packed`
- `read_conv_raw`
- `read_fc_raw`

Accelerator-specific runtime helper labels are emitted by
`AcceleratorAPI.emit_runtime_helpers`, including `acc_load_three_rows`,
`acc_write_conv_w0`, and `acc_write_fc_weights`. Hot control paths inline
`START_CONV`, `START_FC`, `SHIFT_LINES`, status polling, and Conv1 packed
stores to avoid repeated `call`/`ret` overhead.

CNN-specific CPU helper labels such as `zero_words`, `postprocess_accum_11`,
`fill_fc_scratch_conv2`, and `fill_fc_scratch_linear` live in
`cnn_top_emit.py`, not in the accelerator API layer. Conv2 raw accumulation is
unrolled in the Conv2 hot loop and overlaps with the current CONV computation;
the generated code still polls `STATUS_DONE` before `SHIFT_LINES`.

## ReLU / Postprocessing Rule

The accelerator has two different readback styles:

- Packed CONV result reads at `BASE + 100`, `104`, `108`, and `112` already
  apply ReLU and low-8 truncation in hardware.
- Raw CONV result reads at `BASE + 120` onward return signed int32 sums.
- FC reads at `BASE + 100` return signed int32 sums.

Therefore:

- Conv1 uses packed CONV reads and does not apply CPU ReLU.
- Conv2 reads raw CONV sums because it must accumulate across channels; CPU
  applies ReLU and low-8 truncation after channel accumulation.
- FC1 and FC2 read raw FC sums; CPU applies ReLU and low-8 truncation.

## Manual Simulation Notes

The generated hex files are `$readmemh`-style images: one 32-bit word per line,
2048 lines per file. The CPU boots through the existing `bootram` jump into
`0x80000000`, so initialize the instruction SRAM with `icache_initial.hex` and
the D-cache SRAM with `dcache_initial.hex` before simulation.
