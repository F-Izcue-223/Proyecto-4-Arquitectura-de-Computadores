# Ruta de optimización del Pochoco Trader

Qué se probó, qué se decidió, con qué números, y cómo seguir mejorando.
Estado al 16 de noviembre de 2026. Competencia y defensa: 24 de noviembre, 10:30.

## 1. Lo que sabemos del juego

1. La maestra manda un precio (1 a 255) por tick y ejecuta, a ese precio, el byte que encontró en DECISION.
   Ese byte responde al precio **anterior**.
2. La maestra **recorta** las órdenes: compra lo que alcance con la caja, vende lo que haya. Una orden que
   queda en 0 no se ejecuta ni paga los $5 (tarea `ejecutar` de `tb/tb_proyecto_4.sv`).
3. Si no se alcanza a responder, repite la orden anterior.
4. Tres rondas con series distintas (T = 10 ms, 1 ms, 0,1 ms). En la ronda 3 quedan 2.262 ciclos por tick.
5. Dicho por el profesor en clases: cada ronda es una acción distinta, de empresas tecnológicas; no dirá
   cuáles; **no usará el período de caída** de la práctica. Su pista de diseño: "si está subiendo sobre la
   media, pienso que va a seguir subiendo".
6. El puntaje depende del patrimonio final contra comprar y mantener y de la posición entre los grupos.

## 2. Lo que mostró la serie de práctica

| Dato | Valor |
|---|---|
| Rango de precios | 72 a 190 (parte en 151, termina en 98): **nunca toca 1 ni 255** |
| Varianza a 100 ticks / (100 × varianza de un tick) | 0,53: el precio **vuelve a su media** |
| Correlación entre un cambio y el siguiente | −0,11 (no se puede usar: la orden se ejecuta un tick después) |
| Comprar y mantener, 20.000 ticks | $6.497 |
| No operar | $10.000 |

Primera versión del algoritmo (comprar más mientras más bajo, suponiendo rango 1–255): **$2.556**. Descartada.
El diseño de otro grupo que se analizó solo compra bajo 33: no hace ninguna orden y queda en $10.000.

## 3. El algoritmo final ("caídas + tendencia")

Sumas de los últimos 64 precios (S) y de los últimos 512 (SL). `dev = S − 64p`, `tl = 512p − SL`.

| Bandera | Se prende si | Se apaga si | En palabras |
|---|---|---|---|
| CAÍDA | `dev ≥ A_ENTRA·p` | `dev ≤ A_SALE·p` | precio 4,5 % bajo la media corta |
| TENDENCIA | `64·tl ≥ C_SUBE·SL` | `64·tl < −C_BAJA·SL` | precio 1,6 % sobre la media larga (se apaga 6 % bajo) |
| EXCESO | `dev ≤ −B_EXCESO·p` | `2·dev ≥ −B_EXCESO·p` | precio 10 % sobre la media corta |

**Dentro = CAÍDA o (TENDENCIA y no EXCESO).** Dentro manda `0x7F` (comprar 63); fuera, `0xBF` (vender 63).
Sin contabilidad: la maestra recorta. Repetir una orden no hace daño.

Parámetros actuales (`.equ` de `sw/trade.s`): `A_ENTRA=3, A_SALE=2, C_SUBE=1, C_BAJA=4, B_EXCESO=6`.

## 4. Resultados del algoritmo final

| Serie | Agente | Comprar y mantener | No operar |
|---|---|---|---|
| Práctica completa (bajista) | $13.753 | $6.497 | $10.000 |
| Práctica invertida en el tiempo (alcista) | $23.859 | $15.348 | $10.000 |
| Testbench del curso (primeros 2.000 ticks) | $7.978 | $6.695 | $10.000 |

Por ronda de 2.000 ticks (media geométrica de patrimonio / 10.000): práctica 1,044 (CyM 0,959); práctica
invertida 1,082 (CyM 1,042); Alibaba 0,981 (CyM 0,972); Alibaba invertida 1,006 (CyM 1,029).

**Dónde pierde:** si el precio cae sin rebotar (peor ronda: $8.118 en la práctica, $6.426 en Alibaba), y contra
comprar y mantener en subidas fuertes de una acción que revierte poco a su media (Alibaba).

## 5. Perfiles alternativos (cambiando solo las `.equ`)

Media geométrica por ronda según cómo fue la ronda, en las 160 rondas disponibles (`python ref/barrido.py ...`):

| Perfil (A_ENTRA, A_SALE, C_SUBE, C_BAJA, B_EXCESO) | Alcista | Lateral | Bajista | Gana a CyM | Peor ronda |
|---|---|---|---|---|---|
| comprar y mantener | 1,221 | 1,000 | 0,819 | – | – |
| **actual (3, 2, 1, 4, 6)** | 1,164 | 0,982 | 0,881 | **69/160** | 0,643 |
| alcista (4, 2, 1, 8, 4) | 1,193 | 0,970 | 0,846 | 43/160 | 0,639 |
| tipo comprar-y-mantener (3, 2, 0, 8, 8) | 1,213 | 0,991 | 0,830 | 48/160 | 0,642 |
| solo caídas (4, 1, 99, 0, 99) | 1,014 | 1,002 | 0,991 | 84/160 | 0,736 |

Cómo leerla:

1. **Ningún perfil domina.** Más ganancia en rondas alcistas se paga con menos protección en las bajistas.
2. El perfil "alcista" tiene mejor promedio en subidas, pero le gana a comprar y mantener en menos rondas: su
   promedio viene de pocas rondas muy buenas. Con 3 rondas en la competencia se prefirió el **actual**, que gana
   más seguido. Se probó el 16-nov y se revirtió por esa razón.
3. Si el profesor confirmara series claramente alcistas y rondas largas, el perfil "tipo comprar-y-mantener" es
   el más seguro contra la referencia. Si las series fueran laterales o bajistas, "solo caídas".
4. En los datos del profesor (la práctica, en ambos sentidos) el perfil actual le gana a comprar y mantener en
   rondas alcistas (1,274 contra 1,244); en Alibaba no (1,151 contra 1,219).

Para cambiar de perfil: editar las cinco `.equ` de `sw/trade.s` y seguir la lista de la sección 8.

## 6. Hardware: qué se probó y qué quedó

| Variante | Ciclos/tick (prom. / peor) | Celdas (de 1280) | f máx | Decisión |
|---|---|---|---|---|
| Solo software | 415,8 / 445 | 995 | 47–51 MHz | sirve, 19,7 % del tiempo de la ronda 3 |
| Shifter | 391,8 / 421 | 1252 | 40–44 MHz | caro y gana poco (×1,06) |
| **mul8 (final)** | **133,9 / 139** | **1202** | **47–49 MHz** | ×3,11; 6,1 % de la ronda 3 |
| mul8 + shifter | 109,9 / 115 | 1439 | – | no cabe |
| PLL | – | – | – | la HX1K en VQ100 no tiene PLL |

1. La multiplicación por software era el 72,4 % de los ciclos. Amdahl predecía ×2,58 con el peor caso del
   multiplicador; se midió ×3,11 (los umbrales son números chicos y termina en 3 a 5 ciclos).
2. `(* no_rw_check *)` en la RAM liberó unas 200 celdas en el diseño final (174 en una versión anterior). Sin eso no cabía ningún acelerador.
3. Todas las variantes toman las mismas decisiones: la velocidad no cambia la ganancia una vez cumplido el
   deadline. La elección de `mul8` es por margen, área y porque es la que se compila sin opciones.
4. Si el profesor no aceptara cambios dentro del core: usar la variante solo software (cumple el deadline).
   Hay que dejar `HW_MUL` en 0 por defecto en `trade.s` y quitar `mul8` del RTL por defecto.

## 7. Ideas para seguir mejorando (ordenadas por valor esperado)

1. **Validar con más acciones tecnológicas reales** en períodos sin caída, escaladas como la práctica
   (`ref/series.py` muestra cómo). Es lo que más reduce la incertidumbre: hoy solo hay una serie del profesor.
