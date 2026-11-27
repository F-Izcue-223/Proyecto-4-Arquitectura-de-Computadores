# trade_tendencia.s: algoritmo ANTERIOR "caidas + tendencia" (hasta el 17-nov-2026).
# Ya no es el de la competencia (ese es sw/trade.s, "extremos"). Se conserva porque el
# estudio de co-diseno del informe (mul8, shifter, Amdahl, roofline) se midio con el:
# se reproduce con ALGO=tendencia (ver ref/trader.py y el Makefile).
#
#
# Dos medias moviles del precio p: una corta de 64 ticks (suma S) y una larga de 512
# (suma SL). No se divide: se comparan sumas.
#     dev = S - 64p      64 x (media corta - precio); positivo = precio bajo su media
#     tl  = 512p - SL    512 x (precio - media larga); positivo = precio sobre su media
# Tres banderas con histeresis (cada una se prende con un umbral y se apaga con otro):
#   CAIDA      se prende si dev >= A_ENTRA*p       se apaga si dev <= A_SALE*p
#   TENDENCIA  se prende si 64*tl >= C_SUBE*SL     se apaga si 64*tl < -C_BAJA*SL
#   EXCESO     se prende si dev <= -B_EXCESO*p     se apaga si 2*dev >= -B_EXCESO*p
# Los umbrales van en 64avos: A_ENTRA = 3 es "precio 3/67 = 4,5 % bajo la media corta";
# C_SUBE = 1 es "precio 1/64 = 1,6 % sobre la media larga".
#
# Decision:  DENTRO = CAIDA o (TENDENCIA y no EXCESO)
# Con los umbrales elegidos (perfil "casi siempre dentro", validado con 15 acciones
# tecnologicas reales; ver docs/ruta-optimizacion.md):
#   - parte dentro: en el tick 0 las medias valen p0, tl = 0 y TENDENCIA se prende;
#   - TENDENCIA casi no se apaga (haria falta una caida de 37 % bajo la media larga);
#   - solo sale si el precio se dispara 19 % sobre su media corta (EXCESO), y vuelve
#     a entrar cuando baja la mitad de eso, o antes si cae bajo la media (CAIDA).
#   DENTRO -> DECISION = comprar 63;  FUERA -> DECISION = vender 63.
#
# No hay contabilidad. La maestra (tb/tb_proyecto_4.sv, tarea ejecutar) recorta la
# compra a lo que alcanza la caja y la venta a las acciones que hay, y una orden que
# queda en 0 no se ejecuta ni paga comision. Mandar "comprar 63" mientras se quiere
# estar dentro llena la posicion en uno o dos ticks y despues no hace nada. Si el
# programa no alcanzara a responder, la maestra repite la orden anterior, que es
# justo la que se queria mandar.
#
# Ciclo principal, una vuelta por tick:
#   1. esperar precio (STATUS bit 0) y leerlo
#   2. actualizar las dos medias (buffers circulares de 64 y 512 precios)
#   3. calcular dev y 64*tl
#   4. actualizar las tres banderas
#   5. escribir DECISION
# La version de referencia es ref/trader.py; ref/verificar.py comprueba que las dos
# tomen la misma decision en cada tick.
#
# Variantes (se eligen al ensamblar con -D; el RTL tiene que corresponder):
#   HW_MUL=1    (por defecto) instruccion propia mul8 para "constante x valor"
#   HW_MUL=0    por software, sumando y duplicando (rutina mulsw)
#   HW_SHIFT=1  las potencias de 2 con slli en vez de sumas (RTL con ESPINO_SHIFTER)
#
# Registros que viven todo el programa:
#   s0 = base SPI 0x8001_0000        sp = base perifericos 0x8000_0000
#   gp = S  (suma de los ultimos 64)     tp = indice del buffer corto (0..63)
#   a0 = SL (suma de los ultimos 512)    s1 = indice del buffer largo (0..511)
#   a5 = banderas: bit 0 CAIDA, bit 1 TENDENCIA, bit 2 EXCESO
# Durante el tick: a1 = precio p, a2 = dev, a3 = 64*tl; t0, t1, t2, a4 temporales.
# Memoria: programa desde 0x000; buffer largo (512 bytes) en 0x500..0x6FF y buffer
# corto (64 bytes) en 0x700..0x73F.

    .equ A_ENTRA,  3            # CAIDA se prende si dev >= 3p
    .equ A_SALE,   1            # CAIDA se apaga si dev <= 1p
    .equ C_SUBE,   0            # TENDENCIA se prende si tl >= 0 (precio sobre la media larga)
    .equ C_BAJA,   24           # TENDENCIA se apaga si 64 tl < -24 SL (37 % bajo la media larga)
    .equ B_EXCESO, 12           # EXCESO se prende si dev <= -12p (19 % sobre la media corta)
    .equ COMPRAR,  0x7F         # 01 111111: comprar 63
    .equ VENDER,   0xBF         # 10 111111: vender 63
    .equ RING,     0x700        # buffer corto
    .equ RING2,    0x500        # buffer largo
    .equ FIN_RING, 0x740
    .equ HW_MUL,   1
    .equ HW_SHIFT, 0

