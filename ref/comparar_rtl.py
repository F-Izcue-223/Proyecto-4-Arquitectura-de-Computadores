"""Compara la simulacion del RTL (sim/tb_trade.v) con trader.py y con el simulador.

Uso:
  python ref/comparar_rtl.py --serie <serie.csv|txt> <N> <salida.txt>
      deja los primeros N precios en un archivo de un precio por linea (lo que lee tb_trade.v)
  python ref/comparar_rtl.py <variante> <serie.txt> <salida_de_tb_trade.txt>
      revisa tres cosas:
        1. que el byte que la maestra leyo en cada transaccion sea la decision de
           trader.py para el tick anterior (en la transaccion 0 sale 0x00, el reset);
        2. que el programa haya terminado cada tick antes del siguiente (deadline);
        3. que los ciclos e IC de cada tick en el RTL sean iguales a los del simulador
           de instrucciones (asi el modelo de ciclos de espino_iss.py queda validado).
"""
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from espino_iss import correr  # noqa: E402
from mercado import simular  # noqa: E402
from series import leer  # noqa: E402
from trader import Trader  # noqa: E402
from verificar import VARIANTES  # noqa: E402


def main():
    if sys.argv[1] == '--serie':
        precios = leer(sys.argv[2])[:int(sys.argv[3])]
        with open(sys.argv[4], 'w', newline='\n') as f:
            f.writelines(f'{p}\n' for p in precios)
        return
    variante, serie, salida = sys.argv[1:4]
    precios = leer(serie)
    filas = [list(map(int, l.split())) for l in open(salida) if l.strip()]
    leidos = [f[2] for f in filas]
    esperado = [0] + simular(precios, Trader())['decisiones']
    malas = [n for n in range(len(esperado)) if leidos[n] != esperado[n]]

    hexf = os.path.join(AQUI, '..', 'build', f'trade_{variante}.hex')
    _, med_iss, _ = correr(hexf, precios, VARIANTES[variante][1])
    rtl = [(f[4], f[3]) for f in filas[:len(precios)]]
    sin_terminar = [n for n, (ic, cy) in enumerate(rtl) if cy < 0]
    distintos = [n for n in range(len(precios)) if rtl[n] != med_iss[n][:2]]

    print(f'{variante} {os.path.basename(serie)}: {len(precios)} ticks')
    print(f'  bytes leidos por la maestra = decisiones de trader.py: '
          f"{'SI' if not malas else 'NO, primer tick distinto ' + str(malas[0])}")
    print(f'  ticks sin terminar antes del siguiente: {len(sin_terminar)}')
    if distintos:
        n = distintos[0]
        print(f'  ciclos e IC del RTL = simulador de instrucciones: NO en {len(distintos)} ticks, '
              f'primero {n}: rtl {rtl[n]} iss {med_iss[n][:2]}')
    else:
        print('  ciclos e IC del RTL = simulador de instrucciones: SI')
    cy = [c for _, c in rtl[1:]]
    print(f'  ciclos por tick (sin el 0): promedio {sum(cy) / len(cy):.1f}, peor {max(cy)}; '
          f'tick 0 (llenar los buffers): {rtl[0][1]}')
    if malas or sin_terminar or distintos:
        sys.exit(1)


if __name__ == '__main__':
    main()
