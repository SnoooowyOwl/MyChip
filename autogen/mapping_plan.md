# CNN to Accelerator Mapping Plan

This plan maps the quantized CNN in `python/network_structure.py` onto the
current accelerator design in `cv32e40p/fpga/rtl/src/accelerator_sim.sv`.

## Target CNN

Input tensor:

- Shape: `N x 1 x 16 x 15`
- Type: unsigned int8

Layer sequence:

| Layer | Operation | Weights | Output shape |
| --- | --- | --- | --- |
| Conv1 | 2D 3x3 convolution | `10 x 1 x 3 x 3` | `N x 10 x 14 x 13` |
| Conv2 | 3D/channel convolution over Conv1 channels | `1 x 10 x 3 x 3` | `N x 1 x 12 x 11` |
| Flatten | Flatten Conv2 output | - | `N x 132` |
| FC1 | Fully connected | `10 x 132` | `N x 10` |
| FC2 | Fully connected | `1 x 10` | `N x 1` |

The Python model uses unsigned int8 activations, signed int8 weights, signed
int32 accumulation, zero biases, ReLU-like clamp to non-negative, and then keeps
the low 8 bits as the next layer activation.

## Accelerator Capabilities Used

Current accelerator behavior:

- CONV mode computes 14 adjacent 3x3 windows from a 3-row by 16-byte line
  buffer using weight group 0.
- CONV mode provides both packed uint8 outputs and raw signed int32 sums. The
  packed uint8 outputs already apply hardware ReLU and low-8 truncation.
- FC mode computes 36 products per invocation using four 3x3 weight groups.
- FC mode returns one raw signed int32 result at `BASE + 100`; CPU software must
  postprocess FC results.
- The accelerator does not support hardware multi-channel accumulation.
- The accelerator does not implement a configurable read-length register.
- Each `SRC_ADDR` write triggers a fixed 16-byte DMA read into `prefetch_buffer`.

## CPU Fallback Model

The system still includes a CV32E40P CPU running RV32 RISC-V software. The
accelerator is a compute assist block, not the only execution resource.

Anything that is awkward or unsupported in accelerator hardware can fall back to
CPU software. In this mapping, the CPU is responsible for:

- Layer scheduling and accelerator register programming.
- Memory layout conversion and row padding.
- Waiting for DMA/compute completion.
- Multi-channel accumulation.
- Long-vector FC chunk accumulation.
- Bias addition if nonzero biases are introduced later.
- Final ReLU and low-8-bit truncation after raw-result or software
  accumulation paths.
- Any scalar cleanup, boundary handling, or debugging/reference computation.

Practical rule:

- Use the accelerator for the fixed kernels it already supports well:
  single-channel 3x3 CONV and 36-product FC chunks.
- Use the RV32 CPU for everything else, especially reductions across multiple
  accelerator calls.

## Data Layout Assumptions

Rows consumed by the accelerator are 16 bytes wide. The CNN input and Conv1
feature maps have width 15 or 13, so software should store each logical row in a
16-byte physical row.

Padding policy:

- Input rows: store 15 valid pixels plus one zero padding byte.
- Conv1 output rows: store 13 valid pixels plus padding bytes to reach 16 bytes.
- Conv2 output rows: store 11 valid pixels plus padding bytes if reusing the
  same row-buffer/DMA layout.

Software must ignore extra horizontal outputs produced by CONV mode:

- For a 15-wide logical input, CONV mode produces 14 outputs; keep only the
  first 13.
- For a 13-wide logical input, CONV mode produces 14 outputs if padded to 16;
  keep only the first 11 for the valid 3x3 positions.

## Layer Mapping

### Conv1

Conv1 is directly compatible with accelerator CONV mode because each output is a
single-channel 3x3 convolution.

For each sample `n` and each output channel `co = 0..9`:

1. Write Conv1 filter `co` into weight group 0.
2. Prime the accelerator line buffer with input rows 0, 1, and 2.
3. For each 3-row window, start a DMA prefetch for the next input row before
   starting CONV mode, except on the last output row.
4. Poll `STATUS` until done.
5. Read packed outputs from `BASE + 100`, `104`, `108`, and `112`.
6. Issue `SHIFT_LINES` after result handling to roll in the prefetched row,
   except on the last output row.
7. Keep the first 13 outputs for the logical row. No CPU ReLU is needed here
   because packed CONV outputs are already postprocessed by hardware.
8. Store the resulting `uint8` row into the Conv1 activation buffer.

Expected Conv1 output per sample:

- 10 channels
- 14 rows
- 13 valid columns

### Conv2

Conv2 requires a sum across 10 Conv1 channels for each spatial 3x3 location.
The accelerator cannot accumulate across channels in one invocation, so software
must perform channel accumulation using raw CONV results.

For each sample `n`:

