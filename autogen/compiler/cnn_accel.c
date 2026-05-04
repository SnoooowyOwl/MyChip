/* Static C implementation of the current quantized CNN accelerator schedule. */
/* Input and packed weights are linked from a generated .dcache_init assembly file. */

#define ACCELERATOR_BASE 0x70000000u
#define ACC_DMA_WAIT_NOPS 10
#include "accel_runtime.h"

#define DCACHE_BASE_ADDR 0x90000000u
#define D_INPUT_ADDR 0x90000000u
#define D_CONV1_ADDR 0x90000100u
#define D_CONV2_ADDR 0x90000a00u
#define D_FC1_ADDR 0x90000b00u
#define D_OUTPUT_ADDR 0x90000b20u
#define D_SCRATCH_ADDR 0x90000b40u
#define D_ACCUM_ADDR 0x90000b80u
#define D_STACK_TOP_ADDR 0x90001ffcu

#define ROW_STRIDE_BYTES 16u
#define CONV1_COUT_COUNT 10u
#define CONV1_H_COUNT 14u
#define CONV1_ROW_STRIDE_BYTES 16u
#define CONV1_CH_SIZE_BYTES 224u
#define CONV2_H_COUNT 12u
#define CONV2_W_COUNT 11u
#define CONV2_ROW_STRIDE_BYTES 16u
#define FC1_OUT_COUNT 10u
#define FC1_CHUNK_COUNT 4u
#define FC_CHUNK_SIZE 36u

extern const uint32_t conv1_w_packed[];
extern const uint32_t conv2_w_packed[];
extern const uint32_t fc1_w_packed[];
extern const uint32_t fc2_w_packed[];

static inline volatile uint8_t *u8p(uintptr_t addr)
{
    return (volatile uint8_t *)addr;
}

static inline volatile uint32_t *u32p(uintptr_t addr)
{
    return (volatile uint32_t *)addr;
}

static inline volatile int32_t *i32p(uintptr_t addr)
{
    return (volatile int32_t *)addr;
}

static inline uint8_t post_i32(int32_t value)
{
    return value < 0 ? 0u : (uint8_t)value;
}

static void zero_words(uintptr_t addr, uint32_t words)
{
    volatile int32_t *dst = i32p(addr);
    for (uint32_t i = 0; i < words; ++i) {
        dst[i] = 0;
    }
}

static inline void store_packed_13(uintptr_t dst_addr)
{
    volatile uint32_t *dst32 = u32p(dst_addr);
    dst32[0] = acc_read_conv_packed(0);
    dst32[1] = acc_read_conv_packed(1);
    dst32[2] = acc_read_conv_packed(2);
    u8p(dst_addr)[12] = (uint8_t)acc_read_conv_packed(3);
}

static inline void accumulate_raw_11(uintptr_t accum_addr)
{
    volatile int32_t *accum = i32p(accum_addr);
    accum[0] = accum[0] + acc_read_conv_raw(0);
    accum[1] = accum[1] + acc_read_conv_raw(1);
    accum[2] = accum[2] + acc_read_conv_raw(2);
    accum[3] = accum[3] + acc_read_conv_raw(3);
    accum[4] = accum[4] + acc_read_conv_raw(4);
    accum[5] = accum[5] + acc_read_conv_raw(5);
    accum[6] = accum[6] + acc_read_conv_raw(6);
    accum[7] = accum[7] + acc_read_conv_raw(7);
    accum[8] = accum[8] + acc_read_conv_raw(8);
    accum[9] = accum[9] + acc_read_conv_raw(9);
    accum[10] = accum[10] + acc_read_conv_raw(10);
}

static void postprocess_accum_11(uintptr_t accum_addr, uintptr_t dst_addr)
{
    volatile int32_t *accum = i32p(accum_addr);
    volatile uint8_t *dst = u8p(dst_addr);
    for (uint32_t col = 0; col < CONV2_W_COUNT; ++col) {
        dst[col] = post_i32(accum[col]);
    }
}

