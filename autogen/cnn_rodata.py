"""Read-only data packing for the generated RV32 CNN program."""

from __future__ import annotations

import numpy as np

from .accelerator_api import pack_i8_word
from .cnn_config import (
    CONV2_ROW_STRIDE,
    CONV2_W,
    FC1_IN,
    FC1_OUT,
    FC1_CHUNKS,
    FC_CHUNK,
    INPUT_H,
    ROW_STRIDE,
)
from .cnn_model import CnnTensors, validate_cnn_tensors


def pack_3x3_filter(values: np.ndarray) -> list[int]:
    flat = [int(v) for v in values.reshape(-1)]
    if len(flat) != 9:
        raise ValueError("expected a 3x3 filter")
    return [
        pack_i8_word(flat[0:4]),
        pack_i8_word(flat[4:8]),
        pack_i8_word(flat[8:9]),
    ]


def pack_fc_36(values: list[int]) -> list[int]:
    if len(values) != FC_CHUNK:
        raise ValueError("FC accelerator invocation requires exactly 36 weights")
    words: list[int] = []
    for group in range(4):
        base = group * 9
        group_vals = values[base : base + 9]
        words.extend(
            [
                pack_i8_word(group_vals[0:4]),
                pack_i8_word(group_vals[4:8]),
                pack_i8_word(group_vals[8:9]),
            ]
        )
    return words


def build_rodata(tensors: CnnTensors, sample_index: int = 0) -> dict[str, list[int]]:
    """Pack input and weights for the generated one-sample assembly program."""

    validate_cnn_tensors(tensors)
    if not 0 <= sample_index < tensors.sample.shape[0]:
        raise ValueError(f"sample index {sample_index} outside sample count {tensors.sample.shape[0]}")

    input0_padded: list[int] = []
    for row in range(INPUT_H):
        input0_padded.extend(int(v) for v in tensors.sample[sample_index, 0, row])
        input0_padded.append(0)

    conv1_packed: list[int] = []
    for co in range(10):
        conv1_packed.extend(pack_3x3_filter(tensors.conv1_w[co, 0]))

    conv2_packed: list[int] = []
    for ci in range(10):
        conv2_packed.extend(pack_3x3_filter(tensors.conv2_w[0, ci]))

    fc1_packed: list[int] = []
    for out_idx in range(FC1_OUT):
        for chunk in range(FC1_CHUNKS):
            start = chunk * FC_CHUNK
            vals = [int(v) for v in tensors.fc1_w[out_idx, start : start + FC_CHUNK]]
            vals.extend([0] * (FC_CHUNK - len(vals)))
            fc1_packed.extend(pack_fc_36(vals))

    fc2_vals = [int(v) for v in tensors.fc2_w[0]]
    fc2_vals.extend([0] * (FC_CHUNK - len(fc2_vals)))
    fc2_packed = pack_fc_36(fc2_vals)

    fc_scratch_offsets: list[int] = []
    for feature in range(FC_CHUNK):
        group = feature // 9
        inner = feature % 9
        row = inner // 3
        col = group * 3 + (inner % 3)
        fc_scratch_offsets.append(row * ROW_STRIDE + col)

    conv2_flat_offsets: list[int] = []
    for idx in range(FC1_IN):
        row = idx // CONV2_W
        col = idx % CONV2_W
        conv2_flat_offsets.append(row * CONV2_ROW_STRIDE + col)

    return {
        "input0_padded": input0_padded,
        "conv1_w_packed": conv1_packed,
        "conv2_w_packed": conv2_packed,
        "fc1_w_packed": fc1_packed,
        "fc2_w_packed": fc2_packed,
        "fc_scratch_offsets": fc_scratch_offsets,
        "conv2_flat_offsets": conv2_flat_offsets,
    }