2. **Preguntar por el largo de las rondas.** Con rondas de 20.000 ticks pesan más las tendencias; con 2.000,
   las caídas y rebotes.
3. Umbrales proporcionales a la volatilidad reciente (media de |dev|). Se probó en la exploración: fuera de
   muestra rindió parecido a los umbrales fijos, con más código. No se adoptó.
4. Un pipeline de 3 etapas en el Espino (CPI 2,3 → 1,5, visto en clases). No sube la ganancia; mejora el
   margen y la nota de co-diseño. Riesgo alto de romper algo a días de la entrega.
5. Periférico que lleve las medias en hardware. Ahorra unos 25 ciclos por tick; hoy sobran más de 2.000.

Lo que **no** vale la pena (Amdahl aplicado al esfuerzo): seguir bajando ciclos. El tick ya usa 6 % del tiempo.

## 8. Lista para cualquier cambio de parámetros

1. Editar las `.equ` en `sw/trade.s`.
2. `python ref/barrido.py` (o con las combinaciones a comparar) y mirar las cinco columnas, no solo el promedio.
3. `make hex` y `python ref/backtest.py`.
4. `python ref/verificar.py` (trade.s = trader.py en las 4 variantes).
5. `make tb` (debe dar 4/4) y `make sim-trade VARIANT=mul8`.
6. `make prueba-placa`, grabar `build/prueba.bin`, ver los 4 LEDs fijos.
7. `make bin`, grabar `build/pochoco.bin`.
8. `python ref/analisis.py` y recompilar el informe y la guía (los números se actualizan solos; revisar los
   porcentajes escritos en la tabla de banderas).

## 9. Antes del 24 de noviembre

1. Subir el repositorio a GitHub.
2. Completar la declaración de uso de IA del informe.
3. 19-nov: probar con la maestra real (PMOD: CS_n 65, MOSI 64, MISO 63, SCLK 62, tierra común). Los displays
   deben mostrar el precio que manda la maestra.
4. Preguntar al profesor: largo de las rondas; si se permite la instrucción propia dentro del core.
5. Estudiar `docs/guia-defensa.pdf` (22 preguntas con respuesta).

## 10. Validación con acciones tecnológicas reales (17-nov)

`ref/descargar.py` baja de Yahoo Finance 15 tecnológicas (NVDA, AAPL, MSFT, GOOGL, AMZN, META, TSLA, AMD,
AVGO, NFLX, ORCL, CRM, ADBE, INTC, QCOM) en velas de 5 min (60 días) y 1 h (2 años). `ref/validar.py` las
escala como la práctica y corre el agente. Nunca se usaron para elegir parámetros.

Perfil actual (3, 2, 1, 4, 6), media geométrica:

| Conjunto | Agente | CyM | Razón agente/CyM | Gana a CyM | Exposición |
|---|---|---|---|---|---|
| 15 series de 5 min (~4.700 ticks) | 0,902 | 0,931 | 0,970 | 3/15 | 76 % |
| 15 series de 1 h (~5.100 ticks) | 1,194 | 1,498 | 0,797 | 3/15 | 70 % |
| Rondas de 2.000 ticks (60) | – | – | 0,979 | 20/60 | 72 % |
| Rondas donde CyM sube > 8 % | 1,288 | 1,505 | 0,855 | 5/42 | 80 % |
| Rondas donde CyM baja > 8 % | 0,793 | 0,745 | 1,065 | 14/26 | 59 % |

**Conclusión:** en tecnológicas que suben, el perfil actual gana plata (1,288 por ronda) pero **pierde contra
comprar y mantener**, porque sale en los retrocesos y se pierde parte de la subida (AMD 1 h: 0,51; NVDA 1 h: 0,62).
Solo le gana cuando la acción cae.

Razón agente/CyM por perfil (columnas: tec 5m, tec 1h, tec rondas, práctica, práctica inv., Alibaba, Alibaba inv.):

| Perfil | tec 5m | tec 1h | tec rondas | prac | prac inv | ali | ali inv |
|---|---|---|---|---|---|---|---|
| actual (3, 2, 1, 4, 6) | 0,970 | 0,797 | 0,979 | 1,088 | 1,038 | 1,009 | 0,978 |
| tipo CyM (3, 2, 0, 8, 8) | 0,991 | 0,907 | 1,008 | 1,057 | 1,021 | 0,997 | 0,990 |
| **casi siempre dentro (3, 1, 0, 24, 12)** | **1,002** | **1,028** | **1,004** | 1,002 | 1,000 | 1,000 | 1,001 |
| mejor promedio global (3, 2, 0, 6, 12) | 0,996 | 0,981 | 1,024 | 1,076 | 1,022 | 1,004 | 0,988 |

"Casi siempre dentro" es el único que no pierde contra comprar y mantener en ningún conjunto: entra al
primer tick, solo sale si el precio se dispara 19 % sobre la media corta y vuelve a entrar en la caída. Su
ventaja es chica (0 a 3 %) pero no pierde contra la referencia del puntaje. A cambio, en la práctica bajista
deja de ganarle a CyM por 8,8 % y pasa a empatar.

**Decisión del 17-nov (Martín):** se cambia al perfil "casi siempre dentro" (3, 1, 0, 24, 12), porque la
referencia del puntaje es comprar y mantener y las series serán tecnológicas sin el período de caída.

## 11. Especificación nueva (correo de Nico, 17-nov)

- Serie de práctica nueva `tb/practica_meta.csv`: 20.000 ticks de **Meta (feb–may 2022), un precio por minuto de
  mercado, normalizados entre 100 y 255**. Reemplaza a la anterior. El testbench no cambia.
- Competencia: **períodos ocultos de Meta, Apple, Netflix, AMD o Tesla entre 2022 y 2024**, normalizados igual.
  No dirán qué empresa ni qué fechas en cada ronda.
- 18-nov: llevan la FPGA maestra a clases para probar la conexión.

## 12. Algoritmo nuevo: "extremos" (17-nov, noche) — reemplaza a "caídas + tendencia"

### 12.1 La serie de la competencia, reconstruida exacta

`tb/practica_meta.csv` es, **tick a tick (20.000 de 20.000)**, el cierre de META en horario regular
(9:30–16:00 de Nueva York) desde el 23-feb-2022 15:20 hasta el 9-may-2022 10:39, llevado linealmente a
[100, 255] (mínimo de la ventana → 100, máximo → 255) y redondeado. Datos: barras de 1 minuto de Alpaca
(dataset `CryptoSpartan/stocks_bars_1m` de Hugging Face, leído por rangos: solo se bajaron los 43 MB de las
cinco empresas). Quedan en `data/minuto/` (fuera de git). `ref/minuto.py` arma cualquier ventana posible:
~273.000 por empresa, 5 empresas, 2022–2024. Se evalúa con una cada 500 minutos (2732 ventanas).

### 12.2 La ventaja que da la normalización

Como el mínimo vale 100 y el máximo 255, el nivel del precio predice el retorno hasta el final de la ventana
(media geométrica sobre todas las ventanas, `resultados/nivel_retorno.csv`): en 100–109, +64 %; en 170–179,
+3 %; en 250–255, −32 %. Y algo más fuerte:

- **El 100 y el 255 aparecen sí o sí** dentro de la ventana, y el precio nunca sale de [100, 255].
- Si se ve el 100 y todavía no apareció el 255, **el 255 viene después**: comprar en 100 y vender en 255 es
  ×2,55 garantizado (menos comisiones y el precio del tick siguiente).
- Si el 255 ya pasó, comprar en 100 no puede perder (el precio ya no baja de 100).

### 12.3 La regla (sw/trade.s, 20 palabras)

- Precio ≤ 100 → dentro ("comprar 63").
- Precio ≥ techo → fuera ("vender 63"). El techo es 255 hasta que aparece el 255; desde ahí es 220
  (`TOMA_GANANCIA`): sin garantía de volver a 255, se toma la ganancia y se recompra si toca 100 otra vez.
- En el resto no cambia. Parte fuera.

