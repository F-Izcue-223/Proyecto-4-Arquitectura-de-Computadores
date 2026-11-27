"""Barrido de parametros del algoritmo ANTERIOR (sw/trade_tendencia.s) por tipo de ronda.

Corta todas las series de data/series en rondas de 2000 ticks y las clasifica segun
como le fue a comprar y mantener en esa ronda: alcista (> +8 %), lateral, bajista
(< -8 %). Para cada combinacion de parametros informa la media geometrica del
patrimonio final / 10 000 en cada clase, en cuantas rondas le gana a comprar y
mantener y la peor ronda.

Ojo al elegir: una media alta puede venir de pocas rondas muy buenas. La competencia
son 3 rondas, asi que conviene mirar tambien "gana a CyM".

El lazo esta repetido aqui (con numba, para que el barrido tome segundos) en vez de
usar ref/trader.py. Antes de barrer se comprueba que los dos den las mismas decisiones
con los parametros actuales de sw/trade.s.

Uso:
  python ref/barrido.py                      rejilla alrededor de los parametros actuales
  python ref/barrido.py 3,2,1,4,6 4,2,1,8,4  solo esas combinaciones (A_ENTRA,A_SALE,C_SUBE,C_BAJA,B_EXCESO)
"""
import itertools
import os
import sys

import numba
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from mercado import comprar_y_mantener, simular  # noqa: E402
from series import rondas, todas  # noqa: E402
from trader import PROGRAMAS, Tendencia, leer_equ  # noqa: E402


@numba.njit(cache=True)
def correr(pr, a_in, a_out, c_in, c_out, b):
    """Patrimonio final y decisiones con las reglas de la maestra (tb/tb_proyecto_4.sv)."""
    caja, acc, dec = 10000, 0, 0
    r1 = np.zeros(64, np.int64); r2 = np.zeros(512, np.int64)
    s = sl = i1 = i2 = 0
    caida = tend = exceso = False
    decs = np.zeros(len(pr), np.int64)
    for n in range(len(pr)):
        p = pr[n]
        q = dec & 63
        if dec >> 6 == 1:
            q = min(q, (caja - 5) // p)
            if q > 0:
                caja -= q * p + 5; acc += q
        elif dec >> 6 == 2:
            q = min(q, acc)
            if q > 0 and caja + q * p >= 5:
                caja += q * p - 5; acc -= q
        if n == 0:
            r1[:] = p; r2[:] = p; s = 64 * p; sl = 512 * p
        s += p - r1[i1]; r1[i1] = p; i1 = (i1 + 1) & 63
        sl += p - r2[i2]; r2[i2] = p; i2 = (i2 + 1) & 511
        dev = s - 64 * p
        tl64 = 64 * (512 * p - sl)
        if dev >= a_in * p: caida = True
        elif dev <= a_out * p: caida = False
        if tl64 >= c_in * sl: tend = True
        elif tl64 + c_out * sl < 0: tend = False
        if dev + b * p <= 0: exceso = True
        elif 2 * dev + b * p >= 0: exceso = False
        dec = 127 if (caida or (tend and not exceso)) else 191
        decs[n] = dec
    return caja + acc * pr[-1], decs


def main():
    e = leer_equ(PROGRAMAS['tendencia'])
    actual = (e['A_ENTRA'], e['A_SALE'], e['C_SUBE'], e['C_BAJA'], e['B_EXCESO'])
    series = {k: np.array(v, np.int64) for k, v in todas().items()}

    # mismo resultado que trader.py con los parametros actuales
    p0 = next(iter(series.values()))
    assert list(correr(p0, *actual)[1]) == simular(list(p0), Tendencia())['decisiones'], 'barrido.py != trader.py'

    R = [np.array(r, np.int64) for v in series.values() for r in rondas(list(v))]
    cym = np.array([comprar_y_mantener(list(r)) for r in R]) / 1e4
    clase = np.where(cym > 1.08, 0, np.where(cym < 0.92, 2, 1))
    if len(sys.argv) > 1:
        rejilla = [tuple(int(x) for x in a.split(',')) for a in sys.argv[1:]]
    else:
        rejilla = [g for g in itertools.product(*[sorted({max(0, v - d) for d in (-2, -1, 0, 1, 2)}) for v in actual])]
    filas = []
    for g in rejilla:
        w = np.array([correr(r, *g)[0] for r in R]) / 1e4
        lg = np.log(np.maximum(w, 1e-4))
        filas.append((float(lg.mean()), g, [float(np.exp(lg[clase == c].mean())) for c in range(3)],
                      int((w > cym).sum()), float(w.min())))
    print(f'{len(R)} rondas: {int((clase == 0).sum())} alcistas, {int((clase == 1).sum())} laterales, '
          f'{int((clase == 2).sum())} bajistas. CyM: ' +
          ' '.join(f'{np.exp(np.log(cym[clase == c]).mean()):.3f}' for c in range(3)))
    print(f"{'A_ENTRA,A_SALE,C_SUBE,C_BAJA,B':32s} alcista lateral bajista  gana a CyM  peor ronda")
    for _, g, por, gana, peor in sorted(filas, reverse=True)[:20]:
        marca = '  <- actual' if g == actual else ''
        print(f'{str(g):32s} {por[0]:7.3f} {por[1]:7.3f} {por[2]:7.3f}  {gana:5d}/{len(R)}  {peor:10.3f}{marca}')


if __name__ == '__main__':
    main()
