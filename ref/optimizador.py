"""Optimizador que queda corriendo: busca reglas de entrada y ajustes que ganen mas.

Explora, sobre la regla base (comprar en 100, vender en 255 o en TOMA, recomprar en
RECOMPRA), una regla de ENTRADA extra para el tramo sin garantia (antes de ver el 100 o el
255, y opcionalmente tambien en el tramo libre). Familias de entrada:
  1 sube_p0   entra si p >= p0 + x            (el ancla actual: x = ANCLA)
  2 sube_min  entra si p >= minimo visto + x
  3 ruptura   entra si p marca un maximo nuevo de la ronda, despues del tick 100*x
  4 medias    entra si la media rapida (alfa 1/2^x) supera a la lenta (alfa 1/2^y)
  5 caida     entra si p <= p0 - x            (comprar la baja del inicio)
Cada una con: tamanio de la compra q (1..63 acciones, una sola orden y despues mantener),
salida (0: vuelve a p0, 1: cae s desde el maximo desde la entrada, 2: cae s desde la entrada)
y donde actua (0: solo antes del primer extremo, 1: tambien en el tramo libre).

Cada candidata se mide en las ventanas reales (ref/minuto.py) contra la version actual
(las .equ de sw/trade.s) y contra rivales parecidos (100/255 y 100/255+220). Se guarda
solo si cumple los limites de riesgo (peor ronda, prob. de perder mas de 5 %), no baja el
promedio y gana cara a cara a la actual; las que pasan se confirman con el Montecarlo.

Busqueda: al azar + mutaciones de las mejores (evolutiva). Corre hasta --horas o Ctrl+C.
Cada mejora va a resultados/optimizador_mejores.csv y a resultados/optimizador_log.md
(se puede leer mientras corre). Al volver a lanzarlo, sigue desde las mejores guardadas.

Uso:
  python ref/optimizador.py --horas 8
  python ref/optimizador.py --horas 2 --peor 0.95 --familias 1,3
Para aplicar una mejora: escribirla en sw/trade.s y ref/trader.py (si es de otra familia),
correr tools/simular.py, ref/verificar.py y grabar (docs/simular-y-grabar.md).
"""
import argparse
import csv
import os
import sys
import time

import numba
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from minuto import EMPRESAS, ventanas  # noqa: E402
from montecarlo import escenarios, normalizar  # noqa: E402
from trader import PROGRAMAS, leer_equ  # noqa: E402

RES = os.path.join(AQUI, '..', 'resultados')
CAMPOS = ['toma', 'recompra', 'familia', 'x', 'y', 'q', 'salida', 's', 'donde']
FAMILIAS = {0: 'ninguna', 1: 'sube_p0', 2: 'sube_min', 3: 'ruptura', 4: 'medias', 5: 'caida'}
RANGOS = {'toma': (170, 254), 'recompra': (100, 170), 'familia': (0, 5), 'x': (1, 60), 'y': (2, 14),
          'q': (1, 63), 'salida': (0, 2), 's': (3, 40), 'donde': (0, 1)}


