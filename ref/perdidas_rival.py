"""Por que la D pierde contra el rival 100/255 en algunas acciones (AMZN, SNPS, CDNS) y que variables lo corrigen.

1. Descompone la D regla por regla: rival -> + toma 225 -> + recompra 122 -> + ancla (= D), y mide el neto contra el
   rival de cada paso, por accion.
2. Prueba variables nuevas sobre la D (todas implementables con constantes y pocas instrucciones):
     toma_q   vender solo q acciones en la toma (225) y el resto en 255           (0 = todo, como la D)
     rec_q    comprar solo q acciones en la recompra (122) y el resto en 100       (0 = todo, como la D)
     t_toma   la toma 225 recien vale desde el tick t_toma (antes el techo sigue en 255)
     t_rec    la recompra 122 vale solo hasta el tick t_rec (despues el piso vuelve a 100)
   y las mide en las 3 acciones problema, en las 5 de la competencia y en las 22.
Uso (desde la raiz):  python ref/perdidas_rival.py
"""
import os
import sys

import numba
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from competencia import extremos, maestra          # noqa: E402
from minuto import DATOS, EMPRESAS, ventanas        # noqa: E402

PROBLEMA = ('AMZN', 'SNPS', 'CDNS')


@numba.njit(cache=True)
def regla(pr, toma, recompra, ancla, ancla_q, toma_q, rec_q, t_toma, t_rec, a_lo, a_hi, t_ancla):
    """La D (extremos 100/255 + toma + recompra + ancla) con las variables nuevas."""
    decs = np.empty(len(pr), np.int64)
    vio_min = vio_max = False
    dec = 0xBF
    parcial_v = parcial_c = False
    for n in range(len(pr)):
        p = pr[n]
        out = -1
        techo = toma if (vio_max and n >= t_toma) else 255
        piso = recompra if (vio_min and vio_max and n < t_rec) else 100
        if p <= piso:
            if p <= 100:
                vio_min = True
                dec = 0x7F
            elif rec_q > 0:
                if not parcial_c:
                    out = 0x40 | rec_q
                    parcial_c = True
                    dec = 0
            else:
                dec = 0x7F
            parcial_v = False
        elif p >= techo:
            if p >= 255:
                vio_max = True
                dec = 0xBF
            elif toma_q > 0:
                if not parcial_v:
                    out = 0x80 | toma_q
                    parcial_v = True
                    dec = 0
            else:
                dec = 0xBF
            parcial_c = False
        elif ancla > 0 and not vio_min and not vio_max and a_lo <= pr[0] <= a_hi and (n < t_ancla or dec != 0xBF):
            if p >= pr[0] + ancla:
                if dec == 0xBF:
                    out = ancla_q
                    dec = 0
            elif p <= pr[0]:
                dec = 0xBF
        decs[n] = dec if out < 0 else out
    return decs


@numba.njit(parallel=True, cache=True)
def correr(S, toma, recompra, ancla, ancla_q, toma_q, rec_q, t_toma, t_rec, a_lo, a_hi, t_ancla):
    W = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        W[i] = maestra(S[i], regla(S[i], toma, recompra, ancla, ancla_q, toma_q, rec_q, t_toma, t_rec, a_lo, a_hi, t_ancla))[0]
    return W


def neto(a, b):
    return float(np.mean(a > b + 0.5) - np.mean(a < b - 0.5))


