// prueba_placa_top.v - SOLO PARA PROBAR EN LA PLACA (make prueba-placa VARIANT=...).
// El SoC de la competencia + la maestra embebida conectada por dentro a su SPI.
// Se sintetiza con -DSIN_CONTADOR_CICLOS: el contador de ciclos del Proyecto 2 no lo
// usa trade.s y sin el cabe la maestra junto al SoC con mul8.
//
// Lo que se ve en la Go Board:
//   mientras corre (0,1 s):      displays = precio actual (lo escribe trade.s)
//   termino y todo coincide:     los 4 LEDs prendidos fijos
//   termino y hubo un error:     los 4 LEDs parpadean
// Los pines SPI del PMOD no se usan: la maestra esta adentro.
module prueba_placa_top (
  input  wire       i_Clk,
  output wire [3:0] o_LED,
  input  wire [3:0] i_Switch,
  output wire       o_Segment1_A, o_Segment1_B, o_Segment1_C, o_Segment1_D,
  output wire       o_Segment1_E, o_Segment1_F, o_Segment1_G,
  output wire       o_Segment2_A, o_Segment2_B, o_Segment2_C, o_Segment2_D,
  output wire       o_Segment2_E, o_Segment2_F, o_Segment2_G,
  input  wire       i_SPI_SCLK,
  input  wire       i_SPI_MOSI,
  input  wire       i_SPI_CS_n,
  output wire       o_SPI_MISO
);

  wire sclk, mosi, cs_n, miso;
  wire fin, error;
  wire [3:0] led_soc;

  pochoco_soc u_soc (
    .i_Clk(i_Clk), .o_LED(led_soc), .i_Switch(i_Switch),
    .o_Segment1_A(o_Segment1_A), .o_Segment1_B(o_Segment1_B), .o_Segment1_C(o_Segment1_C),
    .o_Segment1_D(o_Segment1_D), .o_Segment1_E(o_Segment1_E), .o_Segment1_F(o_Segment1_F),
    .o_Segment1_G(o_Segment1_G),
    .o_Segment2_A(o_Segment2_A), .o_Segment2_B(o_Segment2_B), .o_Segment2_C(o_Segment2_C),
    .o_Segment2_D(o_Segment2_D), .o_Segment2_E(o_Segment2_E), .o_Segment2_F(o_Segment2_F),
    .o_Segment2_G(o_Segment2_G),
    .i_SPI_SCLK(sclk), .i_SPI_MOSI(mosi), .i_SPI_CS_n(cs_n), .o_SPI_MISO(miso)
  );

  // Un solo contador: el bit 13 (8192 ciclos) da la partida, despues de que el SoC
  // salio del reset (4095 ciclos); el bit 22 (~6 Hz) hace parpadear los LEDs.
  reg [22:0] cnt = 23'd0;
  reg        partio = 1'b0;
  always @(posedge i_Clk) begin
    cnt <= cnt + 23'd1;
    if (cnt[13]) partio <= 1'b1;
  end

  maestra_embebida u_maestra (
    .clk_i(i_Clk), .start_i(partio),
    .sclk_o(sclk), .mosi_o(mosi), .cs_n_o(cs_n), .miso_i(miso),
    .fin_o(fin), .error_o(error)
  );

  assign o_LED = !fin ? led_soc : (error ? {4{cnt[22]}} : 4'b1111);

  assign o_SPI_MISO = 1'b0;
  wire _sin_usar = &{1'b0, i_SPI_SCLK, i_SPI_MOSI, i_SPI_CS_n};

endmodule