static inline void fill_fc_scratch_conv2_chunk_0(void)
{
    volatile uint8_t *scratch = u8p(D_SCRATCH_ADDR);
    volatile uint8_t *conv2 = u8p(D_CONV2_ADDR);
    scratch[0] = conv2[0];
    scratch[1] = conv2[1];
    scratch[2] = conv2[2];
    scratch[16] = conv2[3];
    scratch[17] = conv2[4];
    scratch[18] = conv2[5];
    scratch[32] = conv2[6];
    scratch[33] = conv2[7];
    scratch[34] = conv2[8];
    scratch[3] = conv2[9];
    scratch[4] = conv2[10];
    scratch[5] = conv2[16];
    scratch[19] = conv2[17];
    scratch[20] = conv2[18];
    scratch[21] = conv2[19];
    scratch[35] = conv2[20];
    scratch[36] = conv2[21];
    scratch[37] = conv2[22];
    scratch[6] = conv2[23];
    scratch[7] = conv2[24];
    scratch[8] = conv2[25];
    scratch[22] = conv2[26];
    scratch[23] = conv2[32];
    scratch[24] = conv2[33];
    scratch[38] = conv2[34];
    scratch[39] = conv2[35];
    scratch[40] = conv2[36];
    scratch[9] = conv2[37];
    scratch[10] = conv2[38];
    scratch[11] = conv2[39];
    scratch[25] = conv2[40];
    scratch[26] = conv2[41];
    scratch[27] = conv2[42];
    scratch[41] = conv2[48];
    scratch[42] = conv2[49];
    scratch[43] = conv2[50];
}

static inline void fill_fc_scratch_conv2_chunk_1(void)
{
    volatile uint8_t *scratch = u8p(D_SCRATCH_ADDR);
    volatile uint8_t *conv2 = u8p(D_CONV2_ADDR);
    scratch[0] = conv2[51];
    scratch[1] = conv2[52];
    scratch[2] = conv2[53];
    scratch[16] = conv2[54];
    scratch[17] = conv2[55];
    scratch[18] = conv2[56];
    scratch[32] = conv2[57];
    scratch[33] = conv2[58];
    scratch[34] = conv2[64];
    scratch[3] = conv2[65];
    scratch[4] = conv2[66];
    scratch[5] = conv2[67];
    scratch[19] = conv2[68];
    scratch[20] = conv2[69];
    scratch[21] = conv2[70];
    scratch[35] = conv2[71];
    scratch[36] = conv2[72];
    scratch[37] = conv2[73];
    scratch[6] = conv2[74];
    scratch[7] = conv2[80];
    scratch[8] = conv2[81];
    scratch[22] = conv2[82];
    scratch[23] = conv2[83];
    scratch[24] = conv2[84];
    scratch[38] = conv2[85];
    scratch[39] = conv2[86];
    scratch[40] = conv2[87];
    scratch[9] = conv2[88];
    scratch[10] = conv2[89];
    scratch[11] = conv2[90];
    scratch[25] = conv2[96];
    scratch[26] = conv2[97];
    scratch[27] = conv2[98];
    scratch[41] = conv2[99];
    scratch[42] = conv2[100];
    scratch[43] = conv2[101];
}

static inline void fill_fc_scratch_conv2_chunk_2(void)
{
    volatile uint8_t *scratch = u8p(D_SCRATCH_ADDR);
    volatile uint8_t *conv2 = u8p(D_CONV2_ADDR);
    scratch[0] = conv2[102];
    scratch[1] = conv2[103];
    scratch[2] = conv2[104];
    scratch[16] = conv2[105];
    scratch[17] = conv2[106];
    scratch[18] = conv2[112];
    scratch[32] = conv2[113];
    scratch[33] = conv2[114];
    scratch[34] = conv2[115];
    scratch[3] = conv2[116];
    scratch[4] = conv2[117];
    scratch[5] = conv2[118];
    scratch[19] = conv2[119];
    scratch[20] = conv2[120];
    scratch[21] = conv2[121];
    scratch[35] = conv2[122];
    scratch[36] = conv2[128];
    scratch[37] = conv2[129];
    scratch[6] = conv2[130];
    scratch[7] = conv2[131];
    scratch[8] = conv2[132];
    scratch[22] = conv2[133];
    scratch[23] = conv2[134];
    scratch[24] = conv2[135];
    scratch[38] = conv2[136];
    scratch[39] = conv2[137];
    scratch[40] = conv2[138];
    scratch[9] = conv2[144];
    scratch[10] = conv2[145];
    scratch[11] = conv2[146];
    scratch[25] = conv2[147];
    scratch[26] = conv2[148];
    scratch[27] = conv2[149];
    scratch[41] = conv2[150];
    scratch[42] = conv2[151];
    scratch[43] = conv2[152];
}