def main():
    todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
    V = ventanas(500, empresas=todas)
    S = np.array([v for *_, v in V], np.int64)
    acc = np.array([k for k, _, _ in V])
    grupos = {'3 problema': np.isin(acc, PROBLEMA), '5 competencia': np.isin(acc, EMPRESAS),
              '22 acciones': np.ones(len(S), bool)}
    D = dict(toma=225, recompra=122, ancla=29, ancla_q=0x4F, toma_q=0, rec_q=0, t_toma=0, t_rec=20000, a_lo=0, a_hi=255, t_ancla=20000)

    # la regla nueva con valores de la D da lo mismo que competencia.extremos (la que coincide con el programa)
    for s in S[::997]:
        assert (regla(s, *D.values()) == extremos(s, 100, 255, 225, 122, 29, 0x4F)).all()

    def W(**k):
        return correr(S, *dict(D, **k).values())

    r1 = W(toma=255, recompra=100, ancla=0)
    r2 = W(toma=220, recompra=100, ancla=0)
    wD = W()

    print('1) La D paso a paso: neto contra el rival 100/255 (gana% - pierde%)')
    pasos = (('+ toma 225', W(recompra=100, ancla=0)), ('+ recompra 122', W(ancla=0)), ('+ ancla 29 (= D)', wD))
    print(f'{"":18s}' + ''.join(f'{k:>8s}' for k in PROBLEMA) + f'{"comp5":>8s}{"22":>8s}')
    for nom, w in pasos:
        print(f'{nom:18s}' + ''.join(f'{neto(w[acc == k], r1[acc == k]):+8.1%}' for k in PROBLEMA)
              + f'{neto(w[grupos["5 competencia"]], r1[grupos["5 competencia"]]):+8.1%}{neto(w, r1):+8.1%}')

    print('\n   Rondas que la D pierde contra el rival en las 3 acciones: que paso')
    m = grupos['3 problema'] & (wD < r1 - 0.5)
    sin_toma = W(toma=255)
    sin_rec = W(recompra=100)
    sin_ancla = W(ancla=0)
    print(f'   {m.sum()} rondas perdidas; se arreglan quitando: la toma {np.mean(sin_toma[m] >= r1[m] - 0.5):.0%}, '
          f'la recompra {np.mean(sin_rec[m] >= r1[m] - 0.5):.0%}, el ancla {np.mean(sin_ancla[m] >= r1[m] - 0.5):.0%}')

    print('\n   Rondas donde el ancla compra: D contra B (sin ancla) segun el primer precio p0 y el tick de la compra')
    wB = sin_ancla
    p0 = S[:, 0]
    tick = np.full(len(S), -1)
    for i, s in enumerate(S):
        ext = np.flatnonzero((s <= 100) | (s >= 255))
        sube = np.flatnonzero(s >= min(s[0] + 29, 255))
        if len(sube) and (not len(ext) or sube[0] < ext[0]):
            tick[i] = sube[0]
    disparo = tick >= 0
    for nom, x, cortes in (('p0', p0, (100, 120, 140, 160, 180, 200, 256)),
                           ('tick de compra', tick, (0, 500, 1000, 2000, 4000, 8000, 20000))):
        print(f'   {nom}:')
        for a, b in zip(cortes[:-1], cortes[1:]):
            for g, m in (('3 problema', grupos['3 problema']), ('22', grupos['22 acciones'])):
                mm = disparo & m & (x >= a) & (x < b)
                if mm.sum():
                    print(f'     [{a:5d},{b:5d}) {g:10s} rondas {mm.sum():5d}  neto D vs B {neto(wD[mm], wB[mm]):+6.1%}'
                          f'  neto D vs rival {neto(wD[mm], r1[mm]):+6.1%}')

    print('\n2) Variables nuevas (sobre la D). Neto contra rival 100/255 y +220; peor ronda; promedio')
    cand = [('D', {}), ('B (sin ancla)', {'ancla': 0})]
    cand += [(f'toma parcial q={q}', {'toma_q': q}) for q in (20, 40)]
    cand += [(f'recompra parcial q={q}', {'rec_q': q}) for q in (20, 40)]
    cand += [(f'toma desde tick {t}', {'t_toma': t}) for t in (10000, 17000)]
    cand += [(f'recompra hasta tick {t}', {'t_rec': t}) for t in (14000, 19000)]
    cand += [(f'ancla solo si p0<={h}', {'a_hi': h}) for h in (140, 160, 180, 200)]
    cand += [(f'ancla solo si p0>={lo}', {'a_lo': lo}) for lo in (110, 120, 130)]
    cand += [(f'ancla solo antes tick {t}', {'t_ancla': t}) for t in (500, 1000, 2000, 4000)]
    filas = []
    for nom, k in cand:
        w = W(**k)
        f = [nom]
        for g, m in grupos.items():
            f += [neto(w[m], r1[m]), neto(w[m], r2[m]), w[m].min() / 1e4 - 1, w[m].mean()]
        filas.append(f)
    print(f'{"":24s}| {"3 problema":^30s}| {"5 competencia":^30s}| {"22 acciones":^30s}')
    print(f'{"":24s}' + '| vs100/255  vs220   peor   prom ' * 3)
    for f in filas:
        print(f'{f[0]:24s}' + ''.join(f'| {f[i]:+6.1%}  {f[i + 1]:+6.1%} {f[i + 2]:+6.1%} {f[i + 3]:6.0f} ' for i in (1, 5, 9)))
    return filas


if __name__ == '__main__':
    main()
