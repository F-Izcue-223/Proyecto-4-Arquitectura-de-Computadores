"""Simula el agente como lo haria la FPGA maestra y muestra el resultado.

Usa ref/trader.py (igual instruccion por instruccion a sw/trade.s: lo comprueba
ref/verificar.py) con las reglas de la maestra (tb/tb_proyecto_4.sv, tarea ejecutar).
Imprime patrimonio, ordenes, perdida maxima y comprar y mantener, y guarda un grafico
como la pantalla del profesor en build/simulacion.png.

Ejemplos (desde la raiz del repositorio):
  python tools/simular.py                              practica_meta completa (20 000 ticks)
  python tools/simular.py --serie tb/practica.csv --ticks 2000
  python tools/simular.py --accion AMD --desde "2022-01-10 10:20"
                                                       una ventana real de 20 000 minutos
                                                       (necesita data/minuto, ver ref/minuto.py)
  python tools/simular.py --azar 200                   200 ventanas al azar de las 5 acciones
                                                       2022-2024: ganancia y riesgo
  python tools/simular.py --buscar AMD 2022-01 10:20 8315
                                                       encuentra la serie que mostro la maestra (accion,
                                                       mes, hora de inicio, comprar-y-mantener) y corre
                                                       las tres versiones (A, B, C)
  python tools/simular.py --version todas              compara las versiones A, B y C
  python tools/simular.py --accion TSLA --desde "2023-05-01 09:30" --rtl
                                                       ademas corre el testbench del curso (RTL)
                                                       con esa serie (necesita OSS CAD Suite)

Para cambiar el algoritmo: editar las .equ de sw/trade.s (MINIMO, MAXIMO,
TOMA_GANANCIA, RECOMPRA). Este script las lee de ahi.
"""
import argparse
import os
import subprocess
import sys

import numpy as np

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(RAIZ, 'ref'))
from mercado import CAJA0, caida_maxima, comprar_y_mantener, simular  # noqa: E402
from series import leer  # noqa: E402
from trader import Extremos, Trader, leer_equ, PROGRAMA  # noqa: E402
sys.path.insert(0, os.path.join(RAIZ, 'tools'))
from versiones import VERSIONES, constantes  # noqa: E402


def ventana(accion, desde):
    from minuto import LARGO, cargar, normalizar
    horas, x = cargar(accion)
    s = next((i for i, h in enumerate(horas) if h.startswith(desde.replace('T', ' '))), None)
    if s is None:
        raise SystemExit(f'no hay un minuto de {accion} que empiece con "{desde}" (formato "AAAA-MM-DD HH:MM")')
    if s + LARGO > len(x):
        raise SystemExit('la ventana se sale de los datos (termina despues del 2024-12-31)')
    return [int(v) for v in normalizar(x[s:s + LARGO])], f'{accion} desde {horas[s][:16]}'


def buscar(accion, mes, hora, cym_pantalla):
    """La maestra muestra la accion, el mes, la hora de inicio y 'comprar al inicio y mantener':
    con eso se encuentra la ventana exacta (como AMD ene 2022 10:20 -> 2022-01-10, CyM $8.315)."""
    from minuto import LARGO, cargar, normalizar
    horas, x = cargar(accion)
    hallados = []
    for s, h in enumerate(horas):
        if h.startswith(mes) and h[11:16] == hora and s + LARGO <= len(x):
            p = [int(v) for v in normalizar(x[s:s + LARGO])]
            if comprar_y_mantener(p) == cym_pantalla:
                hallados.append((h[:16], p))
    return hallados


