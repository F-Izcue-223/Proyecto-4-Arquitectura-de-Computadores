"""Series para desarrollar y validar el algoritmo.

  practica            tb/practica.csv: la primera serie de practica del curso (20 000 ticks).
  practica_meta       tb/practica_meta.csv: la serie de practica con el formato de la
                      competencia (META, 1 precio por minuto, normalizada a [100, 255]).
                      competencia() la junta con ventanas iguales de data/minuto.
  alibaba_<t>_<k>     Alibaba (HK 09988), velas de 5 minutos 2019-2026 del repositorio
                      Kronos, tomadas cada 5, 10, 15 y 30 minutos en ventanas de 20 000
                      ticks. Se escalan como la practica: precio * 130 / media, redondeado
                      (sin restar el minimo), asi quedan en un rango parecido (60 a 255).
  *_inv               la misma serie al reves en el tiempo. Conserva los saltos chicos y
                      da vuelta la tendencia: sirve para probar el caso alcista con datos
                      de la misma clase (la practica es bajista: 151 -> 98).

La practica se uso para elegir los parametros; Alibaba no (prueba fuera de muestra).

Uso:  python ref/series.py [ruta_al_zip_de_kronos]   -> escribe data/series/*.txt
"""
import csv
import os
import sys

import numpy as np

RAIZ = os.path.join(os.path.dirname(__file__), '..')
DATA = os.path.join(RAIZ, 'data', 'series')
PRACTICA = os.path.join(RAIZ, 'tb', 'practica.csv')
PRACTICA_META = os.path.join(RAIZ, 'tb', 'practica_meta.csv')
ZIP_KRONOS = os.path.expanduser(
    '~/OneDrive/Escritorio/deporte y alimentacion/raw/proyecto inversiones/Kronos-master.zip')


def leer_csv(ruta=PRACTICA):
    """Serie en el formato del curso: columnas tick,price."""
    with open(ruta) as f:
        return [int(r['price']) for r in csv.DictReader(f)]


def leer(ruta):
    if ruta.endswith('.csv'):
        return leer_csv(ruta)
    with open(ruta) as f:
        return [int(x) for x in f.read().split()]


def escalar(x):
    x = np.asarray(x, float)
    return [int(v) for v in np.clip(np.rint(x * 130 / x.mean()), 1, 255)]


def alibaba(ruta_zip=ZIP_KRONOS):
    import zipfile
    import pandas as pd
    with zipfile.ZipFile(ruta_zip) as z:
        with z.open('Kronos-master/finetune_csv/data/HK_ali_09988_kline_5min_all.csv') as f:
            cierre = pd.read_csv(f, encoding='utf-8-sig').close.values
    out = {}
    for paso, nombre in ((1, '5m'), (2, '10m'), (3, '15m'), (6, '30m')):
        x = cierre[::paso]
        for k in range(0, len(x) - 20000 + 1, 20000):
            out[f'alibaba_{nombre}_{k:05d}'] = escalar(x[k:k + 20000])
    return out


def escribir(nombre, precios):
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, nombre + '.txt'), 'w', newline='\n') as f:
        f.writelines(f'{p}\n' for p in precios)


def todas():
    """{nombre: precios} de todas las series guardadas en data/series."""
    return {os.path.splitext(n)[0]: leer(os.path.join(DATA, n))
            for n in sorted(os.listdir(DATA)) if n.endswith('.txt')}


def competencia(paso=40000):
    """Series con la forma de la competencia: tb/practica_meta.csv y, si estan los datos
    de data/minuto (ref/minuto.py), una ventana cada `paso` minutos de cada empresa."""
    out = {'practica_meta': leer_csv(PRACTICA_META)}
    if os.path.isdir(os.path.join(RAIZ, 'data', 'minuto')):
        from minuto import ventanas
        for k, hora, v in ventanas(paso):
            out[f'{k}_{hora[:10]}'] = [int(x) for x in v]
    return out


def rondas(precios, largo=2000):
    """Corta una serie en rondas de `largo` ticks (cada una parte con la caja inicial)."""
    return [precios[k:k + largo] for k in range(0, len(precios) - largo + 1, largo)]


if __name__ == '__main__':
    series = {'practica': leer_csv()}
    series.update(alibaba(sys.argv[1] if len(sys.argv) > 1 else ZIP_KRONOS))
    for n in os.listdir(DATA) if os.path.isdir(DATA) else []:
        os.remove(os.path.join(DATA, n))
    for nombre, p in series.items():
        escribir(nombre, p)
        escribir(nombre + '_inv', p[::-1])
    print(len(os.listdir(DATA)), 'series en', os.path.normpath(DATA))
