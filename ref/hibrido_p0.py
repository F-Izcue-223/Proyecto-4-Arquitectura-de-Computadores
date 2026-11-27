"""Hibrido: si p0 >= P0, comprar todo al primer precio y aguantar hasta el 255 (sin stop: el 255 esta garantizado);
si P1 <= p0 < P0, comprar q acciones al primer precio con la misma regla; si p0 < P1, el ancla de la D
(compra 15 si sube 29 sobre p0, vende si vuelve a p0). Despues, igual que la D (toma 225, recompra 122)."""
import glob
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import numba                                  # noqa: E402
import numpy as np                            # noqa: E402
from competencia import maestra               # noqa: E402
from esperar_255 import correr_ext            # noqa: E402
from minuto import DATOS, EMPRESAS, ventanas  # noqa: E402
from mejorar_practicas import leer, neto, orden   # noqa: E402


@numba.njit(cache=True)
def regla(pr, P0, P1, q, toma, rec, ancla, aq):
    decs = np.empty(len(pr), np.int64)
    vmin = vmax = False
    piso, techo = 100, 255
    p0 = pr[0]
    dec = 0xBF
    out = -1
    for n in range(len(pr)):
        p = pr[n]
        out = -1
        if p <= piso:
            dec = 0x7F
            if p <= 100:
                vmin = True
        elif p >= techo:
            dec = 0xBF
            if p >= 255:
                vmax = True
                techo = toma
        elif not vmin and not vmax:
            if p0 >= P0:
                dec = 0x7F                      # todo dentro hasta el 255
            elif p0 >= P1:
                if n == 0:
                    out = 0x40 | q              # una parte al primer precio, hasta el 255
                    dec = 0
            elif ancla > 0:
                if p >= p0 + ancla:
                    if dec == 0xBF:
                        out = aq
                        dec = 0
                elif p <= p0:
                    dec = 0xBF
        if vmin and vmax:
            piso = rec
        decs[n] = dec if out < 0 else out
    return decs


@numba.njit(parallel=True, cache=True)
def correr(S, P0, P1, q, toma, rec, ancla, aq):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], regla(S[i], P0, P1, q, toma, rec, ancla, aq))[0]
    return W


def main():
    rutas = sorted(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*_20*.csv')))
    P = np.array([leer(r) for r in rutas], np.int64)
    noms = [os.path.basename(r)[9:-4] for r in rutas]
    todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
    for nombre, emps, paso in (('5 de la competencia', EMPRESAS, 250), ('22 acciones', todas, 500)):
        V = ventanas(paso, empresas=emps)
        S = np.array([v for *_, v in V], np.int64)
        anio = np.array([h[:4] for _, h, _ in V])
        m2 = orden(S) == 2
        r1, r2 = correr_ext(S, 255, 100, 0, 0x7F, 0), correr_ext(S, 220, 100, 0, 0x7F, 0)
        wD = correr_ext(S, 225, 122, 29, 0x4F, 0)
        pD, pr1 = correr_ext(P, 225, 122, 29, 0x4F, 0), correr_ext(P, 255, 100, 0, 0x7F, 0)
        print(f'\n== {nombre} ({len(S)} periodos). D: neto vs rivales {neto(wD, r1):+.1%}/{neto(wD, r2):+.1%}, '
              f'prom ${wD.mean():,.0f}, peor ${wD.min():,.0f}, pierde {np.mean(wD < 1e4):.2%}')
        res = []
        for P0 in (160, 170, 180, 190, 200):
            for P1, q in ((256, 0), (140, 20), (140, 40), (150, 30), (150, 45), (130, 25)):
                if P1 >= P0 and P1 != 256:
                    continue
                for ancla in (0, 29):
                    prm = (P0, min(P1, P0), q, 225, 122, ancla, 0x4F)
                    w, p = correr(S, *prm), correr(P, *prm)
                    res.append((min(neto(w, r1), neto(w, r2)), neto(w[m2], r1[m2]), neto(w[~m2], r1[~m2]), w.mean(), w.min(),
                                np.mean(w < 1e4), neto(w, wD), min(neto(w[anio == y], r1[anio == y]) for y in ('2022', '2023', '2024')),
                                p.mean(), int((p > pD + .5).sum()), int((p < pD - .5).sum()), int((p > pr1 + .5).sum()),
                                int((p < pr1 - .5).sum()), prm, p))
        print(' P0  P1   q anc | neto rival (255 1ro / 100 1ro)   prom   peor  pierde  vs D  peor año | practicas prom  vs D g/p  vs rival g/p')
        for r in sorted(res, key=lambda r: -r[0])[:10]:
            P0, P1, q, _, _, an, _ = r[13]
            print(f' {P0} {P1:3d} {q:3d} {an:3d} | {r[0]:+6.1%} ({r[1]:+6.1%} / {r[2]:+6.1%}) {r[3]:7,.0f} {r[4]:6,.0f} {r[5]:6.2%} {r[6]:+6.1%} {r[7]:+6.1%} |'
                  f' {r[8]:7,.0f}      {r[9]}/{r[10]}        {r[11]}/{r[12]}')
        if nombre.startswith('5'):
            b = max(res, key=lambda r: r[0])
            print(f'  por serie (D -> {b[13][:3]}, ancla {b[13][5]}):')
            for n, a, x, y in zip(noms, pD, b[14], pr1):
                print(f'    {n:14s} D {a:8,.0f} -> {x:8,.0f}   rival {y:8,.0f}')


if __name__ == '__main__':
    main()
