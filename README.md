# Pochoco Trader: co-diseño hardware/software sobre Espino Core

Proyecto 4 de Arquitectura de Computadores 2026-2 (Universidad de los Andes, prof. Jorge Gómez M.),
grupo 2: Josefa Alcaíno, Felipe Izcúe, Martín Norton.

Un agente de inversión que corre en el Pochoco SoC sobre la Go Board. En cada tick la FPGA maestra
manda por SPI el precio de una acción (1 a 255) y lee el byte de decisión. Parte del repositorio base
[pochoco_soc](https://github.com/nic0villegasc/pochoco_soc) (primer commit, sin tocar) con los
cambios del grupo en el Proyecto 2 (segundo commit).

**El diseño de la competencia es el que sale sin ninguna opción**: el Espino sin instrucciones
propias, con una lectura bloqueante en la unidad de carga, a 25 MHz, y `sw/trade.hex`. Funciona tal cual con el testbench del curso:

```bash
python3 tools/pochoasm.py sw/trade.s -o sw/trade.hex
iverilog -g2012 -s tb_proyecto_4 -o /tmp/tb_p4 $(yosys-config --datdir)/ice40/cells_sim.v rtl/*.v rtl/espino_core/*.v tb/tb_proyecto_4.sv
vvp -n /tmp/tb_p4          # Testbenchs aprobados: 4/4
```

## El algoritmo en una frase ("extremos")

Las series de la competencia son 20 000 minutos de META, AAPL, NFLX, AMD o TSLA (2022–2024) llevados
a [100, 255]: el mínimo de la ventana vale 100 y el máximo 255, y los dos aparecen sí o sí. El agente
**compra todo cuando el precio vale 100 y vende todo cuando vale 255**; si el 255 ya pasó, toma la
ganancia en 225, y cuando ya pasaron los dos vuelve a comprar en 122. Antes del primer extremo, si el
precio sube 29 sobre el inicial compra una parte (15 acciones), para no perder las subidas del comienzo. Dentro manda "comprar 63", fuera
"vender 63": la maestra recorta la orden, así que no hay contabilidad y repetir una orden nunca hace
daño. 63 palabras de programa; peor caso precio → DECISION: 12 ciclos con ancla (9 sin ancla) (0,48 µs).

**Para simular y grabar la placa sin saber nada más: `docs/simular-y-grabar.md`** (`tools/simular.py` y `grabar.ps1`).

En 2732 ventanas reales posibles (`ref/competencia.py`): patrimonio final ×2,00 en media geométrica
(comprar y mantener ×1,12), pierde plata en 0,7 % de las ventanas (comprar y mantener en 42 %), peor
caso −3 %. Detalle en `docs/ruta-optimizacion.md` §12, en el encabezado de `sw/trade.s` y en el informe.

El algoritmo anterior ("caídas + tendencia", medias móviles de 64 y 512 ticks) quedó en
`sw/trade_tendencia.s`: con él se hizo el estudio de co-diseño (mul8, shifter, Amdahl, roofline), que
se reproduce con `ALGO=tendencia`.

## Estructura

| Carpeta | Contenido |
|---|---|
| `sw/trade.s`, `sw/trade.hex` | El agente de la competencia en assembly RV32E y su imagen de memoria. No usa multiplicaciones ni shifts. |
| `sw/trade_tendencia.s` | El algoritmo anterior, para el estudio de co-diseño: un solo `.s` para las 4 variantes (`.if HW_MUL`, `.if HW_SHIFT`). |
| `tools/` | `pochoasm.py` (assembler propio del Proyecto 2, con `mul8` y `.if/.else/.endif`) y sus pruebas; `goboard_prog.py` (programa la placa sin cambiar el driver de Windows); `prueba_placa.py`. |
| `rtl/` | SoC y Espino Core. Opcionales del estudio de co-diseño: `espino_mul8.v` (multiplicador, `` `ifdef ESPINO_MUL8 ``) y `` `ifdef ESPINO_SHIFTER `` en `espino_alu.v`. |
| `rtl/prueba_placa/` | Solo para probar en la placa: maestra SPI embebida con 1000 precios en ROM. **No** es el diseño de la competencia. |
| `tb/` | Testbench y series de práctica del curso, sin modificar (`practica_meta.csv` es la del formato de la competencia). |
| `sim/` | Testbenches propios: ISA (`isa_tb.v` + `isa_test.s`), multiplicador (`tb_mul8.v`), maestra SPI con medición de ciclos (`tb_trade.v`), prueba en placa. |
| `ref/` | Referencia en Python: reglas de la maestra (`mercado.py`), los dos algoritmos bit a bit (`trader.py`), series de la competencia reconstruidas (`minuto.py`), ganancia y riesgo (`competencia.py`), simulador de instrucciones del Espino (`espino_iss.py`), verificación, síntesis y figuras. |
| `data/series/` | 16 series de 20 000 ticks del estudio anterior: la primera práctica, Alibaba real a 4 escalas de tiempo, y cada una invertida. |
| `data/minuto/` | (fuera de git) barras de 1 minuto 2022–2024 de las 5 empresas, ver `ref/minuto.py`. |
| `resultados/` | CSV de ganancia y riesgo (`competencia*.csv`), mediciones por tick del programa final (`extremos/`) y del estudio anterior, perfiles, síntesis y la salida del testbench del curso. |
| `informe/`, `docs/` | Informe en LaTeX y guía para la defensa. Tablas y figuras generadas por `ref/analisis.py`. |

## Cambios al RTL respecto al repositorio base

| Archivo | Cambio |
|---|---|
| `rtl/pochoco_ram.v` | Atributo `(* no_rw_check *)`: unas 200 celdas lógicas menos en el diseño final (1187 sin el atributo, 986 con él; 174 en una versión anterior) (Yosys ya no emula leer y escribir la misma dirección en el mismo ciclo, que aquí no ocurre). |
| `rtl/espino_core/espino_mul8.v` (nuevo), `espino_decoder.v`, `espino_id_stage.v`, `espino_core.v` | Instrucción `mul8 rd, rs1, rs2` = `rs1 * rs2[7:0]`, opcode `0x0B`, solo con `-DESPINO_MUL8` (variante de comparación). Sin ese define el core es el original. |
| `rtl/espino_core/espino_alu.v` | Con `-DESPINO_SHIFTER`: SLL/SRL/SRA de verdad (variante de comparación). |
| `rtl/pochoco_spi_slave.v` | Registro NUEVO (offset `0x0C`, solo lectura): `{precio nuevo, 23'b0, precio}`; leerlo baja el aviso como leer PRICE. Su lectura es bloqueante (`wait_o`, ver la fila siguiente). |
| `rtl/espino_core/espino_load_store_unit.v`, `espino_core.v`, `rtl/pochoco_soc.v` | Lectura bloqueante: con `data_wait_i` en 1 el load no termina (repite la petición con el pipeline detenido). El esclavo SPI lo pide al leer NUEVO sin precio nuevo. La espera de `trade.s` es un solo `lw`; peor caso precio → DECISION: 12 ciclos con ancla (9 sin ancla) (antes 34). |
| `rtl/pochoco_soc.v`, `rtl/pochoco_periph.v` | Del Proyecto 2: reset de encendido de 4095 ciclos y contador de ciclos en `0x8000_000C`. |

Mapa de memoria: el del repositorio base. `trade.s` solo usa la RAM para el programa (63 palabras,
252 bytes desde `0x000`); `trade_tendencia.s` además usa buffers en `0x500`–`0x73F`.

## Cómo se usa

Todo se corre desde la raíz. Se necesita [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build)
en el `PATH` (yosys, nextpnr-ice40, icepack, iceprog, iverilog) y Python 3 con numpy y matplotlib
(pandas solo para regenerar las series de Alibaba). No hace falta toolchain de RISC-V. Si `python3` no
es el intérprete correcto, pasar `PY=...` a make.

### Ensamblar `trade.s`

```bash
make hex                                   # sw/trade.s -> sw/trade.hex (+ sw/trade.lst)
python3 tools/pochoasm.py sw/trade.s -o sw/trade.hex
```

`trade.s` corre en cualquier variante. `trade_tendencia.s` se ensambla con `-D HW_MUL=0/1` y
`-D HW_SHIFT=0/1`, y el `.hex` tiene que corresponder al RTL: con `mul8` necesita `-DESPINO_MUL8`.

### Sintetizar y programar la placa

```bash
make bin          # yosys -> nextpnr (HX1K, VQ100, 25 MHz) -> icepack: build/pochoco.bin
make prog         # iceprog build/pochoco.bin
make prog-d2xx    # lo mismo sin cambiar el driver de Windows (tools/goboard_prog.py)
```

`iceprog` necesita el driver WinUSB/libusbK en la **interfaz 0** del FT2232H (Zadig: Options → List
All Devices → "Dual RS232-HS (Interface 0)"). `prog-d2xx` usa el driver de FTDI que trae Windows.

Conexión con la maestra (detalle en `docs/conexion-maestra.md`): PMOD con los pines de `goboard.pcf` (CS_n 65, MOSI 64, MISO 63, SCLK 62) y
tierra común. Los displays muestran el último precio en hexadecimal.

### Pruebas

```bash
make tb               # el testbench del curso (4/4)
make tb-meta          # el mismo testbench con practica_meta.csv completa (20 000 ticks, ronda 3)
make sim-asm          # 26 pruebas del assembler (trade.s sin mul8 ni shifts; trade_tendencia.s en 4 variantes)
make sim-mul8         # multiplicador: 20 006 casos, producto y latencia
make sim-isa-todas    # prueba de instrucciones sobre el SoC en las 4 variantes
make sim-trade NTICKS=20000     # SoC contra una maestra SPI emulada, practica_meta completa
make sim-trade ALGO=tendencia VARIANT=mul8   # el estudio anterior
make sim-prueba-placa           # el bitstream de prueba en placa, simulado
make sim              # todo lo anterior
```

`sim-trade` revisa que cada byte que leyó la maestra sea la decisión de `trader.py`, que ningún tick
haya quedado sin terminar y que los ciclos e IC de cada tick sean los del simulador de instrucciones.
Variantes: `sw`, `shift`, `mul8`, `mul8shift`.

### Referencia en Python, mediciones y figuras

```bash
python3 ref/minuto.py                    # comprueba que se reconstruye practica_meta (necesita data/minuto)
python3 ref/competencia.py               # ganancia y riesgo en 2732 ventanas de la competencia
python3 ref/montecarlo.py                # lo mismo en 8 escenarios de series sinteticas (1000 c/u)
python3 ref/buscar_ventajas.py          # ajustes y reglas que ganen cara a cara a rivales parecidos
python3 ref/optimizador.py --horas 8    # busqueda evolutiva que queda corriendo (resultados/optimizador_log.md)
python3 ref/universo.py                 # 22 acciones tecnologicas -> docs/informe_universo.html
python3 ref/verificar.py                 # trade.s == trader.py, IC/ciclos/CPI por tick, perfil
ALGO=tendencia python3 ref/verificar.py  # lo mismo para el algoritmo anterior (4 variantes)
python3 ref/backtest.py                  # algoritmo anterior vs referencias, en las 16 series
python3 ref/sintesis.py                  # LC, BRAM y Fmax de cada variante -> resultados/sintesis.csv
python3 ref/analisis.py                  # figuras, tablas y números del informe
python3 ref/series.py                    # (opcional) regenera data/series desde el zip de Kronos
```

Para cambiar parámetros del algoritmo basta editar las `.equ` de `sw/trade.s` (`MINIMO`,
`MAXIMO`, `TOMA_GANANCIA`, `RECOMPRA`): `trader.py` las lee de ahí, así que el programa y la referencia nunca
quedan distintos.

### Prueba en la placa (sin la maestra del curso)

```bash
make prueba-placa && python3 tools/goboard_prog.py build/prueba.bin
```

Una maestra embebida le manda al SoC 1000 precios cada 0,1 ms (dos trozos de `practica_meta`: uno con
el 100 y otro con el 255, para pasar por compra y venta) y compara cada byte con el de `trader.py`. Los 4 LEDs prendidos fijos = todo coincide; los 4 parpadeando = algún byte distinto.
Después hay que volver a grabar el bitstream de la competencia (`make bin && make prog-d2xx`).

## Versiones usadas

| Herramienta | Versión |
|---|---|
| OSS CAD Suite | build 2026-08-24 |
| Yosys | 0.68+120 (git sha1 a34d3baae) |
| nextpnr-ice40 | 0.11.1-9-gb17408e2 |
| Icarus Verilog | 14.0 (devel) s20260301 |
| icestorm (icepack, iceprog) | los de la misma OSS CAD Suite |
| Python | 3.11.15 (numpy 1.26.4, matplotlib 3.8.0, pandas 2.1.4) |
| GNU Make | 4.4.1 |
| Tectonic (informe) | conda, entorno `tex` |
| Sistema | Windows 11 + Git Bash |