def resumen(precios, nombre, version=None):
    r = simular(precios, Extremos(constantes(version)) if version else Trader())
    W = r['W']
    cym = comprar_y_mantener(precios)
    q = (CAJA0 - 5) // precios[0]
    cym_serie = [CAJA0 - 5 - q * precios[0] + q * p for p in precios]
    print(f'\n{nombre}: {len(precios)} ticks, precio {precios[0]} -> {precios[-1]} '
          f'(min {min(precios)} en el tick {precios.index(min(precios))}, '
          f'max {max(precios)} en el tick {precios.index(max(precios))})')
    print(f'  patrimonio final     ${W[-1]:>8,}   ({100 * (W[-1] / CAJA0 - 1):+.1f} %)'.replace(',', '.'))
    print(f'  comprar y mantener   ${cym:>8,}   ({100 * (cym / CAJA0 - 1):+.1f} %)'.replace(',', '.'))
    print(f'  vs mantener          {100 * (W[-1] / cym - 1):+.1f} %')
    print(f'  ordenes ejecutadas   {r["ordenes"]}   (comisiones ${r["comisiones"]})')
    print(f'  perdida maxima       ${caida_maxima(W):,}'.replace(',', '.'))
    print(f'  tiempo con acciones  {100 * r["exposicion"]:.0f} %')
    return W, cym_serie


def grafico(precios, W, cym_serie, nombre):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 5.5), sharex=True)
    a1.plot(precios, color='0.3', lw=0.6)
    e = leer_equ(PROGRAMA)
    for k in ('MINIMO', 'MAXIMO', 'TOMA_GANANCIA', 'RECOMPRA'):
        if k in e:
            a1.axhline(e[k], color='C3', lw=0.5, ls='--')
    a1.set_ylabel('precio')
    a1.set_title(nombre)
    a2.plot(W, color='C2', lw=1, label='agente')
    a2.plot(cym_serie, color='C1', lw=0.8, ls='--', label='comprar al inicio y mantener')
    a2.axhline(CAJA0, color='0.6', lw=0.6)
    a2.set_ylabel('patrimonio [$]')
    a2.set_xlabel('tick')
    a2.legend(loc='upper left', fontsize=8)
    fig.tight_layout()
    ruta = os.path.join(RAIZ, 'build', 'simulacion.png')
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    fig.savefig(ruta, dpi=110)
    print(f'  grafico: {os.path.relpath(ruta, RAIZ)}')


def azar(n, semilla):
    from minuto import ventanas
    rng = np.random.default_rng(semilla)
    V = ventanas(250)
    idx = rng.choice(len(V), size=min(n, len(V)), replace=False)
    W, C = [], []
    for i in idx:
        p = [int(v) for v in V[i][2]]
        W.append(simular(p, Trader())['W'][-1] / CAJA0)
        C.append(comprar_y_mantener(p) / CAJA0)
    W, C = np.array(W), np.array(C)
    print(f'\n{len(W)} ventanas al azar (META, AAPL, NFLX, AMD, TSLA 2022-2024), patrimonio final / $10.000:')
    for nombre, x in (('agente', W), ('comprar y mantener', C)):
        print(f'  {nombre:20s} media geo {np.exp(np.log(x).mean()):.3f}  mediana {np.median(x):.3f}  '
              f'peor {x.min():.3f}  mejor {x.max():.3f}  pierde en {100 * np.mean(x < 1):.1f} %')
    print(f'  el agente le gana a comprar y mantener en {100 * np.mean(W > C):.0f} % de las ventanas')