@numba.njit(cache=True)
def patrimonio(pr, prm):
    toma, recompra, fam, x, y, q_ord, salida, s, donde = prm
    caja, acc, dec = 10000, 0, 0
    vio_min = vio_max = extra = False
    piso, techo = 100, 255
    p0 = pr[0]
    actual = 0xBF
    mn, mx, ref, ent = 1e9, 0.0, 0.0, 0.0
    ef = es = float(p0)
    for n in range(len(pr)):
        p = pr[n]
        qq = dec & 63
        if dec >> 6 == 1:
            qq = min(qq, (caja - 5) // p)
            if qq > 0:
                caja -= qq * p + 5
                acc += qq
        elif dec >> 6 == 2:
            qq = min(qq, acc)
            if qq > 0 and caja + qq * p >= 5:
                caja += qq * p - 5
                acc -= qq
        if fam == 4:
            ef += (p - ef) / (1 << x)
            es += (p - es) / (1 << y)
        nuevo_max = p > mx
        mn = min(mn, p)
        mx = max(mx, p)
        out = -1
        if p <= piso:
            actual = 0x7F
            extra = False
            if p <= 100:
                vio_min = True
        elif p >= techo:
            actual = 0xBF
            extra = False
            if p >= 255:
                vio_max = True
                techo = toma
        elif fam > 0 and ((not vio_min and not vio_max) or (donde == 1 and vio_min and vio_max)):
            if extra:
                ref = max(ref, p)
                if salida == 0:
                    sale = p <= p0
                elif salida == 1:
                    sale = p <= ref - s
                else:
                    sale = p <= ent - s
                if sale:
                    actual = 0xBF
                    extra = False
            elif actual == 0xBF:
                if fam == 1:
                    entra = p >= p0 + x
                elif fam == 2:
                    entra = p >= mn + x
                elif fam == 3:
                    entra = nuevo_max and n >= 100 * x
                elif fam == 4:
                    entra = ef > es
                else:
                    entra = p <= p0 - x
                if entra:
                    out = 0x40 | q_ord
                    actual = 0
                    extra = True
                    ref = p
                    ent = p
        if vio_min and vio_max:
            piso = recompra
        dec = actual if out < 0 else out
    return (caja + acc * pr[-1]) / 10000.0


@numba.njit(parallel=True, cache=True)
def evaluar(S, prm):
    out = np.empty(S.shape[0])
    for i in numba.prange(S.shape[0]):
        out[i] = patrimonio(S[i], prm)
    return out


def neto(a, b):
    return float(np.mean(a > b + 1e-9) - np.mean(a < b - 1e-9))


def geo(w):
    return float(np.exp(np.log(w).mean()))


def al_azar(rng):
    c = {k: int(rng.integers(lo, hi + 1)) for k, (lo, hi) in RANGOS.items()}
    if c['familia'] == 4 and c['y'] <= c['x']:
        c['x'], c['y'] = min(c['x'], 12), max(c['x'] + 1, c['y'])
    if c['familia'] == 4:
        c['x'] = min(c['x'], 12)
        c['y'] = min(max(c['y'], c['x'] + 1), 14)
    if c['familia'] == 3:
        c['x'] = min(c['x'], 60)
    return c


def mutar(c, rng):
    m = dict(c)
    for k in rng.choice(list(RANGOS), size=int(rng.integers(1, 3)), replace=False):
        lo, hi = RANGOS[k]
        paso = max(1, (hi - lo) // 10)
        m[k] = int(np.clip(m[k] + rng.integers(-paso, paso + 1), lo, hi))
    if m['familia'] == 4:
        m['x'] = min(m['x'], 12)
        m['y'] = min(max(m['y'], m['x'] + 1), 14)
    return m


def vector(c):
    return np.array([c[k] for k in CAMPOS], np.int64)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--horas', type=float, default=8.0)
    ap.add_argument('--peor', type=float, default=0.94, help='peor ronda permitida (0,94 = perder a lo mas 6 %%)')
    ap.add_argument('--p5', type=float, default=0.0005, help='prob. maxima de perder mas de 5 %%')
    ap.add_argument('--familias', default='0,1,2,3,4,5')
    ap.add_argument('--objetivo', choices=['cara', 'promedio'], default='cara',
                    help='cara: gana cara a cara a la base y a los rivales; promedio: sube el patrimonio promedio')
    ap.add_argument('--base', default='', help='version de tools/versiones.py como punto de partida (A, B, C, D)')
    ap.add_argument('--salida', default='optimizador', help='prefijo de los archivos de resultados')
    ap.add_argument('--universo', action='store_true',
                    help='usar todas las acciones de data/minuto (22) en vez de las 5 de la competencia')
    ap.add_argument('--semilla', type=int, default=int(time.time()))
    a = ap.parse_args()
    rng = np.random.default_rng(a.semilla)
    fams = [int(f) for f in a.familias.split(',')]

    e = leer_equ(PROGRAMAS['extremos'])
    if a.base:
        sys.path.insert(0, os.path.join(AQUI, '..', 'tools'))
        from versiones import constantes
        e = constantes(a.base.upper())
    actual = {'toma': e['TOMA_GANANCIA'], 'recompra': e['RECOMPRA'], 'familia': 1 if e.get('ANCLA', 0) else 0,
              'x': e.get('ANCLA', 1) or 1, 'y': 2, 'q': e.get('ANCLA_ORDEN', 0x7F) & 63, 'salida': 0, 's': 3, 'donde': 0}
    if a.universo:
        from minuto import DATOS
        todas = sorted(os.path.splitext(n)[0] for n in os.listdir(DATOS) if n.endswith('.csv'))
        V = ventanas(500, empresas=todas)
        EMP = todas
    else:
        V = ventanas(250)
        EMP = EMPRESAS
    S = np.array([v for *_, v in V], np.int64)
    emp = np.array([k for k, _, _ in V])
    anio = np.array([h[:4] for _, h, _ in V])
    base = evaluar(S, vector(actual))
    rivales = [evaluar(S, vector(dict(actual, toma=t, recompra=100, familia=0))) for t in (255, 220)]
    mc = [np.array([normalizar(x) for x in xs], np.int64) for _, xs in escenarios(200)]
    mc_base = [evaluar(m, vector(actual)) for m in mc]

    os.makedirs(RES, exist_ok=True)
    ruta_csv = os.path.join(RES, f'{a.salida}_mejores.csv')
    ruta_log = os.path.join(RES, f'{a.salida}_log.md')
    poblacion = []
    if os.path.exists(ruta_csv):
        with open(ruta_csv) as f:
            for r in csv.DictReader(f):
                poblacion.append(({k: int(r[k]) for k in CAMPOS}, float(r['puntaje'])))
    if not poblacion:
        poblacion = [(dict(actual), 0.0)]      # arranca mutando la version actual
    vistos = {tuple(actual[k] for k in CAMPOS)}
    log = open(ruta_log, 'a', encoding='utf-8')
    log.write(f"\n## Corrida {time.strftime('%Y-%m-%d %H:%M')} (peor >= {a.peor}, P(>5%) <= {a.p5})\n"
              f"Version actual: {actual}. geo {geo(base):.4f}, peor {base.min():.3f}. "
              f"Puntaje = neto cara a cara vs actual + el peor neto vs rivales.\n\n")
    log.flush()
    print(f'{len(S)} ventanas reales, Montecarlo {len(mc)}x{len(mc[0])}. Actual: geo {geo(base):.4f}, peor {base.min():.3f}')

    fin = time.time() + 3600 * a.horas
    n_eval = n_ok = 0
    mejor_puntaje = max((p for _, p in poblacion), default=0.0)
    while time.time() < fin:
        if poblacion and rng.random() < 0.6:
            padre = poblacion[int(rng.integers(0, min(10, len(poblacion))))][0]
            c = mutar(padre, rng)
        else:
            c = al_azar(rng)
        if c['familia'] not in fams:
            continue
        clave = tuple(c[k] for k in CAMPOS)
        if clave in vistos:
            continue
        vistos.add(clave)
        w = evaluar(S, vector(c))
        n_eval += 1
        if w.min() < a.peor or np.mean(w < 0.95) > a.p5:
            continue
        if a.objetivo == 'cara':
            if (geo(w) < geo(base) * 0.999 or neto(w, base) <= 0
                    or min(geo(w[emp == k]) / geo(base[emp == k]) for k in EMP) < 0.995
                    or min(geo(w[anio == y]) / geo(base[anio == y]) for y in ('2022', '2023', '2024')) < 0.995):
                continue
        else:
            if (w.mean() <= base.mean()
                    or min(w[emp == k].mean() / base[emp == k].mean() for k in EMP) < 0.99
                    or min(w[anio == y].mean() / base[anio == y].mean() for y in ('2022', '2023', '2024')) < 0.99):
                continue
        Wm = [evaluar(m, vector(c)) for m in mc]
        mc_neto = min(neto(x, b) for x, b in zip(Wm, mc_base))
        if a.objetivo == 'cara' and mc_neto < -0.02:
            continue
        if a.objetivo == 'promedio' and min(x.mean() / b.mean() for x, b in zip(Wm, mc_base)) < 0.98:
            continue
        n_ok += 1
        puntaje = (neto(w, base) + min(neto(w, r) for r in rivales)) if a.objetivo == 'cara' else float(w.mean() * 1e4)
        poblacion.append((c, puntaje))
        poblacion.sort(key=lambda t: -t[1])
        poblacion = poblacion[:50]
        fila = dict(c, puntaje=round(puntaje, 4), promedio=round(float(w.mean() * 1e4)), geo=round(geo(w), 4), peor=round(float(w.min()), 3),
                    p_mas5=round(float(np.mean(w < 0.95)), 5), neto_actual=round(neto(w, base), 4),
                    neto_100_255=round(neto(w, rivales[0]), 4), neto_220=round(neto(w, rivales[1]), 4),
                    mc_neto_min=round(mc_neto, 4))
        nuevo = not os.path.exists(ruta_csv)
        with open(ruta_csv, 'a', newline='') as f:
            wr = csv.DictWriter(f, fieldnames=list(fila))
            if nuevo:
                wr.writeheader()
            wr.writerow(fila)
        if puntaje > mejor_puntaje:
            mejor_puntaje = puntaje
            txt = (f"- {time.strftime('%H:%M')} **mejor nueva**: {FAMILIAS[c['familia']]} x={c['x']} y={c['y']} "
                   f"q={c['q']} salida={c['salida']} s={c['s']} donde={c['donde']}, toma {c['toma']}, recompra "
                   f"{c['recompra']} | promedio ${fila['promedio']:,} geo {fila['geo']} peor {fila['peor']} | neto vs actual {fila['neto_actual']:+}, "
                   f"vs 100/255 {fila['neto_100_255']:+}, vs 220 {fila['neto_220']:+} | MC min {mc_neto:+.3f}\n")
            log.write(txt)
            log.flush()
            print(txt, end='')
    log.write(f"\nFin: {n_eval} candidatas evaluadas, {n_ok} cumplieron los limites.\n")
    log.close()
    print(f'{n_eval} candidatas, {n_ok} cumplieron los limites. Ver {os.path.relpath(ruta_log, os.path.join(AQUI, ".."))}')


if __name__ == '__main__':
    main()
