"""Figuras y tablas del informe, a partir de los CSV de resultados/.

Correr despues de backtest.py, verificar.py, sintesis.py y `make tb`. Escribe:
  informe/figuras/*.pdf      figuras
  informe/tablas/*.tex       tablas (se incluyen con \\input en el informe)
  informe/tablas/numeros.tex macros con los numeros que se citan en el texto
Asi ningun numero del informe se copia a mano.
"""
import csv
import math
import os
import re
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..')
RES = os.path.join(RAIZ, 'resultados')
FIG = os.path.join(RAIZ, 'informe', 'figuras')
TAB = os.path.join(RAIZ, 'informe', 'tablas')
sys.path.insert(0, AQUI)
from mercado import CAJA0, simular  # noqa: E402
from series import leer_csv  # noqa: E402
# Las secciones 1 y 2 (backtest, co-diseno) son del algoritmo anterior, con el que se
# hizo ese estudio; la seccion 3 es la del algoritmo de la competencia (extremos).
from trader import PROGRAMAS, Tendencia as Trader, leer_equ  # noqa: E402

F_CLK = 25e6
T_SPI = 9.5e-6                     # transaccion SPI del testbench del curso (SPI_NS)
RONDAS = [(1, 10e-3), (2, 1e-3), (3, 0.1e-3)]
NOMBRE = {'sw': 'solo software', 'shift': 'shifter', 'mul8': 'mul8', 'mul8shift': 'mul8 + shifter',
          'base_original': 'SoC del P2'}
FAMILIAS = [('practica', 'práctica (bajista)'), ('practica_inv', 'práctica invertida (alcista)'),
            ('alibaba', 'Alibaba'), ('alibaba_inv', 'Alibaba invertida')]
plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})


def leer_res(nombre):
    with open(os.path.join(RES, nombre)) as f:
        return list(csv.DictReader(f))


def miles(x, dec=0):
    """Numero con punto de miles y coma decimal."""
    s = f'{x:,.{dec}f}'
    return s.replace(',', 'X').replace('.', ',').replace('X', '.')


def guardar_tabla(nombre, lineas):
    os.makedirs(TAB, exist_ok=True)
    with open(os.path.join(TAB, nombre), 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lineas) + '\n')


def geo(valores):
    return math.exp(sum(math.log(max(v, 1) / CAJA0) for v in valores) / len(valores))


def familia(serie):
    base = 'practica' if serie.startswith('practica') else 'alibaba'
    return base + ('_inv' if serie.endswith('_inv') else '')


def dagger(v):
    return NOMBRE[v] + ('$^\\dagger$' if v == 'mul8shift' else '')


# --- 1. Algoritmo contra las referencias ------------------------------------------

