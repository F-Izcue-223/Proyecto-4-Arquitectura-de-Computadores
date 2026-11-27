"""Torneo todos contra todos (22 empresas, 2022-2024, 11.789 rondas): cada estrategia contra cada otra,
neto = % de rondas que gana - % que pierde. Se elige la que tiene el mejor neto contra su peor rival
(no sabemos que algoritmo tiene cada companero). Las 8 practicas solo se muestran."""
import glob
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import numpy as np                            # noqa: E402
from casos_f import correr                    # noqa: E402
from minuto import DATOS, ventanas            # noqa: E402
from mejorar_practicas import leer, neto      # noqa: E402

# (P0 todo al inicio, Y todo si llega a Y, ancla, q, stop, toma, recompra); 256 / 0 = apagado
EST = {
    'rival 100/255': (256, 0, 0, 0, 0, 255, 100),
    'rival +220': (256, 0, 0, 0, 0, 220, 100),
    'rival 225/122': (256, 0, 0, 0, 0, 225, 122),
    'D': (256, 0, 29, 0x4F, 1, 225, 122),
    'F (p0>=170)': (170, 0, 29, 0x4F, 1, 225, 122),
    'todo al inicio': (101, 0, 0, 0, 0, 225, 122),
    'G (Y=240)': (256, 240, 0, 0, 0, 225, 122),
    'G (Y=230)': (256, 230, 0, 0, 0, 225, 122),
    'F + Y240': (170, 240, 29, 0x4F, 1, 225, 122),
    'p0>=180 + Y240': (180, 240, 0, 0, 0, 225, 122),
    'p0>=190 + Y240': (190, 240, 0, 0, 0, 225, 122),
    'p0>=200 + Y240': (200, 240, 0, 0, 0, 225, 122),
    'p0>=210 + Y240': (210, 240, 0, 0, 0, 225, 122),
    'p0>=220 + Y240': (220, 240, 0, 0, 0, 225, 122),
    'p0>=200 + Y240 + ancla': (200, 240, 29, 0x4F, 1, 225, 122),
}


def main():
    todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
    V = ventanas(500, empresas=todas)
    S = np.array([v for *_, v in V], np.int64)
    anio = np.array([h[:4] for _, h, _ in V])
    rutas = sorted(glob.glob(os.path.join(os.path.expanduser('~'), 'Downloads', 'practica_*_20*.csv')))
    P = np.array([leer(r) for r in rutas], np.int64)
    W = {k: correr(S, *v) for k, v in EST.items()}
    PW = {k: correr(P, *v) for k, v in EST.items()}
    nombres = list(EST)
    M = np.array([[neto(W[a], W[b]) for b in nombres] for a in nombres])
    peor = [min(M[i, j] for j in range(len(nombres)) if j != i) for i in range(len(nombres))]
    prom = [np.mean([M[i, j] for j in range(len(nombres)) if j != i]) for i in range(len(nombres))]
    orden = np.argsort(peor)[::-1]
    print(f'{len(S)} rondas, 22 empresas. Neto de la fila contra la columna (%):')
    print(f'{"":24s}' + ''.join(f'{n[:7]:>8s}' for n in nombres))
    for i in orden:
        print(f'{nombres[i]:24s}' + ''.join(f'{100 * M[i, j]:8.1f}' if i != j else f'{"-":>8s}' for j in range(len(nombres))))
    print('\nRanking por el peor enfrentamiento:')
    for i in orden:
        w, p = W[nombres[i]], PW[nombres[i]]
        pa = min(neto(w[anio == y], W[nombres[j]][anio == y]) for y in ('2022', '2023', '2024')
                 for j in range(len(nombres)) if j != i)
        print(f'  {nombres[i]:24s} peor neto {peor[i]:+6.1%} (peor año {pa:+6.1%})  neto medio {prom[i]:+6.1%}  prom ${w.mean():,.0f}'
              f'  peor ${w.min():,.0f}  pierde {np.mean(w < 1e4):.2%} | practicas ${p.mean():,.0f}')


if __name__ == '__main__':
    main()
