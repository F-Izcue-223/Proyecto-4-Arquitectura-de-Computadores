// tb_prueba_placa.v - simula el bitstream de prueba en placa antes de grabarlo.
// Se ejecuta con:  make sim-prueba-placa VARIANT=...
`timescale 1ns/1ps

module tb_prueba_placa;
  reg clk = 1'b0;
  always #20 clk = ~clk;              // 25 MHz

  wire [3:0] led;
  prueba_placa_top dut (
    .i_Clk(clk), .o_LED(led), .i_Switch(4'b0000),
    .o_Segment1_A(), .o_Segment1_B(), .o_Segment1_C(), .o_Segment1_D(),
    .o_Segment1_E(), .o_Segment1_F(), .o_Segment1_G(),
    .o_Segment2_A(), .o_Segment2_B(), .o_Segment2_C(), .o_Segment2_D(),
    .o_Segment2_E(), .o_Segment2_F(), .o_Segment2_G(),
    .i_SPI_SCLK(1'b0), .i_SPI_MOSI(1'b0), .i_SPI_CS_n(1'b1), .o_SPI_MISO()
  );

  initial begin
    wait (dut.fin);
    if (!dut.error)
      $display("PRUEBA EN PLACA (simulada): OK - %0d transacciones, todos los bytes esperados", dut.u_maestra.n);
    else
      $fatal(1, "PRUEBA EN PLACA (simulada): FALLO, algun byte no fue el esperado");
    $finish;
  end
endmodule
