"""Versiones de referencia de los programas del Espino, bit a bit.

Extremos (sw/trade.s, el de la competencia desde el 17-nov-2026)
    Las series son ventanas de precios reales llevadas a [100, 255]: el minimo de la
    ventana vale 100 y el maximo 255. Dentro desde que el precio llega al piso vigente
    hasta que llega al techo vigente; entre medio no cambia. Parte fuera. El techo es
    255 hasta que aparece el 255; desde ahi es TOMA_GANANCIA (225). El piso es 100
    hasta que aparecieron el 100 y el 255; desde ahi es RECOMPRA (120).
    Ancla (para no perder las subidas antes del primer extremo): mientras no aparece ni el
    100 ni el 255, si el precio sube ANCLA (30) sobre el primer precio p0 se manda una vez
    ANCLA_ORDEN (comprar 15) y despues "mantener"; si vuelve a p0 o baja de el, "vender 63".
    ANCLA = 0 la apaga.

Tendencia (sw/trade_tendencia.s, el anterior)
    "Caidas + tendencia": medias moviles de 64 y 512 ticks y tres banderas con
    histeresis. Se conserva porque el estudio de co-diseno (mul8, shifter, Amdahl,
    roofline) se midio con el.

Las dos devuelven "comprar 63" (dentro) o "vender 63" (fuera); la maestra recorta
cada orden a lo que se puede ejecutar, asi que no llevan la caja ni las acciones.
Las constantes se leen del .s para que haya una sola fuente de verdad.

Trader y PROGRAMA son los del algoritmo elegido con la variable de entorno ALGO
(extremos por defecto; ALGO=tendencia para reproducir el estudio anterior). Asi
verificar.py, comparar_rtl.py, backtest.py y el Makefile sirven para los dos.

Operaciones utiles (para Ops/s y el roofline): cada suma, resta, comparacion o
multiplicacion sobre datos del mercado que pide el algoritmo, tal como esta escrito
aqui, cuenta 1. No cuentan las direcciones, los indices ni el control.
"""
import os
import re

SW = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'sw')
PROGRAMAS = {'extremos': os.path.join(SW, 'trade.s'),
             'tendencia': os.path.join(SW, 'trade_tendencia.s')}
TRADE_S = PROGRAMAS['extremos']


def leer_equ(ruta=TRADE_S):
    """Constantes .equ de un .s -> dict."""
    equ = {}
    with open(ruta, encoding='utf-8') as f:
        for linea in f:
            m = re.match(r'\s*\.equ\s+(\w+)\s*,\s*([-\w]+)', linea.split('#')[0])
            if m:
                equ[m[1]] = int(m[2], 0)
    return equ


