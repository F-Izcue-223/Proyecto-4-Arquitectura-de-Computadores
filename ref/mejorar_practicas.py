"""Busca como mejorar la D en series como las de practica (7 de 8 'primero el 255'):
ancla mas grande (q acciones, o todo con q=64), disparo X sobre p0, stop en p0 - s, toma y recompra.
Mide en las 8 practicas (Descargas/practica_*.csv) y en las 5 acciones reales (todas y solo 'primero el 255').
"""
import glob
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import numba                                  # noqa: E402
import numpy as np                            # noqa: E402
from competencia import maestra               # noqa: E402
from minuto import EMPRESAS, ventanas         # noqa: E402


@numba.njit(cache=True)
def regla(pr, toma, rec, X, q, s):
    decs = np.empty(len(pr), np.int64)
    vio_min = vio_max = False
    piso, techo = 100, 255
    dec = 0xBF
    p0 = pr[0]
    for n in range(len(pr)):
        p = pr[n]
        out = -1
        if p <= piso:
            dec = 0x7F
            if p <= 100:
                vio_min = True
        elif p >= techo:
            dec = 0xBF
            if p >= 255:
                vio_max = True
                techo = toma
        elif X > 0 and not vio_min and not vio_max:
            if p >= p0 + X:
                if dec == 0xBF:
                    if q >= 64:
                        dec = 0x7F
                    else:
                        out = 0x40 | q
                        dec = 0
            elif p <= p0 - s:
                dec = 0xBF
        if vio_min and vio_max:
            piso = rec
        decs[n] = dec if out < 0 else out
    return decs


@numba.njit(parallel=True, cache=True)
def correr(S, toma, rec, X, q, s):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], regla(S[i], toma, rec, X, q, s))[0]
    return W


@numba.njit(parallel=True, cache=True)
def orden(S):
    o = np.empty(S.shape[0], np.int64)
    for i in numba.prange(S.shape[0]):
        a = b = -1
        for n in range(S.shape[1]):
            if a < 0 and S[i, n] <= 100:
                a = n
            if b < 0 and S[i, n] >= 255:
                b = n
        o[i] = 1 if a < b else 2
    return o


def neto(a, b):
    return float(np.mean(a > b + .5) - np.mean(a < b - .5))


def leer(r):
    with open(r) as f:
        next(f)
        return [int(l.split(',')[1]) for l in f if l.strip()]


def main():
    rutas = sorted(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*.csv')))
    P = np.array([leer(r) for r in rutas], np.int64)
    noms = [os.path.basename(r)[9:-4] for r in rutas]
    V = ventanas(250, empresas=EMPRESAS)
    S = np.array([v for *_, v in V], np.int64)
    o = orden(S)
    m2 = o == 2
    r1 = correr(S, 255, 100, 0, 0, 0)
    D = (225, 122, 29, 15, 0)
    wD, pD = correr(S, *D), correr(P, *D)
    res = []
    for toma in (220, 225, 235):
        for rec in (115, 122, 130):
            for X in (5, 10, 15, 20, 25, 29, 35):
                for q in (15, 25, 40, 64):
                    for s in (0, 5, 10, 20, 40):
                        prm = (toma, rec, X, q, s)
                        w, p = correr(S, *prm), correr(P, *prm)
                        res.append((p.mean(), int((p > pD + .5).sum()), int((p < pD - .5).sum()), np.median(p), p.min(),
                                    w.mean(), neto(w, r1), neto(w[m2], r1[m2]), w.min(), neto(w, wD), prm, p))
    print(f'D en practicas: prom ${pD.mean():,.0f} mediana ${np.median(pD):,.0f} | reales: prom ${wD.mean():,.0f} '
          f'neto vs rival {neto(wD, r1):+.1%} (255 primero {neto(wD[m2], r1[m2]):+.1%}) peor ${wD.min():,.0f}')
    print('\nMejores en las practicas (promedio), con su comportamiento en las 5.462 series reales:')
    print('   toma rec  X   q  s | practicas: prom   med  peor  gana/pierde vs D | reales: prom  neto rival (255 1ro)  peor   neto vs D')
    for r in sorted(res, key=lambda r: -r[0])[:12]:
        print(f'  {r[10][0]:4d} {r[10][1]:3d} {r[10][2]:2d} {r[10][3]:3d} {r[10][4]:2d} | {r[0]:7,.0f} {r[3]:7,.0f} {r[4]:6,.0f}   {r[1]}/{r[2]}'
              f'          | {r[5]:7,.0f} {r[6]:+6.1%} ({r[7]:+6.1%}) {r[8]:6,.0f} {r[9]:+6.1%}')
    print('\nMejores en las reales contra el rival, que ademas no pierden contra la D en las practicas:')
    ok = [r for r in res if r[2] == 0]
    for r in sorted(ok, key=lambda r: -r[6])[:8]:
        print(f'  {r[10][0]:4d} {r[10][1]:3d} {r[10][2]:2d} {r[10][3]:3d} {r[10][4]:2d} | {r[0]:7,.0f} {r[3]:7,.0f} {r[4]:6,.0f}   {r[1]}/{r[2]}'
              f'          | {r[5]:7,.0f} {r[6]:+6.1%} ({r[7]:+6.1%}) {r[8]:6,.0f} {r[9]:+6.1%}')
    best = max(res, key=lambda r: r[0])
    print('\nPor serie (D -> mejor en practicas ' + str(best[10]) + '):')
    for n, a, b in zip(noms, pD, best[11]):
        print(f'  {n:14s} {a:8,.0f} -> {b:8,.0f}')


if __name__ == '__main__':
    main()
