"""Todos los graficos del proyecto en docs/graficos/*.png y una pagina docs/graficos.html que los junta.

Lee lo que ya dejaron las simulaciones en resultados/ (universo.csv, montecarlo.csv, nivel_retorno.csv,
*_mejores.csv, sintesis.csv, medidas_por_variante.csv) y corre la version D sobre la serie de practica.
Uso (desde la raiz):  python ref/graficos.py      (~20 s)
"""
import csv
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..')
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'tools'))
RES = os.path.join(RAIZ, 'resultados')
OUT = os.path.join(RAIZ, 'docs', 'graficos')

# Paleta (rol fijo por entidad): la nuestra azul, rival naranjo, sin ancla aqua, comprar y mantener gris.
AZUL, NARANJO, AQUA, ROJO = '#2a78d6', '#eb6834', '#1baf7a', '#e34948'
GRIS, TINTA, TINTA2, GRILLA = '#8a8984', '#0b0b0b', '#52514e', '#e4e3df'
plt.rcParams.update({
    'figure.facecolor': '#fcfcfb', 'axes.facecolor': '#fcfcfb', 'savefig.facecolor': '#fcfcfb',
    'font.family': 'DejaVu Sans', 'font.size': 10, 'text.color': TINTA, 'axes.labelcolor': TINTA2,
    'axes.edgecolor': GRILLA, 'xtick.color': TINTA2, 'ytick.color': TINTA2, 'axes.grid': True,
    'grid.color': GRILLA, 'grid.linewidth': 0.8, 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.titleweight': 'bold', 'axes.titlesize': 11, 'axes.titlelocation': 'left', 'legend.frameon': False,
})
GRAFICOS = []   # (archivo, titulo, explicacion)


def guardar(fig, nombre, titulo, texto):
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, nombre), dpi=150)
    plt.close(fig)
    GRAFICOS.append((nombre, titulo, texto))
    print('  ', nombre)


def plata(x):
    return f'${x:,.0f}'.replace(',', '.')


def pct(x, signo=True):
    return (f'{x:+.1%}' if signo else f'{x:.1%}').replace('.', ',')


def neto(a, b):
    return float(np.mean(a > b + 1e-9) - np.mean(a < b - 1e-9))


def leer(nombre):
    with open(os.path.join(RES, nombre), encoding='utf-8') as f:
        return list(csv.DictReader(f))


def barras_h(ax, nombres, valores, colores, fmt):
    y = np.arange(len(nombres))[::-1]
    ax.barh(y, valores, color=colores, height=0.62, edgecolor='#fcfcfb', linewidth=2)
    ax.set_yticks(y, nombres)
    ax.grid(axis='y', visible=False)
    for yi, v in zip(y, valores):
        ax.text(v, yi, ' ' + fmt(v), va='center', ha='left' if v >= 0 else 'right', fontsize=9, color=TINTA)