100 y 255 salen de la especificación, no de ajustar. 220 sí es ajustado: +1,1 % en promedio, mejora a las 5
empresas (+0,2 a +1,8 %), gana cara a cara contra la regla sin él en 5,2 % de las ventanas y pierde en 2,3 %.

### 12.3b Recompra en 120 (18-nov, madrugada; las rondas son de 20.000 ticks)

Cuando ya aparecieron el 100 y el 255 no queda garantía, pero comprar cerca del piso arriesga poco (el
precio no baja de 100). El piso sube a 120 (`RECOMPRA`). Barrido: 105 → 1,990; 110 → 1,992; 115 → 1,997;
**120 → 1,998**; 130 → 2,000; 140 → 1,998 (base 1,970). Con 120: mejora a las 5 empresas (+0,5 a +3,1 %) y a
los dos períodos (2022–23 1,948; 2024 2,131), gana a la regla sin recompra en 4,0 % de las ventanas y pierde en
1,1 %; probabilidad de perder y peor caso iguales (1,2 %, 0,970). Costo: pérdida desde un peak p95 sube de
$8.036 a $9.114. Se eligió 120 (centro del rango plano), no el máximo puntual.

Otras ideas con el tiempo restante (las rondas son de 20.000 ticks, así que se puede contar el tiempo) que
**no** mejoraron de forma pareja: comprar en 101–105 antes de ver extremos o tras ver solo el 255, otras tomas
de ganancia (200, 210, 230), y bajar o subir la toma de ganancia en los últimos 1000–6000 ticks.

Programa: 29 palabras; camino común sin saltos hasta escribir DECISION: 11,8 ciclos promedio (antes 12,2), peor 25.

### 12.4 Ganancia y riesgo de mercado (`python ref/competencia.py` → `resultados/competencia.csv`)

Ronda con la serie completa (20.000 ticks), 2732 ventanas:

| | extremos | tendencia (anterior) | comprar y mantener |
|---|---|---|---|
| media geométrica W/10.000 | **1,970** (con recompra 120: **1,998**) | 1,111 | 1,115 |
| mediana | **2,454** | 1,170 | 1,158 |
| 5 % peor | **1,045** | 0,476 | 0,478 |
| peor ventana | **0,970** | 0,400 | 0,399 |
| prob. de terminar bajo $10.000 | **1,2 %** | 41 % | 42 % |
| gana a comprar y mantener | **100 %** | 34 % | — |
| pérdida máx. desde un peak, mediana / p95 | $3.366 / $8.036 | $6.404 / $11.156 | |
| exposición (tiempo con acciones) | 44 % | 100 % | 100 % |

Por año de inicio: 2022 (bajista) 1,749; 2023 2,106; 2024 2,107. En 2022 el algoritmo anterior perdía en 61 %
de las ventanas; este, en 2,6 %.

Ronda de 2000 ticks (los primeros de la ventana, como corre el testbench por defecto): geo **1,071**, mediana
1,000 (en la mayoría de las ventanas el 100 no aparece en esos 2000 ticks y no opera), **nunca pierde** más de
0,1 %, gana a CyM en 66 %. CyM: 1,016 con 48 % de pérdidas. El algoritmo anterior: 1,015.

En practica_meta: el 255 aparece en el tick 10.965 y el 100 en el 17.084 (el máximo antes que el mínimo, el
caso "sin garantía"). Serie completa: **W = $21.752** (CyM $9.695; el algoritmo anterior $11.060), 4 órdenes:
compra en ~101 y toma la ganancia en 220. Primeros 2000 ticks (lo que corre el testbench por defecto): no
opera, W = $10.000 (CyM $11.375).

### 12.5 Qué se probó y se descartó (con números, 2732 ventanas)

- Comprar/vender por nivel con otros umbrales (110/250, 120/240…): todos peores que 100/255.
- Entrada escalonada (mitad en 130–150, todo en 100): peor (1,84–1,90).
- Apostar antes de ver extremos (dentro si p ≥ 200–240): +1–2 % pero no parejo entre años; descartado.
- Modo para rondas cortas (dentro si p ≤ 110–150 mientras no aparezca un extremo): peor en 2000 y en 20.000.
- Tendencia/medias móviles encima de la regla: el nivel ya contiene la información; no suma.

### 12.6 Hardware con el algoritmo nuevo: dónde está el cuello de botella

- El tick cuesta **12,2 ciclos promedio y 20 el peor** (antes 134,8 con mul8 y 418,8 por software): 0,8 % del
  período de la ronda 3. La optimización del algoritmo le ganó por 11× a la del hardware (lección de Amdahl:
  acelerar lo que ya no está en el camino no sirve).
- **No multiplica ni desplaza**: corre en el **Espino original**. El diseño de competencia vuelve al core sin
  tocar (995 de 1280 celdas, 77,7 %; 47,5–51,0 MHz, antes 1202 celdas con mul8); mul8 y shifter quedan como opciones (`-DESPINO_MUL8`, `-DESPINO_SHIFTER`) del estudio de co-diseño
  (que se hizo con `sw/trade_tendencia.s` y se reproduce con `ALGO=tendencia`). Se acaba la duda de si el
  profesor acepta una instrucción propia.
- El cuello de botella que queda **no es de cómputo**: es el protocolo. La decisión del precio n se ejecuta al
  precio n+1 (fijo para todos), y "q ≤ 63" obliga a entrar y salir en dos órdenes (cerca de 100 se compran ~99
  acciones: 63 + 36). Ningún hardware lo cambia.
- **Multiplicación mejor (radix-4)**: con el algoritmo nuevo hay 0 multiplicaciones. Con el anterior era ~13 %
  de los ciclos: Amdahl da como mucho 1/(1 − 0,13·0,5) ≈ 1,07×. No vale los LUT.
- **4 núcleos "recortados"** (Espino solo con las instrucciones que usa el programa): desglose medido
  del SoC en LUT: ALU 255, ID 225, LSU 118, decoder 91, fetch 62 (Espino ≈ 756 LUT + 4 BRAM). Recortado
  quedaría ≈ 400 LUT, pero cada núcleo sigue necesitando 4 BRAM de registros: 4 núcleos ≈ 1600 LUT y
  16 + 8 BRAM, no caben (1280 LC, 16 BRAM). Dos recortados cabrían justo (≈ 1070 LC, 16 BRAM). Aun así:
  misma plata, latencia igual o peor (memoria y SPI compartidos), y el core deja de ser el Espino.
  Lo único que bajaría ciclos de verdad es el pipeline (CPI 2,2 por la lectura sincrónica del banco de
  registros), y ya se usa el 1 % de la ronda 3.
- **Multinúcleo**: no cabe (el SoC de competencia ocupa 995 de las 1280 celdas de la HX1K; quedan 285, y el
  Espino solo es la mayor parte de esas 995) y no hay nada que paralelizar: un precio
  por tick y una cadena de 3 comparaciones dependientes. Fracción paralela ≈ 0 → speedup 1.
- **CUDA**: corre en GPU NVIDIA, no en la FPGA ni en el Espino. Sirve fuera de línea para barrer parámetros,
  pero no hace falta: `ref/competencia.py` simula 220 millones de ticks (2 algoritmos × 2 largos × 2732
  ventanas) en ~4 s con numba en la CPU. Lo que mejoró la ganancia fue entender la normalización, no fuerza bruta.
- **Decisión en hardware** (comparadores en el esclavo SPI): latencia 0, pero no cambia la plata, porque la
  maestra igual lee la decisión del tick anterior. Queda como alternativa analizada.

### 12.7 Riesgos y preguntas para el profesor (18-nov)

1. ~~¿Cuántos ticks tiene cada ronda?~~ **Confirmado (18-nov): 20.000 ticks.**
2. **¿La normalización de la competencia es exactamente la de practica_meta** (mín → 100, máx → 255 sobre la
   serie que se corre)? Si no tocara 100 nunca, el agente no opera y termina con $10.000 (no pierde, pero
   no gana).
3. Si otro grupo encuentra la misma regla, el desempate en plata lo da la toma de ganancia (220).

### 12.7b Montecarlo (`python ref/montecarlo.py` → `resultados/montecarlo.csv`)

