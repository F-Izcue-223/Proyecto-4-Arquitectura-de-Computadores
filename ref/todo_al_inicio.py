"""'Comprar todo al primer precio y esperar el 255': lo que saca en las 8 practicas vs en las 22 empresas."""
import glob
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import numpy as np                            # noqa: E402
from casos_f import correr                    # noqa: E402
from esperar_255 import correr_ext            # noqa: E402
from minuto import DATOS, ventanas            # noqa: E402
from mejorar_practicas import leer, neto, orden   # noqa: E402

T = (101, 0, 0, 0, 0, 225, 122)      # todo al inicio
G = (180, 240, 0, 0, 0, 225, 122)
rutas = sorted(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*_20*.csv')))
P = np.array([leer(r) for r in rutas], np.int64)
pt, pg, pr = correr(P, *T), correr(P, *G), correr_ext(P, 255, 100, 0, 0x7F, 0)
print('Practicas:            todo al inicio        G     rival   p0  primero')
for r, s, a, b, c in zip(rutas, P, pt, pg, pr):
    o = '255' if np.argmax(s >= 255) < np.argmax(s <= 100) else '100'
    print(f'  {os.path.basename(r)[9:-4]:14s} {a:12,.0f} {b:10,.0f} {c:9,.0f}  {s[0]:3d}  el {o}')
print(f'  {"promedio":14s} {pt.mean():12,.0f} {pg.mean():10,.0f} {pr.mean():9,.0f}')
todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
S = np.array([v for *_, v in ventanas(500, empresas=todas)], np.int64)
o = orden(S)
wt, wg, wr = correr(S, *T), correr(S, *G), correr_ext(S, 255, 100, 0, 0x7F, 0)
print(f'\n22 empresas ({len(S)} rondas):')
for nom, m in (('todas', np.ones(len(S), bool)), ('primero el 255', o == 2), ('primero el 100', o == 1)):
    print(f'  {nom:15s} ({m.mean():4.0%}): todo al inicio prom ${wt[m].mean():,.0f} (>= $26.000 en {np.mean(wt[m] >= 26000):.0%})'
          f' | G ${wg[m].mean():,.0f} | rival ${wr[m].mean():,.0f} | todo al inicio vs G neto {neto(wt[m], wg[m]):+.0%}')
