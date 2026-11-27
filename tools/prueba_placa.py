"""Arma la ROM de la maestra embebida (rtl/prueba_placa) para probar trade.s en la placa.

rom[n] = {byte esperado en la transaccion n, precio n}, 16 bits en hexadecimal.
El byte esperado sale de ref/trader.py: en la transaccion 0 es 0x00 (reset de
DECISION) y en la n es la decision que trader.py tomo con el precio n-1. Se agrega
una transaccion final (repite el ultimo precio) para leer la ultima decision.

Uso:  python tools/prueba_placa.py [serie.txt] [N]     (con serie: sus primeros N precios, 1000
      por defecto; sin argumentos: los dos trozos de practica_meta descritos abajo)
"""
import os
import sys

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(RAIZ, 'ref'))
from mercado import simular  # noqa: E402
from series import leer  # noqa: E402
from trader import Trader  # noqa: E402

if len(sys.argv) > 1:
    serie = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    precios = leer(serie)[:n]
else:
    # Por defecto: dos trozos de tb/practica_meta.csv para pasar por todas las ramas de
    # trade.s ("extremos"): alrededor del maximo (255, tick 10965: el techo baja a 225)
    # y despues alrededor del minimo (100, tick 17084: compra y el piso sube a 120, y
    # vuelve a pasar por precios entre 100 y 120). 500 + 500 precios.
    serie = os.path.join(RAIZ, 'tb', 'practica_meta.csv')
    m = leer(serie)
    precios = m[10700:11200] + m[16800:17300]
r = simular(precios, Trader())
esperado = [0] + r['decisiones']
precios = precios + [precios[-1]]
os.makedirs(os.path.join(RAIZ, 'build'), exist_ok=True)
with open(os.path.join(RAIZ, 'build', 'prueba_rom.hex'), 'w', newline='\n') as f:
    f.writelines(f'{e:02x}{p:02x}\n' for e, p in zip(esperado, precios))
ordenes = sum(1 for d in r['decisiones'] if d)
print(f'{os.path.basename(serie)}: {len(precios)} transacciones, {ordenes} decisiones de compra/venta; '
      f'patrimonio final segun trader.py: ${r["W"][-1]}')
