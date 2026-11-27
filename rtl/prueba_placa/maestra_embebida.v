// maestra_embebida.v - SOLO PARA PROBAR EN LA PLACA, no va en el diseno de la competencia
// (el enunciado prohibe guardar series de precios en el diseno).
//
// Hace de FPGA maestra dentro de la misma FPGA: cada T ciclos baja CS_n, manda un
// precio por SPI modo 0 (MSB primero) y lee el byte de DECISION por MISO.
// Los precios y el byte esperado en cada transaccion vienen de una ROM que arma
// tools/prueba_placa.py con ref/trader.py:  rom[n] = {esperado_n, precio_n}.
//
// Para gastar pocas celdas, todo el tiempo sale de un solo contador t (0..T-1):
//   t[11:9] = 0       la transaccion ocupa los primeros 512 ciclos del tick
//   t[8:4]  = fase    17 medios periodos de SCLK de 16 ciclos (SCLK = 0,78 MHz)
//   t[3:0]  = 15      el ciclo en que termina cada medio periodo
// t = 0: CS_n baja y sale el bit 7. Al final de las fases pares 0..14: flanco de
// subida (se muestrea MISO). Al final de las impares 1..15: flanco de bajada (sale el
// bit siguiente). Fase 16: espera. Fin de la fase 17: sube CS_n y se compara el byte
// recibido con el esperado.
module maestra_embebida #(
  parameter N       = 1001,          // transacciones (precios + 1 para leer la ultima decision)
  parameter T       = 2500,          // ciclos entre transacciones (2500 = 0,1 ms = ronda 3)
  parameter RomFile = "build/prueba_rom.hex"
) (
  input  wire       clk_i,
  input  wire       start_i,         // empieza cuando el SoC salio del reset
  output reg        sclk_o,
  output reg        mosi_o,
  output reg        cs_n_o,
  input  wire       miso_i,
  output reg        fin_o,           // termino las N transacciones
  output reg        error_o          // algun byte no fue el esperado
);

  reg [15:0] rom [0:1023];
  initial $readmemh(RomFile, rom);

  reg [9:0]  n = 0;                  // transaccion actual
  reg [15:0] dato = 0;               // {esperado, precio} de la transaccion n
  reg [11:0] t = 0;
  reg [7:0]  rx = 0;

  initial begin
    sclk_o = 0; mosi_o = 0; cs_n_o = 1; fin_o = 0; error_o = 0;
  end

  always @(posedge clk_i) dato <= rom[n];   // lectura sincronica: BRAM

  wire [4:0] fase = t[8:4];
  wire       paso = (t[11:9] == 3'd0) && (t[3:0] == 4'd15);

  always @(posedge clk_i) begin
    if (start_i && !fin_o) begin
      t <= (t == T - 1) ? 12'd0 : t + 12'd1;
      if (t == 0) begin                       // empieza la transaccion
        cs_n_o <= 1'b0;
        mosi_o <= dato[7];
      end else if (paso) begin
        if (fase == 5'd17) begin              // fin: sube CS y revisa el byte
          cs_n_o <= 1'b1;
          if (rx != dato[15:8]) error_o <= 1'b1;
          if (n == N - 1) fin_o <= 1'b1;
          n <= n + 10'd1;
        end else if (fase[0]) begin           // fin de fase impar: flanco de bajada
          sclk_o <= 1'b0;
          if (fase != 5'd15) mosi_o <= dato[6 - (fase >> 1)];
        end else if (fase != 5'd16) begin     // fin de fase par 0..14: flanco de subida
          sclk_o <= 1'b1;
          rx     <= {rx[6:0], miso_i};
        end                                   // fase 16: espera antes de subir CS
      end
    end
  end

endmodule
