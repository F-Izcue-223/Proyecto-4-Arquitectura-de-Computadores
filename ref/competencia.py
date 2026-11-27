"""Ganancia y riesgo en las series que puede tocar en la competencia.

La competencia usa periodos ocultos de META, AAPL, NFLX, AMD o TSLA (2022-2024),
20 000 minutos de mercado normalizados a [100, 255] como tb/practica_meta.csv.
ref/minuto.py arma esas ventanas desde las barras de 1 minuto reales; aqui se toma
una ventana cada PASO minutos de cada empresa (las ventanas se traslapan: dos
inicios cercanos dan series parecidas) y se corren los dos algoritmos:

  extremos   sw/trade.s (el de la competencia)
  tendencia  sw/trade_tendencia.s (el anterior)

con las reglas de la maestra (tb/tb_proyecto_4.sv), contra comprar y mantener (como
lo calcula el testbench) y no operar ($10 000). Dos largos de ronda, porque no se
sabe cual usara la maestra: la serie completa (20 000 ticks) y los primeros 2000
(lo que corre el testbench por defecto).

Riesgo de mercado: probabilidad de terminar bajo $10 000, percentiles bajos de W y
perdida maxima desde un peak (en pesos, como el testbench).

El lazo esta repetido con numba (55 millones de ticks por algoritmo y largo); antes
se comprueba que de las mismas decisiones que ref/trader.py en varias ventanas.

Uso:  python ref/competencia.py [PASO]      (por defecto 500 minutos)
Escribe resultados/competencia.csv (resumen), resultados/competencia_ventanas.csv y
resultados/nivel_retorno.csv (retorno hasta el final segun el nivel del precio).
"""
import csv
import os
import sys

import numba
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from barrido import correr as correr_tendencia  # noqa: E402
from mercado import simular  # noqa: E402
from minuto import EMPRESAS, ventanas  # noqa: E402
from trader import PROGRAMAS, Extremos, leer_equ  # noqa: E402

RES = os.path.join(AQUI, '..', 'resultados')