def backtest(m):
    rondas = leer_res('backtest.csv')
    series = {f['serie']: f for f in leer_res('backtest_series.csv')}
    fams = {}
    for f in rondas:
        fams.setdefault(familia(f['serie']), []).append(f)

    lin = ['\\begin{tabular}{lrrrrrr}', '\\toprule',
           'Rondas de 2000 ticks & $n$ & Agente & CyM & Gana a CyM & Gana a no operar & Peor ronda [\\$] \\\\',
           '\\midrule']
    for clave, nombre in FAMILIAS:
        fs = fams[clave]
        w = [int(f['W']) for f in fs]
        c = [int(f['CyM']) for f in fs]
        k = {'practica': 'Prac', 'practica_inv': 'PracInv', 'alibaba': 'Ali', 'alibaba_inv': 'AliInv'}[clave]
        m[f'Geo{k}'], m[f'Geo{k}CyM'] = miles(geo(w), 3), miles(geo(c), 3)
        m[f'Gana{k}'], m[f'N{k}'] = sum(a > b for a, b in zip(w, c)), len(fs)
        m[f'Peor{k}'] = miles(min(w))
        lin.append(f"{nombre} & {len(fs)} & {miles(geo(w), 3)} & {miles(geo(c), 3)} & "
                   f"{sum(a > b for a, b in zip(w, c))}/{len(fs)} & {sum(a > CAJA0 for a in w)}/{len(fs)} & "
                   f"{miles(min(w))} \\\\")
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('backtest_rondas.tex', lin)

    lin = ['\\begin{tabular}{lrrrrrr}', '\\toprule',
           'Serie (20\\,000 ticks) & Agente [\\$] & CyM [\\$] & No operar [\\$] & Órdenes & Comisiones [\\$] & Pérdida máx. [\\$] \\\\',
           '\\midrule']
    for s in ('practica', 'practica_inv', 'alibaba_5m_00000', 'alibaba_5m_00000_inv',
              'alibaba_15m_00000', 'alibaba_15m_00000_inv'):
        f = series[s]
        lin.append(f"{s.replace('_', chr(92) + '_')} & {miles(int(f['W']))} & {miles(int(f['CyM']))} & {miles(CAJA0)} & "
                   f"{f['ordenes']} & {miles(int(f['comisiones']))} & {miles(int(f['perdida_max']))} \\\\")
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('backtest_series.tex', lin)
    for s, k in (('practica', 'Prac'), ('practica_inv', 'PracInv')):
        m[f'W{k}'], m[f'CyM{k}'] = miles(int(series[s]['W'])), miles(int(series[s]['CyM']))
        m[f'Ordenes{k}'] = series[s]['ordenes']
        m[f'Expo{k}'] = miles(100 * float(series[s]['exposicion']))

    # Resultado del testbench del curso (make tb)
    tb = open(os.path.join(RES, 'tb_oficial.txt')).read()
    for patron, k in (('Patrimonio final', 'TbW'), ('Ordenes ejecutadas', 'TbOrdenes'), ('Perdida maxima', 'TbPerdida'),
                      ('Comprar y mantener', 'TbCyM'), ('precio->decision', 'TbPeor')):
        m[k] = miles(int(re.search(patron + r':\s+(\d+)', tb)[1]))
    m['TbAprobados'] = re.search(r'aprobados: (\d/\d)', tb)[1]

    # Validacion con acciones tecnologicas reales (ref/validar.py)
    tec = leer_res('validacion_tec.csv')
    grupos = [('15 series de 5 min (60 días)', lambda f: f['ronda'] == 'completa' and f['intervalo'] == '5m', 'TecCinco'),
              ('15 series de 1 h (2 años)', lambda f: f['ronda'] == 'completa' and f['intervalo'] == '1h', 'TecHora'),
              ('rondas de 2000 ticks', lambda f: f['ronda'] != 'completa', 'TecRondas'),
              ('rondas en que la acción sube más de 8\\,\\%', lambda f: f['ronda'] != 'completa' and int(f['CyM']) > 10800, 'TecSube'),
              ('rondas en que la acción baja más de 8\\,\\%', lambda f: f['ronda'] != 'completa' and int(f['CyM']) < 9200, 'TecBaja')]
    lin = ['\\begin{tabular}{lrrrrrr}', '\\toprule',
           'Conjunto & $n$ & Agente & CyM & Agente/CyM & Gana a CyM & Exposición \\\\', '\\midrule']
    for nombre, cond, k in grupos:
        fs = [f for f in tec if cond(f)]
        w, c = [int(f['W']) for f in fs], [int(f['CyM']) for f in fs]
        expo = 100 * np.mean([float(f['expo']) for f in fs])
        lin.append(f"{nombre} & {len(fs)} & {miles(geo(w), 3)} & {miles(geo(c), 3)} & {miles(geo(w) / geo(c), 3)} & "
                   f"{sum(a > b for a, b in zip(w, c))}/{len(fs)} & {miles(expo)}\\,\\% \\\\")
        m[f'{k}Razon'], m[f'{k}Expo'], m[f'{k}Geo'] = miles(geo(w) / geo(c), 3), miles(expo), miles(geo(w), 3)
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('validacion_tec.tex', lin)

    # Estadisticas de la serie de practica que justifican el algoritmo
    pr = leer_csv()
    x = np.array(pr, float)
    d = np.diff(x)
    m['PracMin'], m['PracMax'], m['PracIni'], m['PracFin'] = int(x.min()), int(x.max()), pr[0], pr[-1]
    m['PracVR'] = miles((x[100:] - x[:-100]).var() / (100 * d.var()), 2)
    m['PracAC'] = miles(np.corrcoef(d[:-1], d[1:])[0, 1], 2)

    # Figura: practica y practica invertida, precio y patrimonio
    fig, axs = plt.subplots(2, 2, figsize=(7, 4.2), sharex='col')
    for col, (p, titulo) in enumerate(((pr, 'práctica'), (pr[::-1], 'práctica invertida'))):
        r = simular(p, Trader())
        q = (CAJA0 - 5) // p[0]
        axs[0, col].plot(p, color='0.25', lw=0.6)
        axs[0, col].set_title(titulo)
        axs[0, col].set_ylabel('precio $p_n$')
        axs[1, col].plot(r['W'], color='C0', lw=0.9, label='agente')
        axs[1, col].plot([CAJA0 - 5 - q * p[0] + q * x for x in p], color='C1', lw=0.8, label='comprar y mantener')
        axs[1, col].axhline(CAJA0, color='0.5', lw=0.8, label='no operar')
        axs[1, col].set_ylabel('patrimonio [\\$]')
        axs[1, col].set_xlabel('tick $n$')
    axs[1, 0].legend(fontsize=7, loc='upper left')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'series_ejemplo.pdf'))
    plt.close(fig)

    # Figura: como decide (un tramo de la practica con las dos medias y cuando esta dentro)
    a, b = 3000, 8000
    t = Trader()
    dentro, corta, larga = [], [], []
    for n, p in enumerate(pr[:b]):
        dentro.append(t.tick(p, 0) == t.COMPRAR)
        corta.append(t.S / 64)
        larga.append(t.SL / 512)
    x = np.arange(a, b)
    fig, ax = plt.subplots(figsize=(7, 2.9))
    ax.plot(x, pr[a:b], color='0.3', lw=0.6, label='precio')
    ax.plot(x, corta[a:b], color='C0', lw=0.9, label='media de 64')
    ax.plot(x, larga[a:b], color='C3', lw=0.9, label='media de 512')
    ax.fill_between(x, 0, 1, where=dentro[a:b], color='C2', alpha=0.15, transform=ax.get_xaxis_transform(),
                    label='dentro (comprar 63)')
    ax.set_xlabel('tick $n$')
    ax.set_ylabel('precio')
    ax.legend(fontsize=7, ncol=4, loc='upper left')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'decision.pdf'))
    plt.close(fig)

    # Figura: patrimonio por ronda contra comprar y mantener
    fig, axs = plt.subplots(1, 2, figsize=(7, 2.6), sharey=True)
    for ax, (clave, nombre) in zip(axs, FAMILIAS[:2]):
        fs = fams[clave]
        k = np.arange(len(fs))
        ax.bar(k - 0.2, [int(f['W']) for f in fs], 0.4, color='C0', label='agente')
        ax.bar(k + 0.2, [int(f['CyM']) for f in fs], 0.4, color='C1', label='comprar y mantener')
        ax.axhline(CAJA0, color='0.4', lw=0.8)
        ax.set_title(nombre, fontsize=9)
        ax.set_xlabel('ronda de 2000 ticks')
    axs[0].set_ylabel('patrimonio final [\\$]')
    axs[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'rondas.pdf'))
    plt.close(fig)