# ---------------------------------------------------------------- 1. traza de la D en la serie de practica
def traza():
    from mercado import comprar_y_mantener, simular
    from series import PRACTICA_META, leer_csv
    from trader import Extremos
    from versiones import constantes
    p = np.array(leer_csv(PRACTICA_META), float)
    d = simular(p.astype(int).tolist(), Extremos(constantes('E')))
    r = simular(p.astype(int).tolist(), Extremos(dict(constantes('B'), TOMA_GANANCIA=255, RECOMPRA=100)))
    dec = np.array(d['decisiones'])
    t = np.arange(len(p))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True, gridspec_kw={'height_ratios': [3, 2]})
    a1.plot(t, p, color=GRIS, lw=1)
    for nivel, nom in ((100, 'compra (100)'), (120, 'recompra (122)'), (225, 'toma (225)'), (255, 'venta (255)')):
        a1.axhline(nivel if nivel != 120 else 122, color=GRILLA, lw=1, ls='--')
        a1.text(len(p) * 1.005, nivel if nivel != 120 else 122, nom, va='center', fontsize=8, color=TINTA2)
    prev = np.r_[0, dec[:-1]]
    cambio = dec != prev
    compra = cambio & ((dec >> 6) == 1)
    venta = cambio & ((dec >> 6) == 2)
    ic, iv = np.flatnonzero(compra) + 1, np.flatnonzero(venta) + 1     # se ejecuta en el tick siguiente
    ic, iv = ic[ic < len(p)], iv[iv < len(p)]
    a1.scatter(ic, p[ic], marker='^', s=70, color=AZUL, zorder=3, label='compra', edgecolor='#fcfcfb', lw=1.5)
    a1.scatter(iv, p[iv], marker='v', s=70, color=NARANJO, zorder=3, label='venta', edgecolor='#fcfcfb', lw=1.5)
    a1.set_ylabel('precio normalizado')
    a1.set_title('La versión E en la serie de práctica de la maestra (META desde 23-feb-2022, 20.000 ticks)')
    a1.legend(loc='upper left', ncol=2)
    W = np.array(d['W'])
    Wr = np.array(r['W'])
    a2.plot(t, Wr, color=NARANJO, lw=1.6, label=f'rival 100/255: {plata(Wr[-1])}')
    a2.plot(t, W, color=AZUL, lw=2, label=f'versión E: {plata(W[-1])}')
    a2.axhline(10000, color=TINTA2, lw=1)
    a2.set_ylabel('patrimonio ($)')
    a2.set_xlabel('tick (1 minuto de mercado cada uno)')
    a2.yaxis.set_major_formatter(lambda v, _: plata(v))
    a2.legend(loc='upper left')
    cym = comprar_y_mantener(p.astype(int).tolist())
    guardar(fig, '01_traza_E.png', 'Cómo opera la E en una serie',
            f'Arriba, el precio con cada orden: triángulo azul = compra, naranjo = venta. Abajo, el patrimonio de la E '
            f'contra el rival 100/255. La E termina en {plata(W[-1])}, el rival en {plata(Wr[-1])} y comprar y mantener '
            f'en {plata(cym)}. Como el primer precio es {int(p[0])} (≥ 160), el ancla está activa: compra 15 acciones cuando el precio sube 29 sobre el primero y las vende '
            'si vuelve a bajar de él (ganancias y pérdidas chicas). En esta serie la diferencia grande la hace la toma de '
            'ganancia: después de tocar 255, la E vende apenas el precio vuelve a 225 y guarda la plata, mientras el rival '
            'sigue comprado esperando otro 255 que no llega y devuelve la ganancia.')


# ---------------------------------------------------------------- 2. por que funciona: retorno segun nivel
def nivel():
    f = leer('nivel_retorno.csv')
    centro = np.array([(int(r['nivel_desde']) + int(r['nivel_hasta'])) / 2 for r in f])
    ret = np.array([float(r['retorno_medio_al_final']) for r in f])
    fig, ax = plt.subplots(figsize=(9, 4.4))
    ax.bar(centro, ret * 100, width=8.6, color=[AZUL if v > 0 else ROJO for v in ret], edgecolor='#fcfcfb', lw=2)
    ax.axhline(0, color=TINTA2, lw=1)
    for x, nom in ((100, 'compra'), (122, 'recompra'), (225, 'toma'), (255, 'venta')):
        ax.axvline(x, color=TINTA2, lw=1, ls='--')
        ax.text(x, ax.get_ylim()[1] * 0.98, f' {nom} {x}', fontsize=8, color=TINTA2, va='top')
    ax.set_xlabel('nivel del precio normalizado')
    ax.set_ylabel('retorno medio hasta el final (%)')
    ax.set_title('Por qué funcionan las reglas: lo que rinde comprar en cada nivel')
    guardar(fig, '02_nivel_retorno.png', 'Por qué el algoritmo compra abajo y vende arriba',
            'Para cada nivel de precio, cuánto sube o baja en promedio desde ahí hasta el final de la serie '
            f'(todas las series reales). Comprando en 100–109 se gana {pct(ret[0])}; vendiendo en 250–255 se evita '
            f'perder {pct(-ret[-1], False)}. Como la normalización obliga a que la serie toque 100 y 255, el borde de '
            'abajo casi siempre rinde y el de arriba casi siempre pierde. Bajo ~175 conviene estar comprado.')


