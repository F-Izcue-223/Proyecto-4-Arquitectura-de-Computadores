# trade.s: agente de inversion "extremos" para el Espino Core (RV32E).
#
# Por que funciona. Cada serie de la competencia es una ventana de 20000 minutos de
# una accion real llevada linealmente a [100, 255]: el minimo de la ventana vale 100
# y el maximo 255 (tb/practica_meta.csv se reconstruye exacto asi; ver ref/minuto.py).
# Entonces, dentro de la ventana:
#   - el precio nunca baja de 100 ni sube de 255;
#   - el 100 y el 255 aparecen alguna vez.
# Regla: comprar todo cuando el precio llega al piso y vender todo cuando llega al techo.
#   - Piso 100 y techo 255 al partir. Si al ver 100 todavia no aparecio el 255, el 255
#     tiene que venir despues: se compra en el piso y se vende en el techo (x2,55
#     menos comisiones).
#   - Si el 255 ya paso, comprar en 100 no puede perder: el precio no baja de 100.
#     Pero ya no hay garantia de volver a 255: desde que aparecio el 255, el techo
#     baja a 225 (TOMA_GANANCIA).
#   - Cuando ya aparecieron los dos, no queda ninguna garantia, pero comprar cerca del
#     piso arriesga poco (el precio no baja de 100): el piso sube a 122 (RECOMPRA).
#   - Ancla (tendencias alcistas del principio, antes de ver el 100 o el 255): si el
#     precio sube ANCLA (29) sobre el primer precio p0, se compra UNA vez una parte,
#     ANCLA_ORDEN (comprar 15 acciones), y despues se manda "mantener"; si vuelve a p0,
#     se vende todo. Comprar solo 15 acota el dano cuando la subida no sigue: en 13.652
#     ventanas reales la peor ronda pasa de -3,0 % a -5,5 % y gana cara a cara a la
#     version sin ancla en +8,4 % neto (docs/ruta-optimizacion.md seccion 17).
#     Comprando todo (ANCLA_ORDEN = COMPRAR) la peor ronda era -21 %.
#     Con ANCLA_P0 (version E) el ancla se arma solo si p0 >= ANCLA_P0: con p0 bajo la
#     subida del comienzo suele ser un rebote antes de ir al 100 y el ancla pierde; con
#     p0 alto la subida suele seguir al 255 (ref/perdidas_rival.py, ruta seccion 23).
#   - Todo al inicio (version F, TODO_P0): antes de ver un extremo, los dos tienen que llegar. Comprar todo
#     a p y aguantar hasta el 255 sale con x 255/p > 1 aunque el 100 llegue antes. Con p0 >= 170 el 255 llega
#     primero en la mayoria de las series (45-89 %): se compra todo al primer precio (ruta seccion 29).
#   - En el resto no se cambia de idea.
# 100 y 255 salen de la especificacion de la serie, no de ajustar datos. 225 y 120 si
# son ajustados (ref/competencia.py, docs/ruta-optimizacion.md secciones 12 y 13).
# 220 daba el mejor promedio; 225 da casi lo mismo (-0,07 %) y le gana cara a cara a
# 220 y a 100/255 puro en mas rondas, que es lo que importa contra rivales parecidos.
#
# No hay contabilidad. La maestra (tb/tb_proyecto_4.sv, tarea ejecutar) recorta la
# compra a lo que alcanza la caja y la venta a las acciones que hay, y una orden que
# queda en 0 no se ejecuta ni paga comision. Mandar "comprar 63" mientras se quiere
# estar dentro llena la posicion en dos ticks (63 + el resto) y despues no hace nada.
# Si el programa no alcanzara a responder, la maestra repite la orden anterior, que
# es justo la que se queria mandar.
#
# No usa multiplicaciones ni shifts (no necesita mul8 ni shifter). Si usa la lectura
# bloqueante de NUEVO, que agrega este proyecto en el SoC y en la unidad de carga.
# La version de referencia es ref/trader.py (clase Extremos);
# ref/verificar.py comprueba que las dos tomen la misma decision en cada tick.
# Velocidad (el camino precio -> DECISION):
#   - Espera con UNA instruccion: lw del registro NUEVO del esclavo SPI (offset 0x0C,
#     agregado en rtl/pochoco_spi_slave.v): bit 31 = precio nuevo, bits 7:0 = precio.
#     La lectura es bloqueante (espino_load_store_unit, data_wait_i): si todavia no
#     llega un precio, el load espera, y vuelve el ciclo siguiente al ultimo bit del
#     precio. No hay vuelta de espera ni hay que mirar el bit 31.
#   - Como el precio llega con el bit 31 en 1, piso y techo se guardan sumados a
#     0x8000_0000 y se comparan sin signo (bgeu/bltu): mismo resultado, sin limpiar el bit.
#   - El caso comun (no toca piso ni techo) no salta hasta escribir DECISION.
#   - Cuando cambia la decision, se escribe DECISION antes de actualizar piso y techo.
#   - Dos bucles: el del ancla (fase 1) corre solo hasta que aparece el primer extremo;
#     despues, el bucle corto (fase 2). En los dos, el caso comun son dos comparaciones.
#
# Registros:
#   s0 = base SPI 0x8001_0000     sp = base perifericos 0x8000_0000
#   t1 = 0x8000_0000 (el bit de precio nuevo; base de las constantes)
#   gp = t1 + 100 (MINIMO)        a3 = t1 + 255 (MAXIMO)
#   a2 = piso vigente: t1 + 100; t1 + RECOMPRA cuando ya aparecieron el 100 y el 255
#   a4 = techo vigente: t1 + 255; t1 + TOMA_GANANCIA desde que aparecio el 255
#   s1 = 1 si ya aparecio el 100
#   a0 = COMPRAR, ra = VENDER (constantes, para escribir DECISION sin un li antes)
#   a5 = decision vigente (parte fuera: VENDER, que sin acciones no hace nada)
#   tp = t1 + p0 (ancla abajo)    t2 = t1 + p0 + ANCLA (ancla arriba)   (solo fase 1)
#   t0 = ANCLA_ORDEN (comprar 15); en fase 1, a5 = 0 (mantener) mientras se tiene la parte
#   a1 = t1 + precio del tick

    .equ MINIMO,        100     # minimo de la normalizacion
    .equ MAXIMO,        255     # maximo de la normalizacion
    .equ TOMA_GANANCIA, 225     # techo despues de que aparecio el 255
    .equ RECOMPRA,      122     # piso despues de que aparecieron los dos
    .equ ANCLA,         29      # fase 1: compra una parte si sube ANCLA sobre p0 (0 = apagada)
    .equ ANCLA_ORDEN,   0x4F    # 01 001111: comprar 15 (la parte); 0x4A = 10 acciones (-3,5 %)
    .equ ANCLA_P0,      0       # el ancla se arma solo si p0 >= ANCLA_P0 (0 = siempre; la E usa 160)
    .equ TODO_P0,       0       # si p0 >= TODO_P0: comprar todo al inicio y esperar el 255 (0 = no; la F usa 170)
    .equ TODO_Y,        0       # sin ancla: antes de los extremos, comprar todo si p >= TODO_Y o p0 >= TODO_P0
                                # y esperar el 255 (0 = no; la G usa TODO_P0 180 y TODO_Y 240, con ANCLA 0)
    .equ COMPRAR,       0x7F    # 01 111111: comprar 63
    .equ VENDER,        0xBF    # 10 111111: vender 63