class Extremos:
    def __init__(self, equ=None):
        e = equ or leer_equ(PROGRAMAS['extremos'])
        self.MIN, self.MAX = e['MINIMO'], e['MAXIMO']
        self.TOMA, self.RECOMPRA = e['TOMA_GANANCIA'], e['RECOMPRA']
        self.ANCLA = e.get('ANCLA', 0)
        self.ANCLA_ORDEN = e.get('ANCLA_ORDEN', e['COMPRAR'])
        self.ANCLA_P0 = e.get('ANCLA_P0', 0)    # el ancla solo si p0 >= ANCLA_P0
        self.TODO_P0 = e.get('TODO_P0', 0)      # si p0 >= TODO_P0: todo al inicio hasta el 255
        self.TODO_Y = e.get('TODO_Y', 0)        # version G: tambien todo si p >= TODO_Y antes de los extremos
        self.p0 = None
        self.dec = e['VENDER']          # decision vigente (a5 en trade.s)
        self.COMPRAR, self.VENDER = e['COMPRAR'], e['VENDER']
        self.dentro = False
        self.piso, self.techo = self.MIN, self.MAX
        self.vio_min = self.vio_max = False
        self.ops = []            # operaciones utiles por tick (comparaciones de precio)

    def tick(self, p, enviado):
        if self.p0 is None:
            self.p0 = p
        salida = None
        if p <= self.piso:
            self.dentro = True
            self.dec = self.COMPRAR
            ops = 2                               # piso y minimo
            if p <= self.MIN:
                self.vio_min = True
        elif p >= self.techo:
            self.dentro = False
            self.dec = self.VENDER
            ops = 3                               # piso, techo y maximo
            if p >= self.MAX:
                self.vio_max = True
                self.techo = self.TOMA
        elif (((self.TODO_P0 and self.p0 >= self.TODO_P0) or (self.TODO_Y and p >= self.TODO_Y))
              and not self.vio_min and not self.vio_max):
            ops = 2
            self.dec = self.COMPRAR
            self.dentro = True
        elif self.ANCLA and not self.vio_min and not self.vio_max and self.p0 >= self.ANCLA_P0:
            ops = 4                               # piso, techo, ancla arriba y ancla abajo
            if p >= self.p0 + self.ANCLA:
                if self.dec == self.VENDER:       # entra: una orden y despues mantener
                    salida = self.ANCLA_ORDEN
                    self.dec = 0
                    self.dentro = True
            elif p <= self.p0:
                self.dec = self.VENDER
                self.dentro = False
        else:
            ops = 2                               # piso y techo
        if self.vio_min and self.vio_max:
            self.piso = self.RECOMPRA
        self.ops.append(ops)
        return self.dec if salida is None else salida


class Tendencia:
    N, L = 64, 512      # largos de las medias (potencias de 2)

    def __init__(self, equ=None):
        e = equ or leer_equ(PROGRAMAS['tendencia'])
        self.A_ENTRA, self.A_SALE = e['A_ENTRA'], e['A_SALE']
        self.C_SUBE, self.C_BAJA, self.B = e['C_SUBE'], e['C_BAJA'], e['B_EXCESO']
        self.COMPRAR, self.VENDER = e['COMPRAR'], e['VENDER']
        self.r1 = self.r2 = None
        self.S = self.SL = self.i1 = self.i2 = 0
        self.caida = self.tend = self.exceso = False
        self.ops = []            # operaciones utiles por tick

    def tick(self, p, enviado):
        # Medias: sale el precio mas viejo de cada buffer, entra el nuevo
        if self.r1 is None:
            self.r1, self.S = [p] * self.N, self.N * p
            self.r2, self.SL = [p] * self.L, self.L * p
        self.S += p - self.r1[self.i1]
        self.r1[self.i1] = p
        self.i1 = (self.i1 + 1) & (self.N - 1)
        self.SL += p - self.r2[self.i2]
        self.r2[self.i2] = p
        self.i2 = (self.i2 + 1) & (self.L - 1)

        dev = self.S - self.N * p
        tl64 = 64 * (self.L * p - self.SL)
        ops = 9                                   # 4 de las sumas, 64p, dev, 512p, tl, 64 tl

        ops += 2                                  # A_ENTRA*p y comparar
        if dev >= self.A_ENTRA * p:
            self.caida = True
        else:
            ops += 2                              # A_SALE*p y comparar
            if dev <= self.A_SALE * p:
                self.caida = False

        ops += 2                                  # C_SUBE*SL y comparar
        if tl64 >= self.C_SUBE * self.SL:
            self.tend = True
        else:
            ops += 3                              # C_BAJA*SL, sumar y comparar
            if tl64 + self.C_BAJA * self.SL < 0:
                self.tend = False

        ops += 3                                  # B*p, sumar y comparar
        if dev + self.B * p <= 0:
            self.exceso = True
        else:
            ops += 2                              # sumar y comparar
            if 2 * dev + self.B * p >= 0:
                self.exceso = False

        self.ops.append(ops)
        dentro = self.caida or (self.tend and not self.exceso)
        return self.COMPRAR if dentro else self.VENDER


ALGO = os.environ.get('ALGO', 'extremos')
Trader = {'extremos': Extremos, 'tendencia': Tendencia}[ALGO]
PROGRAMA = PROGRAMAS[ALGO]
