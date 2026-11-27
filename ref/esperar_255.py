"""Algoritmo 'comprar y esperar el 255'.

Antes de ver el 100 o el 255, los dos tienen que aparecer. Si se compra todo a un precio p y se aguanta
hasta el 255, se sale con x 255/p > 1 pase lo que pase (si el 100 llega antes, igual despues llega el 255):
no hay perdida posible en esa fase, solo costo de oportunidad (si el 100 llega primero, el rival compra en 100
y saca x 2,55; nosotros x 255/p). Conviene si P(255 primero) es alta.
Entrada (antes de cualquier extremo), si p0 >= P0:
  modo 0: comprar todo al primer precio
  modo 1: comprar todo cuando p >= p0 + X (subida confirmada)
  modo 2: comprar todo cuando p <= p0 - X (en una caida)
  modo 3: comprar todo cuando p <= R (precio de reserva fijo)
Despues: como la D (vender en 255, techo 225 despues del 255, recompra 122 con los dos vistos), sin stop.
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
def regla(pr, modo, X, P0, toma, rec):
    decs = np.empty(len(pr), np.int64)
    vmin = vmax = False
    piso, techo = 100, 255
    dec = 0xBF
    p0 = pr[0]
    for n in range(len(pr)):
        p = pr[n]
        if p <= piso:
            dec = 0x7F
            if p <= 100:
                vmin = True
        elif p >= techo:
            dec = 0xBF
            if p >= 255:
                vmax = True
                techo = toma
        elif not vmin and not vmax and p0 >= P0 and dec == 0xBF:
            if (modo == 0 or (modo == 1 and p >= p0 + X) or (modo == 2 and p <= p0 - X)
                    or (modo == 3 and p <= X)):
                dec = 0x7F
        if vmin and vmax:
            piso = rec
        decs[n] = dec
    return decs


@numba.njit(parallel=True, cache=True)
def correr(S, modo, X, P0, toma, rec):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], regla(S[i], modo, X, P0, toma, rec))[0]
    return W


@numba.njit(parallel=True, cache=True)
def correr_ext(S, toma, rec, a, q, ap0):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], extremos(S[i], 100, 255, toma, rec, a, q, ap0))[0]
    return W


def main():
    rutas = sorted(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*_20*.csv')))
    P = np.array([leer(r) for r in rutas], np.int64)
    noms = [os.path.basename(r)[9:-4] for r in rutas]
    V = ventanas(250, empresas=EMPRESAS)
    S = np.array([v for *_, v in V], np.int64)
    anio = np.array([h[:4] for _, h, _ in V])
    o = orden(S)
    m2 = o == 2
    print('P(255 primero) segun el primer precio p0 (5 acciones reales):')
    for a, b in ((100, 120), (120, 140), (140, 160), (160, 180), (180, 200), (200, 220), (220, 256)):
        m = (S[:, 0] >= a) & (S[:, 0] < b)
        print(f'  p0 {a}-{b - 1}: {m.sum():5d} periodos, P(255 primero) = {m2[m].mean():.0%}')
    r1, r2 = correr_ext(S, 255, 100, 0, 0x7F, 0), correr_ext(S, 220, 100, 0, 0x7F, 0)
    wD, pD = correr_ext(S, 225, 122, 29, 0x4F, 0), correr_ext(P, 225, 122, 29, 0x4F, 0)
    pr1 = correr_ext(P, 255, 100, 0, 0x7F, 0)
    print(f'\nD: practicas prom ${pD.mean():,.0f} med ${np.median(pD):,.0f} | reales prom ${wD.mean():,.0f} '
          f'neto vs rival {neto(wD, r1):+.1%}/{neto(wD, r2):+.1%} peor ${wD.min():,.0f}')
    res = []
    grid = [(0, 0)] + [(1, x) for x in (1, 5, 10, 15, 20, 30)] + [(2, x) for x in (5, 10, 20, 30)] + \
           [(3, x) for x in (130, 140, 150, 160, 170)]
    for modo, X in grid:
        for P0 in (0, 140, 150, 160, 170, 180, 200):
            for toma, rec in ((225, 122), (220, 120), (235, 122), (225, 130)):
                w, p = correr(S, modo, X, P0, toma, rec), correr(P, modo, X, P0, toma, rec)
                res.append((min(neto(w, r1), neto(w, r2)), w.mean(), np.median(w), w.min(), np.mean(w < 1e4), neto(w, wD),
                            min(neto(w[anio == y], r1[anio == y]) for y in ('2022', '2023', '2024')),
                            p.mean(), np.median(p), int((p > pD + .5).sum()), int((p < pD - .5).sum()),
                            int((p > pr1 + .5).sum()), (modo, X, P0, toma, rec), p))
    cab = (' modo  X  P0  toma rec | reales: neto rival  prom   med    peor  pierde  vs D  peor año | '
           'practicas: prom   med  vs D (g/p)  gana al rival')
    for titulo, clave in (('Mejores contra los rivales en las series reales', lambda r: -r[0]),
                          ('Mejores en las practicas', lambda r: -r[7])):
        print(f'\n{titulo}:\n{cab}')
        for r in sorted(res, key=clave)[:10]:
            m, X, P0, t, rc = r[12]
            print(f'  {m}  {X:3d} {P0:3d}  {t} {rc} | {r[0]:+6.1%} {r[1]:7,.0f} {r[2]:7,.0f} {r[3]:6,.0f} {r[4]:6.2%} {r[5]:+6.1%} {r[6]:+6.1%} |'
                  f' {r[7]:7,.0f} {r[8]:7,.0f}  {r[9]}/{r[10]}   {r[11]}/8')
    b = max(res, key=lambda r: r[0])
    print(f'\nPor serie, D -> {b[12]} (la mejor contra rivales en reales):')
    for n, a, x, y in zip(noms, pD, b[13], pr1):
        print(f'  {n:14s} D {a:8,.0f} -> {x:8,.0f}   (rival {y:8,.0f})')


if __name__ == '__main__':
    main()
