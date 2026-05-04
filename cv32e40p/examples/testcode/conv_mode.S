# Example test code for accelerator convolution mode.

.equ ACCELERATOR_BASE, 0x70000000
.equ ICACHE_BASE,      0x80000000
.equ DCACHE_BASE,      0x90000000

    lui t0, %hi(ACCELERATOR_BASE)
    addi t0, t0, %lo(ACCELERATOR_BASE)

    lui t1, %hi(ICACHE_BASE)
    addi t1, t1, %lo(ICACHE_BASE)

    lui t2, %hi(DCACHE_BASE)
    addi t2, t2, %lo(DCACHE_BASE)

    addi a3, x0, 0
CONV_OUT_LABEL:
    addi a1, x0, -1     # GLOBAL_CLEAR
    sw a1, 0(t0)
    li a2, 12
    mul a5, a3, a2
    add a1, a5, t2
    li a2, 240
    add a1, a1, a2
    lw a0, 0(a1)
    sw a0, 52(t0)
    lw a0, 4(a1)
    sw a0, 56(t0)
    lw a0, 8(a1)
    sw a0, 60(t0)

    # SET_DMA_BASE: base 2415919104
    lui a1, 0x90000
    sw a1, 4(t0)        # WAIT: 8
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    # SET_DMA_BASE: base 2415919120
    lui a1, 0x90000
    addi a1, a1, 16
    sw a1, 4(t0)        # WAIT: 8
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    # SET_DMA_BASE: base 2415919136
    lui a1, 0x90000
    addi a1, a1, 32
    sw a1, 4(t0)        # WAIT: 8
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    nop
    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919152
    lui a1, 0x90000
    addi a1, a1, 48
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP0:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP0
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 0
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919168
    lui a1, 0x90000
    addi a1, a1, 64
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP1:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP1
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 16
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919184
    lui a1, 0x90000
    addi a1, a1, 80
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP2:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP2
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 32
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919200
    lui a1, 0x90000
    addi a1, a1, 96
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP3:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP3
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 48
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919216
    lui a1, 0x90000
    addi a1, a1, 112
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP4:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP4
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 64
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919232
    lui a1, 0x90000
    addi a1, a1, 128
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP5:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP5
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 80
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919248
    lui a1, 0x90000
    addi a1, a1, 144
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP6:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP6
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 96
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919264
    lui a1, 0x90000
    addi a1, a1, 160
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP7:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP7
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 112
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919280
    lui a1, 0x90000
    addi a1, a1, 176
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP8:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP8
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 128
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919296
    lui a1, 0x90000
    addi a1, a1, 192
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP9:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP9
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 144
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919312
    lui a1, 0x90000
    addi a1, a1, 208
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP10:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP10
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 160
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919328
    lui a1, 0x90000
    addi a1, a1, 224
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP11:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP11
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 176
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4

    addi a1, x0, 0x200  # SHIFT_LINES
    sw a1, 0(t0)

    lui a1, 0x10000     # PARTIAL_CLEAR
    addi a1, a1, -1
    sw a1, 0(t0)
    # SET_DMA_BASE: base 2415919344
    lui a1, 0x90000
    addi a1, a1, 240
    sw a1, 4(t0)
    lui a1, 0x00010     # START
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP12:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP12
    li a1, 208
    mul a2, a1, a3
    addi a2, a2, 2000
    add a2, a2, 192
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 104(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 108(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    lw a0, 112(t0)
    sw a0, 0(a2)
    addi a2, a2, 4
    addi a3, a3, 1
    li a1, 13
    bne a3, a1, CONV_OUT_LABEL

end_loop:
    j end_loop
