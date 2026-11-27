# Conexión con la FPGA maestra (ficha para llevar a clases)

## Cables

| Pin del PMOD de la Go Board | Pin FPGA (`goboard.pcf`) | Señal | Va a la maestra |
|---|---|---|---|
| 1 | 65 | CS_n (entrada) | CS_n, compartida |
| 2 | 64 | MOSI (entrada) | MOSI, compartida |
| 3 | 63 | **MISO (salida)** | la línea MISO **de nuestro grupo** |
| 4 | 62 | SCLK (entrada) | SCLK, compartida |
| 5 u 11 | — | **GND** | **GND de la maestra (obligatorio)** |
| 6 o 12 | — | 3,3 V | **no conectar** |

- El PMOD es el conector de 2 × 6 pines del borde de la placa. Fila de arriba: pines 1 a 6; fila de abajo: 7 a 12.
  Antes de enchufar, buscar la marca del **pin 1** en la serigrafía.
- **Tierra común sí o sí** (lo pide el enunciado: "ambas placas trabajan a 3,3 V y deben compartir tierra").
  Sin ese cable las señales no tienen referencia y llegan bytes basura.
- **No unir los 3,3 V** de las dos placas: cada una se alimenta por su cable USB, y juntar dos fuentes puede dañarlas.
- Solo nuestro MISO sale de la placa; CS_n, MOSI y SCLK son entradas. Por eso no hay riesgo de pelear con otro grupo.

## Alimentación

- Cable **micro-USB** (el mismo de los Kindle antiguos) al conector de la Go Board, desde un computador o un cargador USB.
- Al encender, la FPGA se configura sola desde la flash con el diseño de competencia (grabado y verificado el
  18-nov). No hace falta el computador ni reprogramar.
- Después del arranque hay un reset de 4095 ciclos (164 µs) y el programa queda esperando precios.

## Cómo saber que funciona

- Los dos displays muestran el **último precio recibido en hexadecimal**. Antes del primer precio muestran `00`.
- Si la maestra está mandando y los displays cambian (por ejemplo, `A5` = 165), la recepción por SPI está bien.
- Los LEDs no se usan en el diseño de competencia.
- Si los displays no cambian: revisar GND, revisar que CS_n/SCLK/MOSI estén en los pines 1, 2 y 4, y desenchufar y
  volver a enchufar el USB para reiniciar.

## Si hay que volver a grabar la placa

```
make bin
python tools/goboard_prog.py build/pochoco.bin
```

(o `make prog-d2xx`). Termina con `VERIFY OK` y `CDONE: alto`.