# ---------------------------------------------------------------------------
# Arranque
# ---------------------------------------------------------------------------
inicio:
    li   s0, 0x80010000
    li   sp, 0x80000000
    li   tp, 0
    li   s1, 0
    li   a5, 0                  # las tres banderas apagadas: parte fuera
espera_p0:                      # primer precio
    lw   t0, 0(s0)
    andi t0, t0, 1
    beqz t0, espera_p0
    lw   a1, 4(s0)
    # Los dos buffers se llenan con p0, asi las medias parten en p0. Se escribe de a
    # una palabra con p0 en sus 4 bytes (p0 * 0x01010101): 144 escrituras en vez de
    # 576, para terminar antes de que llegue el segundo precio en la ronda 3.
.if HW_SHIFT
    slli t0, a1, 8
    add  t0, t0, a1             # p0 * 0x0101
    slli t1, t0, 16
    add  t0, t0, t1             # p0 * 0x01010101
.else
    add  t0, a1, a1
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0             # 256 p0
    add  t0, t0, a1             # p0 * 0x0101
    add  t1, t0, t0
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1
    add  t1, t1, t1             # (p0 * 0x0101) * 65536
    add  t0, t0, t1             # p0 * 0x01010101
.endif
    li   t1, RING2
    li   t2, FIN_RING
llenar:
    sw   t0, 0(t1)
    addi t1, t1, 4
    bne  t1, t2, llenar
.if HW_SHIFT
    slli gp, a1, 6              # S  = 64 p0
    slli a0, a1, 9              # SL = 512 p0
.else
    add  gp, a1, a1
    add  gp, gp, gp
    add  gp, gp, gp
    add  gp, gp, gp
    add  gp, gp, gp
    add  gp, gp, gp             # S  = 64 p0
    add  a0, gp, gp
    add  a0, a0, a0
    add  a0, a0, a0             # SL = 512 p0
.endif
    j    medias

# ---------------------------------------------------------------------------
# 1. Esperar precio
# ---------------------------------------------------------------------------
espera:
    lw   t0, 0(s0)              # STATUS: bit 0 = llego un precio nuevo
    andi t0, t0, 1
    beqz t0, espera
    lw   a1, 4(s0)              # PRICE (leerlo baja el bit 0)

# ---------------------------------------------------------------------------
# 2. Las dos medias moviles: sale el precio mas viejo, entra el nuevo
# ---------------------------------------------------------------------------
medias:
    lbu  t0, RING(tp)
    sb   a1, RING(tp)
    sub  gp, gp, t0
    add  gp, gp, a1
    addi tp, tp, 1
    andi tp, tp, 63             # 64 y 512 son potencias de 2: el modulo es un andi
    lbu  t0, RING2(s1)
    sb   a1, RING2(s1)
    sub  a0, a0, t0
    add  a0, a0, a1
    addi s1, s1, 1
    andi s1, s1, 511

# ---------------------------------------------------------------------------
# 3. dev = S - 64p   y   64*tl = 64*(512p - SL)
# ---------------------------------------------------------------------------
desvios:
.if HW_SHIFT
    slli t0, a1, 6
    sub  a2, gp, t0             # dev
    slli t0, a1, 9
    sub  a3, t0, a0             # tl
    slli a3, a3, 6              # 64 tl
.else
    add  t0, a1, a1
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0             # 64p
    sub  a2, gp, t0             # dev
    add  t0, t0, t0
    add  t0, t0, t0
    add  t0, t0, t0             # 512p
    sub  a3, t0, a0             # tl
    add  a3, a3, a3
    add  a3, a3, a3
    add  a3, a3, a3
    add  a3, a3, a3
    add  a3, a3, a3
    add  a3, a3, a3             # 64 tl
