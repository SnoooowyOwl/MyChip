# Example test code for accelerator fully-connected mode.

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
FC_OUT_LABEL:
    addi a1, x0, -1     # GLOBAL_CLEAR
    sw a1, 0(t0)

    li a1, 240
    add a1, a1, t2
    lw a0, 0(a1)
    sw a0, 52(t0)
    lw a0, 4(a1)
    sw a0, 56(t0)
    lw a0, 8(a1)
    sw a0, 60(t0)
    lw a0, 12(a1)
    sw a0, 64(t0)
    lw a0, 16(a1)
    sw a0, 68(t0)
    lw a0, 20(a1)
    sw a0, 72(t0)
    lw a0, 24(a1)
    sw a0, 76(t0)
    lw a0, 28(a1)
    sw a0, 80(t0)
    lw a0, 32(a1)
    sw a0, 84(t0)
    lw a0, 36(a1)
    sw a0, 88(t0)
    lw a0, 40(a1)
    sw a0, 92(t0)
    lw a0, 44(a1)
    sw a0, 96(t0)

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
    lui a1, 0x00100     # START FC
    addi a1, a1, -1
    sw a1, 0(t0)

WAIT_DONE_LOOP0:
    lw a0, 0(t0)
    addi a1, zero, 1
    bne a0, a1, WAIT_DONE_LOOP0
    addi a2, a2, 2000
    add a2, a2, t2
    lw a0, 100(t0)
    sw a0, 0(a2)
    addi a3, a3, 1
    li a1, 13
    bne a3, a1, FC_OUT_LABEL

end_loop:
    j end_loop