1000 series sintéticas de 20.000 minutos por escenario, normalizadas como la práctica. Algoritmo final:

| escenario | geo | 5 % peor | peor | pierde | órdenes | solo 100/255 | CyM |
|---|---|---|---|---|---|---|---|
| paseo aleatorio | 1,883 | 1,045 | 0,989 | 1,2 % | 3,4 | 1,833 | 0,990 |
| sube +40 % | 2,519 | 2,497 | 1,381 | 0 % | 4,0 | 2,512 | 2,131 |
| baja −30 % | 1,100 | 0,999 | 0,983 | 12,8 % | 2,1 | 1,097 | 0,464 |
| volatilidad ×3 | 1,849 | 1,028 | 0,989 | 1,6 % | 3,4 | 1,809 | 0,995 |
| vuelve a la media | 2,123 | 1,147 | 0,995 | 0,4 % | 4,1 | 1,980 | 0,987 |
| momentum | 1,900 | 1,042 | 0,993 | 0,8 % | 3,4 | 1,864 | 1,009 |
| saltos ±3 % | 1,865 | 1,029 | 0,989 | 0,8 % | 3,4 | 1,826 | 0,980 |
| días reales al azar | 1,859 | 1,025 | 0,986 | 2,3 % | 3,3 | 1,828 | 1,002 |

El resultado no depende de las 5 acciones: el peor caso nunca baja de 0,983 y 220/120 suman en todos los
escenarios (no son sobreajuste). En la tendencia a la baja pierde seguido pero poco (el mínimo está al final:
compra en 100 cerca del cierre; pierde comisiones y redondeo).

### 12.8 ¿Queda algo por mejorar? (18-nov, con la regla final)

- **Contra un oráculo**: una sola compra-venta perfecta sabiendo el futuro da geo 2,191; el agente 1,998 =
  **91 % capturado**. En las ventanas con el mínimo antes que el máximo (57 %) captura el **99,7 %**; en las
  con el máximo primero (43 %) el 81 % (1,45 contra 1,79): se pierde la subida previa al 255, cuando todavía no
  se sabe que el máximo viene primero.
- **Operar muchas veces** exigiría predecir el minuto siguiente. Con el retraso de 1 tick de la maestra lo que
  cuenta es la autocorrelación de cambios a rezago 2: **−0,008** (rezago 1 es −0,12, pero no se alcanza a usar).
  No hay ventaja de corto plazo.
- **Ejecución**: al ver 100 se compra en promedio a 100,94; al ver 255 se vende a 254,06. Fijo por el protocolo
  e igual para todos. Comisiones: 4 órdenes ≈ 0,1 %.
- **Estar dentro antes de ver extremos si p ≥ 200** (lo único que ataca el 43 %): +0,9 % en promedio, pero peor en
  META y en 2024 y el peor caso cae de 0,970 a 0,764. **Descartado.**
- **Hardware**: el tick usa el 1 % de la ronda 3; nada de hardware cambia la plata. Bajar el CPI (2,2) exige
  modificar el core; sacar el contador de ciclos del P2 ahorraría ~150 celdas (solo métrica de área). No vale
  el riesgo a una semana de la competencia.
- **Conclusión**: el algoritmo está cerca del techo práctico. Lo que sí vale: confirmar la normalización con el
  profesor, preparar la defensa, push y declaración de IA.

## 13. Feedback de las prácticas con la maestra (23-nov) y cambios

### 13.1 Lo que se vio (fotos y videos en `Escritorio/avance proyecto`)
- El grupo usó **distintas filas en distintas prácticas (5, 3 y otra)**, así que no se puede leer una fila
  como "nosotros" en todas las rondas.
- Primer video: la **Fila 5** (nosotros) terminó **1ª con ~$21.400 (+109 % vs mantener)**.
- Apple jul 2022: la **Fila 3** terminó **1ª con $20.469 (+85 %)**, 7 órdenes, decisiones `0x7F`/`0xBF`
  (el estilo de nuestro algoritmo).
- AMD ene 2022 (reconstruida exacta: AMD 10-ene-2022 10:20, CyM $8.315 igual a la pantalla): la 1ª fue la
  Fila 6 con $21.695; nuestra versión del 17-nov sin recompra da $21.824 en esa serie (la final daría ~$31.000).
- Las filas con $10.000 exactos y 0 órdenes (y "sin placa" en la pantalla de conexiones) son placas que no
  escribieron DECISION; no hay evidencia de que fuera la nuestra.
- "Si parte alcista no compra nada": es así por diseño (espera el 100). Ver 13.2.
- El simulador del profe usa ~51 días = 20.000 minutos, la misma normalización.

### 13.2 Capturar subidas: híbridos probados (2732 ventanas reales, regla final como base 1,998)
| idea (solo mientras no hay garantía) | geo | peor | por empresa / año |
|---|---|---|---|
| tendencia (medias 64/512 … 512/4096) | 1,919–1,974 | 0,65–0,87 | peor en casi todas |
| "ancla" en el mínimo visto (+10…+40, salida −10…−30 desde el máximo) | 1,890–1,994 | 0,66–0,80 | peor en NFLX y 2024 |
| "ancla" en p0 (+5, +10, +20) | 1,991–2,001 | 0,67–0,85 | NFLX −2 %, 2024 −2 % |
| las mismas también después de ver ambos extremos | 1,817–1,945 | 0,44–0,82 | peor en todo |

Ninguna mejora de forma pareja; la mejor suma +0,15 % y baja el peor caso de 0,970 a 0,668. **No se cambia el
algoritmo.** Comprar al inicio cuando el precio "parte bajo" pierde porque casi siempre el precio todavía baja
al 100 antes de subir (con p0 = 105 el 255 sale primero solo ~3 % de las veces).

### 13.3 Velocidad (la prueba de "1 µs")
- La maestra toma DECISION al bajar CS. Entre el último bit de un precio y la bajada de CS siguiente quedan
  1 µs + (T − transacción): con transacciones pegadas, **~25 ciclos** (menos ~3 de sincronización).
- Antes: peor caso precio → DECISION = **34 ciclos (1,36 µs)**, justo en los ticks donde cambia la decisión
  (actualizaba piso/techo antes de escribir). Llegaba tarde en el único momento que importa.
- Cambios:
  1. Registro **NUEVO** en el esclavo SPI (offset `0x0C`, `rtl/pochoco_spi_slave.v`, +11 celdas):
     `{precio nuevo, 23'b0, precio}`; leerlo baja el aviso. Espera = `lw` + `bgez` (6 ciclos por vuelta),
     sin `andi` ni segunda lectura. Piso/techo se guardan sumados a `0x8000_0000` y se comparan sin signo.
  2. En los ticks de cambio se escribe DECISION **antes** de actualizar el estado; COMPRAR y VENDER quedan
     en registros (`a0`, `ra`) para no gastar un `li`.
- Con 1 y 2: peor caso **16 ciclos (0,64 µs)**.
  3. (Martín autorizó tocar el núcleo sin destruirlo.) **Lectura bloqueante**: el esclavo SPI saca `wait_o`
     cuando se lee NUEVO sin precio nuevo, y `espino_load_store_unit` no termina el load mientras esté en 1
     (repite la petición con el pipeline detenido). La espera es un solo `lw`, sin granularidad.
- Final: peor caso **9 ciclos (0,36 µs)** con T = 100 µs y con transacciones pegadas, **3,8× menos** que en la
  mañana. Misma plata exacta. 985 celdas, 46,7 MHz. ISA en 4 variantes OK, ISS = RTL ciclo a ciclo, placa OK.
- 4 núcleos o 4 hilos (lo del amigo): no bajan la latencia (un precio por tick, comparaciones encadenadas; con
  hilos intercalados cada hilo corre a 1/4 de velocidad). No se hace.
