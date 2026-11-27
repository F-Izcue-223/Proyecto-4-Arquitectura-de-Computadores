# Simular y grabar la placa (paso a paso)

Todo se hace en **PowerShell**, parado en la carpeta del proyecto:

```powershell
cd "$env:USERPROFILE\OneDrive\Escritorio\Proyecto-4-Arquitectura-de-Computadores"
```

Para no escribir la ruta de Python cada vez:

```powershell
$py = "$env:USERPROFILE\anaconda3\python.exe"
```

---

## A. Simular (no necesita la placa)

### A1. La serie de práctica completa

```powershell
& $py tools/simular.py
```

Muestra el patrimonio final, las órdenes, la pérdida máxima, comprar y mantener y cuánto le ganamos.
Guarda el gráfico (precio y patrimonio, como la pantalla del profe) en `build\simulacion.png`.

### A2. Un período real de 50 días (como en la competencia)

```powershell
& $py tools/simular.py --accion AMD --desde "2022-01-10 10:20"
```

- `--accion`: META, AAPL, NFLX, AMD o TSLA.
- `--desde`: fecha y hora de Nueva York (mercado: 09:30 a 16:00), entre 2022 y 2024.
- Corre 20.000 minutos (~51 días) normalizados a [100, 255], igual que la maestra.

### A3. Muchos períodos al azar (ganancia y riesgo)

```powershell
& $py tools/simular.py --azar 200
```

Media, mediana, peor y mejor resultado, y en qué % de los períodos se pierde plata. Cambia
`--semilla 2`, `3`… para otra muestra.

### A4. Lo mismo, pero en el hardware simulado (RTL, el testbench del curso)

Agrega `--rtl` a A1 o A2. Tarda varios minutos con 20.000 ticks:

```powershell
& $py tools/simular.py --accion AMD --desde "2022-01-10 10:20" --rtl
```

Tiene que terminar en `Testbenchs aprobados: 4/4`, con el mismo patrimonio que la simulación en Python.

---

## B. Cambiar el algoritmo

1. Abre `sw\trade.s` y cambia las constantes del principio:
   - `MINIMO 100` y `MAXIMO 255`: la normalización. **Si el profe usa otro rango, se cambian aquí.**
   - `TOMA_GANANCIA 225`: dónde vende si el 255 ya pasó.
   - `RECOMPRA 120`: dónde vuelve a comprar cuando ya pasaron el 100 y el 255.
   - `ANCLA 30` y `ANCLA_ORDEN 0x4F`: antes del primer extremo, si el precio sube 30 sobre el primero
     compra 15 acciones (`0x4F`; `0x4A` = 10 acciones, más seguro; `ANCLA 0` = apagado).
2. Simula otra vez (A1 a A3). `tools/simular.py` lee las constantes de `trade.s`, así que siempre
   simula lo mismo que va a correr la placa.
3. Graba (C).

---

## C. Grabar la placa

1. Conecta la Go Board al computador por USB (el cable micro-USB).
2. Graba el diseño de la competencia:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\grabar.ps1
   ```

   Arma el bitstream (~1 minuto) y lo graba. Termina con `VERIFY OK` y `CDONE: alto`. (Este es el paso C2.)
3. Listo. Al desenchufarla y volver a enchufarla, la placa arranca sola con ese diseño.

### C1. Prueba en la placa (opcional, para estar seguro)

```powershell
powershell -ExecutionPolicy Bypass -File .\grabar.ps1 -Prueba
```

- **4 LEDs prendidos fijos y `A1` en los displays** = la placa decide exactamente lo mismo que la simulación.
- LEDs parpadeando = algún byte distinto (avisar).
- **Después hay que volver a grabar la competencia** (paso C2): la prueba no sirve para competir.

---

## E. Buscar mejoras (opcional)

```powershell
& $py ref/buscar_ventajas.py --reglas todas      # ~30 s: reglas nuevas contra la versión actual
& $py ref/optimizador.py --horas 8               # queda corriendo; leer resultados\optimizador_log.md
```

El optimizador anota cada mejora que gane cara a cara a la versión actual sin pasar el límite de riesgo
(peor ronda −6 %). Si encuentra una, hay que escribirla en `sw/trade.s` y volver a simular y grabar.

## D. Conectar a la maestra

Ver `docs/conexion-maestra.md`: pines 1 a 4 del PMOD (CS_n, MOSI, MISO, SCLK), **GND obligatorio**,
no unir los 3,3 V. Los displays muestran el último precio en hexadecimal; si cambian, está recibiendo.

---

## Si algo falla

| Mensaje | Qué hacer |
|---|---|
| `No encuentro ...oss-cad-suite...` | falta OSS CAD Suite en `%USERPROFILE%\oss-cad-suite` |
| `FT_Open fallo` o no encuentra la placa | revisar el cable USB; cerrar otros programas que usen la placa |
| `no hay un minuto de ... que empiece con` | la fecha no es de mercado (fin de semana o fuera de 09:30-16:00) |
| `--accion` no funciona | faltan los datos en `data\minuto` (no van en git; están en este computador) |
