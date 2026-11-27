"""Verifica el programa contra ref/trader.py y mide cada tick (IC, ciclos, CPI).

Programa: sw/trade.s (extremos) o, con ALGO=tendencia, sw/trade_tendencia.s.

1. Ensambla el programa en las variantes de hardware (build/trade_<v>.hex).
2. Corre cada variante en el simulador del Espino (ref/espino_iss.py) sobre las
   series, y comprueba que la decision de cada tick sea la misma que la de
   trader.py.
3. Reporta IC, ciclos y CPI por tick (promedio y peor caso), el tiempo a la
   frecuencia del reloj y el margen contra el periodo T de cada ronda.
4. Perfil: en que parte del codigo se van los ciclos (para la ley de Amdahl).

Uso:  python ref/verificar.py [--rapido]     (--rapido: 1 de cada 7 series y los CSV en build/)
      ALGO=tendencia python ref/verificar.py     (el estudio anterior, CSV en resultados/)
Con extremos los CSV van a resultados/extremos/.
"""
import csv
import os
import sys
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.join(AQUI, '..')
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(RAIZ, 'tools'))
import pochoasm  # noqa: E402
from espino_iss import Variante, correr  # noqa: E402
from mercado import simular  # noqa: E402
from series import competencia, todas  # noqa: E402
from trader import ALGO, PROGRAMA, Trader  # noqa: E402

VARIANTES = {
    'sw':        ({'HW_MUL': 0}, Variante()),
    'shift':     ({'HW_MUL': 0, 'HW_SHIFT': 1}, Variante(shifter=True)),
    'mul8':      ({'HW_MUL': 1}, Variante(mul8=True)),
    'mul8shift': ({'HW_MUL': 1, 'HW_SHIFT': 1}, Variante(shifter=True, mul8=True)),
}
RONDAS = {1: 10e-3, 2: 1e-3, 3: 0.1e-3}       # periodo T de cada ronda [s]
SECCIONES = ['inicio', 'espera', 'medias', 'desvios', 'caida', 'tendencia', 'exceso', 'decidir', 'mulsw']
NOMBRE_SECCION = {'inicio': 'arranque', 'espera': 'espera', 'medias': 'medias moviles',
                  'desvios': 'desvios', 'caida': 'banderas', 'tendencia': 'banderas',
                  'exceso': 'banderas', 'decidir': 'decision y E/S', 'mulsw': 'multiplicacion'}
# extremos no multiplica ni desplaza: las cuatro variantes dan el mismo programa y se
# mide solo la de la competencia (Espino original). tendencia: las cuatro, como antes.
CORRER = list(VARIANTES) if ALGO == 'tendencia' else ['sw']


def ensamblar(nombre, defines):
    with open(PROGRAMA, encoding='utf-8') as f:
        src = f.read()
    labels = {}
    words, _ = pochoasm.assemble(src, defines, labels)
    os.makedirs(os.path.join(RAIZ, 'build'), exist_ok=True)
    ruta = os.path.join(RAIZ, 'build', f'trade_{nombre}.hex')
    with open(ruta, 'w', newline='\n') as f:
        f.writelines(f'{w:08x}\n' for _, w, _ in words)
    return ruta, words, labels, src.splitlines()


def clasificar(words, labels, lineas):
    """pc -> categoria. Lo que esta en el .else de un .if HW_MUL es 'multiplicacion
    por software'; en el .else de un .if HW_SHIFT, 'duplicaciones por software'.
    En la rama .if, la instruccion de hardware. El resto, por seccion."""
    bloque = {}
    pila = []
    for n, txt in enumerate(lineas, 1):
        t = txt.split('#')[0].split()
        if t and t[0] == '.if':
            pila.append([t[1], True])
        elif t and t[0] == '.else':
            pila[-1][1] = False
        elif t and t[0] == '.endif':
            pila.pop()
        else:
            bloque[n] = [tuple(x) for x in pila]
    inicio_seccion = sorted((labels[s], s) for s in SECCIONES if s in labels)
    cat = {}
    for pc, _, n in words:
        b = dict(bloque.get(n, []))
        if b.get('HW_MUL') is False:
            cat[pc] = 'multiplicacion'
        elif b.get('HW_MUL') is True:
            cat[pc] = 'mul8 (hw)'
        elif b.get('HW_SHIFT') is False:
            cat[pc] = 'duplicaciones'
        elif b.get('HW_SHIFT') is True:
            cat[pc] = 'slli (hw)'
        else:
            sec = [s for a, s in inicio_seccion if a <= pc][-1]
            cat[pc] = NOMBRE_SECCION[sec]
    return cat


