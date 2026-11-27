"""Compara el agente con las dos referencias del enunciado.

Cada serie de data/series (20 000 ticks) se evalua completa y cortada en rondas de
2000 ticks, que es el largo que usa el testbench del curso. Cada ronda parte con
$10.000. Referencias: no operar ($10.000) y comprar y mantener como lo calcula el
testbench (todo al primer precio, una orden).

Por serie y por ronda: patrimonio final, ordenes, comisiones, perdida maxima desde
un peak (en pesos, como el testbench) y fraccion del tiempo con acciones.
Escribe resultados/backtest.csv (rondas) y resultados/backtest_series.csv.

Uso:
  python ref/backtest.py                 todas las series de data/series
  python ref/backtest.py tb/practica.csv una serie (por ejemplo otra que publique el curso)
"""
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from mercado import CAJA0, caida_maxima, comprar_y_mantener, simular  # noqa: E402
from series import leer, rondas, todas  # noqa: E402
# Estudio del algoritmo ANTERIOR (tendencia) en series sin la normalizacion de la
# competencia; el algoritmo de la competencia se evalua en ref/competencia.py.
from trader import Tendencia as Trader  # noqa: E402

RES = os.path.join(os.path.dirname(__file__), '..', 'resultados')


def evaluar(precios):
    r = simular(precios, Trader())
    return {'ticks': len(precios), 'W': r['W'][-1], 'CyM': comprar_y_mantener(precios),
            'ordenes': r['ordenes'], 'comisiones': r['comisiones'],
            'perdida_max': caida_maxima(r['W']), 'exposicion': round(r['exposicion'], 3)}


def geo(valores):
    """Media geometrica de W / 10 000: el factor promedio por ronda."""
    return math.exp(sum(math.log(max(v, 1) / CAJA0) for v in valores) / len(valores))


def familia(nombre):
    base = 'practica' if nombre.startswith('practica') else 'alibaba'
    return base + ('_inv' if nombre.endswith('_inv') else '')


def main():
    if len(sys.argv) > 1:
        series = {os.path.splitext(os.path.basename(sys.argv[1]))[0]: leer(sys.argv[1])}
    else:
        series = todas()
    os.makedirs(RES, exist_ok=True)
    campos = ['serie', 'ronda', 'ticks', 'W', 'CyM', 'ordenes', 'comisiones', 'perdida_max', 'exposicion']
    filas_r, filas_s = [], []
    for nombre, precios in series.items():
        filas_s.append({'serie': nombre, 'ronda': 'completa', **evaluar(precios)})
        for k, r in enumerate(rondas(precios)):
            filas_r.append({'serie': nombre, 'ronda': k, **evaluar(r)})
    if len(sys.argv) == 1:
        for nombre_csv, filas in (('backtest.csv', filas_r), ('backtest_series.csv', filas_s)):
            with open(os.path.join(RES, nombre_csv), 'w', newline='') as fh:
                w = csv.DictWriter(fh, fieldnames=campos)
                w.writeheader()
                w.writerows(filas)

    print(f"{'serie':24s} {'W final':>9s} {'CyM':>8s} {'ordenes':>8s} {'perd. max':>9s} {'expo':>5s}")
    for f in filas_s:
        print(f"{f['serie']:24s} {f['W']:9d} {f['CyM']:8d} {f['ordenes']:8d} {f['perdida_max']:9d} {f['exposicion']:5.2f}")

    print(f"\n{'rondas de 2000 ticks':20s} {'n':>3s} {'agente':>7s} {'CyM':>6s} {'gana a CyM':>10s} {'gana a no operar':>16s} {'peor ronda':>10s}")
    fams = {}
    for f in filas_r:
        fams.setdefault(familia(f['serie']), []).append(f)
    for fam, fs in fams.items():
        print(f"{fam:20s} {len(fs):3d} {geo([f['W'] for f in fs]):7.3f} {geo([f['CyM'] for f in fs]):6.3f} "
              f"{sum(f['W'] > f['CyM'] for f in fs):6d}/{len(fs):<3d} {sum(f['W'] > CAJA0 for f in fs):12d}/{len(fs):<3d} "
              f"{min(f['W'] for f in fs):10d}")
    print('(agente y CyM: media geometrica de W / 10 000 por ronda)')


if __name__ == '__main__':
    main()
