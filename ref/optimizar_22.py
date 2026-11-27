"""Optimizacion sin sobreajuste: 22 empresas, todo 2022-2024, con validacion fuera de muestra.

Familia (ref/casos_f.py): todo al inicio si p0 >= P0; antes de los extremos, todo si el precio llega a Y;
ancla (X, q acciones, con o sin stop en p0) para el resto; toma y recompra despues.
Objetivo = el peor neto contra los dos rivales (100/255 y 100/255+220), con limites: peor ronda >= 85 % y
pierde plata en <= 1 % de las rondas.
Validacion: (1) elegir con 2022-2023 y medir en 2024; (2) elegir con 11 empresas y medir en las otras 11.
Las 8 practicas solo se miran al final (no se usan para elegir).
"""
import glob
import itertools
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import numpy as np                            # noqa: E402
from casos_f import correr                    # noqa: E402
from esperar_255 import correr_ext            # noqa: E402
from minuto import DATOS, ventanas            # noqa: E402
from mejorar_practicas import leer, neto      # noqa: E402


def objetivo(w, r1, r2):
    return min(neto(w, r1), neto(w, r2))


def main():
    t0 = time.time()
    todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
    V = ventanas(500, empresas=todas)
    S = np.array([v for *_, v in V], np.int64)
    emp = np.array([k for k, _, _ in V])
    anio = np.array([h[:4] for _, h, _ in V])
    rng = np.random.default_rng(7)
    grupoA = set(rng.choice(todas, len(todas) // 2, replace=False))
    mA = np.isin(emp, list(grupoA))
    mtr, mte = anio != '2024', anio == '2024'
    r1, r2 = correr_ext(S, 255, 100, 0, 0x7F, 0), correr_ext(S, 220, 100, 0, 0x7F, 0)
    rutas = sorted(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*_20*.csv')))
    P = np.array([leer(r) for r in rutas], np.int64)
    pr1 = correr_ext(P, 255, 100, 0, 0x7F, 0)
    print(f'{len(S)} periodos de {len(todas)} empresas (2022-2024). Grupo A: {sorted(grupoA)}')

    D = (256, 0, 29, 0x4F, 1, 225, 122)
    F = (170, 0, 29, 0x4F, 1, 225, 122)
    grid = list(itertools.product((160, 170, 180, 190, 200, 256), (0, 200, 210, 220, 230, 240),
                                  ((0, 0, 0), (29, 0x4F, 1), (29, 0x4F, 0), (20, 0x4F, 0)),
                                  (220, 225, 230), (115, 122, 130)))
    W = {}
    for i, (P0, Y, (a, q, st), t, rc) in enumerate(grid):
        W[(P0, Y, a, q, st, t, rc)] = correr(S, P0, Y, a, q, st, t, rc)
    for k in (D, F):
        if k not in W:
            W[k] = correr(S, *k)
    print(f'{len(W)} combinaciones en {time.time() - t0:.0f} s')

    def ok(w, m):
        return w[m].min() >= 0.85e4 and np.mean(w[m] < 1e4) <= 0.01

    def mejor(m):
        c = [(objetivo(w[m], r1[m], r2[m]), k) for k, w in W.items() if ok(w, m)]
        return max(c)[1]

    def linea(nom, k):
        w = W[k]
        p = correr(P, *k)
        return (f'{nom:30s} todo {objetivo(w, r1, r2):+6.1%} | 2022-23 {objetivo(w[mtr], r1[mtr], r2[mtr]):+6.1%} '
                f'2024 {objetivo(w[mte], r1[mte], r2[mte]):+6.1%} | grupo A {objetivo(w[mA], r1[mA], r2[mA]):+6.1%} '
                f'grupo B {objetivo(w[~mA], r1[~mA], r2[~mA]):+6.1%} | prom ${w.mean():,.0f} peor ${w.min():,.0f} '
                f'pierde {np.mean(w < 1e4):.2%} | practicas ${p.mean():,.0f} gana al rival {int((p > pr1 + .5).sum())}/8')

    print('\nneto = el peor contra los dos rivales (gana% - pierde%)')
    print(linea('D', D))
    print(linea('F', F))
    kt = mejor(mtr)
    print(linea(f'elegida con 2022-23 {kt}', kt))
    ka = mejor(mA)
    print(linea(f'elegida con grupo A {ka}', ka))
    kb = mejor(~mA)
    print(linea(f'elegida con grupo B {kb}', kb))
    kall = mejor(np.ones(len(S), bool))
    print(linea(f'elegida con todo {kall}', kall))
    print('\nTop 10 con todo (limites de riesgo cumplidos):')
    c = sorted([(objetivo(w, r1, r2), k) for k, w in W.items() if ok(w, np.ones(len(S), bool))], reverse=True)[:10]
    for _, k in c:
        print(linea(str(k), k))


if __name__ == '__main__':
    main()
