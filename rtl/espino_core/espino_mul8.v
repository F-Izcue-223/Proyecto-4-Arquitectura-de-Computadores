// Proyecto 4, variante "mul8": multiplicador secuencial para la instruccion
//     mul8 rd, rs1, rs2      rd = rs1 * rs2[7:0]   (32 bits bajos)
// codificada en el espacio custom-0 de RISC-V (opcode 0x0B, tipo R, funct3 = 0).
//
// Por que secuencial: la iCE40 HX1K no tiene multiplicadores, y uno
// combinacional de 32x8 son 7 sumadores de 32 bits (~250 celdas, el 20 % del
// chip). Este hace un bit del multiplicador por ciclo con un solo sumador:
//     si b[0] = 1:  acc += a;    a <<= 1;   b >>= 1
// y termina apenas los bits que quedan de b son todos 0. El primer paso se hace
// en el mismo ciclo en que se cargan los operandos.
//
// Latencia en el core: 1 ciclo de espera del banco de registros + n pasos + 1
// ciclo de escritura, con n = max(1, bits significativos de b). Para los
// umbrales de trade.s (constantes chicas) son entre 3 y 5 ciclos,
// contra ~65 de la rutina por software (mulsw).
//
// Protocolo con la etapa ID (igual que la LSU con los loads):
//   req_i  = hay un mul8 en ID con los operandos ya leidos.
//   busy_o = detener el pipeline. Se baja en el ciclo en que el producto esta
//            listo: en ese ciclo la etapa ID escribe result_o en rd.
module espino_mul8 (
  input  wire        clk_i,
  input  wire        rst_ni,
  input  wire        req_i,
  input  wire [31:0] a_i,
  input  wire [7:0]  b_i,
  output wire        busy_o,
  output wire [31:0] result_o
);

  reg        run_q;     // hay una multiplicacion en curso
  reg        done_q;    // el producto esta listo (ciclo de escritura)
  reg [31:0] acc_q;     // suma parcial
  reg [31:0] a_q;       // multiplicando, desplazado a la izquierda en cada paso
  reg [6:0]  b_q;       // bits del multiplicador que faltan

  // Un paso: con los operandos de entrada (primer ciclo) o con los guardados.
  wire        first = req_i & ~run_q & ~done_q;
  wire [31:0] a_cur = first ? a_i      : a_q;
  wire [7:0]  b_cur = first ? b_i      : {1'b0, b_q};
  wire [31:0] acc_c = first ? 32'd0    : acc_q;
  wire [31:0] acc_n = b_cur[0] ? acc_c + a_cur : acc_c;
  wire        last  = (b_cur[7:1] == 7'd0);

  always @(posedge clk_i or negedge rst_ni) begin
    if (!rst_ni) begin
      run_q  <= 1'b0;
      done_q <= 1'b0;
      acc_q  <= 32'd0;
      a_q    <= 32'd0;
      b_q    <= 7'd0;
    end else if (done_q) begin
      done_q <= 1'b0;                 // la etapa ID ya escribio el resultado
    end else if (first | run_q) begin
      acc_q  <= acc_n;
      a_q    <= {a_cur[30:0], 1'b0};
      b_q    <= b_cur[7:1];
      run_q  <= ~last;
      done_q <= last;
    end
  end

  assign busy_o   = req_i & ~done_q;
  assign result_o = acc_q;

endmodule
