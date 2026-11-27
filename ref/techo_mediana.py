"""Hasta donde puede llegar la mediana por ronda: separa rondas por orden de los extremos, prob. de que la mediana de n rondas pase $27.000 y mejor mediana con piso/techo/toma/recompra/ancla."""
import os, sys
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(RAIZ, 'ref'))
import numpy as np, numba
from competencia import extremos, maestra
from minuto import EMPRESAS, ventanas

V = ventanas(250, empresas=EMPRESAS)
S = np.array([v for *_, v in V], np.int64)


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


wE = correr(S, 225, 122, 29, 0x4F, 160)
r1 = correr(S, 255, 100, 0, 0x7F, 0)
o = orden(S)
for k, nom in ((1, 'primero el 100, despues el 255'), (2, 'primero el 255, despues el 100')):
    m = o == k
    print(f'{nom}: {m.mean():.1%} de las rondas | E mediana ${np.median(wE[m]):,.0f} prom ${wE[m].mean():,.0f} | rival mediana ${np.median(r1[m]):,.0f} prom ${r1[m].mean():,.0f}')

# probabilidad de que la mediana de n rondas de la E sea >= 27.000
rng = np.random.default_rng(0)
for n in (3, 5, 7):
    meds = np.median(rng.choice(wE, (200000, n)), axis=1)
    print(f'mediana de {n} rondas al azar >= $27.000: {np.mean(meds >= 27000):.2%}  (>= $25.500: {np.mean(meds >= 25500):.1%})')

print('\nMejor mediana posible con piso/techo/toma/recompra/ancla:')
res = []
for toma in (200, 210, 220, 225, 230, 235, 240, 245, 250, 255):
    for rec in (100, 105, 110, 115, 120, 122, 125, 130, 140, 150):
        for anc in ((0, 0x7F, 0), (29, 0x4F, 160), (29, 0x7F, 160), (20, 0x7F, 160)):
            W = correr(S, toma, rec, *anc)
            res.append((np.median(W), W.mean(), W.min(), np.mean(W < 1e4), np.mean(W > r1 + .5) - np.mean(W < r1 - .5), toma, rec, anc))
res.sort(key=lambda r: -r[0])
for r in res[:8]:
    print(f'  toma {r[5]} recompra {r[6]} ancla {r[7]}: mediana ${r[0]:,.0f} prom ${r[1]:,.0f} peor ${r[2]:,.0f} pierde {r[3]:.2%} neto vs rival {r[4]:+.1%}')
print(f'  E: mediana ${np.median(wE):,.0f} prom ${wE.mean():,.0f}; rival: mediana ${np.median(r1):,.0f} prom ${r1.mean():,.0f}')
