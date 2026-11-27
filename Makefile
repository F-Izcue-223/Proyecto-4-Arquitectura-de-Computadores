# Pochoco Trader (Proyecto 4) - Arquitectura de Computadores 2026-2
# Basado en el Makefile de pochoco_soc (Nicolas Villegas, SHL-0.51).
#
# El diseno de la competencia es el que sale sin ninguna opcion: el Espino (con la
# lectura bloqueante de NUEVO en la unidad de carga)
# (sin mul8 ni shifter) con sw/trade.hex (algoritmo "extremos", que no multiplica ni
# desplaza). Asi funciona tal cual con el testbench del curso (tb/tb_proyecto_4.sv),
# que compila rtl/*.v sin defines.
#
# Las otras variantes de hardware son del estudio de co-diseno (VARIANT=...):
#   sw         Espino original: sin mul8 ni shifts (por defecto, la de la competencia)
#   shift      con barrel shifter                        -DESPINO_SHIFTER
#   mul8       con la instruccion propia mul8            -DESPINO_MUL8
#   mul8shift  mul8 + shifter (no cabe en la HX1K)       -DESPINO_MUL8 -DESPINO_SHIFTER
# El estudio se hizo con el algoritmo anterior (sw/trade_tendencia.s, que si multiplica):
# se reproduce con ALGO=tendencia, por ejemplo  make sim-trade ALGO=tendencia VARIANT=mul8
# (El PLL no se puede usar: la HX1K en encapsulado VQ100 de la Go Board no tiene PLL.)
#
# Objetivos principales:
#   make hex            ensambla sw/trade.s -> sw/trade.hex
#   make tb             el testbench del curso, tal como lo corre el profesor
#   make tb-meta        el mismo testbench con tb/practica_meta.csv completa (20 000 ticks)
#   make bin            sintesis + place & route + bitstream: build/pochoco.bin
#   make prog           programa la Go Board con iceprog (prog-d2xx: sin cambiar el driver)
#   make sim            assembler, mul8, ISA en las 4 variantes, trade.s en el RTL
#   make ref            ganancia y riesgo en las series de la competencia, verificacion de
#                       trade.s contra trader.py y backtest del algoritmo anterior
#   make tabla          sintesis de todas las variantes -> resultados/sintesis.csv

VARIANT ?= sw
ALGO    ?= extremos
export ALGO
PROG    := $(if $(filter tendencia,$(ALGO)),sw/trade_tendencia.s,sw/trade.s)
PY      ?= python3
TOP     := pochoco_soc
PCF     := goboard.pcf

DEFS_sw        :=
DEFS_shift     := -DESPINO_SHIFTER
DEFS_mul8      := -DESPINO_MUL8
DEFS_mul8shift := -DESPINO_MUL8 -DESPINO_SHIFTER
ASM_sw         := -D HW_MUL=0
ASM_shift      := -D HW_MUL=0 -D HW_SHIFT=1
ASM_mul8       := -D HW_MUL=1
ASM_mul8shift  := -D HW_MUL=1 -D HW_SHIFT=1

