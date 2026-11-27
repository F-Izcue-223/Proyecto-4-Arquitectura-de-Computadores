"""Las versiones del algoritmo para probar con la maestra (miercoles 25-nov).

  A  ancla15         ancla 30, recompra 120, compra 15 acciones (la que era sw/trade.s antes de elegir la D)
  B  sin_ancla       la mas segura: sin ancla (peor ronda -3 %)
  C  ancla26_rec117  la mejor del optimizador contra nuestra propia version: ancla 26, recompra 117
  D  ancla29_rec122  LA FINAL (sw/trade.s tal cual): la mejor del optimizador contra los rivales, ancla 29, recompra 122
  E  ancla29_rec122_p0160  la D, pero el ancla solo si el primer precio p0 >= 160 (le gana al rival en las 22 acciones)
  F  todo170_ancla29_rec122  si p0 >= 170 compra todo al inicio y espera el 255; si no, la D
  G  todo180_y240_rec122  sin ancla: compra todo si p0 >= 180 o si el precio llega a 240 antes de los extremos,
     y espera el 255 (la que gana el torneo de 22 empresas: ref/torneo.py)

Todas salen de sw/trade.s cambiando constantes con -D al ensamblar (el archivo no se toca).

Uso (desde la raiz, en Git Bash con OSS CAD Suite en el PATH):
  python tools/versiones.py armar        ensambla cada version, comprueba que el programa
                                         decide lo mismo que ref/trader.py (simulador de
                                         instrucciones) y arma build/versiones/<X>_<nombre>.bin
Despues, para grabar una:  .\\grabar.ps1 -Version B   (PowerShell)
Para comparar en una serie: python tools/simular.py --version todas --accion AMD --desde "2022-01-10 10:20"
"""
import os
import shutil
import subprocess
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(RAIZ, 'ref'))
sys.path.insert(0, os.path.join(RAIZ, 'tools'))

VERSIONES = {
    'A': ('ancla15', {'ANCLA': 30, 'RECOMPRA': 120}),
    'B': ('sin_ancla', {'ANCLA': 0}),
    'C': ('ancla26_rec117', {'ANCLA': 26, 'RECOMPRA': 117}),
    'D': ('ancla29_rec122', {'ANCLA': 29, 'RECOMPRA': 122}),
    'E': ('ancla29_rec122_p0160', {'ANCLA': 29, 'RECOMPRA': 122, 'ANCLA_P0': 160}),
    'F': ('todo170_ancla29_rec122', {'ANCLA': 29, 'RECOMPRA': 122, 'TODO_P0': 170}),
    'G': ('todo180_y240_rec122', {'ANCLA': 0, 'RECOMPRA': 122, 'TODO_P0': 180, 'TODO_Y': 240}),
}


def constantes(v):
    """.equ de sw/trade.s con los cambios de la version v."""
    from trader import PROGRAMAS, leer_equ
    e = leer_equ(PROGRAMAS['extremos'])
    e.update(VERSIONES[v][1])
    return e


def defines(v):
    return [x for k, val in VERSIONES[v][1].items() for x in ('-D', f'{k}={val}')]


def armar():
    import pochoasm
    from espino_iss import Variante, correr
    from mercado import simular
    from series import competencia
    from trader import Extremos
    carpeta = os.path.join(RAIZ, 'build', 'versiones')
    os.makedirs(carpeta, exist_ok=True)
    series = list(competencia(40000).items())[:12]          # practica_meta + 11 ventanas reales
    src = open(os.path.join(RAIZ, 'sw', 'trade.s'), encoding='utf-8').read()
    for v, (nombre, cambios) in VERSIONES.items():
        words, avisos = pochoasm.assemble(src, dict(cambios))
        hexf = os.path.join(carpeta, f'{v}_{nombre}.hex')
        with open(hexf, 'w', newline='\n') as f:
            f.writelines(f'{w:08x}\n' for _, w, _ in words)
        malas = 0
        for _, p in series:
            dec, _, _ = correr(hexf, p, Variante())
            malas += dec != simular(p, Extremos(constantes(v)))['decisiones']
        print(f'{v} {nombre}: {len(words)} palabras; programa = trader.py en {len(series) - malas}/{len(series)} series')
        if malas:
            raise SystemExit('el programa no decide lo mismo que la referencia: no se arma el bitstream')
        eq = ' '.join(defines(v))
        r = subprocess.run(['make', 'bin', f'PY={sys.executable}', f'EQU={eq}'], cwd=RAIZ,
                           capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-2000:], r.stderr[-2000:])
            raise SystemExit('fallo el armado del bitstream')
        destino = os.path.join(carpeta, f'{v}_{nombre}.bin')
        shutil.copy(os.path.join(RAIZ, 'build', 'pochoco.bin'), destino)
        print(f'   -> {os.path.relpath(destino, RAIZ)}')
    # dejar sw/trade.hex y build/pochoco.bin como la version A (la de la competencia)
    subprocess.run(['make', 'bin', f'PY={sys.executable}'], cwd=RAIZ, capture_output=True, text=True)
    print('build/pochoco.bin y sw/trade.hex quedan en la version A')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'armar':
        armar()
    else:
        print(__doc__)