- Fuentes revisadas para ganancia (23-nov): Fung 2017 (two-way trading con m y M conocidos: razón óptima
  φ = M/m = 2,55 con una transacción; nuestra regla captura el 99,7 % cuando el mínimo llega primero),
  El-Yaniv et al. 2001 (precio de reserva √(mM) ≈ 160: es un umbral por nivel, ya barrido y peor), Bertram 2010
  (umbrales OU: la serie no es OU), Kelly (no aplica a todo-o-nada). Banda del tramo libre ajustada en conjunto
  (140/190: +0,4 %, no pareja), escalera, stop dinámico y posición parcial: peores o ruido. **Sin cambios.**
- Para simular y grabar: `docs/simular-y-grabar.md` (`tools/simular.py`, `grabar.ps1`).

## 14. Ganarle a rivales con reglas parecidas (23-nov, tarde)

- Entre reglas casi iguales casi todas las rondas empatan: contra 100/255 puro empatamos el 89 %, contra
  100/255+220 el 95 %. Decide el **neto cara a cara** (% de rondas que gano − % que pierdo).
- **Toma de ganancia 225** (antes 220): promedio 1,997 vs 1,998, pero cara a cara +6,2 % neto contra un
  rival con 220 (antes +2,9 %) y +4,7 % contra nuestra propia versión con 220; lo mismo en los 8 escenarios
  del Montecarlo. Adoptado. practica_meta: $22.319.
- **Herramienta que sigue buscando**: `python ref/buscar_ventajas.py` (constantes) y
  `--reglas todas` (reglas nuevas de compra: ancla_p0, ancla_min, ema, ruptura; antes de los extremos o también
  en el tramo libre). Marca "robusta" solo si gana cara a cara a la actual y a cada rival en datos reales, no
  pierde en ningún escenario del Montecarlo, no baja el promedio más de 0,3 % y no empeora la peor ventana.
  Rivales nuevos con `--rival compra,venta,toma,recompra`. ~15–40 s.
- Resultado: ninguna robusta. Las mejores para **capturar subidas** (no robustas por la cola):

| regla (solo antes de ver extremos) | geo | neto vs actual | vs 100/255 | vs +220 | pierde | peor |
|---|---|---|---|---|---|---|
| actual 225/120 | 1,997 | — | +5,3 % | +6,2 % | 1,1 % | 0,970 |
| ancla_p0 +30 (sale en p0) | 2,007 | +8,7 % (5/5 empresas, 3/3 años) | +11,3 % | +11,4 % | 0,9 % | 0,790 |
| ruptura (máximo nuevo tras 3000 ticks, sale −20) | 2,009 | +6,9 % (4/5, 3/3) | +10,3 % | +11,1 % | 1,5 % | 0,817 |

  Ganan cara a cara en datos reales, pero la peor ventana pasa de −3 % a −18/−21 % y en series sintéticas sin
  impulso pierden. Decisión de Martín.

## 15. Velocidad final (23-nov)
Peor caso precio → DECISION: 34 → 16 (registro NUEVO + DECISION primero) → **9 ciclos (0,36 µs)** con la
lectura bloqueante en la unidad de carga del Espino (`data_wait_i`). 985 celdas. Ver 13.3.

## 16. Ancla: probada, escrita y APAGADA (23-nov, noche)

`ANCLA` en `sw/trade.s` (fase 1, antes del primer extremo: compra si p ≥ p0 + ANCLA, vende si p ≤ p0; bucle
aparte para no frenar la fase 2). Con ANCLA = 30, en 13.652 ventanas reales: geo 2,006, cara a cara +7,7 % neto
contra la versión sin ancla y +11 % contra los rivales; pero **peor ronda −21 %** (NFLX 5-ago-2022), pierde más de
10 % en el 0,05 % de las ventanas, y en el Montecarlo el peor caso llega a −46 % (0,49 % de las series pierden >10 %).
Frenos probados (un solo disparo, stop desde la entrada o desde el máximo): los que bajan la peor ronda a ~−10 %
pierden la ventaja cara a cara (−2 a −8 % neto contra sin ancla). Martín pidió la pérdida mínima posible →
**ANCLA = 0**: el programa queda idéntico al de la sección 14 (peor ronda −3 %, P(pierde >5 %) = 0). Para prenderla:
cambiar a 30, `tools/simular.py`, `ref/verificar.py`, `grabar.ps1`.

Testbench oficial con practica_meta completa (225/120, sin ancla): 4/4, $22.319, peor caso 9 ciclos.

## 17. Ancla fraccional: tomar las subidas del comienzo con riesgo acotado (23-nov, noche)

Martín: ganar más aceptando un poco más de riesgo, lo más chico posible. El ancla completa perdía ~20 % por
vuelta (6 vueltas en NFLX 5-ago-2022 14:30: $10.000 → $2.816 antes del 100; final $6.942 vs $24.797 sin ancla).
Frenos (stop, presupuesto de pérdida) acotan la pérdida pero pierden cara a cara (−7 a −17 % neto).
**Solución: tamaño fraccional** — el ancla compra solo q acciones una vez (`ANCLA_ORDEN`) y después "mantener".

| ancla 30, compra… | geo | peor | P(>5 %) | neto vs sin ancla | vs 100/255 | vs +220 |
|---|---|---|---|---|---|---|
| sin ancla | 1,9970 | −3,0 % | 0 % | — | +5,4 % | +6,4 % |
| 10 acciones | 2,0022 | −3,5 % | 0 % | +8,1 % | | |
| **15 acciones (elegido)** | **2,0044** | **−5,5 %** | 0,01 % | **+8,4 %** | **+11,9 %** | **+12,1 %** |
| 20 acciones | 2,0064 | −7,8 % | 0,01 % | +8,5 % | | |
| todo | 2,0070 | −21 % | 0,15 % | +7,7 % | | |

15 acciones: P(pierde) baja de 1,09 % a 0,62 %; por empresa y año nunca peor que sin ancla; Montecarlo peor −14 %.
practica_meta: $23.170. Velocidad: fase 1 reordenada (caso común = 2 comparaciones; primer tick escribe antes
de armar el ancla): peor caso 11–12 ciclos (sin ancla 9). 63 palabras.

Optimizador continuo: `ref/optimizador.py --horas 8` (familias de entrada sube_p0, sube_min, ruptura, medias,
caída; tamaño, salida, toma, recompra; límites peor ≥ 0,94, P(>5 %) ≤ 0,05 %, gana cara a cara a la actual,
no peor por empresa/año, Montecarlo). Log: `resultados/optimizador_log.md`. Lanzado el 23-nov por 8 h.

## 18. Otras "anclas" por tramo (23-nov, 16 h)

Misma idea que el ancla (actuar donde el algoritmo no hace nada, con tamaño chico), tramo por tramo:
- Vio el 100 y espera el 255 / vio el 255 y espera el 100: el siguiente extremo está garantizado; actuar antes solo pierde.
- Tramo libre (vio los dos), compra parcial más arriba (15–30 acciones en ≤140/150/160) o venta parcial antes de 225
  (30–45 en ≥200/210/215): peor ronda igual (−5,5 %), promedio ±0,1 %, contra rivales +13–14 % (vs +11,9 %), pero
  **pierden cara a cara contra la versión grabada** (−1 a −5 % neto) y en el Montecarlo (−3 a −11 %). No se cambia.
El optimizador (ref/optimizador.py) sigue corriendo; su mejor (ancla +26, recompra 117) no supera a la grabada contra rivales.

## 19. Fin del optimizador y versión D (24-nov)

8 h: 82.976 candidatas, 1.834 dentro de los límites, **todas de la familia ancla** (las demás reglas de entrada
nunca cumplieron el riesgo). Mejor contra rivales: **ancla 29, recompra 122 (versión D)**. En 13.652 ventanas
reales: geo 2,0057 (A 2,0044), peor −4,8 % (A −5,5 %), P(pierde) 0,60 %, P(>5 %) 0 %, vs 100/255 +12,1 %,
vs +220 +12,4 %; cara a cara D vs A +12,2 % (2022 +9,1, 2023 +12,9, 2024 +15,5; todas las empresas). Máximo
posible con D: ×6,53 ($65.349, META desde 2022-06-28 14:40); promedio $21.112, mediana $23.916, 1 % mejor
sobre $42.684. Plan: probar A y D con la maestra el miércoles y competir con D si coincide con la simulación.

