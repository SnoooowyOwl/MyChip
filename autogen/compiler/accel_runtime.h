#ifndef AUTOGEN_COMPILER_C_ACCEL_RUNTIME_H
#define AUTOGEN_COMPILER_C_ACCEL_RUNTIME_H

#include <stdint.h>

#ifndef ACCELERATOR_BASE
#define ACCELERATOR_BASE 0x70000000u
#endif

#ifndef ACC_DMA_WAIT_NOPS
#define ACC_DMA_WAIT_NOPS 10
#endif

#define ACC_CMD_START_CONV  0x0000ffffu
#define ACC_CMD_START_FC    0x000fffffu
#define ACC_CMD_RESET_PSUMS 0x0fffffffu
#define ACC_CMD_GLOBAL_RST  0xffffffffu
#define ACC_CMD_SHIFT_LINES 0x00000200u

#define ACC_OFF_CTRL_STATUS 0u
#define ACC_OFF_SRC_ADDR    4u
#define ACC_OFF_W0_0_3      52u
#define ACC_OFF_RES_PACK_0  100u
#define ACC_OFF_RAW_BASE    120u

#ifndef ACC_INLINE
#define ACC_INLINE static inline
#endif

ACC_INLINE volatile uint32_t *acc_word_ptr(uint32_t offset)
{
    return (volatile uint32_t *)(uintptr_t)(ACCELERATOR_BASE + offset);
}

ACC_INLINE void acc_write_word(uint32_t offset, uint32_t value)
{
    *acc_word_ptr(offset) = value;
}

ACC_INLINE uint32_t acc_read_word(uint32_t offset)
{
    return *acc_word_ptr(offset);
}

ACC_INLINE void acc_global_reset(void)
{
    acc_write_word(ACC_OFF_CTRL_STATUS, ACC_CMD_GLOBAL_RST);
}

ACC_INLINE void acc_reset_psums(void)
{
    acc_write_word(ACC_OFF_CTRL_STATUS, ACC_CMD_RESET_PSUMS);
}

ACC_INLINE void acc_set_dma_addr(uintptr_t addr)
{
    acc_write_word(ACC_OFF_SRC_ADDR, (uint32_t)addr);
}

ACC_INLINE void acc_start_conv(void)
{
    acc_write_word(ACC_OFF_CTRL_STATUS, ACC_CMD_START_CONV);
}

ACC_INLINE void acc_start_fc(void)
{
    acc_write_word(ACC_OFF_CTRL_STATUS, ACC_CMD_START_FC);
}

ACC_INLINE void acc_shift_lines(void)
{
    acc_write_word(ACC_OFF_CTRL_STATUS, ACC_CMD_SHIFT_LINES);
}

ACC_INLINE void acc_wait_done(void)
{
    while (acc_read_word(ACC_OFF_CTRL_STATUS) != 1u) {
    }
}

ACC_INLINE void acc_dma_wait(void)
{
#if ACC_DMA_WAIT_NOPS == 10
    __asm__ volatile(
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        :
        :
        : "memory");
#else
    for (uint32_t i = 0; i < ACC_DMA_WAIT_NOPS; ++i) {
        __asm__ volatile("nop" ::: "memory");
    }
#endif
}

ACC_INLINE void acc_dma_shift(uintptr_t addr)
{
    acc_set_dma_addr(addr);
    acc_dma_wait();
    acc_shift_lines();
}

ACC_INLINE void acc_load_three_rows(uintptr_t addr, uint32_t stride)
{
    acc_dma_shift(addr);
    acc_dma_shift(addr + stride);
    acc_dma_shift(addr + 2u * stride);
}

ACC_INLINE void acc_write_conv_w0(const uint32_t *packed_words)
{
    acc_write_word(ACC_OFF_W0_0_3 + 0u, packed_words[0]);
    acc_write_word(ACC_OFF_W0_0_3 + 4u, packed_words[1]);
    acc_write_word(ACC_OFF_W0_0_3 + 8u, packed_words[2]);
}

ACC_INLINE void acc_write_fc_weights(const uint32_t *packed_words)
{
    acc_write_word(ACC_OFF_W0_0_3 + 0u, packed_words[0]);
    acc_write_word(ACC_OFF_W0_0_3 + 4u, packed_words[1]);
    acc_write_word(ACC_OFF_W0_0_3 + 8u, packed_words[2]);
    acc_write_word(ACC_OFF_W0_0_3 + 12u, packed_words[3]);
    acc_write_word(ACC_OFF_W0_0_3 + 16u, packed_words[4]);
    acc_write_word(ACC_OFF_W0_0_3 + 20u, packed_words[5]);
    acc_write_word(ACC_OFF_W0_0_3 + 24u, packed_words[6]);
    acc_write_word(ACC_OFF_W0_0_3 + 28u, packed_words[7]);
    acc_write_word(ACC_OFF_W0_0_3 + 32u, packed_words[8]);
    acc_write_word(ACC_OFF_W0_0_3 + 36u, packed_words[9]);
    acc_write_word(ACC_OFF_W0_0_3 + 40u, packed_words[10]);
    acc_write_word(ACC_OFF_W0_0_3 + 44u, packed_words[11]);
}

ACC_INLINE uint32_t acc_read_conv_packed(uint32_t pack_idx)
{
    return acc_read_word(ACC_OFF_RES_PACK_0 + 4u * pack_idx);
}

ACC_INLINE int32_t acc_read_conv_raw(uint32_t raw_idx)
{
    return (int32_t)acc_read_word(ACC_OFF_RAW_BASE + 4u * raw_idx);
}

ACC_INLINE int32_t acc_read_fc_raw(void)
{
    return (int32_t)acc_read_word(ACC_OFF_RES_PACK_0);
}

#endif
