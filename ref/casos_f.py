"""Casos nuevos sobre la F (todo al inicio si p0 >= P0, si no la D):
  Y     : ademas, antes de los extremos, comprar todo si el precio llega a Y (nivel absoluto), y esperar el 255
  stop  : 1 = el ancla vende si vuelve a p0 (como la D); 0 = el ancla tambien espera el 255 (garantizado)
  toma / recompra re-afinadas con la F
Mide en las 8 practicas, en las 5 acciones (5.462) y en las 22 (11.789)."""
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
from mejorar_practicas import leer, neto      # noqa: E402


@numba.njit(cache=True)
def regla(pr, P0, Y, anc, aq, stop, toma, rec):
    decs = np.empty(len(pr), np.int64)
    vmin = vmax = False
    piso, techo = 100, 255
    p0 = pr[0]
    dec = 0xBF
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
            if p0 >= P0 or (Y > 0 and p >= Y):
                dec = 0x7F
            elif anc > 0:
                if p >= p0 + anc:
                    if dec == 0xBF:
                        out = aq
                        dec = 0
                elif stop and p <= p0:
                    dec = 0xBF
        if vmin and vmax:
            piso = rec
        decs[n] = dec if out < 0 else out
    return decs


@numba.njit(parallel=True, cache=True)
def correr(S, P0, Y, anc, aq, stop, toma, rec):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], regla(S[i], P0, Y, anc, aq, stop, toma, rec))[0]
    return W


def main():
    rutas = sorted(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*_20*.csv')))
    P = np.array([leer(r) for r in rutas], np.int64)
    todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
    S5 = np.array([v for *_, v in ventanas(250, empresas=EMPRESAS)], np.int64)
    S22 = np.array([v for *_, v in ventanas(500, empresas=todas)], np.int64)
    F = (170, 0, 29, 0x4F, 1, 225, 122)
    ref = {}
    for nom, S in (('5', S5), ('22', S22), ('P', P)):
        ref[nom] = (correr_ext(S, 255, 100, 0, 0x7F, 0), correr_ext(S, 220, 100, 0, 0x7F, 0), correr(S, *F))
    res = []
    for P0 in (160, 170, 180):
        for Y in (0, 190, 200, 210, 220, 230):
            for anc, aq, stop in ((29, 0x4F, 1), (29, 0x4F, 0), (20, 0x4F, 0), (29, 0x59, 0), (0, 0, 0)):
                for toma, rec in ((225, 122), (220, 122), (230, 122), (225, 115), (225, 130), (235, 125), (215, 120)):
                    prm = (P0, Y, anc, aq, stop, toma, rec)
                    fila = [prm]
                    for nom, S in (('5', S5), ('22', S22), ('P', P)):
                        w = correr(S, *prm)
                        r1, r2, wf = ref[nom]
                        fila += [min(neto(w, r1), neto(w, r2)), w.mean(), w.min(), neto(w, wf)]
                    pw = correr(P, *prm)
                    fila += [int((pw > ref['P'][2] + .5).sum()), int((pw < ref['P'][2] - .5).sum())]
                    res.append(fila)
    cab = '   P0   Y anc  q stop toma rec |   5: neto   prom   peor  vsF |  22: neto   prom   peor  vsF | practicas prom  vs F g/p'
    for titulo, clave in (('Mejores contra rivales en las 5 acciones', lambda r: -r[1]),
                          ('Mejores contra rivales en las 22', lambda r: -r[5]),
                          ('Mejores en las practicas (sin perder neto en las 5 vs la F)', lambda r: -r[10] if r[4] >= 0 else 0)):
        print(f'\n{titulo}:\n{cab}')
        for r in sorted(res, key=clave)[:8]:
            P0, Y, anc, aq, stop, toma, rec = r[0]
            print(f'  {P0} {Y:3d} {anc:3d} {aq & 63:2d}   {stop}  {toma} {rec} | {r[1]:+6.1%} {r[2]:6,.0f} {r[3]:6,.0f} {r[4]:+5.1%} |'
                  f' {r[5]:+6.1%} {r[6]:6,.0f} {r[7]:6,.0f} {r[8]:+5.1%} | {r[10]:8,.0f}  {r[13]}/{r[14]}')
    f0 = [r for r in res if r[0] == F][0]
    print(f'\nF actual: 5: {f0[1]:+.1%} prom {f0[2]:,.0f} | 22: {f0[5]:+.1%} prom {f0[6]:,.0f} | practicas {f0[10]:,.0f}')


if __name__ == '__main__':
    main()
