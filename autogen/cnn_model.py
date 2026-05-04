"""Pure-Python CNN model and input/weight parsing.

This module is intentionally free of assembly generation.  It provides the
reference math used by the standalone verifier.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .cnn_config import (
    CONV1_COUT,
    CONV2_H,
    CONV2_W,
    DATA_DIR,
    FC1_CHUNKS,
    FC1_IN,
    FC1_OUT,
    FC_CHUNK,
    INPUT_H,
    INPUT_W,
    PYTHON_DIR,
)


@dataclass(frozen=True)
class CnnTensors:
    sample: np.ndarray
    expected_output: np.ndarray
    conv1_w: np.ndarray
    conv2_w: np.ndarray
    fc1_w: np.ndarray
    fc2_w: np.ndarray


def load_hex_weights(path: Path) -> np.ndarray:
    vals: list[int] = []
    for token in path.read_text(encoding="ascii").split():
        value = int(token, 16)
        vals.append(value - 256 if value > 127 else value)
    return np.array(vals, dtype=np.int32)


def parse_sample_io(path: Path) -> tuple[np.ndarray, np.ndarray]:
    text = path.read_text(encoding="ascii")
    sample_match = re.search(r"Sample Input:\s*(.*?)\nQuantized Output:", text, re.S)
    if not sample_match:
        raise ValueError(f"could not find Sample Input block in {path}")
    sample_nums = [int(x) for x in re.findall(r"(?<![A-Za-z0-9_])-?\d+", sample_match.group(1))]
    sample = np.array(sample_nums, dtype=np.uint8).reshape(-1, 1, INPUT_H, INPUT_W)

    output_match = re.search(r"Quantized Output:\s*tensor\((.*?),\s*dtype=", text, re.S)
    if not output_match:
        raise ValueError(f"could not find Quantized Output tensor in {path}")
    output_nums = [int(x) for x in re.findall(r"(?<![A-Za-z0-9_])-?\d+", output_match.group(1))]
    output = np.array(output_nums, dtype=np.uint8).reshape(-1, 1)
    return sample, output


def load_cnn_tensors() -> CnnTensors:
    sample, expected_output = parse_sample_io(PYTHON_DIR / "sample_io.txt")
    conv1_w = load_hex_weights(DATA_DIR / "conv1_weight.txt").reshape(10, 1, 3, 3)
    conv2_w = load_hex_weights(DATA_DIR / "conv2_weight.txt").reshape(1, 10, 3, 3)
    fc1_w = load_hex_weights(DATA_DIR / "fc1_weight.txt").reshape(10, 132)
    fc2_w = load_hex_weights(DATA_DIR / "fc2_weight.txt").reshape(1, 10)
    return CnnTensors(sample, expected_output, conv1_w, conv2_w, fc1_w, fc2_w)


def validate_cnn_tensors(tensors: CnnTensors) -> None:
    if tensors.sample.ndim != 4 or tensors.sample.shape[1:] != (1, INPUT_H, INPUT_W):
        raise AssertionError(f"unexpected input shape {tensors.sample.shape}")
    if tensors.expected_output.shape != (tensors.sample.shape[0], 1):
        raise AssertionError(f"unexpected output shape {tensors.expected_output.shape}")
    if tensors.conv1_w.shape != (10, 1, 3, 3):
        raise AssertionError(f"unexpected Conv1 weight shape {tensors.conv1_w.shape}")
    if tensors.conv2_w.shape != (1, 10, 3, 3):
        raise AssertionError(f"unexpected Conv2 weight shape {tensors.conv2_w.shape}")
    if tensors.fc1_w.shape != (10, 132):
        raise AssertionError(f"unexpected FC1 weight shape {tensors.fc1_w.shape}")
    if tensors.fc2_w.shape != (1, 10):
        raise AssertionError(f"unexpected FC2 weight shape {tensors.fc2_w.shape}")


def post_uint8(acc: int | np.ndarray) -> np.ndarray:
    arr = np.asarray(acc, dtype=np.int64)
    arr = np.clip(arr, 0, (1 << 23) - 1)
    return (arr & 0xFF).astype(np.uint8)


def post_uint8_scalar(acc: int) -> int:
    return int(post_uint8(acc).reshape(()))


def quantized_conv2d(x: np.ndarray, weight: np.ndarray) -> np.ndarray:
    n_batch, _, height, width = x.shape
    cout, _, kh, kw = weight.shape
    out = np.zeros((n_batch, cout, height - kh + 1, width - kw + 1), dtype=np.uint8)
    for n in range(n_batch):
        for co in range(cout):
            for row in range(out.shape[2]):
                for col in range(out.shape[3]):
                    patch = x[n, :, row : row + kh, col : col + kw].astype(np.int32)
                    out[n, co, row, col] = post_uint8_scalar(int(np.sum(patch * weight[co])))
    return out


def quantized_conv3d(x: np.ndarray, weight: np.ndarray) -> np.ndarray:
    n_batch, cin, height, width = x.shape
    _, kd, kh, kw = weight.shape
    cout = cin - kd + 1
    out = np.zeros((n_batch, cout, height - kh + 1, width - kw + 1), dtype=np.uint8)
    for n in range(n_batch):
        for co in range(cout):
            for row in range(out.shape[2]):
                for col in range(out.shape[3]):
                    patch = x[n, co : co + kd, row : row + kh, col : col + kw].astype(np.int32)
                    out[n, co, row, col] = post_uint8_scalar(int(np.sum(patch * weight[co])))
    return out


def quantized_linear(x: np.ndarray, weight: np.ndarray) -> np.ndarray:
    out = np.zeros((x.shape[0], weight.shape[0]), dtype=np.uint8)
    for n in range(x.shape[0]):
        for o in range(weight.shape[0]):
            acc = int(np.sum(x[n].astype(np.int32) * weight[o]))
            out[n, o] = post_uint8_scalar(acc)
    return out


def compute_golden(tensors: CnnTensors) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    conv1 = quantized_conv2d(tensors.sample, tensors.conv1_w)
    conv2 = quantized_conv3d(conv1, tensors.conv2_w)
    fc1 = quantized_linear(conv2.reshape(tensors.sample.shape[0], -1), tensors.fc1_w)
    fc2 = quantized_linear(fc1, tensors.fc2_w)
    return conv1, conv2, fc1, fc2


def compute_mapped_golden(
    sample0: np.ndarray, tensors: CnnTensors
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Mirror the accelerator mapping, including raw partial accumulation."""

    conv1 = quantized_conv2d(sample0, tensors.conv1_w)

    conv2 = np.zeros((1, 1, CONV2_H, CONV2_W), dtype=np.uint8)
    for row in range(CONV2_H):
        for col in range(CONV2_W):
            acc = 0
            for ci in range(CONV1_COUT):
                patch = conv1[0, ci, row : row + 3, col : col + 3].astype(np.int32)
                acc += int(np.sum(patch * tensors.conv2_w[0, ci]))
            conv2[0, 0, row, col] = post_uint8_scalar(acc)

    flat = conv2.reshape(1, FC1_IN)
    fc1 = np.zeros((1, FC1_OUT), dtype=np.uint8)
    for out_idx in range(FC1_OUT):
        acc = 0
        for chunk in range(FC1_CHUNKS):
            start = chunk * FC_CHUNK
            stop = min(start + FC_CHUNK, FC1_IN)
            acc += int(
                np.sum(flat[0, start:stop].astype(np.int32) * tensors.fc1_w[out_idx, start:stop])
            )
        fc1[0, out_idx] = post_uint8_scalar(acc)

    fc2_acc = int(np.sum(fc1[0].astype(np.int32) * tensors.fc2_w[0]))
    fc2 = np.array([[post_uint8_scalar(fc2_acc)]], dtype=np.uint8)
    return conv1, conv2, fc1, fc2
