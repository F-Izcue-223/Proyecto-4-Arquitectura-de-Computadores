"""Simulacion completa sobre un universo de acciones tecnologicas -> informe HTML.

Toma todas las acciones de data/minuto (barras de 1 minuto 2022-2024, horario regular),
arma periodos de 20.000 minutos (~50 dias de mercado) normalizados a [100, 255] igual que
la maestra, y corre las versiones del algoritmo (tools/versiones.py), dos rivales probables
(100/255 y 100/255 con techo 220) y comprar y mantener, con las reglas de la maestra.

Las 5 acciones de la competencia (META, AAPL, NFLX, AMD, TSLA) son "dentro de muestra":
con ellas se ajustaron los parametros. Las demas son una prueba FUERA de muestra.

Entrega docs/informe_universo.html (tablas, graficos e ideas de mejora generadas a partir
de los resultados) y resultados/universo.csv (un periodo por fila).

Uso:  python ref/universo.py [--paso 500]      (un periodo cada `paso` minutos por accion)
"""
import argparse
import base64
import csv
import io
import os
import sys
import time

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..')
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'tools'))
from competencia import cym, extremos, maestra  # noqa: E402
from minuto import DATOS, EMPRESAS, ventanas  # noqa: E402
from versiones import VERSIONES, constantes  # noqa: E402

F_CLK = 25e6
SPI = 9.5e-6                       # transaccion SPI del testbench del curso
LATENCIA = {'A': 12, 'B': 9, 'C': 12, 'D': 12, 'E': 12, 'F': 12, 'G': 13}   # peor caso precio -> DECISION medido en el RTL (ciclos)


def estrategias():
    e = {}
    for v, (nombre, _) in VERSIONES.items():
        c = constantes(v)
        e[f'{v} {nombre}'] = (c['MINIMO'], c['MAXIMO'], c['TOMA_GANANCIA'], c['RECOMPRA'], c.get('ANCLA', 0),
                              c.get('ANCLA_ORDEN', 0x7F), c.get('ANCLA_P0', 0), c.get('TODO_P0', 0), c.get('TODO_Y', 0))
    e['rival 100/255'] = (100, 255, 255, 100, 0, 0x7F, 0, 0, 0)
    e['rival 100/255+220'] = (100, 255, 220, 100, 0, 0x7F, 0, 0, 0)
    return e


def neto(a, b):
    return float(np.mean(a > b + 1e-9) - np.mean(a < b - 1e-9))


def geo(w):
    return float(np.exp(np.log(w).mean()))


def png(fig):
    import matplotlib.pyplot as plt
    b = io.BytesIO()
    fig.savefig(b, format='png', dpi=110, bbox_inches='tight')
    plt.close(fig)
    return '<img src="data:image/png;base64,' + base64.b64encode(b.getvalue()).decode() + '">'


def plata(x):
    return f'${x:,.0f}'.replace(',', '.')