# ---------------------------------------------------------------- 3 a 8: universo de 22 acciones
def universo():
    f = leer('universo.csv')
    cols = list(f[0].keys())[2:]
    X = {c: np.array([float(r[c]) for r in f]) for c in cols}
    acc = np.array([r['accion'] for r in f])
    anio = np.array([r['inicio'][:4] for r in f])
    from minuto import EMPRESAS
    comp = np.isin(acc, EMPRESAS)
    nom = {'A ancla15': 'A (ancla 30, 15 acc.)', 'B sin_ancla': 'B (sin ancla)', 'C ancla26_rec117': 'C (ancla 26, rec. 117)',
           'D ancla29_rec122': 'D (ancla 29, rec. 122)', 'E ancla29_rec122_p0160': 'E (D + ancla si p0 ≥ 160)', 'F todo170_ancla29_rec122': 'F (todo si p0 ≥ 170)',
           'rival 100/255': 'rival 100/255',
           'rival 100/255+220': 'rival 100/255 + toma 220', 'comprar_y_mantener': 'comprar y mantener'}
    color = {c: (AZUL if c[0] in 'ABCDEF' and ' ' in c and not c.startswith('rival') else NARANJO if c.startswith('rival') else GRIS)
             for c in cols}
    r1, r2 = X['rival 100/255'], X['rival 100/255+220']
    D, B, E = X['D ancla29_rec122'], X['B sin_ancla'], X['E ancla29_rec122_p0160']

    # 3. promedio
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
    for ax, m, tit in ((axs[0], np.ones(len(f), bool), f'22 acciones ({len(f):,} períodos)'.replace(',', '.')),
                       (axs[1], comp, f'5 de la competencia ({comp.sum():,} períodos)'.replace(',', '.'))):
        barras_h(ax, [nom[c] for c in cols], [X[c][m].mean() for c in cols], [color[c] for c in cols], plata)
        ax.set_title(tit)
        ax.set_xlim(0, 25500)
        ax.xaxis.set_major_formatter(lambda v, _: plata(v))
    fig.suptitle('Patrimonio final promedio por ronda (parte con $10.000)', x=0.01, ha='left', fontweight='bold')
    guardar(fig, '03_promedio.png', 'Promedio por ronda',
            f'Azul = nuestras versiones, naranjo = los rivales, gris = comprar y mantener. Todas las nuestras promedian '
            f'~{plata(D.mean())} contra ~{plata(r2.mean())} de los rivales. Comprar y mantener queda en {plata(X["comprar_y_mantener"].mean())}. '
            'El promedio casi no separa las versiones entre sí: lo que las separa es cuántas rondas le ganan al rival (gráfico 4).')

    # 4. neto contra rivales
    vers = ['A ancla15', 'B sin_ancla', 'C ancla26_rec117', 'D ancla29_rec122', 'E ancla29_rec122_p0160', 'F todo170_ancla29_rec122']
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, m, tit in ((axs[0], np.ones(len(f), bool), '22 acciones'), (axs[1], comp, '5 de la competencia')):
        x = np.arange(len(vers))
        v1 = [neto(X[v][m], r1[m]) * 100 for v in vers]
        v2 = [neto(X[v][m], r2[m]) * 100 for v in vers]
        ax.bar(x - 0.2, v1, 0.38, color=AZUL, label='vs rival 100/255', edgecolor='#fcfcfb', lw=2)
        ax.bar(x + 0.2, v2, 0.38, color=NARANJO, label='vs rival + toma 220', edgecolor='#fcfcfb', lw=2)
        for xi, a, b in zip(x, v1, v2):
            ax.text(xi - 0.2, a, f'{a:+.1f}'.replace('.', ','), ha='center', va='bottom', fontsize=8)
            ax.text(xi + 0.2, b, f'{b:+.1f}'.replace('.', ','), ha='center', va='bottom', fontsize=8)
        ax.set_xticks(x, [v[0] for v in vers])
        ax.grid(axis='x', visible=False)
        ax.set_title(tit)
    axs[0].set_ylabel('neto (%) = % rondas que ganamos − % que perdemos')
    axs[0].legend(loc='upper left')
    guardar(fig, '04_neto_rivales.png', 'Cuántas rondas le ganamos a los rivales',
            f'El “neto” es el % de rondas en que terminamos con más plata que el rival menos el % en que terminamos con menos '
            f'(el resto empata). En las 5 acciones de la competencia la E gana neto {pct(neto(E[comp], r1[comp]))} contra el rival '
            f'100/255 (la D {pct(neto(D[comp], r1[comp]))}). La B (sin ancla) gana mucho menos: el ancla es lo que desempata contra '
            'compañeros con reglas parecidas, y la E la usa solo cuando conviene.')

    # 5. distribucion
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    bins = np.linspace(0, 70000, 71)
    for x, c, n, lw in ((X['comprar_y_mantener'], GRIS, 'comprar y mantener', 1.6), (r1, NARANJO, 'rival 100/255', 1.6),
                        (E, AZUL, 'versión E', 2.2)):
        ax.hist(np.clip(x, 0, 69999), bins=bins, histtype='step', color=c, lw=lw, label=n)
    ax.axvline(10000, color=TINTA2, lw=1, ls='--')
    ax.text(10000, ax.get_ylim()[1] * 0.97, ' $10.000 (empate)', fontsize=8, color=TINTA2, va='top')
    ax.set_xlabel('patrimonio final de la ronda')
    ax.set_ylabel('cantidad de períodos')
    ax.xaxis.set_major_formatter(lambda v, _: plata(v))
    ax.legend()
    ax.set_title('Cómo se reparten los resultados (22 acciones)')
    guardar(fig, '05_distribucion.png', 'Reparto de los resultados',
            f'Cada curva cuenta cuántos períodos terminaron en cada patrimonio (no compara ronda por ronda: para eso, el gráfico 04). Comprar y mantener pierde plata en '
            f'{pct(np.mean(X["comprar_y_mantener"] < 1e4), False)} de los períodos. La D y el rival casi nunca bajan de $10.000 '
            f'(la E pierde en {pct(np.mean(E < 1e4), False)}); la mayoría termina cerca de $20.000 porque la normalización '
            'asegura un viaje completo de 100 a 255.')

    # 6. riesgo
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    peor = [(X[c].min() / 1e4 - 1) * 100 for c in cols[:-1]]
    pp = [np.mean(X[c] < 1e4) * 100 for c in cols[:-1]]
    barras_h(axs[0], [nom[c] for c in cols[:-1]], peor, [color[c] for c in cols[:-1]], lambda v: f'{v:.1f} %'.replace('.', ','))
    axs[0].set_title('Peor ronda (% de pérdida)')
    axs[0].set_xlim(-19, 3)
    barras_h(axs[1], [nom[c] for c in cols[:-1]], pp, [color[c] for c in cols[:-1]], lambda v: f'{v:.2f} %'.replace('.', ','))
    axs[1].set_title('Rondas que terminan perdiendo plata (%)')
    axs[1].set_xlim(0, 2.2)
    guardar(fig, '06_riesgo.png', 'Riesgo: la peor ronda y cuántas pierden',
            f'En las 22 acciones la peor ronda de la D pierde {pct(D.min() / 1e4 - 1, False).lstrip("-")} '
            f'(Intel, dic-2022) y la B solo {pct(B.min() / 1e4 - 1, False).lstrip("-")}: el ancla compra al comienzo y, si la '
            f'acción cae fuerte justo después, se pierde. En las 5 de la competencia la peor ronda de la D es '
            f'{pct(D[comp].min() / 1e4 - 1, False).lstrip("-")}. Comprar y mantener no aparece: pierde hasta '
            f'{pct(1 - X["comprar_y_mantener"].min() / 1e4, False)}.')

    # 7. por accion
    ks = sorted(set(acc), key=lambda k: neto(D[acc == k], r1[acc == k]))
    fig, axs = plt.subplots(1, 2, figsize=(11, 7), sharey=True)
    y = np.arange(len(ks))
    for ax, w, tit in ((axs[0], D, 'Versión D contra el rival 100/255'), (axs[1], E, 'Versión E contra el rival 100/255')):
        v = np.array([neto(w[acc == k], r1[acc == k]) * 100 for k in ks])
        ax.barh(y, v, color=[AZUL if x > 0 else ROJO for x in v], height=0.66, edgecolor='#fcfcfb', lw=1.5)
        ax.axvline(0, color=TINTA2, lw=1)
        ax.set_title(tit)
        ax.set_xlabel('neto (%)')
        ax.grid(axis='y', visible=False)
    axs[0].set_yticks(y, [k + (' ★' if k in EMPRESAS else '') for k in ks])
    pierde_r = [k for k in ks if neto(D[acc == k], r1[acc == k]) < 0]
    pierde_e = [k for k in ks if neto(E[acc == k], r1[acc == k]) < 0]
    peor_e = min(ks, key=lambda k: neto(E[acc == k], r1[acc == k]))
    guardar(fig, '07_por_accion.png', 'Acción por acción',
            'Azul = gana más rondas de las que pierde contra el rival; rojo = pierde más. ★ = acción de la competencia. '
            f'La D le gana al rival en {len(ks) - len(pierde_r)} de {len(ks)} acciones (pierde en {", ".join(pierde_r)}): '
            'casi todas esas rondas las pierde el ancla cuando el primer precio es bajo. La E arma el ancla solo si el primer '
            f'precio es ≥ 160 y le gana al rival en {len(ks) - len(pierde_e)} de {len(ks)} '
            f'(la que menos: {peor_e}, {pct(neto(E[acc == peor_e], r1[acc == peor_e]))}).')

    # 8. por anio
    anios = ('2022', '2023', '2024')
    series = (('E ancla29_rec122_p0160', AZUL, 'versión E'), ('B sin_ancla', AQUA, 'versión B'),
              ('rival 100/255', NARANJO, 'rival 100/255'), ('comprar_y_mantener', GRIS, 'comprar y mantener'))
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    x = np.arange(len(anios))
    for i, (c, col, n) in enumerate(series):
        v = [X[c][anio == a].mean() for a in anios]
        ax.bar(x + (i - 1.5) * 0.2, v, 0.19, color=col, label=n, edgecolor='#fcfcfb', lw=1.5)
    ax.set_xticks(x, [f'empieza en {a}' for a in anios])
    ax.grid(axis='x', visible=False)
    ax.yaxis.set_major_formatter(lambda v, _: plata(v))
    ax.set_ylabel('patrimonio final promedio')
    ax.legend(ncol=4, loc='upper left', bbox_to_anchor=(0, -0.1))
    ax.set_title('Por año (22 acciones)')
    dA = ', '.join(f'{a}: {plata(E[anio == a].mean())}' for a in anios)
    cA = ', '.join(f'{a}: {plata(X["comprar_y_mantener"][anio == a].mean())}' for a in anios)
    guardar(fig, '08_por_anio.png', 'Año por año',
            f'Promedio de la E según el año en que empieza el período: {dA}. Comprar y mantener: {cA}. '
            'Los tres años la E le gana al rival y a comprar y mantener. Los períodos que empiezan en 2022 (año bajista) rinden '
            'menos para todos, pero el nuestro sigue cerca del doble, mientras comprar y mantener pierde plata.')
    return D, E, comp, r1