# --- 2. Mediciones por tick y co-diseno --------------------------------------------

def medidas(m):
    med = {f['variante']: f for f in leer_res('medidas_por_variante.csv')}
    syn = {f['variante']: f for f in leer_res('sintesis.csv')}
    presupuesto = (1e-4 - T_SPI) * F_CLK

    lin = ['\\begin{tabular}{lrrrrrrrrr}', '\\toprule',
           ' & \\multicolumn{2}{c}{IC} & \\multicolumn{2}{c}{Ciclos} & & \\multicolumn{2}{c}{Tiempo [$\\mu$s]}'
           ' & \\multicolumn{2}{c}{\\% de $T-T_\\text{SPI}$} \\\\',
           '\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){7-8}\\cmidrule(lr){9-10}',
           'Variante & prom. & peor & prom. & peor & CPI & prom. & peor & R2 & R3 \\\\', '\\midrule']
    for v, k in (('sw', 'Sw'), ('shift', 'Shift'), ('mul8', 'Mul'), ('mul8shift', 'MulShift')):
        x = med[v]
        cp, cw = float(x['ciclos_prom']), int(x['ciclos_max'])
        pct = [100 * cw / F_CLK / (T - T_SPI) for _, T in RONDAS]
        lin.append(f"{dagger(v)} & {miles(float(x['IC_prom']), 1)} & {x['IC_max']} & {miles(cp, 1)} & {cw} & "
                   f"{miles(float(x['CPI']), 2)} & {miles(cp / F_CLK * 1e6, 1)} & {miles(cw / F_CLK * 1e6, 1)} & "
                   f"{miles(pct[1], 1)} & {miles(pct[2], 1)} \\\\")
        m[f'CiclosProm{k}'], m[f'CiclosPeor{k}'] = miles(cp, 1), cw
        m[f'ICProm{k}'], m[f'CPI{k}'] = miles(float(x['IC_prom']), 1), miles(float(x['CPI']), 2)
        m[f'Palabras{k}'], m[f'TickCero{k}'] = x['palabras'], miles(int(x['ciclos_tick0']))
        m[f'Mops{k}'], m[f'MIPS{k}'] = miles(float(x['Mops_s']), 2), miles(float(x['MIPS']), 2)
        m[f'PctRtres{k}'] = miles(pct[2], 1)
        m[f'Speedup{k}'] = miles(float(med['sw']['ciclos_prom']) / cp, 2)
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('medidas.tex', lin)
    m['NTicks'] = miles(int(med['sw']['ticks']) + 16)
    m['OpsTick'] = miles(float(med['sw']['ops_utiles_tick']), 1)
    m['BytesTick'] = miles(float(med['sw']['bytes_tick']), 0)
    m['IntensidadOp'] = miles(float(med['sw']['ops_utiles_tick']) / float(med['sw']['bytes_tick']), 2)
    m['Presupuesto'] = miles(int(presupuesto))
    m['MulPorTick'] = miles(float(med['sw']['mul_por_tick']), 1)

    # Perfil sin 'espera' (detectar el precio y leer PRICE): los ciclos por tick se miden
    # desde que se leyo PRICE, asi el speedup de Amdahl es el mismo de la tabla de medidas.
    perf = {v: {f['categoria']: int(f['ciclos']) for f in leer_res(f'perfil_{v}.csv')
                if f['categoria'] != 'espera'} for v in med}
    tot = {v: sum(perf[v].values()) for v in perf}
    m['FracMul'] = miles(100 * perf['sw']['multiplicacion'] / tot['sw'], 1)
    m['FracDup'] = miles(100 * perf['sw']['duplicaciones'] / tot['sw'], 1)
    m['CiclosMulSw'] = miles(perf['sw']['multiplicacion'] / (float(med['sw']['mul_por_tick']) * float(med['sw']['ticks'])), 0)

    # Amdahl. El speedup s de la parte acelerada se predice antes de construir el hardware:
    #   shifter: cada cadena de k sumas (2k ciclos) pasa a ser un slli (2 ciclos);
    #   mul8:    cada llamada a mulsw pasa a ser un mul8 en su peor caso, 2 + 8 = 10 ciclos.
    n_mul = float(med['sw']['mul_por_tick']) * float(med['sw']['ticks'])
    hw_pred = {'duplicaciones': perf['shift']['slli (hw)'], 'multiplicacion': 10 * n_mul}
    lin = ['\\begin{tabular}{lrrrrr}', '\\toprule',
           'Variante & $f$ & $s$ predicho & $S$ Amdahl & $S$ medido & $S_\\text{máx}=1/(1-f)$ \\\\', '\\midrule']
    for v, partes, k in (('shift', ['duplicaciones'], 'Shift'), ('mul8', ['multiplicacion'], 'Mul'),
                         ('mul8shift', ['duplicaciones', 'multiplicacion'], 'MulShift')):
        sw_c = sum(perf['sw'][p] for p in partes)
        f = sw_c / tot['sw']
        s = sw_c / sum(hw_pred[p] for p in partes)
        pred, medido, smax = 1 / ((1 - f) + f / s), tot['sw'] / tot[v], 1 / (1 - f)
        lin.append(f"{dagger(v)} & {miles(100 * f, 1)}\\,\\% & {miles(s, 2)} & {miles(pred, 2)} & {miles(medido, 2)} & "
                   f"{miles(smax, 2)} \\\\")
        m[f'AmdahlF{k}'], m[f'AmdahlS{k}'] = miles(100 * f, 1), miles(s, 1)
        m[f'AmdahlPred{k}'], m[f'AmdahlMed{k}'], m[f'AmdahlMax{k}'] = miles(pred, 2), miles(medido, 2), miles(smax, 2)
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('amdahl.tex', lin)

    lin = ['\\begin{tabular}{lrrrrrrrr}', '\\toprule',
           'Variante & LC & \\% HX1K & LUT4 & FF & BRAM & $f_\\text{máx}$ [MHz] & Ciclos/tick & Mops útiles/s \\\\',
           '\\midrule']
    for v, k in (('base_original', 'Original'), ('sw', 'Sw'), ('shift', 'Shift'), ('mul8', 'Mul'), ('mul8shift', 'MulShift')):
        s = syn[v]
        cabe = s['cierra_timing'] != 'no cabe'
        fm = f"{miles(float(s['Fmax_min']), 1)}--{miles(float(s['Fmax_max']), 1)}" if cabe else 'no cabe'
        vm = 'sw' if v == 'base_original' else v
        lin.append(f"{dagger(v)} & {s['LC']} & {miles(float(s['LC_pct']), 1)} & {s['LUT4']} & {s['FF']} & {s['BRAM']} & {fm} & "
                   f"{miles(float(med[vm]['ciclos_prom']), 1)} & {miles(float(med[vm]['Mops_s']), 2)} \\\\")
        m[f'LC{k}'], m[f'LCPct{k}'] = s['LC'], miles(float(s['LC_pct']), 1)
        if cabe:
            m[f'Fmax{k}'] = fm
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('sintesis.tex', lin)
    m['AhorroRAM'] = int(syn['base_original']['LC']) - int(syn['sw']['LC'])
    m['LCLibres'] = 1280 - int(syn['sw']['LC'])
    m['CostoMul'] = int(syn['mul8']['LC']) - int(syn['sw']['LC'])
    m['CostoShift'] = int(syn['shift']['LC']) - int(syn['sw']['LC'])

    # Figura: histograma de ciclos por tick
    fig, ax = plt.subplots(figsize=(6.5, 2.6))
    for v, c in (('sw', 'C0'), ('shift', 'C1'), ('mul8', 'C2')):
        h = leer_res(f'ciclos_por_tick_{v}.csv')
        x = np.array([int(r['ciclos']) for r in h])
        y = np.array([int(r['ticks']) for r in h])
        ax.hist(x, bins=np.arange(100, 460, 4), weights=y, histtype='stepfilled', alpha=0.6, color=c,
                label=f"{NOMBRE[v]} (peor {x.max()})")
    ax.set_xlabel('ciclos por tick')
    ax.set_ylabel('ticks')
    ax.set_yscale('log')
    ax.legend(fontsize=7)
    ax.set_title(f'presupuesto de la ronda 3: {int(presupuesto)} ciclos', fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'ciclos_por_tick.pdf'))
    plt.close(fig)

    # Figura: perfil por variante, en ciclos promedio por tick
    cats = ['multiplicacion', 'mul8 (hw)', 'duplicaciones', 'slli (hw)', 'banderas', 'medias moviles', 'decision y E/S']
    vs = ['sw', 'shift', 'mul8', 'mul8shift']
    fig, ax = plt.subplots(figsize=(6.5, 2.3))
    izq = np.zeros(len(vs))
    for c, col in zip(cats, plt.cm.tab10(np.arange(len(cats)))):
        val = np.array([perf[v].get(c, 0) / float(med[v]['ticks']) for v in vs])
        ax.barh(range(len(vs)), val, left=izq, color=col, label=c, height=0.6)
        izq += val
    ax.set_yticks(range(len(vs)), [NOMBRE[v] for v in vs])
    ax.invert_yaxis()
    ax.set_xlabel('ciclos promedio por tick')
    ax.legend(fontsize=6, ncol=4, loc='upper center', bbox_to_anchor=(0.5, -0.38))
    fig.savefig(os.path.join(FIG, 'perfil.pdf'), bbox_inches='tight')
    plt.close(fig)

    # Figura: roofline con las definiciones de la clase (Bs = 4 B/ciclo, pico = 1 op cada 2 ciclos)
    fig, ax = plt.subplots(figsize=(4.8, 3.2))
    oi = np.logspace(-2, 1.3, 200)
    bs, pico = 4 * F_CLK / 1e6, F_CLK / 2 / 1e6
    ax.plot(oi, np.minimum(bs * oi, pico), 'k', lw=1.2)
    ax.text(0.012, bs * 0.012 * 1.5, f'memoria: {bs:.0f} MB/s', rotation=38, fontsize=7)
    ax.text(2.5, pico * 1.12, f'pico: {pico:.1f} MOPS', fontsize=7, ha='center')
    ax.axvline(pico / bs, color='0.6', lw=0.6, ls=':')
    for v, c, mk in (('sw', 'C0', 'o'), ('shift', 'C1', 's'), ('mul8', 'C2', '^'), ('mul8shift', '0.5', 'D')):
        x = float(med[v]['ops_utiles_tick']) / float(med[v]['bytes_tick'])
        y = float(med[v]['Mops_s'])
        ax.plot(x, y, mk, color=c, mfc='none' if v == 'mul8shift' else c,
                label=f"{NOMBRE[v]}: {y:.2f} MOPS" + (' (no cabe)' if v == 'mul8shift' else ''))
    if os.path.exists(os.path.join(RES, 'extremos', 'medidas_por_variante.csv')):
        x = leer_res(os.path.join('extremos', 'medidas_por_variante.csv'))[0]
        ax.plot(float(x['ops_utiles_tick']) / float(x['bytes_tick']), float(x['Mops_s']), '*', color='C3', ms=9,
                label=f"final (extremos): {float(x['Mops_s']):.2f} MOPS")
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel('intensidad aritmética [ops útiles / byte]')
    ax.set_ylabel('desempeño [MOPS útiles]')
    ax.set_ylim(0.3, 30)
    ax.legend(fontsize=7, loc='lower left')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'roofline.pdf'))
    plt.close(fig)

    # Figura: area contra ciclos
    fig, ax = plt.subplots(figsize=(4.4, 2.9))
    for v, c in (('sw', 'C0'), ('shift', 'C1'), ('mul8', 'C2'), ('mul8shift', '0.5')):
        x, y = int(syn[v]['LC']), float(med[v]['ciclos_prom'])
        ax.plot(x, y, 'o', color=c, mfc='none' if v == 'mul8shift' else c)
        ax.annotate(NOMBRE[v], (x, y), textcoords='offset points', xytext=(5, 4), fontsize=7)
    ax.axvline(1280, color='C3', lw=1, ls='--')
    ax.text(1288, 250, 'HX1K: 1280 LC', color='C3', fontsize=7, rotation=90)
    ax.set_xlabel('celdas lógicas (LC)')
    ax.set_ylabel('ciclos promedio por tick')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'area_vs_ciclos.pdf'))
    plt.close(fig)