def pct(x, d=1):
    return f'{100 * x:.{d}f} %'.replace('.', ',')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--paso', type=int, default=500)
    a = ap.parse_args()
    t0 = time.time()
    acciones = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
    V = ventanas(a.paso, empresas=acciones)
    est = estrategias()
    nombres = list(est)
    tk = np.array([k for k, _, _ in V])
    anio = np.array([h[:4] for _, h, _ in V])
    W = {n: np.array([maestra(s, extremos(s, *p))[0] for *_, s in V]) / 1e4 for n, p in est.items()}
    C = np.array([cym(s) for *_, s in V]) / 1e4
    dentro = np.isin(tk, EMPRESAS)
    principal = [n for n in nombres if n.startswith('D ')][0]
    segura = [n for n in nombres if n.startswith('B ')][0]
    grabada = [n for n in nombres if n.startswith('A ')][0]

    with open(os.path.join(RAIZ, 'resultados', 'universo.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['accion', 'inicio'] + nombres + ['comprar_y_mantener'])
        for i, (k, h, _) in enumerate(V):
            w.writerow([k, h[:16]] + [int(W[n][i] * 1e4) for n in nombres] + [int(C[i] * 1e4)])

    def fila(w, m):
        x = w[m]
        return [plata(x.mean() * 1e4), plata(np.median(x) * 1e4), plata(x.min() * 1e4), plata(x.max() * 1e4),
                pct(np.mean(x < 1)), pct(np.mean(x < 0.95), 2)]

    html = ['<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Pochoco Trader: universo tecnológico</title>',
            '<style>body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1d2433}'
            'h1{font-size:26px}h2{font-size:20px;margin-top:32px;border-bottom:2px solid #dde3ee;padding-bottom:4px}'
            'table{border-collapse:collapse;margin:8px 0 16px;font-size:13.5px}th,td{border:1px solid #d6dbe6;padding:4px 8px;text-align:right}'
            'th{background:#eef2f8}td:first-child,th:first-child{text-align:left}.nota{color:#56607a;font-size:13px}'
            '.idea{background:#f3f8ef;border-left:4px solid #5a9a3c;padding:8px 12px;margin:8px 0}'
            '.alerta{background:#fdf3ec;border-left:4px solid #d0782f;padding:8px 12px;margin:8px 0}img{max-width:100%}</style></head><body>',
            '<h1>Pochoco Trader: simulación sobre el universo tecnológico</h1>',
            f'<p class="nota">{time.strftime("%d-%m-%Y %H:%M")} · {len(acciones)} acciones · {len(V):,} períodos de 20.000 minutos '
            f'(~50 días de mercado, 2022–2024), uno cada {a.paso} minutos por acción · normalizados a [100, 255] como la maestra · '
            'reglas de la maestra ($10.000 iniciales, comisión $5, máximo 63 acciones por orden, la orden se ejecuta al tick siguiente).'
            .replace(',', '.') + '</p>',
            f'<p class="nota">Dentro de muestra (con ellas se ajustaron los parámetros): {", ".join(EMPRESAS)}. '
            f'Fuera de muestra: {", ".join(k for k in acciones if k not in EMPRESAS)}. Sin datos de 1 minuto en EE.UU.: Samsung, SK Hynix, '
            'ASML y Arm.</p>']

    # 1. Resumen general
    html.append('<h2>1. Resultado general (todas las acciones)</h2><table><tr><th>estrategia</th><th>promedio</th><th>mediana</th>'
                '<th>peor</th><th>mejor</th><th>pierde</th><th>pierde &gt;5 %</th><th>neto vs rival 100/255</th>'
                '<th>neto vs rival +220</th><th>gana a mantener</th></tr>')
    r1, r2 = W['rival 100/255'], W['rival 100/255+220']
    todo = np.ones(len(V), bool)
    for n in nombres:
        html.append(f'<tr><td>{n}</td>' + ''.join(f'<td>{c}</td>' for c in fila(W[n], todo)) +
                    f'<td>{pct(neto(W[n], r1))}</td><td>{pct(neto(W[n], r2))}</td><td>{pct(np.mean(W[n] > C))}</td></tr>')
    html.append('<tr><td>comprar y mantener</td>' + ''.join(f'<td>{c}</td>' for c in fila(C, todo)) + '<td></td><td></td><td></td></tr></table>')
    html.append('<p class="nota">"Neto vs rival" = % de períodos en que la estrategia termina con más plata que el rival menos % en '
                'que termina con menos (los demás son empates). Es lo que decide contra compañeros con reglas parecidas.</p>')

    # 2. Dentro vs fuera de muestra
    html.append('<h2>2. ¿Sirven las reglas fuera de las 5 acciones de la competencia?</h2><table><tr><th>estrategia</th>'
                '<th>promedio dentro</th><th>promedio fuera</th><th>peor fuera</th><th>pierde fuera</th>'
                '<th>neto vs 100/255 fuera</th><th>neto vs +220 fuera</th></tr>')
    for n in nombres:
        x = W[n]
        html.append(f'<tr><td>{n}</td><td>{plata(x[dentro].mean() * 1e4)}</td><td>{plata(x[~dentro].mean() * 1e4)}</td>'
                    f'<td>{plata(x[~dentro].min() * 1e4)}</td><td>{pct(np.mean(x[~dentro] < 1))}</td>'
                    f'<td>{pct(neto(x[~dentro], r1[~dentro]))}</td><td>{pct(neto(x[~dentro], r2[~dentro]))}</td></tr>')
    html.append('</table>')

    # 3. Por accion (version principal)
    html.append(f'<h2>3. Por acción ({principal}, la recomendada)</h2><table><tr><th>acción</th><th>períodos</th><th>promedio</th>'
                '<th>peor</th><th>mejor</th><th>pierde</th><th>mantener (prom.)</th><th>neto vs B sin ancla</th>'
                '<th>neto vs rival 100/255</th></tr>')
    por_accion = []
    for k in acciones:
        m = tk == k
        x = W[principal][m]
        por_accion.append((k, x.mean(), x.min(), np.mean(x < 1), neto(x, W[segura][m]), neto(x, r1[m]), C[m].mean()))
        html.append(f'<tr><td>{k}{" *" if k in EMPRESAS else ""}</td><td>{m.sum()}</td><td>{plata(x.mean() * 1e4)}</td>'
                    f'<td>{plata(x.min() * 1e4)}</td><td>{plata(x.max() * 1e4)}</td><td>{pct(np.mean(x < 1))}</td>'
                    f'<td>{plata(C[m].mean() * 1e4)}</td><td>{pct(neto(x, W[segura][m]))}</td><td>{pct(neto(x, r1[m]))}</td></tr>')
    html.append('</table><p class="nota">* acciones de la competencia.</p>')

    # 4. Por anio
    html.append('<h2>4. Por año de inicio del período</h2><table><tr><th>estrategia</th>' +
                ''.join(f'<th>{y} prom.</th><th>{y} peor</th>' for y in ('2022', '2023', '2024')) + '</tr>')
    for n in nombres + ['comprar y mantener']:
        x = C if n == 'comprar y mantener' else W[n]
        html.append(f'<tr><td>{n}</td>' + ''.join(f'<td>{plata(x[anio == y].mean() * 1e4)}</td><td>{plata(x[anio == y].min() * 1e4)}</td>'
                                                 for y in ('2022', '2023', '2024')) + '</tr>')
    html.append('</table>')

    # 5. Velocidad
    html.append('<h2>5. Velocidad según el período de la maestra</h2><p>La maestra toma DECISION al bajar CS. Entre el último bit '
                'de un precio y la bajada de CS siguiente quedan 1 µs + (T − 9,5 µs); se descuentan 3 ciclos de sincronización. '
                'Latencia medida en el RTL con el testbench del curso (peor caso precio → DECISION).</p><table><tr><th>período T</th>'
                '<th>ciclos disponibles</th>' + ''.join(f'<th>{v} ({LATENCIA[v]} ciclos)</th>' for v in LATENCIA) + '</tr>')
    for nom, T in (('10 ms (ronda 1)', 10e-3), ('1 ms (ronda 2)', 1e-3), ('100 µs (ronda 3)', 100e-6), ('20 µs', 20e-6),
                   ('12 µs', 12e-6), ('10 µs', 10e-6), ('9,5 µs (transacciones pegadas)', 9.5e-6)):
        disp = int((T - SPI + 1e-6) * F_CLK) - 3
        html.append(f'<tr><td>{nom}</td><td>{disp:,}</td>'.replace(',', '.') +
                    ''.join(f'<td>{"a tiempo" if LATENCIA[v] <= disp else "TARDE"} (margen {disp - LATENCIA[v]:,})</td>'.replace(',', '.')
                            for v in LATENCIA) + '</tr>')
    html.append('</table><p class="nota">Mientras la decisión llegue a tiempo, la plata es idéntica en todos los períodos (las '
                'decisiones no dependen del tiempo). Con transacciones pegadas el programa sigue llegando con margen.</p>')

    # 6. Graficos
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 3.6))
    bins = np.arange(0.3, 4.0, 0.05)
    ax.hist(C, bins=bins, alpha=0.5, label='comprar y mantener', color='#d0782f')
    ax.hist(W[principal], bins=bins, alpha=0.6, label=principal, color='#3c7a9a')
    ax.axvline(1, color='0.3', ls=':')
    ax.set_xlabel('patrimonio final / $10.000')
    ax.set_ylabel('períodos')
    ax.legend()
    html.append('<h2>6. Distribución del patrimonio final</h2>' + png(fig))
    fig, ax = plt.subplots(figsize=(10, 3.6))
    orden = sorted(por_accion, key=lambda t: -t[1])
    ax.bar([t[0] for t in orden], [t[1] * 1e4 for t in orden], color=['#5a9a3c' if t[0] in EMPRESAS else '#3c7a9a' for t in orden])
    ax.bar([t[0] for t in orden], [t[6] * 1e4 for t in orden], color='#d0782f', alpha=0.6, width=0.4, label='mantener')
    ax.axhline(1e4, color='0.3', ls=':')
    ax.set_ylabel('promedio [$]')
    ax.tick_params(axis='x', rotation=60)
    ax.legend()
    html.append('<p class="nota">Promedio por acción (verde: acciones de la competencia; naranjo: comprar y mantener).</p>' + png(fig))

    # 7. Ideas de mejora (generadas de los resultados)
    html.append('<h2>7. Diagnóstico e ideas de mejora</h2>')
    ideas = []
    dD, dB = W[principal], W[segura]
    if neto(dD[~dentro], dB[~dentro]) > 0 and dD[~dentro].mean() >= dB[~dentro].mean():
        ideas.append(('idea', f'El ancla también sirve fuera de muestra: en las {len(acciones) - len(EMPRESAS)} acciones nuevas la '
                      f'versión principal le gana cara a cara a la versión sin ancla ({pct(neto(dD[~dentro], dB[~dentro]))} neto) y '
                      f'promedia {plata(dD[~dentro].mean() * 1e4)} contra {plata(dB[~dentro].mean() * 1e4)}. No está sobreajustada a 5 acciones.'))
    else:
        ideas.append(('alerta', f'Fuera de muestra el ancla no rinde igual (neto vs sin ancla {pct(neto(dD[~dentro], dB[~dentro]))}, '
                      f'promedio {plata(dD[~dentro].mean() * 1e4)} vs {plata(dB[~dentro].mean() * 1e4)}): puede estar ajustada a las 5 acciones.'))
    peores = sorted(por_accion, key=lambda t: t[2])[:3]
    ideas.append(('idea', 'Las peores pérdidas aparecen en ' + ', '.join(f'{t[0]} ({plata(t[2] * 1e4)})' for t in peores) +
                  '. Revisar esos períodos con tools/simular.py: si son del caso "el máximo llega primero y la serie termina cerca '
                  'de 100", el riesgo es estructural y no se corrige con parámetros.'))
    malas = [t for t in por_accion if t[4] < 0]
    if malas:
        ideas.append(('alerta', 'El ancla pierde cara a cara contra la versión sin ancla en: ' +
                      ', '.join(f'{t[0]} ({pct(t[4])})' for t in malas) + '. Son candidatas para un ancla más chica o más alta.'))
    mejor_prom = max(nombres[:len(VERSIONES)], key=lambda n: W[n].mean())
    mejor_cara = max(nombres[:len(VERSIONES)], key=lambda n: min(neto(W[n], r1), neto(W[n], r2)))
    ideas.append(('idea', f'En el universo completo, el mejor promedio es de {mejor_prom} ({plata(W[mejor_prom].mean() * 1e4)}) y el '
                  f'mejor cara a cara contra rivales es {mejor_cara}. Si no coinciden con la versión recomendada, correr '
                  '<code>ref/optimizador.py</code> sobre el universo (más acciones = parámetros más robustos) antes de cambiar la placa.'))
    ideas.append(('idea', 'La velocidad no limita la ganancia en ningún período probado (sección 5): mejorar más el hardware no '
                  'cambia la plata. La ventaja contra compañeros está en las reglas (ancla, toma, recompra) y en que la placa '
                  'funcione sin fallas el día de la competencia.'))
    for tipo, txt in ideas:
        html.append(f'<div class="{tipo}">{txt}</div>')
    html.append(f'<p class="nota">Generado por ref/universo.py en {time.time() - t0:.0f} s. Datos período a período: resultados/universo.csv.</p></body></html>')
    ruta = os.path.join(RAIZ, 'docs', 'informe_universo.html')
    open(ruta, 'w', encoding='utf-8').write('\n'.join(html))
    print(f'{len(V)} periodos de {len(acciones)} acciones en {time.time() - t0:.0f} s -> docs/informe_universo.html')
    for n in nombres:
        print(f'  {n:22s} promedio {plata(W[n].mean() * 1e4)}  dentro {plata(W[n][dentro].mean() * 1e4)}  fuera {plata(W[n][~dentro].mean() * 1e4)}  '
              f'peor {plata(W[n].min() * 1e4)}  pierde {pct(np.mean(W[n] < 1))}  vs100/255 {pct(neto(W[n], r1))}  vs220 {pct(neto(W[n], r2))}')
    print(f'  comprar y mantener     promedio {plata(C.mean() * 1e4)}  pierde {pct(np.mean(C < 1))}')


if __name__ == '__main__':
    main()