static inline void fill_fc_scratch_conv2_chunk_3(void)
{
    volatile uint8_t *scratch = u8p(D_SCRATCH_ADDR);
    volatile uint8_t *conv2 = u8p(D_CONV2_ADDR);
    scratch[0] = conv2[153];
    scratch[1] = conv2[154];
    scratch[2] = conv2[160];
    scratch[16] = conv2[161];
    scratch[17] = conv2[162];
    scratch[18] = conv2[163];
    scratch[32] = conv2[164];
    scratch[33] = conv2[165];
    scratch[34] = conv2[166];
    scratch[3] = conv2[167];
    scratch[4] = conv2[168];
    scratch[5] = conv2[169];
    scratch[19] = conv2[170];
    scratch[20] = conv2[176];
    scratch[21] = conv2[177];
    scratch[35] = conv2[178];
    scratch[36] = conv2[179];
    scratch[37] = conv2[180];
    scratch[6] = conv2[181];
    scratch[7] = conv2[182];
    scratch[8] = conv2[183];
    scratch[22] = conv2[184];
    scratch[23] = conv2[185];
    scratch[24] = conv2[186];
    scratch[38] = 0u;
    scratch[39] = 0u;
    scratch[40] = 0u;
    scratch[9] = 0u;
    scratch[10] = 0u;
    scratch[11] = 0u;
    scratch[25] = 0u;
    scratch[26] = 0u;
    scratch[27] = 0u;
    scratch[41] = 0u;
    scratch[42] = 0u;
    scratch[43] = 0u;
}

static inline void fill_fc_scratch_fc1(void)
{
    volatile uint8_t *scratch = u8p(D_SCRATCH_ADDR);
    volatile uint8_t *fc1 = u8p(D_FC1_ADDR);
    scratch[0] = fc1[0];
    scratch[1] = fc1[1];
    scratch[2] = fc1[2];
    scratch[16] = fc1[3];
    scratch[17] = fc1[4];
    scratch[18] = fc1[5];
    scratch[32] = fc1[6];
    scratch[33] = fc1[7];
    scratch[34] = fc1[8];
    scratch[3] = fc1[9];
    scratch[4] = 0u;
    scratch[5] = 0u;
    scratch[19] = 0u;
    scratch[20] = 0u;
    scratch[21] = 0u;
    scratch[35] = 0u;
    scratch[36] = 0u;
    scratch[37] = 0u;
    scratch[6] = 0u;
    scratch[7] = 0u;
    scratch[8] = 0u;
    scratch[22] = 0u;
    scratch[23] = 0u;
    scratch[24] = 0u;
    scratch[38] = 0u;
    scratch[39] = 0u;
    scratch[40] = 0u;
    scratch[9] = 0u;
    scratch[10] = 0u;
    scratch[11] = 0u;
    scratch[25] = 0u;
    scratch[26] = 0u;
    scratch[27] = 0u;
    scratch[41] = 0u;
    scratch[42] = 0u;
    scratch[43] = 0u;
}

static void run_conv1(void)
{
    for (uint32_t co = 0; co < CONV1_COUT_COUNT; ++co) {
        const uint32_t *weights = conv1_w_packed + co * 3u;
        uintptr_t out_base = D_CONV1_ADDR + co * CONV1_CH_SIZE_BYTES;
        acc_write_conv_w0(weights);
        acc_load_three_rows(D_INPUT_ADDR, ROW_STRIDE_BYTES);
        for (uint32_t row = 0; row < CONV1_H_COUNT; ++row) {
            if (row < CONV1_H_COUNT - 1u) {
                acc_set_dma_addr(D_INPUT_ADDR + (row + 3u) * ROW_STRIDE_BYTES);
            }
            acc_start_conv();
            acc_wait_done();
            store_packed_13(out_base + row * CONV1_ROW_STRIDE_BYTES);
            if (row < CONV1_H_COUNT - 1u) {
                acc_shift_lines();
            }
        }
    }
}