@numba.njit(cache=True)
def maestra(pr, decs):
    """Patrimonio final, perdida maxima, ordenes y fraccion del tiempo con acciones.
    decs[n] es la decision tomada con el precio n; se ejecuta al precio n+1."""
    caja, acc, dec, peak, mdd, nord, dentro = 10000, 0, 0, 10000, 0, 0, 0
    for n in range(len(pr)):
        p = pr[n]
        q = dec & 63
        if dec >> 6 == 1:
            q = min(q, (caja - 5) // p)
            if q > 0:
                caja -= q * p + 5; acc += q; nord += 1
        elif dec >> 6 == 2:
            q = min(q, acc)
            if q > 0 and caja + q * p >= 5:
                caja += q * p - 5; acc -= q; nord += 1
        w = caja + acc * p
        peak = max(peak, w); mdd = max(mdd, peak - w)
        dentro += acc > 0
        dec = decs[n]
    return caja + acc * pr[-1], mdd, nord, dentro / len(pr)


@numba.njit(cache=True)
def extremos(pr, bajo, alto, toma, recompra, ancla=0, ancla_orden=0x7F, ancla_p0=0, todo_p0=0, todo_y=0):
    decs = np.empty(len(pr), np.int64)
    vio_min = vio_max = False
    piso, techo = bajo, alto
    dec = 0xBF
    for n in range(len(pr)):
        salida = -1
        if pr[n] <= piso:
            dec = 0x7F
            if pr[n] <= bajo:
                vio_min = True
        elif pr[n] >= techo:
            dec = 0xBF
            if pr[n] >= alto:
                vio_max = True
                techo = toma
        elif not vio_min and not vio_max and ((todo_p0 > 0 and pr[0] >= todo_p0) or (todo_y > 0 and pr[n] >= todo_y)):
            dec = 0x7F
        elif ancla > 0 and not vio_min and not vio_max and pr[0] >= ancla_p0:
            if pr[n] >= pr[0] + ancla:
                if dec == 0xBF:
                    salida = ancla_orden
                    dec = 0
            elif pr[n] <= pr[0]:
                dec = 0xBF
        if vio_min and vio_max:
            piso = recompra
        decs[n] = dec if salida < 0 else salida
    return decs


def cym(pr):
    q = (10000 - 5) // int(pr[0])
    return 10000 - 5 - q * int(pr[0]) + q * int(pr[-1])


def resumen(W, C, D, O, X):
    w = W / 1e4
    return {'n': len(w), 'geo': np.exp(np.log(w).mean()), 'mediana': np.median(w),
            'p1': np.percentile(w, 1), 'p5': np.percentile(w, 5), 'p95': np.percentile(w, 95),
            'min': w.min(), 'max': w.max(), 'P_pierde': np.mean(w < 1), 'P_gana_CyM': np.mean(W > C),
            'DD_mediana': np.median(D), 'DD_p95': np.percentile(D, 95), 'ordenes_mediana': np.median(O),
            'exposicion': X.mean()}


def main():
    paso = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    e = leer_equ(PROGRAMAS['extremos'])
    bajo, alto, toma, recompra = e['MINIMO'], e['MAXIMO'], e['TOMA_GANANCIA'], e['RECOMPRA']
    ancla = e.get('ANCLA', 0)
    ancla_orden = e.get('ANCLA_ORDEN', 0x7F)
    t = leer_equ(PROGRAMAS['tendencia'])
    pt = (t['A_ENTRA'], t['A_SALE'], t['C_SUBE'], t['C_BAJA'], t['B_EXCESO'])

    V = ventanas(paso)
    # mismas decisiones que trader.py
    for _, _, s in V[::max(1, len(V) // 8)]:
        assert list(extremos(s, bajo, alto, toma, recompra, ancla, ancla_orden)) == simular([int(x) for x in s], Extremos())['decisiones']
    print(f'{len(V)} ventanas de 20 000 minutos (una cada {paso}); extremos == trader.py: SI')

    filas, por_ventana = [], []
    for largo in (20000, 2000):
        r = {'extremos': [], 'tendencia': []}
        C = []
        for k, hora, s in V:
            s = s[:largo]
            r['extremos'].append(maestra(s, extremos(s, bajo, alto, toma, recompra, ancla, ancla_orden)))
            r['tendencia'].append(maestra(s, correr_tendencia(s, *pt)[1]))
            C.append(cym(s))
        C = np.array(C)
        emp = np.array([k for k, _, _ in V])
        anio = np.array([h[:4] for _, h, _ in V])
        grupos = [('todas', np.ones(len(V), bool))] + [(k, emp == k) for k in EMPRESAS] + \
                 [(a, anio == a) for a in ('2022', '2023', '2024')]
        for algo, res in r.items():
            res = np.array(res)
            for g, m in grupos:
                filas.append({'algoritmo': algo, 'ticks': largo, 'grupo': g,
                              **resumen(res[m, 0], C[m], res[m, 1], res[m, 2], res[m, 3])})
        cy = C / 1e4
        for g, m in grupos:
            filas.append({'algoritmo': 'CyM', 'ticks': largo, 'grupo': g, 'n': int(m.sum()),
                          'geo': np.exp(np.log(cy[m]).mean()), 'mediana': np.median(cy[m]),
                          'p1': np.percentile(cy[m], 1), 'p5': np.percentile(cy[m], 5),
                          'p95': np.percentile(cy[m], 95), 'min': cy[m].min(), 'max': cy[m].max(),
                          'P_pierde': np.mean(cy[m] < 1)})
        for i, (k, hora, s) in enumerate(V):
            if largo == 20000:
                por_ventana.append({'empresa': k, 'inicio': hora, 'tick_min': int(np.argmin(s)),
                                    'tick_max': int(np.argmax(s))})
            por_ventana[i][f'W_extremos_{largo}'] = int(r['extremos'][i][0])
            por_ventana[i][f'W_tendencia_{largo}'] = int(r['tendencia'][i][0])
            por_ventana[i][f'CyM_{largo}'] = int(C[i])

    # Por que funciona: retorno promedio desde cada tick hasta el final de la ventana,
    # segun el nivel del precio en ese tick (tramos de 10)
    suma, cuenta = np.zeros(16), np.zeros(16)
    for _, _, s in V:
        x = s.astype(float)
        b = np.minimum((s - 100) // 10, 15)
        np.add.at(suma, b, np.log(x[-1] / x))
        np.add.at(cuenta, b, 1)

    os.makedirs(RES, exist_ok=True)
    with open(os.path.join(RES, 'nivel_retorno.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['nivel_desde', 'nivel_hasta', 'ticks', 'retorno_medio_al_final'])
        for i in range(16):
            w.writerow([100 + 10 * i, min(255, 109 + 10 * i), int(cuenta[i]), f'{np.expm1(suma[i] / cuenta[i]):.4f}'])
    campos = list(filas[0].keys())
    with open(os.path.join(RES, 'competencia.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        for fl in filas:
            w.writerow({c: (f'{v:.4f}' if isinstance(v, float) else v) for c, v in fl.items()})
    with open(os.path.join(RES, 'competencia_ventanas.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(por_ventana[0].keys()))
        w.writeheader()
        w.writerows(por_ventana)

    for largo in (20000, 2000):
        print(f'\n== {largo} ticks')
        print(f"{'':10s} {'grupo':6s} {'geo':>6s} {'mediana':>7s} {'p5':>6s} {'min':>6s} "
              f"{'P(W<1)':>6s} {'>CyM':>5s} {'DD med':>7s} {'DD p95':>7s} {'ord':>4s} {'expo':>5s}")
        for fl in filas:
            if fl['ticks'] != largo or fl['grupo'] not in ('todas', '2022', '2023', '2024'):
                continue
            print(f"{fl['algoritmo']:10s} {fl['grupo']:6s} {fl['geo']:6.3f} {fl['mediana']:7.3f} "
                  f"{fl['p5']:6.3f} {fl['min']:6.3f} {fl['P_pierde']:6.3f} "
                  + (f"{fl['P_gana_CyM']:5.2f} {fl['DD_mediana']:7.0f} {fl['DD_p95']:7.0f} "
                     f"{fl['ordenes_mediana']:4.0f} {fl['exposicion']:5.2f}" if 'DD_mediana' in fl else ''))


if __name__ == '__main__':
    main()