# --- 3. Algoritmo de la competencia: extremos -----------------------------------------

def competencia(m):
    filas = leer_res('competencia.csv')
    fila = {(f['algoritmo'], f['ticks'], f['grupo']): f for f in filas}
    nombre = {'extremos': 'extremos (final)', 'tendencia': 'tendencia (anterior)', 'CyM': 'comprar y mantener'}
    lin = ['\\begin{tabular}{llrrrrrrr}', '\\toprule',
           'Ronda & Algoritmo & Geo. & Mediana & 5\\,\\% peor & Peor & Pierde & Gana a CyM & Pérd. máx. p95 [\\$] \\\\',
           '\\midrule']
    for ticks, txt in (('20000', '20\\,000 ticks'), ('2000', '2000 ticks')):
        for a in ('extremos', 'tendencia', 'CyM'):
            f = fila[(a, ticks, 'todas')]
            gana = f"{miles(100 * float(f['P_gana_CyM']))}\\,\\%" if f.get('P_gana_CyM') else '--'
            dd = miles(float(f['DD_p95'])) if f.get('DD_p95') else '--'
            lin.append(f"{txt if a == 'extremos' else ''} & {nombre[a]} & {miles(float(f['geo']), 3)} & "
                       f"{miles(float(f['mediana']), 3)} & {miles(float(f['p5']), 3)} & {miles(float(f['min']), 3)} & "
                       f"{miles(100 * float(f['P_pierde']), 1)}\\,\\% & {gana} & {dd} \\\\")
        if ticks == '20000':
            lin.append('\\midrule')
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('competencia.tex', lin)

    lin = ['\\begin{tabular}{lrrrrrrrr}', '\\toprule',
           'Ronda de 20\\,000 ticks & META & AAPL & NFLX & AMD & TSLA & 2022 & 2023 & 2024 \\\\', '\\midrule']
    for a in ('extremos', 'tendencia', 'CyM'):
        lin.append(nombre[a] + ''.join(f" & {miles(float(fila[(a, '20000', g)]['geo']), 3)}"
                                       for g in ('META', 'AAPL', 'NFLX', 'AMD', 'TSLA', '2022', '2023', '2024')) + ' \\\\')
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('competencia_grupos.tex', lin)

    for (a, t), k in ((('extremos', '20000'), 'Ext'), (('extremos', '2000'), 'ExtCorta'), (('tendencia', '20000'), 'Tend'),
                      (('tendencia', '2000'), 'TendCorta'), (('CyM', '20000'), 'Cym'), (('CyM', '2000'), 'CymCorta')):
        f = fila[(a, t, 'todas')]
        m[f'{k}Geo'], m[f'{k}Mediana'] = miles(float(f['geo']), 3), miles(float(f['mediana']), 3)
        m[f'{k}Pcinco'], m[f'{k}Peor'] = miles(float(f['p5']), 3), miles(float(f['min']), 3)
        m[f'{k}Pierde'] = miles(100 * float(f['P_pierde']), 1)
        if f.get('P_gana_CyM'):
            m[f'{k}GanaCym'] = miles(100 * float(f['P_gana_CyM']))
            m[f'{k}DDmed'], m[f'{k}DDpnoventa'] = miles(float(f['DD_mediana'])), miles(float(f['DD_p95']))
            m[f'{k}Expo'] = miles(100 * float(f['exposicion']))
    m['NVentanas'] = miles(int(fila[('extremos', '20000', 'todas')]['n']))
    for g, k in (('2022', 'Dosmilveintidos'), ('2023', 'Dosmilveintitres'), ('2024', 'Dosmilveinticuatro')):
        m[f'ExtGeo{k}'] = miles(float(fila[('extremos', '20000', g)]['geo']), 3)
        m[f'ExtPierde{k}'] = miles(100 * float(fila[('extremos', '20000', g)]['P_pierde']), 1)
        m[f'TendPierde{k}'] = miles(100 * float(fila[('tendencia', '20000', g)]['P_pierde']))

    # Montecarlo (ref/montecarlo.py)
    if os.path.exists(os.path.join(RES, 'montecarlo.csv')):
        mc = leer_res('montecarlo.csv')
        nombres = {'paseo': 'paseo aleatorio', 'sube': 'tendencia al alza (+40\\,\\%)',
                   'baja': 'tendencia a la baja ($-$30\\,\\%)', 'volatil': 'volatilidad triple',
                   'reversion': 'vuelve a la media', 'momentum': 'momentum',
                   'saltos': 'saltos de $\\pm$3\\,\\%', 'bootstrap': 'días reales al azar'}
        lin = ['\\begin{tabular}{lrrrrrrr}', '\\toprule',
               'Escenario & Geo. & 5\\,\\% peor & Peor & Pierde & Órdenes & Solo 100/255 & CyM \\\\', '\\midrule']
        for e in nombres:
            fin = [f for f in mc if f['escenario'] == e and f['variante'] == 'version D']
            base = [f for f in mc if f['escenario'] == e and f['variante'] == '100/255']
            if not fin:
                continue
            f, b = fin[0], base[0]
            lin.append(f"{nombres[e]} & {miles(float(f['geo']), 3)} & {miles(float(f['p5']), 3)} & "
                       f"{miles(float(f['peor']), 3)} & {miles(100 * float(f['P_pierde']), 1)}\\,\\% & "
                       f"{miles(float(f['ordenes']), 1)} & {miles(float(b['geo']), 3)} & {miles(float(f['CyM_geo']), 3)} \\\\")
        lin += ['\\bottomrule', '\\end{tabular}']
        guardar_tabla('montecarlo.tex', lin)
        m['MCN'] = miles(int(mc[0]['n']))
        m['MCPeor'] = miles(min(float(f['peor']) for f in mc if f['variante'] == 'version D'), 3)

    # practica_meta con los dos algoritmos
    from series import PRACTICA_META
    from trader import Extremos
    pm = leer_csv(PRACTICA_META)
    q = (CAJA0 - 5) // pm[0]
    for n, k in ((20000, ''), (2000, 'Corta')):
        m[f'MetaW{k}'] = miles(simular(pm[:n], Extremos())['W'][-1])
        m[f'MetaWTend{k}'] = miles(simular(pm[:n], Trader())['W'][-1])
        m[f'MetaCym{k}'] = miles(CAJA0 - 5 - q * pm[0] + q * pm[n - 1])
    m['MetaTickMax'], m['MetaTickMin'] = miles(pm.index(255)), miles(pm.index(100))

    # Medidas por tick del programa final (ref/verificar.py -> resultados/extremos/)
    x = leer_res(os.path.join('extremos', 'medidas_por_variante.csv'))[0]
    m['ExtPalabras'], m['ExtCiclosProm'], m['ExtCiclosPeor'] = x['palabras'], miles(float(x['ciclos_prom']), 1), x['ciclos_max']
    m['ExtIC'], m['ExtICPeor'], m['ExtCPI'] = miles(float(x['IC_prom']), 1), x['IC_max'], miles(float(x['CPI']), 2)
    m['ExtMops'], m['ExtMIPS'] = miles(float(x['Mops_s']), 2), miles(float(x['MIPS']), 2)
    m['ExtOpsTick'], m['ExtBytesTick'] = miles(float(x['ops_utiles_tick']), 1), miles(float(x['bytes_tick']), 0)
    m['ExtNTicks'] = miles(int(x['ticks']))
    m['ExtPctRtres'] = miles(100 * int(x['ciclos_max']) / F_CLK / (1e-4 - T_SPI), 1)
    tend = {f['variante']: f for f in leer_res('medidas_por_variante.csv')}
    m['ExtSpeedupMul'] = miles(float(tend['mul8']['ciclos_prom']) / float(x['ciclos_prom']), 0)
    m['ExtSpeedupSw'] = miles(float(tend['sw']['ciclos_prom']) / float(x['ciclos_prom']), 0)

    # Testbench del curso con el programa final (make tb / make tb-meta)
    for archivo, k in (('tb_oficial.txt', 'TbExt'), ('tb_meta.txt', 'TbMeta')):
        ruta = os.path.join(RES, archivo)
        if os.path.exists(ruta):
            tb = open(ruta).read()
            for patron, kk in (('Patrimonio final', 'W'), ('Ordenes ejecutadas', 'Ordenes'),
                               ('Perdida maxima', 'Perdida'), ('Comprar y mantener', 'CyM'),
                               ('precio->decision', 'Peor')):
                m[k + kk] = miles(int(re.search(patron + r':\s+(\d+)', tb)[1]))
            m[k + 'Aprobados'] = re.search(r'aprobados: (\d/\d)', tb)[1]

    # Figura: retorno hasta el final segun el nivel
    nr = leer_res('nivel_retorno.csv')
    fig, ax = plt.subplots(figsize=(6.2, 2.5))
    xs = [int(f['nivel_desde']) + 5 for f in nr]
    ys = [100 * float(f['retorno_medio_al_final']) for f in nr]
    ax.bar(xs, ys, width=8, color=['C2' if y > 0 else 'C3' for y in ys])
    ax.axhline(0, color='0.3', lw=0.6)
    ax.set_xlabel('nivel del precio normalizado')
    ax.set_ylabel('retorno hasta el final [%]')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'nivel_retorno.pdf'))
    plt.close(fig)

    # Figura: distribucion del patrimonio final en las ventanas (ronda de 20 000)
    v = leer_res('competencia_ventanas.csv')
    fig, ax = plt.subplots(figsize=(6.2, 2.6))
    bins = np.arange(0.35, 2.65, 0.05)
    for col, c, et in (('CyM_20000', 'C1', 'comprar y mantener'), ('W_tendencia_20000', 'C0', 'tendencia (anterior)'),
                       ('W_extremos_20000', 'C2', 'extremos (final)')):
        ax.hist([int(f[col]) / CAJA0 for f in v], bins=bins, histtype='stepfilled', alpha=0.5, color=c, label=et)
    ax.axvline(1, color='0.3', lw=0.8, ls=':')
    ax.set_xlabel('patrimonio final / \\$10.000')
    ax.set_ylabel('ventanas')
    ax.legend(fontsize=7, loc='upper left')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'competencia_hist.pdf'))
    plt.close(fig)

    # Figura: practica_meta con el algoritmo final
    r = simular(pm, Extremos())
    fig, axs = plt.subplots(2, 1, figsize=(6.5, 3.6), sharex=True)
    axs[0].plot(pm, color='0.25', lw=0.5)
    dentro = np.array([d == 0x7F for d in r['decisiones']])
    axs[0].fill_between(np.arange(len(pm)), 0, 1, where=dentro, color='C2', alpha=0.2,
                        transform=axs[0].get_xaxis_transform(), label='dentro')
    for y in (100, 220, 255):
        axs[0].axhline(y, color='C3', lw=0.6, ls='--')
    axs[0].set_ylabel('precio')
    axs[0].legend(fontsize=7, loc='lower left')
    axs[1].plot(r['W'], color='C2', lw=0.9, label='extremos')
    axs[1].plot([CAJA0 - 5 - q * pm[0] + q * x for x in pm], color='C1', lw=0.8, label='comprar y mantener')
    axs[1].axhline(CAJA0, color='0.5', lw=0.8, label='no operar')
    axs[1].set_ylabel('patrimonio [\\$]')
    axs[1].set_xlabel('tick $n$')
    axs[1].legend(fontsize=7, loc='upper left')
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, 'practica_meta.pdf'))
    plt.close(fig)


