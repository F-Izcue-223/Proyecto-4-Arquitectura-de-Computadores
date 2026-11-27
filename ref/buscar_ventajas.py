"""Busca ajustes del algoritmo que le ganen cara a cara a rivales con reglas parecidas.

En la competencia varios grupos tienen reglas casi iguales: la mayoria de las rondas
terminan en empate y gana quien saca ventaja en las pocas que difieren. Este script
prueba variantes de las cuatro constantes de sw/trade.s y las mide contra:
  - la version actual (las .equ de sw/trade.s),
  - rivales probables (100/255 puro, 100/255 con toma en 220; se agregan con --rival),
en las ventanas reales de la competencia (META, AAPL, NFLX, AMD, TSLA 2022-2024,
ref/minuto.py) y en los escenarios sinteticos de ref/montecarlo.py.

"Neto" contra un rival = % de rondas que le gano - % de rondas que me gana.

Una variante es VENTAJA ROBUSTA si cumple todo esto:
  1. neto > 0 contra la version actual y contra cada rival, en las ventanas reales;
  2. neto >= 0 contra la version actual en cada escenario del Montecarlo;
  3. su media geometrica real no baja mas de --tolerancia (0,3 % por defecto);
  4. su peor ventana real no es peor que la de la version actual.
Si aparece alguna, el script dice que .equ cambiar en sw/trade.s. Despues hay que
correr tools/simular.py, ref/verificar.py y grabar la placa (docs/simular-y-grabar.md).

Uso:
  python ref/buscar_ventajas.py                    rejilla alrededor de la version actual
  python ref/buscar_ventajas.py --rival 100,255,230,110 --rival 101,255,220,120
  python ref/buscar_ventajas.py --toma 200:250:5 --recompra 100:150:5 --compra 100:102:1 --venta 253:255:1
  python ref/buscar_ventajas.py --reglas todas     reglas de compra nuevas (ancla, medias, ruptura)
  python ref/buscar_ventajas.py --reglas ema,ruptura
  python ref/buscar_ventajas.py --rapido           menos ventanas y series (para probar)

Una regla nueva que salga robusta hay que escribirla tambien en sw/trade.s y en
ref/trader.py (clase Extremos); las familias estan descritas junto a FAMILIAS.
Escribe resultados/ventajas.csv.

Parametros de una variante: compra (piso inicial), venta (techo inicial), toma (techo
desde que aparece el MAXIMO) y recompra (piso desde que aparecieron MINIMO y MAXIMO).
El minimo y el maximo de la normalizacion (100 y 255) se leen de sw/trade.s.
"""
import argparse
import csv
import itertools
import os
import sys

import numba
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from minuto import EMPRESAS, ventanas  # noqa: E402
from montecarlo import escenarios, normalizar  # noqa: E402
from trader import PROGRAMAS, leer_equ  # noqa: E402

RES = os.path.join(AQUI, '..', 'resultados')


# Reglas extra de compra (familias). Actuan solo cuando no hay garantia: antes de ver
# ningun extremo (donde=0) o tambien en el tramo libre, fuera, despues de ver los dos (donde=1).
#   0 ninguna
#   1 ancla_p0:  dentro si p >= p0 + x; sale si p <= p0
#   2 ancla_min: dentro si p >= minimo visto + x; sale si cae y desde el maximo desde la entrada
#   3 ema:       medias exponenciales con alfa 1/2^x (rapida) y 1/2^y (lenta): dentro si rapida > lenta
#   4 ruptura:   dentro si p marca un nuevo maximo de la ronda (despues de x ticks); sale si cae y
FAMILIAS = {'ninguna': 0, 'ancla_p0': 1, 'ancla_min': 2, 'ema': 3, 'ruptura': 4}


