"""Techo con vision perfecta: lo maximo que se podia sacar en cada serie con k operaciones (compra + venta),
todo el patrimonio en cada una. Ignora el redondeo a acciones enteras y cobra $5 por orden (2 por operacion).
Uso:  python ref/compras_perfectas.py serie1.csv serie2.csv ...
"""
import math
import os
import sys

import numpy as np


def leer(ruta):
    with open(ruta) as f:
        next(f)
        return [int(l.split(',')[1]) for l in f if l.strip()]


def mejor_k(p, k):
    """Maximo producto de k subidas no superpuestas (DP clasico de k transacciones en log)."""
    lp = [math.log(x) for x in p]
    comprado = [-1e18] * (k + 1)
    vendido = [0.0] * (k + 1)
    for x in lp:
        for j in range(1, k + 1):
            comprado[j] = max(comprado[j], vendido[j - 1] - x)
            vendido[j] = max(vendido[j], comprado[j] + x)
    return math.exp(max(vendido))


def main(rutas):
    ks = (1, 2, 3, 5, 10)
    filas = []
    print(f'{"serie":14s}' + ''.join(f'{f"{k} op.":>10s}' for k in ks) + f'{"ilimitadas":>14s}')
    for r in rutas:
        p = leer(r)
        nom = os.path.splitext(os.path.basename(r))[0].replace('practica_', '')
        w = [10000 * mejor_k(p, k) - 10 * k for k in ks]
        subidas = sum(max(0.0, math.log(b) - math.log(a)) for a, b in zip(p, p[1:]))
        ilim = 10000 * math.exp(subidas)
        filas.append(w)
        print(f'{nom:14s}' + ''.join(f'{x:10,.0f}' for x in w) + f'{ilim:14.2e}')
    W = np.array(filas)
    print(f'{"mediana":14s}' + ''.join(f'{x:10,.0f}' for x in np.median(W, axis=0)))
    print(f'{"promedio":14s}' + ''.join(f'{x:10,.0f}' for x in W.mean(axis=0)))


if __name__ == '__main__':
    main(sys.argv[1:])
