`timescale 1ns / 1ps

// =================================================================
// 1. 核心计算单元 (PE) - 保持不变
// =================================================================
module conv_core (
    input  logic [7:0]        data_window [0:8], // 无符号输入
    input  logic signed [7:0] weights [0:8],     // 有符号权重
    output logic signed [31:0] psum_out,         // 原始累加和
    output logic [7:0]        result_out         // ReLU + 截断后结果
);
    logic signed [16:0] prods [0:8];
    logic signed [31:0] sum_all;
    genvar k;
    generate
        for (k = 0; k < 9; k = k + 1) begin : gen_mult
            assign prods[k] = $signed({1'b0, data_window[k]}) * weights[k];
        end
    endgenerate
    assign sum_all = prods[0] + prods[1] + prods[2] +
                     prods[3] + prods[4] + prods[5] +
                     prods[6] + prods[7] + prods[8];
    assign psum_out = sum_all;
    assign result_out = (sum_all[31]) ? 8'd0 : sum_all[7:0];
endmodule

// =================================================================
// 2. 加速器顶层模块 (1组PE版 - 资源最小化)
// =================================================================
module accelerator (
    input  logic        clka,
    input  logic        rst_ni,
    // Slave Interface
    input  logic        wea,
    input  logic        ena,
    input  logic [10:0] addra,
    input  logic [31:0] dina,
    output logic [31:0] douta,
    // Master Interface
    output logic [31:0] m_axi_araddr,
    output logic [7:0]  m_axi_arlen,
    output logic [2:0]  m_axi_arsize,
    output logic [1:0]  m_axi_arburst,
    output logic        m_axi_arvalid,
    input  logic        m_axi_arready,
    input  logic [31:0] m_axi_rdata,
    input  logic [1:0]  m_axi_rresp,
    input  logic        m_axi_rlast,
    input  logic        m_axi_rvalid,
    output logic        m_axi_rready
);

    // =================================================================
    // --- 1. 参数定义 (保持不变) ---
    // =================================================================
    localparam ADDR_CTRL_STATUS    = 11'h000;
    localparam ADDR_SRC_ADDR       = 11'h004;
    // Weights Addresses
    localparam ADDR_W0_0_3         = 11'h034; localparam ADDR_W0_4_7 = 11'h038; localparam ADDR_W0_8 = 11'h03C;
    localparam ADDR_W1_0_3         = 11'h040; localparam ADDR_W1_4_7 = 11'h044; localparam ADDR_W1_8 = 11'h048;
    localparam ADDR_W2_0_3         = 11'h04C; localparam ADDR_W2_4_7 = 11'h050; localparam ADDR_W2_8 = 11'h054;
    localparam ADDR_W3_0_3         = 11'h058; localparam ADDR_W3_4_7 = 11'h05C; localparam ADDR_W3_8 = 11'h060;
    // Results
    localparam ADDR_RES_PACK_0     = 11'h064; localparam ADDR_RES_PACK_1 = 11'h068; 
    localparam ADDR_RES_PACK_2     = 11'h06C; localparam ADDR_RES_PACK_3 = 11'h070; 
    localparam ADDR_RES_ORI_BASE   = 11'h078;
    // Commands
    localparam CMD_START_CONV      = 32'h0000FFFF;
    localparam CMD_START_FC        = 32'h000FFFFF;
    localparam CMD_RESET_PSUMS     = 32'h0FFFFFFF;
    localparam CMD_GLOBAL_RESET    = 32'hFFFFFFFF;
    localparam CMD_SHIFT_LINES     = 32'h00000200;
    // Status
    localparam STATUS_DONE         = 32'h00000001;
    localparam STATUS_BUSY         = 32'h00000000;

    // =================================================================
    // --- 2. 内部存储 ---
    // =================================================================
    reg  [7:0] line_buffer [0:2][0:15];
    reg  [7:0] prefetch_buffer [0:15];
    
    // 权重寄存器：保留4组，为了兼容软件写入
    reg  signed [7:0] weights [0:3][0:8];
    
    // 结果寄存器
    reg  [7:0]        conv_final_results [0:13];
    reg  signed [31:0] conv_psum [0:13];
    
    // FC 模式累加寄存器
    reg  signed [31:0] fc_accum; 
    reg  signed [31:0] fc_result;

    reg [31:0] reg_src_addr;
    reg [31:0] douta_reg;
    reg [31:0] status_reg;

    typedef enum logic { MODE_CONV, MODE_FC } mode_t;
    mode_t current_mode;

    typedef enum logic [1:0] { IDLE, COMPUTING, DONE } comp_state_t;
    reg [1:0] comp_state;
    reg [3:0] sub_cycle_cnt; // 扩展为4bit，因为Conv模式需要计数到13

    // DMA
    typedef enum logic [1:0] { DMA_IDLE, DMA_SEND_ADDR, DMA_READ_DATA } dma_state_t;
    reg [1:0] dma_state;
    reg dma_addr_valid;
    reg [31:0] dma_read_addr;
    reg [2:0]  dma_word_cnt;

    // =================================================================
    // --- 3. 核心计算逻辑 (1-Way 串行，物理资源最小) ---
    // =================================================================
    
    // 单个 PE 接口信号
    logic [7:0]         pe_window [0:8];
    logic signed [7:0]  pe_weight [0:8]; 
    logic signed [31:0] pe_psum;
    logic [7:0]         pe_result;      

    // --- 3a. 实例化 1 个计算核心 (Single Instance) ---
    conv_core u_core (
        .data_window (pe_window),
        .weights     (pe_weight), 
        .psum_out    (pe_psum),
        .result_out  (pe_result)
    );

    // --- 3b. 动态数据与权重分发 (时分复用逻辑 - 1核) ---
    always_comb begin
        integer k;
        integer center_col;
        integer tile_col_base;
        
        // 默认清零
        for (k = 0; k < 9; k = k + 1) begin
            pe_window[k] = 8'd0;
            pe_weight[k] = 8'd0;
        end

        if (current_mode == MODE_FC) begin
            // ====== FC Mode (0~3 Cycles) ======
            // Cycle 0: Group 0 weights, Cols 0-2
            // Cycle 1: Group 1 weights, Cols 3-5
            // Cycle 2: Group 2 weights, Cols 6-8
            // Cycle 3: Group 3 weights, Cols 9-11
            
            // 1. 权重：直接使用 sub_cycle_cnt 作为组索引
            for (k = 0; k < 9; k = k + 1) pe_weight[k] = weights[sub_cycle_cnt][k];

            // 2. 数据：平铺
            tile_col_base = sub_cycle_cnt * 3;
            for (k = 0; k < 9; k = k + 1) begin
                pe_window[k] = line_buffer[k/3][tile_col_base + (k % 3)];
            end
        end 
        else begin
            // ====== Conv Mode (0~13 Cycles) ======
            // Cycle 0 -> Calc result 0
            // ...
            // Cycle 13 -> Calc result 13
            
            // 1. 权重：始终共享 Group 0
            for (k = 0; k < 9; k = k + 1) pe_weight[k] = weights[0][k];

            // 2. 数据：滑窗，center_col 就是 sub_cycle_cnt
            center_col = sub_cycle_cnt; 
            
            if (center_col < 14) begin
                for (k = 0; k < 9; k = k + 1) begin
                    pe_window[k] = line_buffer[k/3][center_col + (k % 3)];
                end
            end
        end
    end

    // =================================================================
    // --- 3c. AXI Master (保持不变) ---
    // =================================================================
    assign m_axi_araddr  = dma_read_addr;
    assign m_axi_arlen   = 8'd3;    
    assign m_axi_arsize  = 3'b010;  
    assign m_axi_arburst = 2'b01;
    always_comb begin
        m_axi_arvalid = 1'b0;
        m_axi_rready  = 1'b0;
        case (dma_state)
            DMA_IDLE:      m_axi_arvalid = 1'b0;
            DMA_SEND_ADDR: m_axi_arvalid = 1'b1;
            DMA_READ_DATA: m_axi_rready  = 1'b1;
            default: ;
        endcase
    end
    assign douta = douta_reg;

    // =================================================================
    // --- 4. 时序逻辑 ---
    // =================================================================
    integer i, j;
    logic [10:0] raw_offset;
    logic [31:0] raw_index;

    always_ff @(posedge clka or negedge rst_ni) begin
        if (!rst_ni) begin
            // --- 复位 ---
            comp_state     <= IDLE;
            current_mode   <= MODE_CONV;
            dma_state      <= DMA_IDLE;
            status_reg     <= STATUS_BUSY;
            sub_cycle_cnt  <= 4'b0;
            reg_src_addr   <= 32'h0;
            dma_addr_valid <= 1'b0;
            dma_read_addr  <= 32'h0;
            dma_word_cnt   <= 3'b0;
            douta_reg      <= 32'h0;
            fc_result      <= 32'b0;
            fc_accum       <= 32'b0;

            for (i=0; i<3; i=i+1) for (j=0; j<16; j=j+1) line_buffer[i][j] <= 8'b0;
            for (j=0; j<16; j=j+1) prefetch_buffer[j] <= 8'b0;
            for (i=0; i<4; i=i+1) for (j=0; j<9; j=j+1) weights[i][j] <= 8'b0;
            for (i=0; i<14; i=i+1) conv_final_results[i] <= 8'b0;
            for (i=0; i<14; i=i+1) conv_psum[i] <= 32'b0;

        end else begin
            
            // --- 4a. Slave 读写逻辑 (完全保持不变) ---
            if (ena) begin
                if (wea) begin
                    case (addra)
                        ADDR_CTRL_STATUS: begin
                            if (dina == CMD_GLOBAL_RESET) begin
                                comp_state     <= IDLE;
                                dma_state      <= DMA_IDLE;
                                status_reg     <= STATUS_BUSY;
                                dma_addr_valid <= 1'b0;
                                for (i=0; i<3; i=i+1) for (j=0; j<16; j=j+1) line_buffer[i][j] <= 8'b0;
                                for (j=0; j<16; j=j+1) prefetch_buffer[j] <= 8'b0;
                                for (i=0; i<14; i=i+1) conv_final_results[i] <= 8'b0;
                                for (i=0; i<14; i=i+1) conv_psum[i] <= 32'b0;
                                fc_result <= 32'b0;
                                fc_accum  <= 32'b0;
                            end
                            else if (dina == CMD_RESET_PSUMS) begin
                                status_reg     <= STATUS_BUSY;
                                comp_state     <= IDLE;
                                for (i=0; i<14; i=i+1) conv_final_results[i] <= 8'b0;
                                for (i=0; i<14; i=i+1) conv_psum[i] <= 32'b0;
                                fc_result <= 32'b0;
                                fc_accum  <= 32'b0;
                            end
                            else if (dina == CMD_START_CONV) begin
                                sub_cycle_cnt  <= 4'b0;
                                status_reg     <= STATUS_BUSY;
                                current_mode   <= MODE_CONV;
                                comp_state     <= COMPUTING;
                            end
                            else if (dina == CMD_START_FC) begin
                                sub_cycle_cnt  <= 4'b0;
                                status_reg     <= STATUS_BUSY;
                                current_mode   <= MODE_FC;
                                comp_state     <= COMPUTING;
                                fc_accum       <= 32'b0; // 清空累加器准备新计算
                            end
                            else if (dina == CMD_SHIFT_LINES) begin
                                for (i = 0; i < 16; i = i + 1) begin
                                    line_buffer[0][i] <= line_buffer[1][i];
                                    line_buffer[1][i] <= line_buffer[2][i];
                                    line_buffer[2][i] <= prefetch_buffer[i];
                                end
                            end
                        end
                        ADDR_SRC_ADDR: begin
                            reg_src_addr   <= dina; 
                            dma_addr_valid <= 1'b1;
                        end

                        // --- 权重写入 (4组) ---
                        // 依然保留4组地址映射，存入 weights[0..3]
                        ADDR_W0_0_3: begin weights[0][0]<=dina[7:0]; weights[0][1]<=dina[15:8]; weights[0][2]<=dina[23:16]; weights[0][3]<=dina[31:24]; end
                        ADDR_W0_4_7: begin weights[0][4]<=dina[7:0]; weights[0][5]<=dina[15:8]; weights[0][6]<=dina[23:16]; weights[0][7]<=dina[31:24]; end
                        ADDR_W0_8:   begin weights[0][8]<=dina[7:0]; end
                        
                        ADDR_W1_0_3: begin weights[1][0]<=dina[7:0]; weights[1][1]<=dina[15:8]; weights[1][2]<=dina[23:16]; weights[1][3]<=dina[31:24]; end
                        ADDR_W1_4_7: begin weights[1][4]<=dina[7:0]; weights[1][5]<=dina[15:8]; weights[1][6]<=dina[23:16]; weights[1][7]<=dina[31:24]; end
                        ADDR_W1_8:   begin weights[1][8]<=dina[7:0]; end
                        
                        ADDR_W2_0_3: begin weights[2][0]<=dina[7:0]; weights[2][1]<=dina[15:8]; weights[2][2]<=dina[23:16]; weights[2][3]<=dina[31:24]; end
                        ADDR_W2_4_7: begin weights[2][4]<=dina[7:0]; weights[2][5]<=dina[15:8]; weights[2][6]<=dina[23:16]; weights[2][7]<=dina[31:24]; end
                        ADDR_W2_8:   begin weights[2][8]<=dina[7:0]; end
                        
                        ADDR_W3_0_3: begin weights[3][0]<=dina[7:0]; weights[3][1]<=dina[15:8]; weights[3][2]<=dina[23:16]; weights[3][3]<=dina[31:24]; end
                        ADDR_W3_4_7: begin weights[3][4]<=dina[7:0]; weights[3][5]<=dina[15:8]; weights[3][6]<=dina[23:16]; weights[3][7]<=dina[31:24]; end
                        ADDR_W3_8:   begin weights[3][8]<=dina[7:0]; end

                        default: ;
                    endcase
                end 
                else begin
                    // ====== 读操作 (保持不变) ======
                    raw_offset = addra - ADDR_RES_ORI_BASE;
                    raw_index  = {20'b0, raw_offset[10:2]}; 

                    case (addra)
                        ADDR_CTRL_STATUS:  douta_reg <= status_reg;
                        ADDR_RES_PACK_0: begin
                            if (current_mode == MODE_FC)
                                douta_reg <= fc_result;
                            else
                                douta_reg <= {conv_final_results[3], conv_final_results[2], conv_final_results[1], conv_final_results[0]};
                        end
                        ADDR_RES_PACK_1: douta_reg <= {conv_final_results[7], conv_final_results[6], conv_final_results[5], conv_final_results[4]};
                        ADDR_RES_PACK_2: douta_reg <= {conv_final_results[11], conv_final_results[10], conv_final_results[9], conv_final_results[8]};
                        ADDR_RES_PACK_3: douta_reg <= {16'h0000, conv_final_results[13], conv_final_results[12]};
                        default: begin
                            if (addra >= 11'h078 && addra <= 11'h0AC) begin
                                douta_reg <= conv_psum[raw_index[3:0]];
                            end else begin
                                douta_reg <= 32'h0;
                            end
                        end
                    endcase
                end
            end

            // --- 4b. 计算状态机 (1-Core 极度时分复用) ---
            case (comp_state)
                IDLE: begin end
                
                COMPUTING: begin
                    if (current_mode == MODE_FC) begin
                        // ====== FC 逻辑: 4 周期串行累加 (0,1,2,3) ======
                        if (sub_cycle_cnt == 4'd0) begin
                            // Cycle 0: 算 Group 0
                            fc_accum <= pe_psum; 
                            sub_cycle_cnt <= sub_cycle_cnt + 1;
                        end
                        else if (sub_cycle_cnt < 4'd3) begin
                            // Cycle 1, 2: 算 Group 1, 2 并累加
                            fc_accum <= fc_accum + pe_psum;
                            sub_cycle_cnt <= sub_cycle_cnt + 1;
                        end
                        else begin
                            // Cycle 3: 算 Group 3 并输出最终结果
                            fc_result <= fc_accum + pe_psum;
                            comp_state <= DONE;
                            status_reg <= STATUS_DONE;
                        end
                    end 
                    else begin
                        // ====== Conv 逻辑: 14 周期串行计算 (0~13) ======
                        if (sub_cycle_cnt < 14) begin
                            conv_final_results[sub_cycle_cnt] <= pe_result;
                            conv_psum[sub_cycle_cnt]          <= pe_psum;
                        end

                        if (sub_cycle_cnt == 4'd13) begin // 14个周期
                            comp_state <= DONE;
                            status_reg <= STATUS_DONE; 
                        end else begin
                            sub_cycle_cnt <= sub_cycle_cnt + 1;
                        end
                    end
                end
                
                DONE: begin end
            endcase

            // --- 4c. DMA 状态机 (保持不变) ---
            case (dma_state)
                DMA_IDLE: begin
                    dma_word_cnt <= 3'b0;
                    if (dma_addr_valid) begin 
                        dma_state     <= DMA_SEND_ADDR;
                        dma_read_addr <= reg_src_addr; 
                        dma_addr_valid <= 1'b0;        
                    end
                end
                DMA_SEND_ADDR: begin
                    if (m_axi_arvalid && m_axi_arready) begin
                        dma_state <= DMA_READ_DATA;
                    end
                end
                DMA_READ_DATA: begin
                    if (m_axi_rvalid && m_axi_rready) begin
                        prefetch_buffer[dma_word_cnt*4 + 3] <= m_axi_rdata[31:24];
                        prefetch_buffer[dma_word_cnt*4 + 2] <= m_axi_rdata[23:16];
                        prefetch_buffer[dma_word_cnt*4 + 1] <= m_axi_rdata[15:8];
                        prefetch_buffer[dma_word_cnt*4 + 0] <= m_axi_rdata[7:0];
                        
                        dma_word_cnt <= dma_word_cnt + 1;
                        if (m_axi_rlast) begin
                            if (dma_addr_valid) begin
                                dma_state <= DMA_SEND_ADDR;
                                dma_read_addr <= reg_src_addr; 
                                dma_addr_valid <= 1'b0;        
                            end else begin
                                dma_state <= DMA_IDLE;
                            end
                        end
                    end
                end
                default: dma_state <= DMA_IDLE;
            endcase

        end 
    end 
endmodule