def main():
    rapido = '--rapido' in sys.argv
    # con --rapido los CSV van a build/ para no pisar los resultados completos del informe
    salida = os.path.join(RAIZ, 'build' if rapido else 'resultados')
    if ALGO != 'tendencia':
        salida = os.path.join(salida, ALGO)    # los CSV del estudio anterior quedan donde estaban
    series = todas() if ALGO == 'tendencia' else {**competencia(), **todas()}
    if rapido:
        series = dict(list(series.items())[::7])
    print(f'{len(series)} series, {sum(len(v) for v in series.values())} ticks')

    # decisiones de referencia y operaciones utiles por tick
    ref, ops = {}, []
    for nombre, precios in series.items():
        t = Trader()
        r = simular(precios, t)
        ref[nombre] = r['decisiones']
        ops += t.ops[1:]
    ops_tick = sum(ops) / len(ops)
    print(f'operaciones utiles por tick (trader.py): promedio {ops_tick:.1f}, max {max(ops)}')

    os.makedirs(os.path.join(salida), exist_ok=True)
    resumen = []
    for vnombre in CORRER:
        defines, variante = VARIANTES[vnombre]
        hexf, words, labels, lineas = ensamblar(vnombre, defines)
        cat = clasificar(words, labels, lineas)
        perfil_cat = defaultdict(int)
        llamadas_mul = 0
        ticks, ok, peor, peor_ic = [], True, (0, ''), 0
        for nombre, precios in series.items():
            dec, med, cpu = correr(hexf, precios, variante, perfil=True)
            dref = ref[nombre]
            if dec != dref:
                k = next(i for i in range(len(dec)) if dec[i] != dref[i])
                print(f'  DIFERENCIA {vnombre} {nombre}: tick {k}, asm={dec[k]:#x} ref={dref[k]:#x}')
                ok = False
            ticks += med[1:]                       # el tick 0 (llenar el buffer) aparte
            for pc, c in cpu.perfil.items():
                perfil_cat[cat[pc]] += c
            if 'mulsw' in labels:            # 'li t1, 0' al entrar a mulsw: 2 ciclos por llamada
                llamadas_mul += cpu.perfil.get(labels['mulsw'], 0) // 2
            m = max(med[1:], key=lambda x: x[1])
            if m[1] > peor[0]:
                peor = (m[1], nombre)
            peor_ic = max(peor_ic, max(x[0] for x in med[1:]))
            tick0 = med[0][1]
        ic = [x[0] for x in ticks]
        cy = [x[1] for x in ticks]
        by = [x[2] for x in ticks]
        fila = {
            'variante': vnombre, 'palabras': len(words), 'decisiones_identicas': ok,
            'ticks': len(cy), 'IC_prom': sum(ic) / len(ic), 'IC_max': peor_ic,
            'ciclos_prom': sum(cy) / len(cy), 'ciclos_max': peor[0], 'serie_peor': peor[1],
            'CPI': sum(cy) / sum(ic), 'ciclos_tick0': tick0,
            'ops_utiles_tick': ops_tick, 'bytes_tick': sum(by) / len(by),
            'Mops_s': ops_tick / (sum(cy) / len(cy) / 25e6) / 1e6,
            'MIPS': 25e6 / (sum(cy) / sum(ic)) / 1e6,
            'mul_por_tick': llamadas_mul / sum(len(v) for v in series.values()),
        }
        resumen.append(fila)
        total = sum(perfil_cat.values())
        print(f"\n== {vnombre}: {len(words)} palabras; decisiones identicas a trader.py: {'SI' if ok else 'NO'}")
        print(f"   IC/tick prom {fila['IC_prom']:.1f}  max {peor_ic};  ciclos/tick prom {fila['ciclos_prom']:.1f}"
              f"  max {peor[0]} ({peor[1]});  CPI {fila['CPI']:.3f};  tick 0 (arranque) {tick0} ciclos")
        print(f"   {fila['Mops_s']:.2f} Mops utiles/s, {fila['MIPS']:.2f} MIPS, {fila['bytes_tick']:.1f} bytes/tick")
        for k, v in sorted(perfil_cat.items(), key=lambda kv: -kv[1]):
            print(f'     {k:16s} {100 * v / total:5.1f} %')
        with open(os.path.join(salida, f'perfil_{vnombre}.csv'), 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['categoria', 'ciclos', 'fraccion'])
            for k, v in sorted(perfil_cat.items(), key=lambda kv: -kv[1]):
                w.writerow([k, v, f'{v / total:.4f}'])
        # histograma de ciclos por tick
        hist = defaultdict(int)
        for c in cy:
            hist[c] += 1
        with open(os.path.join(salida, f'ciclos_por_tick_{vnombre}.csv'), 'w', newline='') as fh:
            w = csv.writer(fh)
            w.writerow(['ciclos', 'ticks'])
            for c in sorted(hist):
                w.writerow([c, hist[c]])

    with open(os.path.join(salida, 'medidas_por_variante.csv'), 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(resumen[0].keys()))
        w.writeheader()
        w.writerows(resumen)

    print('\nMargen contra el periodo de cada ronda (peor tick, 25 MHz):')
    for f in resumen:
        t = f['ciclos_max'] / 25e6
        print(f"  {f['variante']:10s} peor tick {f['ciclos_max']:5d} ciclos = {t * 1e6:6.1f} us   " +
              '  '.join(f'R{r}: {100 * t / T:5.1f}% de T' for r, T in RONDAS.items()))
    if not all(f['decisiones_identicas'] for f in resumen):
        sys.exit(1)


if __name__ == '__main__':
    main()