inicio:
    li   s0, 0x80010000
    li   sp, 0x80000000
    li   t1, 0x80000000
    addi gp, t1, MINIMO
    addi a3, t1, MAXIMO
    mv   a2, gp
    mv   a4, a3
    li   s1, 0
    li   a0, COMPRAR
    li   ra, VENDER
    mv   a5, ra
.if TODO_Y
# ---------------------------------------------------------------------------
# Fase 1 de la version G (sin ancla): antes de ver el 100 o el 255, comprar todo si p0 >= TODO_P0
# o si el precio llega a TODO_Y, y esperar el 255 en la fase 2 (esta garantizado: sale con x 255/p)
# ---------------------------------------------------------------------------
    addi t0, t1, TODO_Y         # constantes antes del primer precio: no suman latencia
    addi t2, t1, TODO_P0
    lw   a1, 12(s0)             # primer precio p0 (bloqueante)
    bgeu a2, a1, piso           # p0 <= 100
    bgeu a1, a4, techo          # p0 >= 255
    bgeu a1, t2, todo_y         # p0 >= TODO_P0: el 255 suele llegar primero
    j    sigue_y
espera_y:
    lw   a1, 12(s0)             # NUEVO (bloqueante)
    bgeu a2, a1, piso           # p <= 100: aparece el minimo (fase 2)
    bgeu a1, a4, techo          # p >= 255: aparece el maximo (fase 2)
    bgeu a1, t0, todo_y         # p >= TODO_Y: comprar todo y esperar el 255
sigue_y:
    sw   a5, 8(s0)              # DECISION (fuera)
    sw   a1, 0(sp)
    j    espera_y
todo_y:
    sw   a0, 8(s0)              # DECISION = comprar todo
    mv   a5, a0
    sw   a1, 0(sp)
    j    espera                 # fase 2: vende en el 255