def referencias_y_extremos(m):
    """Tablas del programa final: comparacion con las dos referencias en la practica nueva
    (patrimonio, ordenes, comisiones, perdida maxima) y mediciones por tick de trade.s."""
    from mercado import NoOperar, caida_maxima, comprar_y_mantener
    from series import PRACTICA_META
    from trader import Extremos
    pm = leer_csv(PRACTICA_META)
    ag = simular(pm, Extremos())
    no = simular(pm, NoOperar())
    q = (CAJA0 - 5) // pm[0]
    w_cym = [CAJA0 - 5 - q * pm[0] + q * x for x in pm]
    filas = [('Agente (versión D)', ag['W'][-1], ag['ordenes'], ag['comisiones'], caida_maxima(ag['W'])),
             ('No operar', no['W'][-1], 0, 0, 0),
             ('Comprar y mantener', comprar_y_mantener(pm), 1, 5, caida_maxima(w_cym))]
    lin = ['\\begin{tabular}{lrrrr}', '\\toprule',
           'Estrategia & Patrimonio final [\\$] & Órdenes & Comisiones [\\$] & Pérdida máxima [\\$] \\\\', '\\midrule']
    for nombre, w, o, c, d in filas:
        lin.append(f'{nombre} & {miles(w)} & {o} & {miles(c)} & {miles(d)} \\\\')
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('referencias.tex', lin)
    m['RefW'], m['RefOrdenes'] = miles(filas[0][1]), filas[0][2]
    m['RefComisiones'], m['RefPerdida'] = miles(filas[0][3]), miles(filas[0][4])
    m['RefCymPerdida'] = miles(filas[2][4])

    x = leer_res(os.path.join('extremos', 'medidas_por_variante.csv'))[0]
    cp, cw = float(x['ciclos_prom']), int(x['ciclos_max'])
    icp, icw = float(x['IC_prom']), int(x['IC_max'])
    lin = ['\\begin{tabular}{lrr}', '\\toprule', 'Métrica & Promedio & Peor caso \\\\', '\\midrule',
           f'Instrucciones ejecutadas (IC) & {miles(icp, 1)} & {icw} \\\\',
           f'Ciclos & {miles(cp, 1)} & {cw} \\\\',
           f"CPI & {miles(float(x['CPI']), 2)} & -- \\\\",
           f'Tiempo de ejecución a 25\\,MHz [$\\mu$s] & {miles(cp / F_CLK * 1e6, 2)} & {miles(cw / F_CLK * 1e6, 2)} \\\\']
    for r, T in RONDAS:
        lin.append(f'\\% de $T-T_\\text{{SPI}}$, ronda {r} & {miles(100 * cp / F_CLK / (T - T_SPI), 2)}'
                   f' & {miles(100 * cw / F_CLK / (T - T_SPI), 2)} \\\\')
    lin += ['\\bottomrule', '\\end{tabular}']
    guardar_tabla('extremos_medidas.tex', lin)
    m['ExtTiempoProm'] = miles(cp / F_CLK * 1e6, 2)
    m['ExtTiempoPeor'] = miles(cw / F_CLK * 1e6, 2)
    m['ExtTickCero'] = x['ciclos_tick0']


if __name__ == '__main__':
    os.makedirs(FIG, exist_ok=True)
    for viejo in os.listdir(TAB) if os.path.isdir(TAB) else []:
        os.remove(os.path.join(TAB, viejo))
    m = {}
    backtest(m)
    medidas(m)
    competencia(m)
    referencias_y_extremos(m)
    e = leer_equ(PROGRAMAS['tendencia'])
    for k, nombre in (('A_ENTRA', 'AEntra'), ('A_SALE', 'ASale'), ('C_SUBE', 'CSube'), ('C_BAJA', 'CBaja'), ('B_EXCESO', 'BExceso')):
        m[nombre] = e[k]
    lin = ['% GENERADO por ref/analisis.py: numeros que se citan en el texto. No editar a mano.']
    lin += [f'\\newcommand{{\\{k}}}{{{v}}}' for k, v in m.items()]
    guardar_tabla('numeros.tex', lin)
    print('figuras en', os.path.normpath(FIG), '| tablas en', os.path.normpath(TAB), '|', len(m), 'macros')
