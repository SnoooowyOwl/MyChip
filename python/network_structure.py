import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

# Define quantization functions
def quantize_int8(tensor, is_weight=False):
    if is_weight:
        return torch.clamp(tensor.round(), -128, 127).to(torch.int8)
    else:
        return torch.clamp(tensor.round(), 0, 255).to(torch.uint8)

#def quantized_relu8(x):
#    return torch.clamp(x, 0, 255).to(torch.uint8)

def mac_24bit(input_patch, weight, bias=None):
    inp = input_patch.to(torch.int32)
    w = weight.to(torch.int32)
    acc = torch.sum(inp * w, dim=(1, 2, 3), keepdim=False)
    if bias is not None:
        acc += bias.to(torch.int32)
    #acc = torch.clamp(acc, -2**23, 2**23-1)
    #print(acc)
    acc = torch.clamp(acc, 0, 2**23-1)
    #print(acc)
    out8 = ((acc ) & 0xFF).to(torch.uint8)
    return out8

def quantized_conv2d(x, weight, bias, stride=1):
    N, Cin, H, W = x.shape
    Cout, _, Kh, Kw = weight.shape
    Hout = (H - Kh) // stride + 1
    Wout = (W - Kw) // stride + 1
    out = torch.zeros((N, Cout, Hout, Wout), dtype=torch.uint8)
    for n in range(N):
        for co in range(Cout):
            for i in range(Hout):
                for j in range(Wout):
                    patch = x[n, :, i:i+Kh, j:j+Kw]
                    val = mac_24bit(patch, weight[co:co+1], bias[co])
                    out[n, co, i, j] = val
    return out

def quantized_conv3d(x, weight, bias, stride=1):
    N, Cin, H, W = x.shape  # 3D input
    _, Kd, Kh, Kw = weight.shape  # 3D filter
    Cout = (Cin - Kd) // stride + 1
    Hout = (H - Kh) // stride + 1
    Wout = (W - Kw) // stride + 1
    out = torch.zeros((N, Cout, Hout, Wout), dtype=torch.uint8)
    for n in range(N):
        for co in range(Cout):
            for i in range(Hout):
                for j in range(Wout):
                    patch = x[n, co:co+Kd, i:i+Kh, j:j+Kw]
                    val = mac_24bit(patch, weight[co:co+1], bias[co])
                    out[n, co, i, j] = val
    return out

def quantized_linear(x, weight, bias):
    N, In = x.shape
    Out, _ = weight.shape
    out = torch.zeros((N, Out), dtype=torch.uint8)
    for n in range(N):
        for o in range(Out):
            if Out==10: print(o)
            val = mac_24bit(x[n:n+1, :].view(1, 1, 1, In), weight[o:o+1].view(1, 1, 1, In), bias[o])
            if Out==10: print(val)
            out[n, o] = val
    return out

# Implement the quantized network
class QuantizedCNN(nn.Module):
    def __init__(self, q_conv1_w, q_conv1_b, q_conv2_w, q_conv2_b, q_fc1_w, q_fc1_b, q_fc2_w, q_fc2_b):
        super().__init__()
        # Weights passed as arguments are quantized
        self.q_conv1_w = q_conv1_w
        self.q_conv1_b = q_conv1_b
        self.q_conv2_w = q_conv2_w
        self.q_conv2_b = q_conv2_b
        self.q_fc1_w = q_fc1_w
        self.q_fc1_b = q_fc1_b
        self.q_fc2_w = q_fc2_w
        self.q_fc2_b = q_fc2_b

    def forward(self, x):
        x = quantized_conv2d(x, self.q_conv1_w, self.q_conv1_b)
        #print("Shape of x:", x.shape)
        #x = quantized_relu8(x)
        print("===================== CONV1 =====================")
        print([f'0x{a:02x}' for a in x])
        print("===================== CONV1 =====================")

        x = quantized_conv3d(x, self.q_conv2_w, self.q_conv2_b)  # Use 3D convolution
        #print("Shape of x:", x.shape)
        #x = quantized_relu8(x)
        x = x.view(x.size(0), -1)  # Flatten for fully connected layers
        #print("Shape of x:", x.shape)
        x = quantized_linear(x, self.q_fc1_w, self.q_fc1_b)
        #print("Shape of x:", x.shape)
        #x = quantized_relu8(x)
        x = quantized_linear(x, self.q_fc2_w, self.q_fc2_b)
        #print("Shape of x:", x.shape)
        return x

# Load weights from the `.txt` files (assumed to be in 16 hexadecimal format)
def load_hex_weights(file_path):
    # Read the file as a string of hex values
    with open(file_path, 'r') as f:
        data = f.read().splitlines()
    
    # Convert each space-separated hex string to integer
    weights = []
    for line in data:
        for val in line.split():
            # Handle two's complement for negative numbers in int8 range
            int_val = int(val, 16)  # Convert hex string to integer
            if int_val > 127:  # If the value is above 127, it should be a negative number
                int_val -= 256  # Convert to signed 8-bit integer (two's complement)
            weights.append(int_val)
    
    return np.array(weights, dtype=np.int8)

# Use the function to load weights
conv1_weight = load_hex_weights('data/conv1_weight.txt')
conv2_weight = load_hex_weights('data/conv2_weight.txt')
fc1_weight = load_hex_weights('data/fc1_weight.txt')
fc2_weight = load_hex_weights('data/fc2_weight.txt')

# For conv2_weight, reshape the 9x10 matrix to 3x3x10x1
conv1_weight = conv1_weight.reshape(10, 1, 3, 3)  # Reshaping 9x10 to 3x3x10x1
conv2_weight = conv2_weight.reshape(1, 10, 3, 3)  # Reshaping 9x10 to 3x3x10x1
fc1_weight = fc1_weight.reshape(10, 132)  # Reshaping 9x10 to 3x3x10x1
fc2_weight = fc2_weight.reshape(1, 10)
print(fc2_weight)

# Bias initialization (zero)
conv1_bias = np.zeros(10, dtype=np.int8)
conv2_bias = np.zeros(3, dtype=np.int8)  # 3 output channels
fc1_bias = np.zeros(10, dtype=np.int8)
fc2_bias = np.zeros(1, dtype=np.int8)

# Simulating some sample inputs
sample_input = np.random.randint(0, 255, (5, 1, 16, 15), dtype=np.uint8)  # 5 sample inputs of size 16x15
np.set_printoptions(threshold=np.inf)
print("Sample Input:", sample_input)
# Convert to torch tensors
q_conv1_w = torch.tensor(conv1_weight, dtype=torch.int8)
q_conv1_b = torch.tensor(conv1_bias, dtype=torch.int8)
q_conv2_w = torch.tensor(conv2_weight, dtype=torch.int8)
q_conv2_b = torch.tensor(conv2_bias, dtype=torch.int8)
q_fc1_w = torch.tensor(fc1_weight, dtype=torch.int8)
q_fc1_b = torch.tensor(fc1_bias, dtype=torch.int8)
q_fc2_w = torch.tensor(fc2_weight, dtype=torch.int8)
q_fc2_b = torch.tensor(fc2_bias, dtype=torch.int8)

# Instantiate the model with the quantized weights
model = QuantizedCNN(q_conv1_w, q_conv1_b, q_conv2_w, q_conv2_b, q_fc1_w, q_fc1_b, q_fc2_w, q_fc2_b)

# Run inference on a sample input
x = torch.tensor(sample_input, dtype=torch.uint8)

# Quantized inference
output = model(x)

# Print the output to check for both 0s and 1s
print("Quantized Output:", output)