## 20. ¿Promedio de $24.000–25.000? (24-nov, madrugada)

- Comparar lo comparable: en las prácticas de la maestra reconstruidas (AMD ene 2022 10:20, Apple jul 2022, practica_meta),
  las versiones promedian ~$26.200 (A $26.361, D $26.245); los compañeros reportan ~$22.000 en sus rondas.
- Sobre TODOS los períodos posibles (13.652): D $21.112; **una sola compra-venta perfecta sabiendo el futuro: $22.409**
  (D captura el 94 %). Mínimo primero: D $25.266 vs perfecta $25.500; máximo primero: $15.609 vs $18.315.
  Promediar $24–25k en general exige varias operaciones casi perfectas por ronda (predecir minuto a minuto), lo que no
  existe en estos datos. Techo con costo 10 % por cambio: $28.693; con 20 %: $17.720.
- Optimizador con objetivo promedio (`ref/optimizador.py --objetivo promedio --base D --peor 0.90`): prueba corta,
  mejor ruptura (q≈40, toma 180, recompra 140): $21.404 (+1,4 %), peor −9,5 %, Montecarlo −7 % cara a cara. Corrida de
  2 h lanzada (resultados/promedio_log.md).
- Versión segura guardada: etiqueta `competencia-v1` y `versiones_guardadas/competencia-v1/` (A–D, bitstreams + md5).

## 21. Universo tecnológico: 22 acciones, 11.789 períodos (24-nov)

`ref/universo.py` → `docs/informe_universo.html`. Acciones: META, AAPL, NFLX, AMD, TSLA (dentro de muestra) + NVDA, TSM,
AVGO, MU, INTC, QCOM, MSFT, GOOGL, AMZN, PLTR, ORCL, IBM, AMAT, LRCX, KLAC, SNPS, CDNS (fuera; sin datos: Samsung,
SK Hynix, ASML, Arm). Promedios: A $21.113, B $21.175, C $21.077, D $21.118; rivales 100/255 $20.664, +220 $20.787;
mantener $12.571 (pierde 40 %). Neto vs rivales: D +8,7/+9,9 %, A +8,8/+10,0 %, B +4,8/+7,1 %. Fuera de muestra el ancla
no sube el promedio (D $21.122 vs B $21.200) pero sí gana más rondas a los rivales; su peor caso empeora a −13,6 %
(INTC dic-2022; KLAC abr-2022; QCOM sep-2024) y pierde cara a cara contra B en AMAT, AMZN, CDNS, KLAC, MSFT, NFLX,
PLTR y SNPS. Velocidad: todas las versiones a tiempo hasta transacciones pegadas (margen 10–13 ciclos).
Siguiente: optimizador sobre el universo (`--universo --objetivo cara --base D`), lanzado 3 h → resultados/universo_log.md.

## 22. Resultado del optimizador sobre las 22 acciones (24-nov)
Corrió 3 horas (80.061 candidatas, 909 cumplieron peor >= 0,90). La mejor: ancla 22, compra 14 acciones,
recompra 119 (`ref/comparar_universo.py` la mide):

| versión | promedio | peor | neto vs 100/255 | neto vs +220 | neto vs D |
|---|---|---|---|---|---|
| D (22 acciones) | $21.118 | −13,5 % | **+8,7 %** | **+9,9 %** | 0 |
| mejor del optimizador (22 acciones) | $21.102 | −9,9 % | +5,8 % | +7,1 % | +18,0 % |
| D (5 de la competencia) | $21.120 | −4,7 % | **+12,7 %** | **+12,8 %** | 0 |
| mejor del optimizador (5) | $21.098 | −3,0 % | +9,8 % | +9,9 % | +17,4 % |

Le gana a la D cara a cara, pero contra los rivales (los compañeros) gana menos rondas que la D, en las 22
acciones y en las 5. Lo que importa es ganarles a los rivales: **no se agrega versión E; se compite con la D.**
La única ventaja de la candidata es una peor ronda más chica (−3 % vs −4,7 % en las 5 de la competencia).

## 23. Por qué la D perdía contra el rival en Amazon, Synopsys y Cadence, y la versión E (24-nov)
`ref/perdidas_rival.py` descompone la D regla por regla y prueba variables nuevas.

**La causa es el ancla.** De las 348 rondas que la D pierde contra el rival 100/255 en esas tres acciones,
el 85 % se arregla quitando el ancla, el 11 % quitando la toma 225 y el 2 % quitando la recompra 122. Sin
ancla, la D le gana al rival en las tres.

**El ancla depende del primer precio p0.** En las rondas donde el ancla compra (22 acciones), neto de la D
contra la versión sin ancla según p0:

| p0 | 100–119 | 120–139 | 140–159 | 160–179 | 180–199 | 200–255 |
|---|---|---|---|---|---|---|
| neto D vs sin ancla | −55,8 % | −31,5 % | −12,5 % | +16,9 % | +37,0 % | +49,2 % |

Con p0 bajo, el 100 suele estar todavía por venir: la subida del comienzo es un rebote que vuelve a p0 y el
ancla vende con pérdida. Con p0 alto, la subida suele seguir hasta el 255. El patrón es igual en las tres
acciones problema, en las 5 de la competencia y en las 22.

**Lo que no sirvió** (neto contra el rival en las 22 acciones, D = +8,7 %): toma parcial (vender 20–50
acciones en 225 y el resto en 255): −6,5 % a +9,1 %; recompra parcial: −3,8 % a +8,3 %; toma 225 solo desde
el tick 10.000–17.000: +8,3 % a +8,6 %; recompra solo hasta el tick 14.000–19.000: +6,2 % a +8,2 %; ancla
solo en los primeros 500–4.000 ticks: +1,5 % a +3,4 %.

**Versión E = D + `ANCLA_P0 = 160`:** el ancla se arma solo si p0 ≥ 160. Son 2 instrucciones al arrancar,
después de escribir la primera DECISION; los bucles no cambian (latencia igual a la D).

| | D | E |
|---|---|---|
| neto vs 100/255 / vs +220, 22 acciones | +8,7 % / +9,9 % | **+12,4 % / +14,0 %** |
| neto vs 100/255, 3 acciones problema | −2,0 % | **+6,8 %** |
| peor acción (neto vs 100/255) | −4,0 % (Cadence) | **+5,0 %**: gana en las 22 |
| peor año (neto vs 100/255) | +3,1 % | **+8,3 %** |
| neto vs 100/255 / vs +220, 5 de la competencia (paso 250) | +12,7 % / +12,8 % | **+15,4 % / +15,4 %** |
| peor ronda, 22 acciones / 5 de la competencia | −13,5 % / −4,7 % | −13,5 % / −4,7 % (igual) |
| promedio, 22 acciones / 5 de la competencia | $21.118 / $21.120 | $21.183 / $21.148 |
| E contra D cara a cara | | +4,0 % (22) / +2,3 % (5) |

El corte es una meseta: 140, 150, 160 y 170 dan entre +11,6 % y +12,4 % en las 22 y +14,6 % a +15,4 % en las 5;
se eligió 160 (el mejor en las 22). Con ancla más grande (35, 25–40 acciones) se gana un poco más de neto, pero
la peor ronda llega a −19 % hasta −55 %: no se usa.
Verificado: el programa ensamblado (65 palabras) decide igual que `ref/trader.py` y que el simulador numba en
24 series elegidas con p0 bajo y alto (`tools/versiones.py armar` repite la comprobación).

## 24. Estado de la versión E: velocidad, tiempo sin hacer nada y ganancia (24-nov)
**Velocidad** (reloj 25 MHz). Del precio a la DECISION: peor caso 12 ciclos (RTL, testbench oficial); 9 si
p0 < 160 (sin ancla). El tick completo (leer precio → volver a esperar) en el ISS: 11,9 ciclos promedio,
p99 16, máximo 20 (120.000 ticks). El resto del tiempo el núcleo está detenido en la lectura bloqueante.

