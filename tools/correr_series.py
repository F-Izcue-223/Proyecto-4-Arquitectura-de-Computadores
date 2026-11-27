"""Corre todas las versiones (A-E), los rivales y comprar y mantener sobre una o mas series CSV (tick,price).

Uso:  python tools/correr_series.py archivo1.csv archivo2.csv ...
"""
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(RAIZ, 'ref'))
sys.path.insert(0, os.path.join(RAIZ, 'tools'))
import numpy as np                                    # noqa: E402
from mercado import caida_maxima, comprar_y_mantener, simular   # noqa: E402
from trader import Extremos                           # noqa: E402
from versiones import VERSIONES, constantes           # noqa: E402


def leer(ruta):
    with open(ruta) as f:
        next(f)
        return [int(l.split(',')[1]) for l in f if l.strip()]


def main(rutas):
    est = {f'{v} {n}': constantes(v) for v, (n, _) in VERSIONES.items()}
    base = constantes('B')
    est['rival 100/255'] = dict(base, TOMA_GANANCIA=255, RECOMPRA=100)
    est['rival 100/255+220'] = dict(base, TOMA_GANANCIA=220, RECOMPRA=100)
    tabla = {k: [] for k in est}
    tabla['comprar y mantener'] = []
    nombres = []
    for r in rutas:
        p = leer(r)
        nom = os.path.splitext(os.path.basename(r))[0].replace('practica_', '')
        nombres.append(nom)
        i100 = next((i for i, x in enumerate(p) if x <= 100), None)
        i255 = next((i for i, x in enumerate(p) if x >= 255), None)
        orden = '100 primero' if (i100 or 0) < (i255 or 0) else '255 primero'
        print(f'\n{nom}: {len(p)} ticks, p0={p[0]}, min {min(p)} max {max(p)}, final {p[-1]} ({orden})')
        for k, c in est.items():
            s = simular(p, Extremos(c))
            tabla[k].append(s['W'][-1])
            print(f'  {k:28s} ${s["W"][-1]:>8,}  ordenes {s["ordenes"]:2d}  perdida max ${caida_maxima(s["W"]):,}'.replace(',', '.'))
        c = comprar_y_mantener(p)
        tabla['comprar y mantener'].append(c)
        print(f'  {"comprar y mantener":28s} ${c:>8,}'.replace(',', '.'))
    print('\nRESUMEN (patrimonio final por serie)')
    print(f'{"":28s}' + ''.join(f'{n[:11]:>12s}' for n in nombres) + f'{"promedio":>11s}{"mediana":>10s}')
    for k, v in tabla.items():
        print(f'{k:28s}' + ''.join(f'{x:12,}'.replace(',', '.') for x in v) +
              f'{np.mean(v):11,.0f}{np.median(v):10,.0f}'.replace(',', '.'))


if __name__ == '__main__':
    main(sys.argv[1:])
