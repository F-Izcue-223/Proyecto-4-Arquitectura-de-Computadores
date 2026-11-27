// tb_trade.v - el SoC completo con trade.hex contra una maestra SPI emulada.
// Se ejecuta con:  make sim-trade VARIANT=<v> SERIE=data/series/<x>.txt [T_NS=100000]
//
// La maestra hace lo mismo que la FPGA del curso (enunciado, seccion 2):
//   cada T ns baja CS_n, manda el precio (SPI modo 0, MSB primero, SCLK de 1 MHz)
//   y lee por MISO el byte que el SoC tenia en DECISION.
// Escribe una linea por tick en el archivo +salida:
//   tick  precio  byte_leido  ciclos  IC
// ciclos e IC: lo que tardo el programa en ese tick, desde que consumio el precio hasta
// que volvio a leer STATUS (misma definicion que ref/espino_iss.py). Se miden
// mirando el bus de datos del core y la senal commit de la etapa ID.
// ref/comparar_rtl.py compara ese archivo con trader.py y con el simulador.
`timescale 1ns/1ps

module tb_trade;
  real    clk_ns  = 40.0;          // 25 MHz (+clk_ns=25.1 para simular el PLL a 39,844 MHz)
  integer t_ns    = 100000;        // periodo de la ronda 3: 0,1 ms
  integer half_ns = 500;           // medio periodo de SCLK: 1 MHz

  reg clk = 1'b0;
  always #(clk_ns / 2) clk = ~clk;

  reg  sclk = 1'b0, mosi = 1'b0, cs_n = 1'b1;
  wire miso;
  wire [3:0] led;

  pochoco_soc #(.MemFile("build/trade.hex")) dut (
    .i_Clk(clk), .o_LED(led), .i_Switch(4'b0000),
    .o_Segment1_A(), .o_Segment1_B(), .o_Segment1_C(), .o_Segment1_D(),
    .o_Segment1_E(), .o_Segment1_F(), .o_Segment1_G(),
    .o_Segment2_A(), .o_Segment2_B(), .o_Segment2_C(), .o_Segment2_D(),
    .o_Segment2_E(), .o_Segment2_F(), .o_Segment2_G(),
    .i_SPI_SCLK(sclk), .i_SPI_MOSI(mosi), .i_SPI_CS_n(cs_n), .o_SPI_MISO(miso)
  );

  // --- Medidas: mirar el bus de datos del core --------------------------------
  wire        dreq  = dut.data_req;
  wire        dwe   = dut.data_we;
  wire [31:0] daddr = dut.data_addr;
  wire        commit = dut.u_core.u_id.commit;

  integer ciclo = 0, ic = 0, t_precio = -1, ic_precio = 0;
  integer med_ciclos = -1, med_ic = -1;
  always @(posedge clk) begin
    ciclo = ciclo + 1;
    if (commit) ic = ic + 1;
    // Empieza el tick cuando consume el precio: lee PRICE, o lee NUEVO (0x0C) con un
    // precio nuevo. Termina cuando vuelve a esperar: lee STATUS, o NUEVO otra vez.
    if (dreq && !dwe && (daddr == 32'h8001_0004 ||
                         (daddr == 32'h8001_000C && dut.u_spi.new_price_q))) begin
      t_precio  = ciclo;
      ic_precio = ic;
    end
    else if (dreq && !dwe && (daddr == 32'h8001_0000 || daddr == 32'h8001_000C) && t_precio >= 0) begin
      med_ciclos = ciclo - t_precio - 3;
      med_ic     = ic - ic_precio - 1;
      t_precio   = -1;
    end
  end

  // --- La maestra ---------------------------------------------------------------
  integer fin, fout, r, n, k, precio;
  reg [7:0] leido;
  reg [8*256-1:0] archivo_serie, archivo_salida;
  real t0;

  task transaccion(input [7:0] p, output [7:0] rx);
    begin
      cs_n = 1'b0;
      mosi = p[7];
      #(half_ns);
      for (k = 7; k >= 0; k = k - 1) begin
        sclk = 1'b1;              // flanco de subida: los dos muestrean
        rx[k] = miso;
        #(half_ns);
        sclk = 1'b0;              // flanco de bajada: el esclavo saca el siguiente bit
        if (k > 0) mosi = p[k - 1];
        #(half_ns);
      end
      cs_n = 1'b1;
    end
  endtask

  initial begin
    if (!$value$plusargs("serie=%s", archivo_serie)) $fatal(1, "falta +serie=archivo");
    if (!$value$plusargs("salida=%s", archivo_salida)) $fatal(1, "falta +salida=archivo");
    if ($value$plusargs("T_NS=%d", t_ns)) ;
    if ($value$plusargs("clk_ns=%f", clk_ns)) ;
    fin  = $fopen(archivo_serie, "r");
    fout = $fopen(archivo_salida, "w");
    if (fin == 0) $fatal(1, "no se pudo abrir la serie");

    #300000;                       // 0,3 ms: pasa el reset de encendido (4095 ciclos)
    t0 = $realtime;
    n = 0;
    // (wait($realtime >= x) no sirve en iverilog: $realtime no es un evento y la
    // condicion no se vuelve a evaluar. Se espera con retardos explicitos.)
    while ($fscanf(fin, "%d", precio) == 1) begin
      #(t0 + n * t_ns - $realtime);                   // inicio del tick n
      med_ciclos = -1;
      med_ic = -1;
      transaccion(precio[7:0], leido);
      // esperar a que el programa termine este tick, o a que llegue el siguiente
      while (med_ciclos < 0 && $realtime < t0 + (n + 1) * t_ns - 2 * clk_ns)
        @(posedge clk);
      $fwrite(fout, "%0d %0d %0d %0d %0d\n", n, precio, leido, med_ciclos, med_ic);
      n = n + 1;
    end
    // una transaccion mas para leer la decision del ultimo precio
    #(t0 + n * t_ns - $realtime);
    transaccion(8'd1, leido);
    $fwrite(fout, "%0d %0d %0d %0d %0d\n", n, -1, leido, -1, -1);
    $fclose(fout);
    $display("tb_trade: %0d ticks, LED de deadline perdido = %0d", n, led[0]);
    $finish;
  end
endmodule