# ---------------------------------------------------------------- 9. optimizador
def optimizador(D, E, comp, r1):
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.6))
    for ax, archivos, tit, dpeor, dneto in (
            (axs[0], ['universo_mejores.csv'], '22 acciones (3 h, 80.061 candidatas)', D.min() / 1e4, neto(D, r1)),
            (axs[1], ['optimizador_mejores.csv', 'promedio_mejores.csv'], '5 de la competencia', 0.953, 0.127)):
        f = [r for a in archivos for r in leer(a)]
        pe = np.array([float(r['peor']) for r in f])
        ne = np.array([float(r['neto_100_255']) for r in f])
        ax.scatter((pe - 1) * 100, ne * 100, s=10, color=GRIS, alpha=0.45, lw=0, label=f'candidatas que cumplen ({len(f):,})'.replace(',', '.'))
        ax.scatter([(dpeor - 1) * 100], [dneto * 100], s=110, color=AZUL, edgecolor='#fcfcfb', lw=2, zorder=3, label='versión D')
        ax.annotate('D', ((dpeor - 1) * 100, dneto * 100), xytext=(8, 4), textcoords='offset points', fontweight='bold')
        epeor, eneto = (E.min() / 1e4, neto(E, r1)) if ax is axs[0] else (0.953, 0.154)
        ax.scatter([(epeor - 1) * 100], [eneto * 100], s=110, color=AQUA, edgecolor='#fcfcfb', lw=2, zorder=3, label='versión E')
        ax.annotate('E', ((epeor - 1) * 100, eneto * 100), xytext=(8, 4), textcoords='offset points', fontweight='bold')
        ax.set_xlabel('peor ronda (%)')
        ax.set_title(tit)
        ax.legend(loc='lower center')
    axs[0].set_ylabel('neto contra el rival 100/255 (%)')
    guardar(fig, '09_optimizador.png', 'Lo que buscó el optimizador',
            'Cada punto gris es una variante que el optimizador probó y que cumple los límites de riesgo. Arriba = le gana más '
            'rondas al rival; a la derecha = su peor ronda pierde menos. En las 22 acciones ninguna candidata le gana más rondas '
            'al rival que la D: las de peor ronda más chica lo pagan con menos rondas ganadas. En las 5 de la competencia '
            'algunas llegan a ~14 % (la D 12,7 %), pero su peor ronda es de −6 a −10 %, y llevadas a las 22 acciones '
            'su peor ronda empeora a −19 % hasta −42 % (la D −13,5 %). La E (aqua) es otra cosa: no cambia ninguna constante, '
            'agrega la condición p0 ≥ 160 al ancla, y queda por encima de todas las candidatas con la misma peor ronda que la D.')