.endif
.if ANCLA
    li   t0, ANCLA_ORDEN
.if TODO_P0
    addi t2, t1, TODO_P0        # antes del primer precio: no suma latencia
.endif
    lw   a1, 12(s0)             # primer precio p0 (bloqueante)
    bgeu a2, a1, piso           # p0 <= 100: ya es el minimo (fase 2)
    bgeu a1, a4, techo          # p0 >= 255: ya es el maximo (fase 2)
.if TODO_P0
    bltu a1, t2, sin_todo       # p0 alto: el 255 llega primero en la mayoria de las series y,
    mv   a5, a0                 # pase lo que pase, llega antes del final: comprar todo ya y
    sw   a5, 8(s0)              # esperarlo en la fase 2 (vende en el 255; sin stop)
    sw   a1, 0(sp)
    j    espera
sin_todo:
.endif
    sw   a5, 8(s0)              # DECISION del primer tick (fuera), antes de armar el ancla
    sw   a1, 0(sp)
.if ANCLA_P0
    addi t2, t1, ANCLA_P0       # p0 bajo: la subida inicial suele ser un rebote que
    bltu a1, t2, espera         # vuelve a p0, y el ancla pierde (ref/perdidas_rival.py): sin ancla
.endif
    mv   tp, a1                 # ancla abajo: p0
    addi t2, a1, ANCLA          # ancla arriba: p0 + ANCLA, pero no mas que 255: asi
    bltu t2, a3, espera_ancla   # "p >= ancla arriba" cubre tambien "p >= 255"
    mv   t2, a3

# ---------------------------------------------------------------------------
# Fase 1 (antes de ver el 100 o el 255): piso, techo y ancla
# ---------------------------------------------------------------------------
espera_ancla:
    lw   a1, 12(s0)             # NUEVO (bloqueante): t1 + precio
decidir_ancla:
    # El caso comun (p0 < p < p0 + ANCLA) pasa por dos comparaciones, como la fase 2.
    # Fuera de esa zona: p <= p0 incluye p <= 100 y p >= ancla arriba incluye p >= 255.
    bgeu a1, t2, ancla_alto     # p >= p0 + ANCLA (o p >= 255)
    bgeu tp, a1, ancla_bajo     # p <= p0 (o p <= 100)
    sw   a5, 8(s0)              # DECISION (no cambia)
    sw   a1, 0(sp)
    j    espera_ancla
ancla_alto:
    bgeu a1, a4, techo          # p >= 255: aparece el maximo (pasa a la fase 2)
    beqz a5, ancla_tengo        # ya compro la parte: sigue "mantener"
    sw   t0, 8(s0)              # DECISION = comprar 15, una sola vez
    li   a5, 0                  # desde el tick siguiente: mantener
    sw   a1, 0(sp)
    j    espera_ancla
ancla_tengo:
    sw   a5, 8(s0)              # DECISION = mantener
    sw   a1, 0(sp)
    j    espera_ancla
ancla_bajo:
    bgeu a2, a1, piso           # p <= 100: aparece el minimo (pasa a la fase 2)
    sw   ra, 8(s0)              # DECISION = vender todo
    mv   a5, ra
    sw   a1, 0(sp)
    j    espera_ancla
.endif

# ---------------------------------------------------------------------------
# Fase 2: un tick = esperar precio, compararlo con piso y techo, escribir DECISION
# ---------------------------------------------------------------------------
espera:
    lw   a1, 12(s0)             # NUEVO (bloqueante): t1 + precio
decidir:
    bgeu a2, a1, piso           # p <= piso vigente
    bgeu a1, a4, techo          # p >= techo vigente
    sw   a5, 8(s0)              # DECISION (no cambia)
    sw   a1, 0(sp)              # displays: precio en hexadecimal (bits 7:0)
    j    espera

piso:
    sw   a0, 8(s0)              # DECISION = comprar, antes que nada
    mv   a5, a0
    sw   a1, 0(sp)
    bltu gp, a1, espera         # p > 100: recompra, no es el minimo
    li   s1, 1                  # aparecio el 100
    beq  a4, a3, espera         # el 255 todavia no aparece
    addi a2, t1, RECOMPRA       # ya aparecieron los dos
    j    espera

techo:
    sw   ra, 8(s0)              # DECISION = vender, antes que nada
    mv   a5, ra
    sw   a1, 0(sp)
    bltu a1, a3, espera         # p < 255: toma de ganancia
    addi a4, t1, TOMA_GANANCIA  # aparecio el 255
    beqz s1, espera             # el 100 todavia no aparece
    addi a2, t1, RECOMPRA       # ya aparecieron los dos
    j    espera
