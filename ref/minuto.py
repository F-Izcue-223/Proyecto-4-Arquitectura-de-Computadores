"""Ventanas de la competencia reconstruidas desde barras de 1 minuto reales.

tb/practica_meta.csv es exactamente esto (comprobado tick a tick, 20000 de 20000):
cierre de META en horario regular (9:30-16:00 hora de Nueva York) desde el
23-feb-2022 15:20 hasta el 9-may-2022 10:39, llevado linealmente a [100, 255]
(minimo de la ventana -> 100, maximo -> 255) y redondeado.

La competencia usa "periodos ocultos de Meta, Apple, Netflix, AMD o Tesla
(2022-2024) con la misma normalizacion", asi que cada inicio posible de una
ventana de 20000 minutos de esas cinco acciones es una serie que podria tocar.

Datos: data/minuto/<TICKER>.csv (hora,close), sacados del dataset
CryptoSpartan/stocks_bars_1m de Hugging Face (barras de Alpaca). No van al repo.

Uso:
  python ref/minuto.py           comprueba que se reconstruye tb/practica_meta.csv
"""
import os

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
DATOS = os.path.join(AQUI, '..', 'data', 'minuto')
EMPRESAS = ('META', 'AAPL', 'NFLX', 'AMD', 'TSLA')
LARGO = 20000

_cache = {}


def cargar(ticker):
    """Horas (texto) y cierres (float) de una accion, en orden."""
    if ticker not in _cache:
        horas, cierre = [], []
        with open(os.path.join(DATOS, ticker + '.csv')) as f:
            next(f)
            for linea in f:
                h, c = linea.rstrip().split(',')
                horas.append(h)
                cierre.append(float(c))
        _cache[ticker] = (horas, np.array(cierre))
    return _cache[ticker]


def normalizar(x):
    """Igual que el profesor: minimo -> 100, maximo -> 255, redondeado."""
    return np.round(100 + (x - x.min()) / (x.max() - x.min()) * 155).astype(np.int64)


def ventanas(paso, largo=LARGO, empresas=EMPRESAS, anios=None):
    """Lista de (ticker, hora_inicio, serie) cada `paso` minutos.

    anios: si se da, solo ventanas que empiezan en esos anios (para separar
    afinar / probar, por ejemplo afinar con 2022-2023 y probar con 2024).
    """
    out = []
    for k in empresas:
        horas, x = cargar(k)
        for s in range(0, len(x) - largo + 1, paso):
            if anios and int(horas[s][:4]) not in anios:
                continue
            out.append((k, horas[s], normalizar(x[s:s + largo])))
    return out


def main():
    horas, x = cargar('META')
    s = horas.index('2022-02-23 15:20:00-05:00')
    w = normalizar(x[s:s + LARGO])
    with open(os.path.join(AQUI, '..', 'tb', 'practica_meta.csv')) as f:
        next(f)
        pm = np.array([int(l.split(',')[1]) for l in f])
    iguales = int((w == pm).sum())
    print(f'practica_meta reconstruida: {iguales}/{LARGO} ticks iguales '
          f'({horas[s]} a {horas[s + LARGO - 1]})')
    for k in EMPRESAS:
        h, c = cargar(k)
        print(f'{k:5s} {len(c):7d} minutos  {h[0][:10]} a {h[-1][:10]}  '
              f'{len(c) - LARGO + 1} ventanas posibles')


if __name__ == '__main__':
    main()