# ---------------------------------------------------------------- 10. montecarlo
def montecarlo():
    f = leer('montecarlo.csv')
    esc = list(dict.fromkeys(r['escenario'] for r in f))
    var = list(dict.fromkeys(r['variante'] for r in f))
    cols = {var[0]: NARANJO, var[1]: GRIS, var[2]: AQUA, var[3]: AZUL}
    nomv = {var[0]: 'rival 100/255', var[1]: 'rival + toma 220', var[2]: 'versión D', var[3]: 'versión F'}
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.4))
    x = np.arange(len(esc))
    for i, v in enumerate(var):
        g = [float(r['neto_vs_100_255']) * 100 for e in esc for r in f if r['escenario'] == e and r['variante'] == v]
        p = [float(r['P_pierde']) * 100 for e in esc for r in f if r['escenario'] == e and r['variante'] == v]
        axs[0].bar(x + (i - 1.5) * 0.2, g, 0.19, color=cols[v], label=nomv[v], edgecolor='#fcfcfb', lw=1.5)
        axs[1].bar(x + (i - 1.5) * 0.2, p, 0.19, color=cols[v], label=nomv[v], edgecolor='#fcfcfb', lw=1.5)
    for ax in axs:
        ax.set_xticks(x, esc, rotation=30, ha='right')
        ax.grid(axis='x', visible=False)
    axs[0].set_title('Neto contra el rival 100/255 (%)')
    axs[0].axhline(0, color=TINTA2, lw=1)
    axs[1].set_title('Rondas que pierden plata (%)')
    axs[0].legend(loc='upper left')
    guardar(fig, '10_montecarlo.png', 'Mercados inventados (Montecarlo)',
            '1.000 series simuladas por escenario (paseo al azar, sube, baja, volátil, vuelve a la media, inercia, saltos y '
            'remuestreo de días reales), normalizadas como la maestra. La F le gana al rival en unas 30 % más de rondas de las que '
            'pierde en casi todos los escenarios, el doble que la D, y pierde plata en menos rondas. En “sube” (mercado que solo '
            'sube) todos quedan parejos con el rival.')