| período de la maestra | ciclos por tick | ventana para decidir | margen (− 12) | núcleo esperando |
|---|---|---|---|---|
| 10 ms (ronda 1) | 250.000 | 249.784 | 249.772 | 99,995 % |
| 1 ms (ronda 2) | 25.000 | 24.784 | 24.772 | 99,95 % |
| 100 µs (ronda 3) | 2.500 | 2.284 | 2.272 | 99,5 % |
| 20 µs | 500 | 284 | 272 | 97,6 % |
| 10 µs | 250 | 34 | 22 | 95,2 % |
| 9,5 µs (transacciones pegadas) | 237 | 22 | 10 | 95,0 % |

**Mercado** (5 de la competencia, 5.462 períodos; entre paréntesis el rival 100/255):
promedio $21.148 ($20.465), mediana $24.443, p5 $10.578, peor $9.527, mejor $65.349, pierde plata 0,77 %
(1,14 %), le gana a comprar y mantener 99,7 %. Con acciones el 47,9 % del tiempo (45,5 %): **en caja el 52,1 %**,
esperando el piso. 4,1 órdenes por ronda (3,2). Caída máxima promedio $3.985. En las 22 acciones: promedio
$21.183, pierde 1,32 %, en caja 52,1 %.

## 25. ¿Se puede llegar a una mediana de $27.000? (24-nov)
Un compañero reporta mediana ≈ $27.000 con poco riesgo. Medido en las 5 acciones de la competencia (5.462
períodos, `ref/techo_mediana.py` y un barrido de estrategias con bandas):

- **Techo de una operación por ronda: mediana $25.500** (comprar todo en 100 y vender en 255 = ×2,55). Ninguna
  ronda pasa $27.000 con una sola operación: hace falta ganar en varias operaciones en más de la mitad de las rondas.
- Las rondas son de dos tipos. **Primero el 100 (57 %):** la E saca mediana $25.072, casi el techo. **Primero el
  255 (43 %):** la E saca mediana $13.996 (el rival $13.616). La mediana total la fija el primer tipo.
- La mejor mediana posible variando toma, recompra y ancla es $24.578 (toma 210, recompra 140, sin ancla): solo
  $135 más que la E, y le gana menos rondas al rival (+6,4 % contra +15,4 %). No conviene.
- Operar oscilaciones con bandas alrededor de una media (sola, o sumada a la E cuando está en caja o siempre):
  1.176 combinaciones, todas peores. La mejor mezcla con la E da mediana $24.068, pierde plata en 3 % de las
  rondas y pierde contra la E en neto −20 %. La banda sola pierde plata en 41 % de las rondas. La orden se ejecuta
  al precio del tick siguiente, y eso se come las oscilaciones de un minuto.
- Con reglas como las nuestras, que la mediana de 3 rondas al azar pase $27.000 ocurre en el 0,4 % de los casos.
  **Una mediana de $27.000 tiene que salir de pocas series favorables**, no de muchas rondas. En la práctica de
  AMD (enero 2022) la E saca $29.930, y la mejor fila de la sala sacó $21.695 (foto en Escritorio/avance proyecto).
  En las 3 series de práctica conocidas la E saca $29.930, $25.589 y $23.215 (mediana $25.589).
- Las reglas oficiales (`tb/tb_proyecto_4.sv`) recortan la compra a la caja y la venta a las acciones que hay:
  no hay apalancamiento ni venta en corto que permita pasar el techo.

**Para comparar en serio:** anotar las series donde el compañero sacó esos montos (acción, mes, hora de inicio
y "comprar y mantener" de la pantalla) y correr `tools/simular.py --buscar` en cada una: muestra lo que habría
sacado cada versión nuestra en esa misma serie.
- Un simulador que ejecuta la orden al precio del **mismo** tick (error común; la maestra usa el siguiente)
  infla los resultados: la E pasa de mediana $24.443 a $25.030 y las bandas suben hasta $6.000 en mediana. Aun
  así nada llega a $27.000. Si el compañero midió con su propio simulador, revisar ese punto, las comisiones y el
  tope de 63 por orden. La comparación que vale es en la maestra, con todas las placas en la misma serie.

## 26. Más de $40.000 en la META del testbench = ajustado a esa serie (24-nov)
Los compañeros reportan más de $40.000 en `tb/practica_meta.csv`. En esa serie es posible: p0 = 165, baja a
**134** (tick 4.959), sube a **255** (tick 10.965), baja a **100** (tick 17.084), sube a **225** y termina en 160.
Dos operaciones perfectas (134 → 255 y 100 → 225) dan **$42.817**. Una regla que compre todo en p ≤ 135 antes
de ver el 100 o el 255 saca **$38.926** ahí (la E: $23.215).

Pero esa misma regla en las 5 acciones de la competencia (5.462 períodos, `ref/sobreajuste_meta.py`):

| comprar todo en p ≤ X al comienzo | META testbench | mediana | promedio | neto vs E | neto vs rival 100/255 |
|---|---|---|---|---|---|
| E (esperar el 100) | $23.215 | **$24.443** | **$21.148** | 0 | **+15,4 %** |
| X = 135 | **$38.926** | $19.055 | $19.694 | −47,7 % | −28,5 % |
| X = 150 | $36.304 | $18.647 | $19.490 | −45,2 % | −27,2 % |

La serie de práctica es pública y una sola: se puede ajustar una regla a ella, pero en las series ocultas
de la competencia pierde contra la E en casi la mitad de las rondas y contra el rival simple también.
**No se cambia la E.** Si un grupo saca más de $40.000 en la META del testbench, lo más probable es que
en la competencia saque menos que nosotros.

## 27. Las 8 series de práctica nuevas (24-nov): conviene la D, no la E
`tools/correr_series.py` sobre las 8 prácticas (Descargas/practica_*.csv; meta_2022 = tb/practica_meta.csv):

| serie | A | B | C | D | E | rival 100/255 | rival +220 | CyM |
|---|---|---|---|---|---|---|---|---|
| META 2022 | 23.170 | 22.319 | 23.399 | 23.215 | 23.215 | 15.894 | 21.752 | 9.695 |
| AMD ene 2022 | 30.139 | 29.479 | 31.368 | 29.930 | 29.930 | 17.181 | 21.824 | 8.315 |
| AMD may 2022 | 16.771 | 16.164 | 16.861 | 16.693 | 16.693 | 16.164 | 16.164 | 9.647 |
| Apple 2022 | 25.773 | 25.773 | 26.603 | 25.589 | 25.589 | 24.974 | 24.974 | 11.063 |
| Apple 2023 | 12.229 | 10.872 | 11.808 | 12.229 | 10.872 | 10.872 | 10.872 | 10.371 |
| Netflix 2022 | 14.939 | 13.356 | 14.969 | 14.909 | 13.356 | 13.356 | 13.356 | 9.179 |
| Netflix 2023 | 17.327 | 16.199 | 17.417 | 17.342 | 17.342 | 16.199 | 16.199 | 9.170 |
| Tesla 2022 | 22.071 | 21.659 | 22.131 | 22.071 | 22.071 | 20.421 | 21.467 | 9.995 |
| **promedio** | 20.302 | 19.478 | **20.570** | 20.247 | 19.884 | 16.883 | 18.326 | 9.679 |

7 de las 8 son "primero el 255, después el 100" (en las series reales: 59 % en 2022, 35 % en 2023, 33 % en
2024). En ese tipo el ancla vale mucho (`ref/tipo_255_primero.py`, 2.347 períodos): neto vs rival 100/255
D +47,8 %, C +49,0 %, E +39,0 %, B +8,2 %. En "primero el 100" el ancla resta (D −13,7 %, E −2,4 %).
La D le gana a la E si más del 56 % de las rondas son "primero el 255". Si la competencia se parece a las
prácticas, **competir con la D** (le gana a los rivales en las 8; la E empata en 2). La C saca un poco más
en promedio, pero su recompra 117 la hace perder más en "primero el 100".