static void run_conv2(void)
{
    zero_words(D_ACCUM_ADDR, CONV2_H_COUNT * CONV2_W_COUNT);
    for (uint32_t ci = 0; ci < CONV1_COUT_COUNT; ++ci) {
        const uint32_t *weights = conv2_w_packed + ci * 3u;
        uintptr_t in_base = D_CONV1_ADDR + ci * CONV1_CH_SIZE_BYTES;
        acc_write_conv_w0(weights);
        acc_load_three_rows(in_base, CONV1_ROW_STRIDE_BYTES);
        /* Conv2 row 0. */
        acc_set_dma_addr(in_base + 3u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 0u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 1. */
        acc_set_dma_addr(in_base + 4u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 44u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 2. */
        acc_set_dma_addr(in_base + 5u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 88u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 3. */
        acc_set_dma_addr(in_base + 6u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 132u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 4. */
        acc_set_dma_addr(in_base + 7u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 176u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 5. */
        acc_set_dma_addr(in_base + 8u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 220u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 6. */
        acc_set_dma_addr(in_base + 9u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 264u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 7. */
        acc_set_dma_addr(in_base + 10u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 308u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 8. */
        acc_set_dma_addr(in_base + 11u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 352u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 9. */
        acc_set_dma_addr(in_base + 12u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 396u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 10. */
        acc_set_dma_addr(in_base + 13u * CONV1_ROW_STRIDE_BYTES);
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 440u);
        acc_wait_done();
        acc_shift_lines();
        /* Conv2 row 11. */
        acc_start_conv();
        accumulate_raw_11(D_ACCUM_ADDR + 484u);
        acc_wait_done();
    }
    for (uint32_t row = 0; row < CONV2_H_COUNT; ++row) {
        postprocess_accum_11(
            D_ACCUM_ADDR + row * CONV2_W_COUNT * 4u,
            D_CONV2_ADDR + row * CONV2_ROW_STRIDE_BYTES);
    }
}

static void run_fc1(void)
{
    zero_words(D_ACCUM_ADDR, FC1_OUT_COUNT);
    fill_fc_scratch_conv2_chunk_0();
    acc_load_three_rows(D_SCRATCH_ADDR, ROW_STRIDE_BYTES);
    acc_write_fc_weights(fc1_w_packed + 0u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[0] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 48u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[1] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 96u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[2] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 144u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[3] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 192u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[4] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 240u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[5] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 288u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[6] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 336u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[7] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 384u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[8] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 432u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[9] += acc_read_fc_raw();
    fill_fc_scratch_conv2_chunk_1();
    acc_load_three_rows(D_SCRATCH_ADDR, ROW_STRIDE_BYTES);
    acc_write_fc_weights(fc1_w_packed + 12u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[0] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 60u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[1] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 108u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[2] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 156u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[3] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 204u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[4] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 252u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[5] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 300u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[6] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 348u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[7] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 396u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[8] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 444u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[9] += acc_read_fc_raw();
    fill_fc_scratch_conv2_chunk_2();
    acc_load_three_rows(D_SCRATCH_ADDR, ROW_STRIDE_BYTES);
    acc_write_fc_weights(fc1_w_packed + 24u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[0] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 72u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[1] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 120u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[2] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 168u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[3] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 216u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[4] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 264u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[5] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 312u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[6] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 360u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[7] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 408u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[8] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 456u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[9] += acc_read_fc_raw();
    fill_fc_scratch_conv2_chunk_3();
    acc_load_three_rows(D_SCRATCH_ADDR, ROW_STRIDE_BYTES);
    acc_write_fc_weights(fc1_w_packed + 36u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[0] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 84u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[1] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 132u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[2] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 180u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[3] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 228u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[4] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 276u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[5] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 324u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[6] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 372u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[7] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 420u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[8] += acc_read_fc_raw();
    acc_write_fc_weights(fc1_w_packed + 468u);
    acc_start_fc();
    acc_wait_done();
    i32p(D_ACCUM_ADDR)[9] += acc_read_fc_raw();
    for (uint32_t neuron = 0; neuron < FC1_OUT_COUNT; ++neuron) {
        u8p(D_FC1_ADDR)[neuron] = post_i32(i32p(D_ACCUM_ADDR)[neuron]);
    }
}

static void run_fc2(void)
{
    fill_fc_scratch_fc1();
    acc_write_fc_weights(fc2_w_packed);
    acc_load_three_rows(D_SCRATCH_ADDR, ROW_STRIDE_BYTES);
    acc_start_fc();
    acc_wait_done();
    u8p(D_OUTPUT_ADDR)[0] = post_i32(acc_read_fc_raw());
}

void cnn_main(void)
{
    acc_global_reset();
    run_conv1();
    run_conv2();
    run_fc1();
    run_fc2();
    for (;;) {
    }
}

__attribute__((naked, section(".text.start"))) void _start(void)
{
    __asm__ volatile(
        ".option push\n"
        ".option norvc\n"
        "li sp, 0x90001ffc\n"
        "call cnn_main\n"
        "1: j 1b\n"
        ".option pop\n");
}