# ---------------------------------------------------------------- 11 y 12. velocidad
def velocidad():
    from universo import F_CLK, LATENCIA, SPI
    per = (('10 ms\n(ronda 1)', 10e-3), ('1 ms\n(ronda 2)', 1e-3), ('100 µs\n(ronda 3)', 100e-6), ('20 µs', 20e-6),
           ('12 µs', 12e-6), ('10 µs', 10e-6), ('9,5 µs\n(pegadas)', 9.5e-6))
    disp = [int((T - SPI + 1e-6) * F_CLK) - 3 for _, T in per]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    x = np.arange(len(per))
    ax.bar(x, disp, 0.6, color=AQUA, edgecolor='#fcfcfb', lw=2, label='ciclos disponibles para decidir')
    ax.axhline(LATENCIA['A'], color=AZUL, lw=2, label=f'A, C, D: {LATENCIA["A"]} ciclos')
    ax.axhline(LATENCIA['B'], color=NARANJO, lw=2, ls='--', label=f'B: {LATENCIA["B"]} ciclos')
    for xi, v in zip(x, disp):
        ax.text(xi, v, f'{v:,}'.replace(',', '.'), ha='center', va='bottom', fontsize=8)
    ax.set_yscale('log')
    ax.set_xticks(x, [n for n, _ in per])
    ax.grid(axis='x', visible=False)
    ax.set_ylabel('ciclos de reloj (25 MHz, escala log)')
    ax.legend(loc='upper right')
    ax.set_title('¿Alcanza a decidir antes de la siguiente transacción?')
    guardar(fig, '11_velocidad.png', 'Velocidad en cada período de la maestra',
            f'Barra = ciclos que hay entre que llega un precio y que la maestra lee la decisión. Línea = lo que tarda nuestro '
            f'programa en el peor caso, medido en el RTL. Incluso con transacciones pegadas (9,5 µs) quedan {disp[-1]} ciclos y '
            f'usamos {LATENCIA["A"]}: llega a tiempo en todos los períodos, y por eso la plata es la misma en todas las rondas de velocidad.')

    m = {r['variante']: r for r in leer('medidas_por_variante.csv')}
    filas = [('algoritmo viejo, software', float(m['sw']['ciclos_max']), GRIS),
             ('viejo + desplazador', float(m['shift']['ciclos_max']), GRIS),
             ('viejo + multiplicador 8 bits', float(m['mul8']['ciclos_max']), GRIS),
             ('viejo + mult. + despl.', float(m['mul8shift']['ciclos_max']), GRIS),
             ('extremos A–D (lectura bloqueante)', LATENCIA['A'], AZUL),
             ('extremos B (sin ancla)', LATENCIA['B'], AZUL)]
    fig, ax = plt.subplots(figsize=(10, 3.8))
    barras_h(ax, [f[0] for f in filas], [f[1] for f in filas], [f[2] for f in filas], lambda v: f'{v:.0f} ciclos')
    ax.set_xscale('log')
    ax.set_xlim(5, 2000)
    ax.set_xlabel('ciclos del precio a la decisión, peor caso (escala log)')
    ax.set_title('Cómo bajó la latencia durante el proyecto')
    guardar(fig, '12_latencia.png', 'Evolución de la latencia',
            f'El algoritmo viejo (tendencias con multiplicaciones) tardaba hasta {float(m["sw"]["ciclos_max"]):.0f} ciclos por precio; '
            'con hardware de multiplicación bajó a ~115–140. El algoritmo de extremos solo compara, y con la lectura bloqueante '
            f'del registro NUEVO (el núcleo espera el precio sin preguntar en un ciclo) llega a {LATENCIA["A"]} ciclos: ~37 veces más rápido.')


