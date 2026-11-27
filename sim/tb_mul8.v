// tb_mul8.v - prueba unitaria de rtl/espino_core/espino_mul8.v.
// Se ejecuta con:  make sim-mul8
//
// Hace de etapa ID: pide una multiplicacion, mantiene req mientras busy esta en 1
// y lee el resultado en el ciclo en que busy baja. Revisa para cada caso:
//   1. el producto (32 bits bajos de a * b[7:0]);
//   2. la latencia: busy dura exactamente max(1, bits de b) ciclos, que es lo que
//      supone el modelo de ciclos de ref/espino_iss.py.
// Casos: bordes (0, 1, 255, 2^31) y 20 000 al azar.
`timescale 1ns/1ps

module tb_mul8;
  reg clk = 1'b0;
  always #20 clk = ~clk;

  reg         rst_n = 1'b0;
  reg         req = 1'b0;
  reg  [31:0] a = 0;
  reg  [7:0]  b = 0;
  wire        busy;
  wire [31:0] y;

  espino_mul8 dut (.clk_i(clk), .rst_ni(rst_n), .req_i(req), .a_i(a), .b_i(b),
                   .busy_o(busy), .result_o(y));

  integer errores = 0, casos = 0, i;

  function integer bits_de(input [7:0] v);
    integer k;
    begin
      bits_de = 1;
      for (k = 0; k < 8; k = k + 1) if (v[k]) bits_de = k + 1;
    end
  endfunction

  task probar(input [31:0] ta, input [7:0] tb);
    integer ciclos;
    reg [31:0] esperado;
    begin
      @(negedge clk);
      a = ta; b = tb; req = 1'b1;          // operandos listos en ID
      ciclos = 0;
      #1;
      while (busy) begin                   // cuenta los ciclos detenidos
        ciclos = ciclos + 1;
        @(negedge clk);
      end
      // busy = 0: ciclo de escritura, el producto ya esta en result_o
      esperado = ta * tb;
      casos = casos + 1;
      if (y !== esperado || ciclos != bits_de(tb)) begin
        errores = errores + 1;
        if (errores < 10)
          $display("FALLO: %0d * %0d = %0d (esperado %0d), %0d ciclos (esperado %0d)",
                   ta, tb, y, esperado, ciclos, bits_de(tb));
      end
      @(negedge clk);
      req = 1'b0;            // la etapa ID avanzo; la siguiente instruccion pasa
    end                      // un ciclo esperando el banco de registros (el @negedge de arriba)
  endtask

  initial begin
    repeat (3) @(posedge clk);
    rst_n = 1'b1;
    probar(0, 0);
    probar(12345, 0);
    probar(12345, 1);
    probar(32'hFFFFFFFF, 8'hFF);
    probar(32'h01000000, 8'h80);
    probar(255, 255);
    for (i = 0; i < 20000; i = i + 1)
      probar($random, $random);
    if (errores == 0)
      $display("MUL8: OK - %0d casos, producto y latencia correctos", casos);
    else
      $fatal(1, "MUL8: FALLO - %0d de %0d casos", errores, casos);
    $finish;
  end
endmodule