## 28. Compras perfectas en las 8 prácticas y cuánto captura la D (24-nov)
`ref/compras_perfectas.py` (visión perfecta, todo el patrimonio en cada operación, $5 por orden):
mediana con 1 operación $22.490, 2 operaciones $36.642, 3 $52.202, 5 $83.099, 10 $176.677.
La D captura de la ganancia de **la mejor operación única**: mediana **89 %** (rival 100/255: 57 %).
Rango: 15 % (Apple 2023) a 160 % (AMD ene 2022, donde hace más de una operación buena).
Contra el techo de 2 operaciones la D llega a una mediana de 54 % del patrimonio.

## 29. Versión F: comprar todo al inicio si p0 ≥ 170 y esperar el 255 (24-nov)
**Idea.** Antes de ver un extremo, el 100 y el 255 todavía tienen que aparecer. Si se compra todo a un precio
p y se aguanta hasta el 255, se sale con ×255/p > 1 **pase lo que pase**: si el 100 llega antes, igual
después llega el 255. En esa fase no hay pérdida posible, solo costo de oportunidad (si el 100 llega primero,
el rival compra en 100 y saca ×2,55). Es el problema de búsqueda con precios acotados de El-Yaniv, Fiat,
Karp y Turpin ("one-way trading", precio de reserva √(100·255) ≈ 160), con un dato extra: aquí los dos
extremos están garantizados. El primer precio predice cuál llega primero (`ref/esperar_255.py`):

| p0 | 100–119 | 120–139 | 140–159 | 160–179 | 180–199 | 200–219 | 220–255 |
|---|---|---|---|---|---|---|---|
| P(255 primero) | 2 % | 11 % | 31 % | 45 % | 62 % | 72 % | 89 % |

**F** (`-D ANCLA=29 -D RECOMPRA=122 -D TODO_P0=170`): si p0 ≥ 170 compra todo en el primer tick y espera el
255 (sin stop); si no, la D (ancla 29 con 15 acciones). Después, igual que la D. 69 palabras; los bucles no
cambian. Probado también (`ref/mejorar_practicas.py`, `ref/grilla.py`, `ref/hibrido_p0.py`): ancla grande con
stop (peor −32 %), grilla por nivel (pierde contra el rival en las reales) y cortes 160–200 (meseta).

| | D | **F** |
|---|---|---|
| 8 prácticas: promedio / mediana | $20.247 / $19.706 | **$23.031 / $23.436** |
| 8 prácticas: contra la D | | gana 4, empata 4, pierde 0 |
| 8 prácticas: contra el rival 100/255 | gana 8 | gana 8 |
| 5 acciones (5.462): neto vs 100/255 / +220 | +12,7 % / +12,8 % | **+22,1 %** / +22,1 % |
| 5 acciones: peor ronda / pierde plata | $9.527 / 0,66 % | **$9.842 / 0,07 %** |
| 22 acciones (11.789): neto vs 100/255 / +220 | +8,7 % / +9,9 % | **+18,3 % / +18,4 %** |
| 22 acciones: promedio / peor / pierde | $21.118 / $8.645 / 1,2 % | $20.546 / **$9.207 / 0,2 %** |
| Montecarlo (8 escenarios × 1.000): neto vs 100/255 | +13 % a +16 % (sube −5,5 %) | **+29 % a +84 %** (sube −6 %) |

Costo: en series al azar el **promedio** baja ~$570 (en "primero el 100" saca ×255/p en vez de ×2,55), pero
gana muchas más rondas, pierde plata en menos y en las prácticas del profesor saca $2.800 más por ronda.
Verificado en el RTL con el testbench del curso: AMD ene 2022 $35.554, Tesla 2022 $25.922 y META 2022 (tb/practica_meta.csv) $23.215, 4/4 cada una, 12 ciclos; igual al modelo.

## 30. Optimización con las 22 empresas y torneo todos contra todos: versión G (24-nov)
Sin usar las prácticas para elegir. `ref/optimizar_22.py`: 1.296 combinaciones (todo al inicio si p0 ≥ P0;
todo si el precio llega a Y antes de los extremos; ancla con o sin stop; toma; recompra) sobre 11.789 rondas
de las 22 empresas 2022–2024, con límites de riesgo (peor ≥ 85 %, pierde ≤ 1 %) y validación fuera de
muestra. La mejor contra los rivales fue "todo si llega a 240" (neto +35,5 %), estable fuera de muestra
(elegida con 2022–23: +33,5 % en 2024; elegida con 11 empresas: +35,4 % en las otras 11). Pero gana muchas
rondas por poco, y la F le gana cara a cara. Por eso `ref/torneo.py` enfrenta 15 estrategias todas contra
todas y elige la de mejor neto contra su peor rival: **p0 ≥ 180 + Y 240** es la única que le gana a todas
(+0,8 % contra su peor rival, +5,0 % contra la F, +25 % contra la D, +30 % contra los rivales simples).

**G** (`-D ANCLA=0 -D RECOMPRA=122 -D TODO_P0=180 -D TODO_Y=240`, 51 palabras): antes de los extremos compra
todo si el primer precio es ≥ 180 o si el precio llega a 240, y espera el 255 (garantizado, sale con ×255/p).
Sin ancla. Después, igual que la D.

| | D | F | **G** |
|---|---|---|---|
| 22 acciones: neto vs 100/255 / +220 | +8,7 / +9,9 % | +18,3 / +18,4 % | **+29,7 / +30,2 %** |
| 22 acciones: promedio / peor / pierde | $21.118 / $8.645 / 1,2 % | $20.546 / $9.207 / 0,2 % | $20.738 / $8.922 / 0,2 % |
| Torneo (15 estrategias): neto contra su peor rival | −36,9 % | −5,9 % | **+0,8 %** |
| Montecarlo: neto vs 100/255 (8 escenarios) | −5,5 a +16 % | −6 a +84 % | **+0,1 a +84 %** |
| 8 prácticas: promedio / mediana | $20.247 / $19.706 | **$23.031 / $23.436** | $21.970 / $23.213 |
| 8 prácticas: gana al rival 100/255 | 8 | 8 | 8 |

En las prácticas la F saca más (AMD may, Apple 2023, Netflix 2022), pero son 8 series elegidas; en todo lo
demás (22 empresas, fuera de muestra, torneo, Montecarlo) la G es la mejor.
RTL de la G con el testbench del curso: META 2022 $23.256 (4/4, peor caso 13 ciclos: 9 de margen con
transacciones pegadas) y AMD ene 2022 $35.554 (4/4, 11 ciclos); igual al modelo. Guardada en competencia-v4.

## 31. Por qué los compañeros sacan ~$26.000 en las prácticas (24-nov)
"Comprar todo al primer precio y esperar el 255" (`ref/todo_al_inicio.py`) saca **$26.685** de promedio en
las 8 prácticas (G $21.970, rival $16.883): las prácticas son 7 de 8 "primero el 255" y con p0 alto, donde
comprar al inicio captura p0 → 255 y después 100 → final. En las 22 empresas (11.789 rondas) la misma regla
saca $19.343 de promedio y llega a $26.000 solo en el 8 % de las rondas; contra la G pierde en neto −36 %.

| tipo de ronda (22 empresas) | % | todo al inicio | G | rival | todo al inicio vs G |
|---|---|---|---|---|---|
| primero el 255 | 41 % | $19.072 | $16.786 | $14.519 | +24 % |
| primero el 100 | 59 % | $19.531 | $23.470 | $24.913 | −78 % |

"Todo al inicio" le gana a la G solo si más del **76 %** de las rondas de la competencia son "primero el 255"
(en las prácticas fueron 87,5 %; en datos reales 33–59 % según el año). Es una apuesta a cómo elige el
profesor las series. Ninguna regla saca $26.000 "casi siempre" en series al azar: el techo de una operación
perfecta es $25.500.

## 32. Decisión final (25-nov)
Probadas con la maestra la G, la F y la D, **la D fue la que mejor se comportó** (decisión del grupo).
La placa quedó con la D (`.\grabar.ps1 -Version D`, VERIFY OK; bitstream = versiones_guardadas/competencia-v4/D_ancla29_rec122.bin).