RTL := $(wildcard rtl/*.v) $(wildcard rtl/espino_core/*.v)
# Modelos de simulacion de las primitivas de la iCE40 (SB_RAM40_4K del banco de registros).
# En Windows `yosys-config --datdir` devuelve una ruta que no existe: se busca primero
# en la instalacion de OSS CAD Suite.
SIMLIB ?= $(firstword $(wildcard $(YOSYSHQ_ROOT)/share/yosys/ice40/cells_sim.v \
            $(HOME)/oss-cad-suite/share/yosys/ice40/cells_sim.v) \
            $(shell yosys-config --datdir 2>/dev/null)/ice40/cells_sim.v)

.PHONY: all hex tb tb-meta bin prog prog-d2xx sim sim-asm sim-isa sim-isa-todas sim-mul8 sim-trade \
        ref tabla clean prueba-rom prueba-placa sim-prueba-placa

all: bin

build:
	mkdir -p build

# --- Programa de la competencia ------------------------------------------------------
# EQU: cambia constantes de trade.s sin editarlo, p. ej. make bin EQU="-D ANCLA=0" (ver tools/versiones.py)
EQU ?=
hex:
	$(PY) tools/pochoasm.py sw/trade.s -o sw/trade.hex -l sw/trade.lst $(EQU)

# --- Testbench del curso (los mismos comandos del encabezado de tb/tb_proyecto_4.sv) --
tb: hex | build
	iverilog -g2012 -s tb_proyecto_4 -o build/tb_p4.vvp $(SIMLIB) $(RTL) tb/tb_proyecto_4.sv
	vvp -n build/tb_p4.vvp

# Copia del testbench oficial con otra serie, largo y periodo (el original no se toca).
TB_SERIE   ?= tb/practica_meta.csv
TB_NTICKS  ?= 20000
TB_PERIODO ?= 100000
tb-meta: hex | build
	sed -e 's|"tb/practica.csv"|"$(TB_SERIE)"|' -e 's|NTICKS     = 2000;|NTICKS     = $(TB_NTICKS);|' 	    -e 's|PERIODO_NS = 100000;|PERIODO_NS = $(TB_PERIODO);|' tb/tb_proyecto_4.sv > build/tb_meta.sv
	iverilog -g2012 -s tb_proyecto_4 -o build/tb_meta.vvp $(SIMLIB) $(RTL) build/tb_meta.sv
	vvp -n build/tb_meta.vvp

# --- FPGA: Yosys -> nextpnr -> icepack -------------------------------------------------
bin: hex | build
	yosys -q -p "read_verilog $(RTL); synth_ice40 -top $(TOP) -json build/pochoco.json; tee -q -o build/pochoco_yosys.txt stat"
	nextpnr-ice40 --hx1k --package vq100 --json build/pochoco.json --pcf $(PCF) --asc build/pochoco.asc \
	  --freq 25 --log build/pochoco_nextpnr.log -q
	icepack build/pochoco.asc build/pochoco.bin
	@grep -E "ICESTORM_LC:|ICESTORM_RAM:|Max frequency" build/pochoco_nextpnr.log | tail -3

prog:
	iceprog build/pochoco.bin

# Sin cambiar el driver de Windows: usa ftd2xx.dll (el driver de FTDI que trae Windows)
prog-d2xx:
	$(PY) tools/goboard_prog.py build/pochoco.bin

# --- Simulacion -----------------------------------------------------------------------
sim: sim-asm sim-mul8 sim-isa-todas sim-trade tb

sim-asm:
	$(PY) -m unittest discover -s tools

sim-mul8: | build
	iverilog -g2012 -o build/tb_mul8.vvp sim/tb_mul8.v rtl/espino_core/espino_mul8.v
	vvp -n build/tb_mul8.vvp

sim-isa: | build
	$(PY) tools/pochoasm.py sim/isa_test.s -o build/isa_test.hex $(ASM_$(VARIANT))
	iverilog -g2012 $(DEFS_$(VARIANT)) -o build/isa_$(VARIANT).vvp sim/isa_tb.v $(RTL) $(SIMLIB)
	vvp -n build/isa_$(VARIANT).vvp

sim-isa-todas:
	$(MAKE) sim-isa VARIANT=sw
	$(MAKE) sim-isa VARIANT=shift
	$(MAKE) sim-isa VARIANT=mul8
	$(MAKE) sim-isa VARIANT=mul8shift

# trade.s de la variante sobre el RTL contra una maestra SPI emulada, comparado tick a
# tick con trader.py y con el simulador de instrucciones (ciclos e IC).
SERIE ?= tb/practica_meta.csv
T_NS  ?= 100000
NTICKS ?= 2000
sim-trade: | build
	$(PY) tools/pochoasm.py $(PROG) -o build/trade_$(VARIANT).hex $(ASM_$(VARIANT))
	cp build/trade_$(VARIANT).hex build/trade.hex
	$(PY) ref/comparar_rtl.py --serie $(SERIE) $(NTICKS) build/serie_tb.txt
	iverilog -g2012 $(DEFS_$(VARIANT)) -o build/tb_trade_$(VARIANT).vvp sim/tb_trade.v $(RTL) $(SIMLIB)
	vvp -n build/tb_trade_$(VARIANT).vvp +serie=build/serie_tb.txt +salida=build/rtl_$(VARIANT).txt +T_NS=$(T_NS)
	$(PY) ref/comparar_rtl.py $(VARIANT) build/serie_tb.txt build/rtl_$(VARIANT).txt

# --- Prueba en la placa (bitstream aparte, NO es el de la competencia) ----------------
# La maestra embebida le manda 1000 precios cada 0,1 ms (ronda 3) y compara cada byte
# con el de trader.py. Resultado en los LEDs (ver rtl/prueba_placa). Sin el contador de
# ciclos del Proyecto 2 (trade.s no lo usa), para que quepa junto al SoC.
PRUEBA_RTL := $(RTL) rtl/prueba_placa/maestra_embebida.v rtl/prueba_placa/prueba_placa_top.v

prueba-rom: hex | build
	$(PY) tools/prueba_placa.py

sim-prueba-placa: prueba-rom
	iverilog -g2012 -DSIN_CONTADOR_CICLOS -o build/tb_prueba.vvp sim/tb_prueba_placa.v $(PRUEBA_RTL) $(SIMLIB)
	vvp -n build/tb_prueba.vvp

prueba-placa: prueba-rom
	yosys -q -p "read_verilog -DSIN_CONTADOR_CICLOS $(PRUEBA_RTL); synth_ice40 -top prueba_placa_top -json build/prueba.json"
	nextpnr-ice40 --hx1k --package vq100 --json build/prueba.json --pcf $(PCF) \
	  --asc build/prueba.asc --freq 25 --log build/prueba_nextpnr.log -q
	icepack build/prueba.asc build/prueba.bin
	@grep -E "ICESTORM_LC:|Max frequency" build/prueba_nextpnr.log | tail -2

# --- Referencia en Python ---------------------------------------------------------------
ref:
	$(PY) ref/competencia.py
	$(PY) ref/verificar.py
	$(PY) ref/backtest.py

tabla:
	$(PY) ref/sintesis.py

clean:
	rm -rf build