def rtl(precios, version=None):
    """Corre el testbench del curso (copia con esta serie) sobre el RTL, con el programa de la version."""
    from versiones import defines
    ruta = os.path.join(RAIZ, 'build', 'serie_simulada.csv')
    with open(ruta, 'w', newline='\n') as f:
        f.write('tick,price\n' + ''.join(f'{i},{p}\n' for i, p in enumerate(precios)))
    eq = ' '.join(defines(version)) if version else ''
    print(f'\nTestbench del curso con esta serie ({len(precios)} ticks, version {version or "A"}; '
          'puede tardar varios minutos)...')
    r = subprocess.run(['make', 'tb-meta', 'TB_SERIE=build/serie_simulada.csv', f'TB_NTICKS={len(precios)}',
                        f'PY={sys.executable}', f'EQU={eq}'], cwd=RAIZ, capture_output=True, text=True)
    if eq:   # dejar sw/trade.hex en la version A (la de build/pochoco.bin)
        subprocess.run(['make', 'hex', f'PY={sys.executable}'], cwd=RAIZ, capture_output=True, text=True)
    lineas = [l for l in (r.stdout + r.stderr).splitlines()
              if l.startswith(('Patrimonio', 'Ordenes', 'Perdida', 'Comprar', 'Peor', 'PASS', 'FAIL', 'Testbenchs'))]
    print('\n'.join('  ' + l for l in lineas) if lineas else (r.stdout + r.stderr)[-2000:])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--serie', default=os.path.join('tb', 'practica_meta.csv'), help='CSV tick,price o .txt')
    ap.add_argument('--ticks', type=int, default=20000)
    ap.add_argument('--accion', help='META, AAPL, NFLX, AMD o TSLA (con --desde)')
    ap.add_argument('--desde', help='"AAAA-MM-DD HH:MM" (hora de Nueva York, horario de mercado)')
    ap.add_argument('--azar', type=int, help='N ventanas al azar: resumen de ganancia y riesgo')
    ap.add_argument('--semilla', type=int, default=1)
    ap.add_argument('--rtl', action='store_true', help='ademas correr el testbench del curso sobre el RTL')
    ap.add_argument('--buscar', nargs=4, metavar=('ACCION', 'AAAA-MM', 'HH:MM', 'CYM'),
                    help='encuentra la serie de la maestra: accion, mes, hora de inicio y el valor de '
                         '"comprar al inicio y mantener" de la pantalla; corre las tres versiones')
    ap.add_argument('--version', help='A, B, C (tools/versiones.py) o "todas" para compararlas en la misma serie')
    a = ap.parse_args()
    print(f'programa: {os.path.relpath(PROGRAMA, RAIZ)}  constantes: ' +
          ', '.join(f'{k}={v}' for k, v in leer_equ(PROGRAMA).items() if k not in ('COMPRAR', 'VENDER')))
    if a.azar:
        azar(a.azar, a.semilla)
        return
    if a.buscar:
        acc, mes, hora, cym = a.buscar
        hallados = buscar(acc.upper(), mes, hora, int(cym.replace('.', '').replace('$', '')))
        if not hallados:
            raise SystemExit('no hay ninguna ventana con ese mes, hora y comprar-y-mantener (revisa los datos)')
        for h, _ in hallados:
            print(f'  ventana: {acc.upper()} desde {h}')
        precios, nombre = hallados[0][1], f'{acc.upper()} desde {hallados[0][0]}'
        a.version = a.version or 'todas'
    elif a.accion:
        precios, nombre = ventana(a.accion.upper(), a.desde or '')
    else:
        precios, nombre = leer(os.path.join(RAIZ, a.serie))[:a.ticks], os.path.basename(a.serie)
    if a.version and a.version.lower() == 'todas':
        print(f'\n{nombre}: las tres versiones (tools/versiones.py)')
        for v, (nom, _) in VERSIONES.items():
            r = simular(precios, Extremos(constantes(v)))
            print(f'  {v} {nom:16s} patrimonio ${r["W"][-1]:>7,}  ordenes {r["ordenes"]:2d}  '
                  f'perdida max ${caida_maxima(r["W"]):,}'.replace(',', '.'))
        print(f'  comprar y mantener   ${comprar_y_mantener(precios):>7,}'.replace(',', '.'))
        return
    if a.version:
        nombre += f' (version {a.version.upper()}: {VERSIONES[a.version.upper()][0]})'
    W, cym_serie = resumen(precios, nombre, a.version.upper() if a.version else None)
    grafico(precios, W, cym_serie, nombre)
    if a.rtl:
        rtl(precios, a.version.upper() if a.version else None)


if __name__ == '__main__':
    main()