@numba.njit(cache=True)
def patrimonio(pr, compra, venta, toma, recompra, minimo, maximo, regla=0, x=0, y=0, donde=0):
    """Patrimonio final con las reglas de la maestra (igual que competencia.maestra + extremos)."""
    caja, acc, dec = 10000, 0, 0
    dentro = vio_min = vio_max = False
    piso, techo = compra, venta
    extra = False
    mn, mx, pico = 1e9, 0.0, 0.0
    ef = es = float(pr[0])
    for n in range(len(pr)):
        p = pr[n]
        q = dec & 63
        if dec >> 6 == 1:
            q = min(q, (caja - 5) // p)
            if q > 0:
                caja -= q * p + 5
                acc += q
        elif dec >> 6 == 2:
            q = min(q, acc)
            if q > 0 and caja + q * p >= 5:
                caja += q * p - 5
                acc -= q
        if regla == 3:
            ef += (p - ef) / (1 << x)
            es += (p - es) / (1 << y)
        nuevo_max = p > mx
        mn = min(mn, p)
        mx = max(mx, p)
        garantia = False
        if p <= piso:
            dentro = True
            garantia = True
            extra = False
            if p <= minimo:
                vio_min = True
        elif p >= techo:
            dentro = False
            garantia = True
            extra = False
            if p >= maximo:
                vio_max = True
                techo = toma
        if vio_min and vio_max:
            piso = recompra
        libre = (not vio_min and not vio_max) or (donde == 1 and vio_min and vio_max)
        if regla > 0 and not garantia and libre and (extra or not dentro):
            if regla == 1:
                quiero = p >= pr[0] + x if not extra else p > pr[0]
            elif regla == 2:
                if extra:
                    pico = max(pico, p)
                    quiero = p > pico - y
                else:
                    quiero = p >= mn + x
                    pico = p
            elif regla == 3:
                quiero = ef > es
            else:
                if extra:
                    pico = max(pico, p)
                    quiero = p > pico - y
                else:
                    quiero = nuevo_max and n >= x
                    pico = p
            if quiero and not dentro:
                dentro = True
                extra = True
            elif not quiero and extra:
                dentro = False
                extra = False
        dec = 0x7F if dentro else 0xBF
    return caja + acc * pr[-1]


@numba.njit(parallel=True, cache=True)
def evaluar(series, largos, prm, minimo, maximo):
    """series: matriz (n, 20000); prm: (k, 8) = compra, venta, toma, recompra, regla, x, y, donde.
    Devuelve W (k, n) / 10 000."""
    k, n = prm.shape[0], series.shape[0]
    out = np.empty((k, n))
    for i in numba.prange(k * n):
        a, b = i // n, i % n
        out[a, b] = patrimonio(series[b, :largos[b]], prm[a, 0], prm[a, 1], prm[a, 2], prm[a, 3],
                               minimo, maximo, prm[a, 4], prm[a, 5], prm[a, 6], prm[a, 7]) / 10000.0
    return out


def rejilla_regla(nombre):
    """Variantes de cada familia: (regla, x, y, donde)."""
    r = FAMILIAS[nombre]
    if r == 1:
        xy = [(x, 0) for x in (5, 10, 15, 20, 30)]
    elif r == 2:
        xy = [(x, y) for x in (10, 20, 30, 40) for y in (10, 20, 30)]
    elif r == 3:
        xy = [(x, y) for x in (4, 6, 8) for y in (8, 10, 12) if y > x]
    elif r == 4:
        xy = [(x, y) for x in (200, 1000, 3000) for y in (10, 20, 40)]
    else:
        return [(0, 0, 0, 0)]
    return [(r, x, y, d) for x, y in xy for d in (0, 1)]


def neto(w, r):
    return float(np.mean(w > r + 1e-9) - np.mean(w < r - 1e-9))


def rango(txt):
    a, b, s = (int(x) for x in txt.split(':'))
    return list(range(a, b + 1, s))


def main():
    e = leer_equ(PROGRAMAS['extremos'])
    actual = (e['MINIMO'], e['MAXIMO'], e['TOMA_GANANCIA'], e['RECOMPRA'])
    regla_actual = (1, e['ANCLA'], 0, 0) if e.get('ANCLA', 0) else (0, 0, 0, 0)
    t, r = e['TOMA_GANANCIA'], e['RECOMPRA']
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--toma', default=f'{t - 15}:{t + 15}:5')
    ap.add_argument('--recompra', default=f'{max(e["MINIMO"], r - 15)}:{r + 20}:5')
    ap.add_argument('--compra', default=f'{e["MINIMO"]}:{e["MINIMO"] + 1}:1')
    ap.add_argument('--venta', default=f'{e["MAXIMO"] - 1}:{e["MAXIMO"]}:1')
    ap.add_argument('--rival', action='append', default=[], help='compra,venta,toma,recompra')
    ap.add_argument('--tolerancia', type=float, default=0.003)
    ap.add_argument('--reglas', default='ninguna',
                    help='familias de reglas extra a probar, separadas por coma: ' + ', '.join(FAMILIAS) +
                         ' (con "todas" prueba todas, sobre las constantes actuales)')
    ap.add_argument('--rapido', action='store_true')
    a = ap.parse_args()

    rivales = {'100/255': (100, 255, 255, 100), '100/255+220': (100, 255, 220, 100)}
    for x in a.rival:
        rivales[f'rival {x}'] = tuple(int(v) for v in x.split(','))

    paso = 1000 if a.rapido else 250
    reales = [s for *_, s in ventanas(paso)]
    emp = np.array([k for k, _, _ in ventanas(paso)])
    mc = list(escenarios(100 if a.rapido else 300))
    print(f'{len(reales)} ventanas reales; Montecarlo: {len(mc)} escenarios x {len(mc[0][1])} series')

    fams = list(FAMILIAS) if a.reglas == 'todas' else a.reglas.split(',')
    if fams == ['ninguna']:
        cand = sorted(set(itertools.product(rango(a.compra), rango(a.venta), rango(a.toma), rango(a.recompra))))
        cand = [c + regla_actual for c in cand]
    else:
        cand = [actual + rg for f in fams for rg in rejilla_regla(f)]
    nada = (0, 0, 0, 0)
    yo = actual + regla_actual
    todos = [yo] + [r + nada for r in rivales.values()] + [c for c in cand if c != yo]
    prm = np.array(todos, np.int64)
    mini, maxi = e['MINIMO'], e['MAXIMO']

    R = np.array(reales, np.int64)
    Wr = evaluar(R, np.full(len(R), R.shape[1]), prm, mini, maxi)
    Wmc = []
    for nombre, xs in mc:
        S = np.array([normalizar(x) for x in xs], np.int64)
        Wmc.append((nombre, evaluar(S, np.full(len(S), S.shape[1]), prm, mini, maxi)))
    nr = 1 + len(rivales)

    def geo(w):
        return float(np.exp(np.log(w).mean()))

    base = Wr[0]
    filas = []
    filas_por_indice = {}
    for i, p in enumerate(todos):
        if 0 < i < nr:
            continue
        w = Wr[i]
        nom = [k for k, v in FAMILIAS.items() if v == p[4]][0]
        detalle = f'({p[5]},{p[6]},' + ('tambien libre' if p[7] else 'solo inicio') + ')' if p[4] else ''
        f = {'compra': p[0], 'venta': p[1], 'toma': p[2], 'recompra': p[3], 'regla': nom + detalle,
             'geo_real': geo(w),
             'peor_real': float(w.min()), 'pierde_real': float(np.mean(w < 1)),
             'neto_vs_actual': neto(w, base),
             'peor_empresa_vs_actual': min(geo(w[emp == k]) / geo(base[emp == k]) for k in EMPRESAS)}
        for j, nombre in enumerate(rivales, 1):
            f[f'neto_vs_{nombre}'] = neto(w, Wr[j])
        f['mc_min_neto_vs_actual'] = min(neto(W[i], W[0]) for _, W in Wmc)
        f['mc_min_neto_vs_rivales'] = min(neto(W[i], W[j]) for _, W in Wmc for j in range(1, nr))
        f['mc_geo_medio'] = float(np.mean([geo(W[i]) for _, W in Wmc]))
        f['robusta'] = (i > 0 and f['neto_vs_actual'] > 0
                        and all(f[f'neto_vs_{k}'] > 0 for k in rivales)
                        and f['mc_min_neto_vs_actual'] >= 0
                        and f['geo_real'] >= geo(base) * (1 - a.tolerancia)
                        and f['peor_real'] >= float(base.min()) - 1e-9)
        filas.append(f)
        filas_por_indice[i] = f

    filas.sort(key=lambda f: (f['robusta'], f['neto_vs_actual'] + min(f[f'neto_vs_{k}'] for k in rivales)), reverse=True)
    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, 'ventajas.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0]))
        w.writeheader()
        for f in filas:
            w.writerow({k: (f'{v:.4f}' if isinstance(v, float) else v) for k, v in f.items()})

    act = filas_por_indice[0]
    print(f"\nversion actual {actual}: geo real {act['geo_real']:.4f}, peor {act['peor_real']:.3f}; " +
          ', '.join(f"neto vs {k} {act[f'neto_vs_{k}']:+.3f}" for k in rivales))
    print(f"\n{'compra,venta,toma,recompra + regla':50s} {'robusta':8s} {'geo':>6s} {'peor':>6s} {'vs actual':>9s} " +
          ' '.join(f'{("vs " + k)[:14]:>14s}' for k in rivales) + '  MC min vs actual  MC min vs rivales')
    for f in filas[:15]:
        print(f"{str((f['compra'], f['venta'], f['toma'], f['recompra'])) + ' ' + f['regla']:50s} {'SI' if f['robusta'] else 'no':8s} "
              f"{f['geo_real']:6.4f} {f['peor_real']:6.3f} {f['neto_vs_actual']:+9.3f} " +
              ' '.join(f"{f[f'neto_vs_{k}']:+14.3f}" for k in rivales) +
              f"  {f['mc_min_neto_vs_actual']:+16.3f}  {f['mc_min_neto_vs_rivales']:+17.3f}")
    mejor = next((f for f in filas if f['robusta']), None)
    if mejor:
        print(f"\nVENTAJA ROBUSTA: regla {mejor['regla']}; en sw/trade.s TOMA_GANANCIA = {mejor['toma']}, RECOMPRA = {mejor['recompra']}"
              + (f", piso inicial {mejor['compra']}" if mejor['compra'] != actual[0] else '')
              + (f", techo inicial {mejor['venta']}" if mejor['venta'] != actual[1] else '')
              + '.\nDespues: tools/simular.py, ref/verificar.py y grabar (docs/simular-y-grabar.md).')
    else:
        print('\nNinguna variante cumple las cuatro condiciones: la version actual queda.')
    print('Tabla completa en resultados/ventajas.csv')


if __name__ == '__main__':
    main()
