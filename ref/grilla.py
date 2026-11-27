"""Algoritmo distinto a 'extremos': posicion segun el nivel (grilla).

Objetivo de acciones = fraccion f(p) del patrimonio, f = 1 bajo L, 0 sobre H, lineal entre medio.
El agente lleva su propia cuenta (caja y acciones, las reglas de la maestra son deterministas) y manda
comprar/vender la diferencia (max 63 por orden) solo si pasa de d acciones (para no pagar comisiones de mas).
modo 0: grilla siempre (con 100 -> todo dentro y 255 -> todo fuera).
modo 1: como 0, pero si ya aparecio el 100 y todavia no el 255, todo dentro (el 255 esta garantizado).
modo 2: como 1, y ademas si ya aparecio el 255 y todavia no el 100, todo fuera (el 100 esta garantizado).
Se mide en las 8 practicas y en las 5.462 series reales de las 5 acciones.
"""
import glob
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import numba                                  # noqa: E402
import numpy as np                            # noqa: E402
from competencia import extremos, maestra     # noqa: E402
from minuto import EMPRESAS, ventanas         # noqa: E402
from mejorar_practicas import leer, neto, orden   # noqa: E402


@numba.njit(cache=True)
def grilla(pr, L, H, d, modo):
    caja, acc = 10000, 0
    dec = 0
    vmin = vmax = False
    for n in range(len(pr)):
        p = pr[n]
        # la maestra ejecuta la decision anterior a este precio
        q = dec & 63
        if dec >> 6 == 1:
            q = min(q, (caja - 5) // p)
            if q > 0:
                caja -= q * p + 5
                acc += q
        elif dec >> 6 == 2:
            q = min(q, acc)
            if q > 0:
                caja += q * p - 5
                acc -= q
        if p <= 100:
            vmin = True
        if p >= 255:
            vmax = True
        if p <= 100:
            f = 1.0
        elif p >= 255:
            f = 0.0
        elif modo >= 1 and vmin and not vmax:
            f = 1.0
        elif modo >= 2 and vmax and not vmin:
            f = 0.0
        elif p <= L:
            f = 1.0
        elif p >= H:
            f = 0.0
        else:
            f = (H - p) / (H - L)
        w = caja + acc * p
        objetivo = int(f * (w - 10) / p)
        dif = objetivo - acc
        if dif > d or (f == 1.0 and dif > 0):
            dec = 0x40 | min(dif, 63)
        elif -dif > d or (f == 0.0 and acc > 0):
            dec = 0x80 | min(-dif, 63)
        else:
            dec = 0
    return caja + acc * pr[-1]


@numba.njit(parallel=True, cache=True)
def correr(S, L, H, d, modo):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = grilla(S[i], L, H, d, modo)
    return W


@numba.njit(parallel=True, cache=True)
def correr_ext(S, toma, rec, a, q, ap0):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], extremos(S[i], 100, 255, toma, rec, a, q, ap0))[0]
    return W


def main():
    rutas = sorted(set(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*_20*.csv'))))
    P = np.array([leer(r) for r in rutas], np.int64)
    noms = [os.path.basename(r)[9:-4] for r in rutas]
    S = np.array([v for *_, v in ventanas(250, empresas=EMPRESAS)], np.int64)
    m2 = orden(S) == 2
    r1 = correr_ext(S, 255, 100, 0, 0x7F, 0)
    wD, pD = correr_ext(S, 225, 122, 29, 0x4F, 0), correr_ext(P, 225, 122, 29, 0x4F, 0)
    print(f'{len(P)} practicas: {noms}')
    print(f'D: practicas prom ${pD.mean():,.0f} med ${np.median(pD):,.0f} | reales prom ${wD.mean():,.0f} neto vs rival {neto(wD, r1):+.1%} peor ${wD.min():,.0f}')
    res = []
    for modo in (0, 1, 2):
        for L in (100, 110, 120, 130, 140):
            for H in (150, 170, 190, 210, 230, 255):
                if H <= L + 10:
                    continue
                for d in (2, 5, 10, 20, 40):
                    w, p = correr(S, L, H, d, modo), correr(P, L, H, d, modo)
                    res.append((p.mean(), np.median(p), int((p > pD + .5).sum()), int((p < pD - .5).sum()), w.mean(),
                                np.median(w), neto(w, r1), neto(w[m2], r1[m2]), neto(w, wD), w.min(), (modo, L, H, d), p))
    print('\nMejores en las practicas:')
    print(' modo   L   H   d | practicas prom   med  gana/pierde vs D | reales prom   med  neto rival (255 1ro)  vs D   peor')
    for r in sorted(res, key=lambda r: -r[0])[:10]:
        print(f'  {r[10][0]}   {r[10][1]:3d} {r[10][2]:3d} {r[10][3]:2d} | {r[0]:9,.0f} {r[1]:7,.0f}   {r[2]}/{r[3]}          | {r[4]:7,.0f} {r[5]:7,.0f} {r[6]:+6.1%} ({r[7]:+6.1%}) {r[8]:+6.1%} {r[9]:6,.0f}')
    print('\nMejores en las reales contra el rival:')
    for r in sorted(res, key=lambda r: -r[6])[:6]:
        print(f'  {r[10][0]}   {r[10][1]:3d} {r[10][2]:3d} {r[10][3]:2d} | {r[0]:9,.0f} {r[1]:7,.0f}   {r[2]}/{r[3]}          | {r[4]:7,.0f} {r[5]:7,.0f} {r[6]:+6.1%} ({r[7]:+6.1%}) {r[8]:+6.1%} {r[9]:6,.0f}')
    b = max(res, key=lambda r: r[0])
    print(f'\nPor serie, D -> grilla {b[10]}:')
    for n, a, x in zip(noms, pD, b[11]):
        print(f'  {n:14s} {a:8,.0f} -> {x:8,.0f}')


if __name__ == '__main__':
    main()