# ---------------------------------------------------------------- 13. recursos de la FPGA
def recursos():
    f = {r['variante']: r for r in leer('sintesis.csv')}
    filas = [('Pochoco original', f['base_original']), ('software (final)', f['sw']), ('+ desplazador', f['shift']),
             ('+ multiplicador 8 bits', f['mul8']), ('+ mult. + despl.', f['mul8shift'])]
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
    lc = [float(r['LC_pct']) for _, r in filas]
    cols = [AZUL if n == 'software (final)' else ROJO if v > 100 else GRIS for (n, _), v in zip(filas, lc)]
    barras_h(axs[0], [n for n, _ in filas], lc, cols, lambda v: f'{v:.0f} %')
    axs[0].axvline(100, color=TINTA2, lw=1, ls='--')
    axs[0].set_title('Celdas lógicas usadas (% de las 1.280)')
    axs[0].set_xlim(0, 135)
    fm = [float(r['Fmax_min'] or 0) for _, r in filas]
    barras_h(axs[1], [n for n, _ in filas], fm, cols, lambda v: f'{v:.1f} MHz'.replace('.', ',') if v else 'no cabe')
    axs[1].axvline(25, color=TINTA2, lw=1, ls='--')
    axs[1].text(25, 4.45, ' reloj 25 MHz', fontsize=8, color=TINTA2)
    axs[1].set_title('Frecuencia máxima (peor de las semillas)')
    axs[1].set_xlim(0, 60)
    guardar(fig, '13_recursos.png', 'Espacio en la FPGA',
            'El diseño final (azul) usa 985 de 1.280 celdas (77 %) y aguanta ~46 MHz, casi el doble de los 25 MHz del reloj. '
            'Agregar multiplicador y desplazador juntos no cabe en la iCE40 (rojo). Como el algoritmo final no multiplica, '
            'no hace falta ese hardware.')


