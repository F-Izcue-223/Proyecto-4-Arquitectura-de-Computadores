"""Las series de practica del profesor son casi todas 'primero el 255, despues el 100' (7 de 8).
Compara las versiones solo en ese tipo de periodo (5 acciones de la competencia) y busca el mejor ancla para el."""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, '..', 'tools'))
import numba                                      # noqa: E402
import numpy as np                                # noqa: E402
from competencia import extremos, maestra         # noqa: E402
from minuto import EMPRESAS, ventanas             # noqa: E402


@numba.njit(parallel=True, cache=True)
def correr(S, toma, rec, ancla, ao, ap0):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], extremos(S[i], 100, 255, toma, rec, ancla, ao, ap0))[0]
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


V = ventanas(250, empresas=EMPRESAS)
S = np.array([v for *_, v in V], np.int64)
o = orden(S)
r1, r2 = correr(S, 255, 100, 0, 0x7F, 0), correr(S, 220, 100, 0, 0x7F, 0)
vers = {'A': (225, 120, 30, 0x4F, 0), 'B': (225, 120, 0, 0x7F, 0), 'C': (225, 117, 26, 0x4F, 0),
        'D': (225, 122, 29, 0x4F, 0), 'E': (225, 122, 29, 0x4F, 160)}
for tipo, nom in ((2, 'PRIMERO EL 255 (como 7 de 8 practicas)'), (1, 'PRIMERO EL 100'), (0, 'TODAS')):
    m = (o == tipo) if tipo else np.ones(len(S), bool)
    print(f'\n== {nom}: {m.sum()} periodos')
    for v, prm in vers.items():
        w = correr(S, *prm)[m]
        print(f'  {v}  prom ${w.mean():7,.0f}  mediana ${np.median(w):7,.0f}  peor ${w.min():6,.0f}  pierde {np.mean(w < 1e4):5.2%}'
              f'  neto vs 100/255 {neto(w, r1[m]):+6.1%}  vs +220 {neto(w, r2[m]):+6.1%}')

m = o == 2
print('\nMejor ancla solo en "primero el 255" (toma 225):')
res = []
for rec in (117, 120, 122, 125):
    for anc in (20, 25, 29, 35):
        for q in (10, 15, 20, 25):
            for ap0 in (0, 120, 140, 160):
                w = correr(S, 225, rec, anc, 0x40 | q, ap0)
                wm = w[m]
                res.append((min(neto(wm, r1[m]), neto(wm, r2[m])), rec, anc, q, ap0, wm.mean(), wm.min(),
                            min(neto(w, r1), neto(w, r2)), w.min()))
res.sort(key=lambda r: -r[0])
for r in res[:8]:
    print(f'  rec {r[1]} ancla {r[2]} q {r[3]:2d} p0>={r[4]:3d}: neto min vs rivales (255 primero) {r[0]:+6.1%}  prom ${r[5]:,.0f}'
          f'  peor ${r[6]:,.0f} | en todas: neto {r[7]:+6.1%} peor ${r[8]:,.0f}')
