"""Compara A, B, D y las mejores del optimizador del universo contra los rivales (22 acciones y las 5 de la competencia)."""
import os, sys
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(RAIZ, 'ref'))
import numpy as np
from optimizador import evaluar, vector, neto, geo
from minuto import DATOS, ventanas, EMPRESAS

todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
base = {'toma': 225, 'recompra': 120, 'familia': 1, 'x': 30, 'y': 2, 'q': 15, 'salida': 0, 's': 3, 'donde': 0}
cand = {
    'A ancla30 q15 rec120': base,
    'B sin ancla': dict(base, familia=0),
    'D ancla29 q15 rec122': dict(base, x=29, recompra=122),
    'E1 ancla22 q14 rec119': dict(base, x=22, q=14, recompra=119),
    'E2 ancla22 q14 rec120': dict(base, x=22, q=14, recompra=120),
    'E3 ancla24 q13 rec122': dict(base, x=24, q=13, recompra=122),
}
for nombre, emps, paso in (('UNIVERSO 22', todas, 500), ('COMPETENCIA 5', EMPRESAS, 250)):
    V = ventanas(paso, empresas=emps)
    S = np.array([v for *_, v in V], np.int64)
    r1 = evaluar(S, vector(dict(base, toma=255, recompra=100, familia=0)))
    r2 = evaluar(S, vector(dict(base, toma=220, recompra=100, familia=0)))
    W = {k: evaluar(S, vector(c)) for k, c in cand.items()}
    print(f'\n{nombre}: {len(S)} periodos')
    print(f'{"version":24s} prom$   geo    peor   P<0.95  neto100/255 neto220  netoVsD')
    for k, w in W.items():
        print(f'{k:24s} {w.mean()*1e4:6.0f} {geo(w):.4f} {w.min():.3f} {np.mean(w<0.95):.4f}  {neto(w,r1):+.3f}      {neto(w,r2):+.3f}   {neto(w,W["D ancla29 q15 rec122"]):+.3f}')