def pagina():
    partes = ['<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
              '<title>Gráficos Pochoco Trader</title><style>body{font-family:system-ui,sans-serif;background:#fcfcfb;color:#0b0b0b;'
              'max-width:1100px;margin:0 auto;padding:24px 16px;line-height:1.5}h1{margin:0 0 4px}p.sub{color:#52514e;margin:0 0 24px}'
              'figure{margin:0 0 40px}figure img{width:100%;height:auto;border:1px solid #e4e3df;border-radius:8px}'
              'figcaption{color:#3b3a37;margin-top:8px}figcaption b{color:#0b0b0b}nav a{margin-right:12px;color:#2a78d6;font-size:14px}</style>'
              '</head><body><h1>Pochoco Trader: todos los gráficos</h1><p class="sub">Se regeneran con '
              '<code>python ref/graficos.py</code>. Los PNG están en <code>docs/graficos/</code> para usarlos en el informe.</p><nav>']
    partes += [f'<a href="#{n[:2]}">{n[:2]}. {t}</a>' for n, t, _ in GRAFICOS]
    partes.append('</nav><hr>')
    for n, t, texto in GRAFICOS:
        partes.append(f'<figure id="{n[:2]}"><img src="graficos/{n}" alt="{t}"><figcaption><b>{n[:2]}. {t}.</b> {texto}</figcaption></figure>')
    partes.append('</body></html>')
    with open(os.path.join(RAIZ, 'docs', 'graficos.html'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(partes))


if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    traza()
    nivel()
    D, E, comp, r1 = universo()
    optimizador(D, E, comp, r1)
    montecarlo()
    velocidad()
    recursos()
    pagina()
    print('docs/graficos.html')
