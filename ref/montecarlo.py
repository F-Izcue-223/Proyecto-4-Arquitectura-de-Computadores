"""Montecarlo: el algoritmo final en series sinteticas normalizadas como la competencia.

ref/competencia.py usa ventanas reales de 5 acciones (2022-2024). Aqui se generan
series de 20 000 minutos con distintos comportamientos, se llevan a [100, 255] igual
que tb/practica_meta.csv (minimo -> 100, maximo -> 255, redondeado) y se corre el
agente con las reglas de la maestra. Sirve para ver si el resultado depende de esas
5 acciones o se sostiene en cualquier serie con esa normalizacion, y si los dos
parametros ajustados (TOMA_GANANCIA, RECOMPRA) ayudan fuera de los datos
con que se eligieron.

Escenarios (retornos logaritmicos por minuto):
  paseo         paseo aleatorio sin tendencia (sigma 0,1 %)
  sube / baja   con tendencia: +40 % / -30 % en la ventana
  volatil       sigma 0,3 %
  reversion     el precio vuelve a una media (Ornstein-Uhlenbeck en el logaritmo)
  momentum      cada retorno arrastra el 10 % del anterior
  saltos        paseo con saltos de +-3 % (1 cada 2000 minutos en promedio)
  bootstrap     dias completos (390 minutos) de las 5 acciones reales, en orden al azar
                (necesita data/minuto; conserva la volatilidad intradia real)

Variantes del agente: solo 100/255, con toma de ganancia 220, y la final (constantes de sw/trade.s).

Uso:  python ref/montecarlo.py [N]       (N series por escenario, 1000 por defecto)
Escribe resultados/montecarlo.csv.
"""
import csv
import os
import sys

import numba
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from competencia import cym, extremos, maestra  # noqa: E402
from minuto import DATOS, EMPRESAS, cargar  # noqa: E402

LARGO = 20000
RES = os.path.join(AQUI, '..', 'resultados')
from trader import PROGRAMAS, leer_equ  # noqa: E402
_e = leer_equ(PROGRAMAS['extremos'])
sys.path.insert(0, os.path.join(AQUI, '..', 'tools'))
from versiones import constantes  # noqa: E402


def _prm(c):
    return (c['MINIMO'], c['MAXIMO'], c['TOMA_GANANCIA'], c['RECOMPRA'], c.get('ANCLA', 0), c.get('ANCLA_ORDEN', 0x7F),
            c.get('ANCLA_P0', 0), c.get('TODO_P0', 0), c.get('TODO_Y', 0))


VARIANTES = {'100/255': (100, 255, 255, 100), '+ toma 220': (100, 255, 220, 100),
             'version D': _prm(constantes('D')), 'version F': _prm(constantes('F')),
             'version G': _prm(constantes('G'))}


@numba.njit(cache=True)
def generar(tipo, semilla, sigma, deriva, kappa, rho, salto):
    np.random.seed(semilla)
    x = np.empty(LARGO)
    lx, r_ant = 0.0, 0.0
    for n in range(LARGO):
        r = deriva + sigma * np.random.randn()
        if tipo == 1:                                   # reversion a la media (OU)
            r -= kappa * lx
        elif tipo == 2:                                 # momentum
            r += rho * r_ant
        elif tipo == 3 and np.random.rand() < 1 / 2000:  # saltos
            r += salto if np.random.rand() < 0.5 else -salto
        lx += r
        r_ant = r
        x[n] = np.exp(lx)
    return x


def normalizar(x):
    return np.round(100 + (x - x.min()) / (x.max() - x.min()) * 155).astype(np.int64)


def bootstrap(n, rng):
    """Dias completos de retornos reales (de las 5 acciones), en orden al azar."""
    dias = []
    for k in EMPRESAS:
        _, c = cargar(k)
        r = np.diff(np.log(c))
        dias += [r[i:i + 390] for i in range(0, len(r) - 390, 390)]
    out = []
    for _ in range(n):
        idx = rng.integers(0, len(dias), LARGO // 390 + 1)
        r = np.concatenate([dias[i] for i in idx])[:LARGO]
        out.append(np.exp(np.cumsum(r)))
    return out


def escenarios(n):
    s = 0.001
    sint = {'paseo': (0, s, 0.0, 0, 0, 0), 'sube': (0, s, np.log(1.4) / LARGO, 0, 0, 0),
            'baja': (0, s, np.log(0.7) / LARGO, 0, 0, 0), 'volatil': (0, 3 * s, 0.0, 0, 0, 0),
            'reversion': (1, s, 0.0, 1 / 3000, 0, 0), 'momentum': (2, s, 0.0, 0, 0.1, 0),
            'saltos': (3, s, 0.0, 0, 0, 0.03)}
    for i, (nombre, (tipo, sig, der, kap, rho, sal)) in enumerate(sint.items()):
        yield nombre, [generar(tipo, 1000 * i + k, sig, der, kap, rho, sal) for k in range(n)]
    if os.path.isdir(DATOS):
        yield 'bootstrap', bootstrap(n, np.random.default_rng(7))


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    filas = []
    print(f"{'escenario':10s} {'variante':18s} {'geo':>6s} {'mediana':>7s} {'p5':>6s} {'peor':>6s} "
          f"{'pierde':>6s} {'ordenes':>7s} {'expo':>5s} | CyM geo, pierde")
    for nombre, xs in escenarios(n):
        S = [normalizar(x) for x in xs]
        c = np.array([cym(s) for s in S]) / 1e4
        for v, prm in VARIANTES.items():
            r = np.array([maestra(s, extremos(s, *prm)) for s in S])
            w = r[:, 0] / 1e4
            if v == '100/255':
                w_rival = w
            f = {'escenario': nombre, 'variante': v, 'n': len(S), 'geo': np.exp(np.log(w).mean()),
                 'neto_vs_100_255': float(np.mean(w > w_rival + 5e-5) - np.mean(w < w_rival - 5e-5)),
                 'mediana': np.median(w), 'p5': np.percentile(w, 5), 'peor': w.min(),
                 'P_pierde': np.mean(w < 1), 'ordenes': r[:, 2].mean(), 'exposicion': r[:, 3].mean(),
                 'CyM_geo': np.exp(np.log(c).mean()), 'CyM_pierde': np.mean(c < 1)}
            filas.append(f)
            print(f"{nombre:10s} {v:18s} {f['geo']:6.3f} {f['mediana']:7.3f} {f['p5']:6.3f} {f['peor']:6.3f} "
                  f"{f['P_pierde']:6.3f} {f['ordenes']:7.1f} {f['exposicion']:5.2f} | {f['CyM_geo']:.3f}, {f['CyM_pierde']:.2f}"
                  f" | neto vs 100/255 {f['neto_vs_100_255']:+.1%}")
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, 'montecarlo.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        for f in filas:
            w.writerow({k: (f'{v:.4f}' if isinstance(v, float) else v) for k, v in f.items()})


if __name__ == '__main__':
    main()
