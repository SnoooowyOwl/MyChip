module bootram(
    input  logic        clk_i,
    input  logic        rst_ni,
    input  logic        req_i,
    input  logic        wen_i,
    input  logic [3:0]  addr_i,
    input  logic [31:0] data_i,
    output logic [31:0] data_o
);
    logic [15:0][31:0]  mem_q;
    logic [15:0][31:0]  mem_d;
    logic [31:0]        data_d;

    always@ (posedge clk_i or negedge rst_ni) begin
        if(!rst_ni) begin
            // lui t0, 0x80000 (assign 0x80000000 to register t0)
            // By convention, the variable t0 here will actually
            // point to x5
            // 0x80000000 is the base address of sram_ff
            mem_q[0] <= 32'h800002b7;
            // addi t0, t0, 0x000
            mem_q[1] <= 32'h00028293;
            // jr t0 (jump to t0, discarding the result; short for jalr x0 t0)
            // jalr x0 t0 stores the address of the next instruction
            // following the jump into x0, which is hard-wired to zero;
            // this actually means that the result is discarded
            mem_q[2] <= 32'h00028067;
            // Set the remaining registers which will not be read to zero
            for(int i = 3; i < 16; i = i + 1) begin
                mem_q[i] <= '0;
            end
            data_o <= '0;
        end
        else begin
            mem_q  <= mem_d;
            data_o <= data_d;
        end
    end

    always_comb begin
        mem_d  = mem_q;
        data_d = data_o;
        if(req_i) begin
            if(wen_i) begin
                mem_d[addr_i] = data_i;
            end
            data_d = mem_q[addr_i];
        end
        else begin
            data_d = '0;
        end
    end
endmodule
