// isa_tb.v - corre sim/isa_test.hex (armado para la variante) sobre el SoC y revisa el resultado.
// Se ejecuta con:  make sim-isa VARIANT=<sw|shift|mul8|mul8shift>
// Viene del Proyecto 2; en el Proyecto 4 instancia pochoco_soc directamente.
`timescale 1ns/1ps

module isa_tb;
  reg clk = 1'b0;
  always #20 clk = ~clk;                       // 25 MHz

  wire [3:0] led;
  wire [6:0] seg1, seg2;                       // pines {G,F,E,D,C,B,A}, activos en bajo

  pochoco_soc #(.MemFile("build/isa_test.hex")) dut (
    .i_Clk(clk), .o_LED(led), .i_Switch(4'b1010),
    .o_Segment1_A(seg1[0]), .o_Segment1_B(seg1[1]), .o_Segment1_C(seg1[2]), .o_Segment1_D(seg1[3]),
    .o_Segment1_E(seg1[4]), .o_Segment1_F(seg1[5]), .o_Segment1_G(seg1[6]),
    .o_Segment2_A(seg2[0]), .o_Segment2_B(seg2[1]), .o_Segment2_C(seg2[2]), .o_Segment2_D(seg2[3]),
    .o_Segment2_E(seg2[4]), .o_Segment2_F(seg2[5]), .o_Segment2_G(seg2[6]),
    .i_SPI_SCLK(1'b0), .i_SPI_MOSI(1'b0), .i_SPI_CS_n(1'b1), .o_SPI_MISO()
  );

  `include "sim/seg2hex.vh"

  initial begin
    wait (led == 4'hF || led == 4'h9);
    repeat (5) @(posedge clk);
    if (led == 4'hF && shown(seg1, seg2) == 8'hAA)
      $display("ISA: OK - todas las pruebas pasaron");
    else
      $fatal(1, "ISA: FALLO - prueba %0d (displays = %h)", shown(seg1, seg2), shown(seg1, seg2));
    $finish;
  end

  initial begin
    #(40 * 40000);
    $fatal(1, "ISA: FALLO - timeout, el programa no termino");
  end
endmodule
