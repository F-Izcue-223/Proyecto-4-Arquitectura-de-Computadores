"""Valida el agente con las acciones tecnologicas descargadas por ref/descargar.py.

Estos datos no se usaron para elegir ningun parametro. Cada serie se escala como en
ref/series.py (precio * 130 / media, redondeado, entre 1 y 255) y se corre completa
con las reglas de la maestra. Por serie informa:
  W        patrimonio final del agente
  CyM      comprar y mantener (como el testbench: todo al primer precio)
  razon    W / CyM
  expo     fraccion de los ticks con acciones
ademas de ordenes y perdida maxima. Tambien corta cada serie en rondas de 2000 ticks.
Escribe resultados/validacion_tec.csv.

Uso:  python ref/validar.py
"""
import csv
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from mercado import CAJA0, caida_maxima, comprar_y_mantener, simular  # noqa: E402
from series import escalar, rondas  # noqa: E402
# Estudio del algoritmo ANTERIOR (tendencia) en series sin la normalizacion de la
# competencia; el algoritmo de la competencia se evalua en ref/competencia.py.
from trader import Tendencia as Trader  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), '..')
YAHOO = os.path.join(RAIZ, 'data', 'yahoo')


def cargar():
    """{(ticker, intervalo): precios escalados}"""
    out = {}
    for n in sorted(os.listdir(YAHOO)):
        with open(os.path.join(YAHOO, n)) as f:
            cierres = [float(r['close']) for r in csv.DictReader(f)]
        ticker, intervalo = n[:-4].split('_')
        out[(ticker, intervalo)] = escalar(cierres)
    return out


def geo(v):
    return math.exp(sum(math.log(max(x, 1e-9)) for x in v) / len(v))


def evaluar(p):
    r = simular(p, Trader())
    cym = comprar_y_mantener(p)
    return {'ticks': len(p), 'p_ini': p[0], 'p_fin': p[-1], 'W': r['W'][-1], 'CyM': cym,
            'razon': round(r['W'][-1] / cym, 3), 'expo': round(r['exposicion'], 3),
            'ordenes': r['ordenes'], 'perdida_max': caida_maxima(r['W'])}


def resumen(titulo, filas):
    w = [f['W'] / CAJA0 for f in filas]
    c = [f['CyM'] / CAJA0 for f in filas]
    print(f"{titulo:34s} n={len(filas):3d}  agente {geo(w):.3f}  CyM {geo(c):.3f}  razon {geo(w) / geo(c):.3f}  "
          f"gana a CyM {sum(a > b for a, b in zip(w, c)):3d}/{len(filas):<3d} gana a no operar {sum(a > 1 for a in w):3d}/{len(filas):<3d} "
          f"expo {np.mean([f['expo'] for f in filas]):.2f}  peor {min(w):.3f}")


def main():
    series = cargar()
    campos = ['serie', 'intervalo', 'ronda', 'ticks', 'p_ini', 'p_fin', 'W', 'CyM', 'razon', 'expo', 'ordenes', 'perdida_max']
    completas, por_ronda = [], []
    for (ticker, intervalo), p in series.items():
        completas.append({'serie': ticker, 'intervalo': intervalo, 'ronda': 'completa', **evaluar(p)})
        for k, r in enumerate(rondas(p)):
            por_ronda.append({'serie': ticker, 'intervalo': intervalo, 'ronda': k, **evaluar(r)})
    with open(os.path.join(RAIZ, 'resultados', 'validacion_tec.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(completas + por_ronda)

    print(f"{'serie':6s} {'int':3s} {'ticks':>5s} {'precio':>9s} {'W':>7s} {'CyM':>7s} {'razon':>6s} {'expo':>5s} {'ord':>4s} {'perd.max':>8s}")
    for f in completas:
        print(f"{f['serie']:6s} {f['intervalo']:3s} {f['ticks']:5d} {f['p_ini']:4d}->{f['p_fin']:<4d} {f['W']:7d} {f['CyM']:7d} "
              f"{f['razon']:6.3f} {f['expo']:5.2f} {f['ordenes']:4d} {f['perdida_max']:8d}")
    print('\nMedia geometrica de patrimonio / 10 000 (razon = agente / CyM):')
    for intervalo in ('5m', '1h'):
        resumen(f'series completas {intervalo}', [f for f in completas if f['intervalo'] == intervalo])
    for intervalo in ('5m', '1h'):
        resumen(f'rondas de 2000 ticks {intervalo}', [f for f in por_ronda if f['intervalo'] == intervalo])
    todo = completas + por_ronda
    resumen('todo, CyM sube mas de 8 %', [f for f in todo if f['CyM'] > 1.08 * CAJA0])
    resumen('todo, CyM entre -8 % y +8 %', [f for f in todo if 0.92 * CAJA0 <= f['CyM'] <= 1.08 * CAJA0])
    resumen('todo, CyM baja mas de 8 %', [f for f in todo if f['CyM'] < 0.92 * CAJA0])


if __name__ == '__main__':
    main()
