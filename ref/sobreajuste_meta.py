"""Por que se puede sacar mas de $40.000 en la serie META del testbench y que pasa si esa regla se usa en las series de la competencia."""
import os, sys
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(RAIZ, 'ref'))
import numpy as np, numba
from competencia import extremos, maestra
from minuto import EMPRESAS, ventanas
from series import PRACTICA_META, leer_csv

pm = np.array(leer_csv(PRACTICA_META), np.int64)
i255 = int(np.argmax(pm >= 255)); i100 = int(np.argmax(pm <= 100))
print(f'practica_meta: p0={pm[0]}, 255 en tick {i255}, 100 en tick {i100}, minimo antes del 255 = {pm[:i255].min()} '
      f'(tick {int(np.argmin(pm[:i255]))}), maximo despues del 100 = {pm[i100:].max()}, final = {pm[-1]}')
dos = 10000 * 255 / pm[:i255].min() * pm[i100:].max() / 100
print(f'dos operaciones perfectas (min antes del 255 -> 255, 100 -> max despues): ${dos:,.0f}')


@numba.njit(cache=True)
def regla(pr, piso0, toma, rec, ancla, ao, ap0):
    """La E, pero antes de ver cualquier extremo compra todo si p <= piso0 (en vez de esperar el 100)."""
    decs = extremos(pr, 100, 255, toma, rec, ancla, ao, ap0)
    if piso0 <= 100:
        return decs
    vio = False
    dentro = False
    for n in range(len(pr)):
        p = pr[n]
        if p <= 100 or p >= 255:
            vio = True
        if not vio:
            if p <= piso0:
                dentro = True
            if dentro:
                decs[n] = 0x7F
    return decs


@numba.njit(parallel=True, cache=True)
def correr(S, piso0):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], regla(S[i], piso0, 225, 122, 29, 0x4F, 160))[0]
    return W


V = ventanas(250, empresas=EMPRESAS)
S = np.array([v for *_, v in V], np.int64)
wE = correr(S, 0)
r1 = np.array([maestra(s, extremos(s, 100, 255, 255, 100, 0, 0x7F, 0))[0] for s in S])
print('\nRegla "comprar todo en p <= X antes de ver el 100 o el 255" (sobre la E):')
print(f'{"X":>5s} {"META testbench":>15s} | 5 acciones: {"mediana":>8s} {"prom":>8s} {"peor":>8s} {"pierde":>7s} {"neto vs E":>9s} {"neto vs rival":>13s}')
for X in (0, 120, 130, 135, 140, 145, 150, 160):
    w_pm = maestra(pm, regla(pm, X, 225, 122, 29, 0x4F, 160))[0]
    W = correr(S, X)
    print(f'{X:5d} {w_pm:15,.0f} | {np.median(W):19,.0f} {W.mean():8,.0f} {W.min():8,.0f} {np.mean(W < 1e4):7.2%} '
          f'{np.mean(W > wE + .5) - np.mean(W < wE - .5):+9.1%} {np.mean(W > r1 + .5) - np.mean(W < r1 - .5):+13.1%}')