1. Initialize a full 12x11 software int32 accumulator buffer.
2. For each Conv1 channel `ci = 0..9`:
   1. Write the 3x3 slice `conv2_weight[0, ci, :, :]` into weight group 0.
   2. Prime the accelerator line buffer with Conv1 activation rows 0, 1, and 2
      for channel `ci`.
   3. For each output row `r = 0..11`, start a DMA prefetch for row `r+3`
      before starting CONV mode, except on the last output row.
   4. Start CONV mode.
   5. Read the first 11 raw signed sums from `BASE + 120` through `BASE + 160`
      in order.
   6. Accumulate those raw sums into the corresponding row of the full software
      int32 accumulator buffer while later CONV columns are still being
      computed.
   7. Poll `STATUS` after the raw-result accumulation to guarantee the CONV
      state machine is done before mutating the line buffer.
   8. Issue `SHIFT_LINES` after result handling to roll in the prefetched row,
      except on the last output row.
   The generated Conv2 row body is unrolled because the fixed 12-row shape is
   known and the code still fits within the SRAM budget.
3. After all 10 channels are accumulated, apply final Conv2 postprocessing in
   software:
   - if accumulator is negative, output `0`;
   - otherwise output `accumulator & 0xff`.
4. Store the result rows into the Conv2 activation buffer.

Expected Conv2 output per sample:

- 1 channel
- 12 rows
- 11 columns
- 132 flattened values

### FC1

FC1 maps to accelerator FC mode with software chunk accumulation. FC mode can
compute 36 products per invocation; each FC1 output needs 132 products.

For each sample `n`:

1. Initialize 10 software int32 accumulators to zero.
2. Split the 132 input features into four chunks:
   - chunk 0: features `0..35`
   - chunk 1: features `36..71`
   - chunk 2: features `72..107`
   - chunk 3: features `108..131`, padded with 12 zeros
3. For each chunk:
   1. Arrange the 36 input bytes as three 16-byte DMA rows with generated
      fixed-offset loads/stores, using only columns `0..11` and padding the
      remaining row bytes.
   2. Load the three input rows into the accelerator line buffer once.
   3. For each FC1 output neuron `o = 0..9`:
      1. Write the corresponding 36 signed weights into weight groups 0..3.
      2. Start FC mode and poll `STATUS`.
      3. Read the raw signed int32 chunk sum from `BASE + 100`.
      4. Add the chunk sum to the software accumulator for neuron `o`.
4. Apply final FC1 postprocessing in software:
   - if accumulator is negative, output `0`;
   - otherwise output `accumulator & 0xff`.
5. Store the 10 results as FC1 activations.

Expected FC1 output per sample:

- 10 unsigned int8 activations

### FC2

FC2 has only 10 inputs, so it fits in one padded FC-mode invocation.

For each sample `n`:

1. Arrange the 10 FC1 activations into the FC input layout and pad the remaining
   26 positions with zeros.
2. Write the 10 FC2 weights into the first 10 weight positions and write zeros
   into the remaining weight positions.
3. Load the padded input into the accelerator line buffer.
4. Start FC mode and poll `STATUS`.
5. Read the raw signed int32 result from `BASE + 100`.
6. Apply final FC2 postprocessing in software:
   - if result is negative, output `0`;
   - otherwise output `result & 0xff`.

Expected FC2 output per sample:

- 1 unsigned int8 value

## Required Software Responsibilities

Software must handle:

- Row padding to the accelerator's 16-byte row width.
- Ignoring invalid extra CONV outputs caused by padding.
- Multi-channel Conv2 accumulation.
- FC chunk accumulation for FC1.
- Final ReLU and low-8-bit truncation after raw-result or software
  accumulation paths.
- Weight loading before each accelerator invocation.
- Explicit DMA waits for FC row loads, and CONV/DMA overlap where CONV
  computation provides enough time before `SHIFT_LINES`.
- Avoiding redundant per-invocation reset commands on the current RTL.
- Reusing FC1 chunk input loads across all 10 output neurons.
- Overlapping Conv2 raw-result CPU accumulation with the current CONV
  invocation while still waiting for `STATUS_DONE` before `SHIFT_LINES`.
- Spending instruction memory on fixed-shape unrolling while keeping the
  initialized I/D image under the combined 16 KiB SRAM budget.
- CPU fallback for any operation that does not fit the accelerator's fixed
  CONV or FC modes.

## Current Hardware Limitations

The following are not supported directly in hardware:

- Multi-channel convolution accumulation.
- Bias addition.
- Configurable DMA read length.
- DMA completion status.
- Fully connected vectors longer than 36 inputs per invocation.
- Final activation/truncation after software-accumulated Conv2 or FC1 chunks.

These limitations are workable for the current Python model because biases are
zero and RV32 software can accumulate raw int32 partial sums or run unsupported
pieces directly on the CPU.

## Suggested Validation Path

1. Freeze one deterministic input tensor instead of using random input.
2. Generate Python golden intermediate tensors for Conv1, Conv2, FC1, and FC2.
3. Implement the layer schedule in RISC-V software using the accelerator
   register interface.
4. Compare CPU-visible intermediate buffers against the Python golden tensors.
5. Only then optimize row loading, weight reuse, and memory layout.
