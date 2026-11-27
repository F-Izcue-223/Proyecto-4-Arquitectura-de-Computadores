"""Descarga precios reales de acciones tecnologicas para validar el algoritmo.

Fuente: la API publica de graficos de Yahoo Finance (la misma que usa su pagina).
Entrega velas de 5 minutos de los ultimos 60 dias y de 1 hora de los ultimos 2 anos.
Solo horario normal de mercado.

Los datos crudos quedan en data/yahoo/ (fuera de git: no son nuestros para
redistribuir). ref/validar.py los escala como la serie de practica y corre el agente.

Uso:  python ref/descargar.py [TICKER ...]
"""
import json
import os
import sys
import time
import urllib.request

DESTINO = os.path.join(os.path.dirname(__file__), '..', 'data', 'yahoo')
TICKERS = ['NVDA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'TSLA', 'AMD', 'AVGO', 'NFLX',
           'ORCL', 'CRM', 'ADBE', 'INTC', 'QCOM']
CONSULTAS = [('5m', '60d'), ('1h', '730d')]


def bajar(ticker, intervalo, rango):
    url = f'https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?interval={intervalo}&range={rango}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        res = json.load(r)['chart']['result'][0]
    cierres = res['indicators']['quote'][0]['close']
    return [(t, c) for t, c in zip(res['timestamp'], cierres) if c is not None]


def main():
    os.makedirs(DESTINO, exist_ok=True)
    for ticker in sys.argv[1:] or TICKERS:
        for intervalo, rango in CONSULTAS:
            try:
                filas = bajar(ticker, intervalo, rango)
            except Exception as e:                       # un ticker caido no detiene al resto
                print(f'{ticker} {intervalo}: ERROR {e}')
                continue
            with open(os.path.join(DESTINO, f'{ticker}_{intervalo}.csv'), 'w', newline='\n') as f:
                f.write('timestamp,close\n')
                f.writelines(f'{t},{c:.4f}\n' for t, c in filas)
            print(f'{ticker} {intervalo}: {len(filas)} velas, {filas[0][1]:.2f} -> {filas[-1][1]:.2f}')
            time.sleep(1)


if __name__ == '__main__':
    main()