.endif

# ---------------------------------------------------------------------------
# 4a. CAIDA
# ---------------------------------------------------------------------------
caida:
    li   t0, A_ENTRA
.if HW_MUL
    mul8 t1, a1, t0
.else
    mv   t2, a1
    jal  ra, mulsw              # t1 = A_ENTRA * p
.endif
    blt  a2, t1, caida_sale
    ori  a5, a5, 1              # dev >= A_ENTRA*p
    j    tendencia
caida_sale:
    li   t0, A_SALE
.if HW_MUL
    mul8 t1, a1, t0
.else
    mv   t2, a1
    jal  ra, mulsw              # t1 = A_SALE * p
.endif
    blt  t1, a2, tendencia      # entre los dos umbrales: no cambia
    andi a5, a5, -2             # dev <= A_SALE*p

# ---------------------------------------------------------------------------
# 4b. TENDENCIA
# ---------------------------------------------------------------------------
tendencia:
    li   t0, C_SUBE
.if HW_MUL
    mul8 t1, a0, t0
.else
    mv   t2, a0
    jal  ra, mulsw              # t1 = C_SUBE * SL
.endif
    blt  a3, t1, tend_baja
    ori  a5, a5, 2              # 64 tl >= C_SUBE*SL
    j    exceso
tend_baja:
    li   t0, C_BAJA
.if HW_MUL
    mul8 t1, a0, t0
.else
    mv   t2, a0
    jal  ra, mulsw              # t1 = C_BAJA * SL
.endif
    add  t1, t1, a3             # 64 tl + C_BAJA*SL
    bgez t1, exceso             # todavia no cae tanto: no cambia
    andi a5, a5, -3

# ---------------------------------------------------------------------------
# 4c. EXCESO
# ---------------------------------------------------------------------------
exceso:
    li   t0, B_EXCESO
.if HW_MUL
    mul8 t1, a1, t0
.else
    mv   t2, a1
    jal  ra, mulsw              # t1 = B_EXCESO * p
.endif
    add  t1, t1, a2             # dev + B_EXCESO*p
    blt  zero, t1, exceso_sale
    ori  a5, a5, 4              # dev <= -B_EXCESO*p
    j    decidir
exceso_sale:
    add  t1, t1, a2             # 2 dev + B_EXCESO*p
    bltz t1, decidir            # sigue muy arriba: no cambia
    andi a5, a5, -5

# ---------------------------------------------------------------------------
# 5. DENTRO = CAIDA o (TENDENCIA y no EXCESO); escribir DECISION
# ---------------------------------------------------------------------------
decidir:
    li   t1, COMPRAR
    andi t0, a5, 1
    bnez t0, escribir           # CAIDA
    andi t0, a5, 6
    li   t2, 2
    beq  t0, t2, escribir       # TENDENCIA sin EXCESO
    li   t1, VENDER
escribir:
    sw   t1, 8(s0)              # DECISION
    sw   a1, 0(sp)              # displays: precio en hexadecimal
    j    espera

.if HW_MUL
.else
# ---------------------------------------------------------------------------
# mulsw: t1 = t2 * t0, con t0 de 8 bits (0..255). Suma y duplica: por cada bit
# de t0 en 1 se suma el multiplicando, que se duplica en cada paso (no hay shift).
# Destruye t2 y a4. Desenrollado: sin contador de vueltas.
# ---------------------------------------------------------------------------
mulsw:
    li   t1, 0
    andi a4, t0, 1
    beqz a4, m1
    add  t1, t1, t2
m1: add  t2, t2, t2
    andi a4, t0, 2
    beqz a4, m2
    add  t1, t1, t2
m2: add  t2, t2, t2
    andi a4, t0, 4
    beqz a4, m3
    add  t1, t1, t2
m3: add  t2, t2, t2
    andi a4, t0, 8
    beqz a4, m4
    add  t1, t1, t2
m4: add  t2, t2, t2
    andi a4, t0, 16
    beqz a4, m5
    add  t1, t1, t2
m5: add  t2, t2, t2
    andi a4, t0, 32
    beqz a4, m6
    add  t1, t1, t2
m6: add  t2, t2, t2
    andi a4, t0, 64
    beqz a4, m7
    add  t1, t1, t2
m7: add  t2, t2, t2
    andi a4, t0, 128
    beqz a4, m8
    add  t1, t1, t2
m8: ret
.endif
