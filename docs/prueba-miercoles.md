# Prueba con la maestra (miércoles)

## Llevar
Notebook con el proyecto, Go Board, cable micro-USB, cables PMOD (pines 1–4) y **GND**.

## Versiones (ya armadas en `build\versiones`)
| | qué es | grabar (PowerShell, en la carpeta del proyecto) |
|---|---|---|
| **A** | competencia: ancla 15 acciones | `powershell -ExecutionPolicy Bypass -File .\grabar.ps1 -Version A` |
| **B** | sin ancla (la más segura) | `... .\grabar.ps1 -Version B` |
| **C** | ancla 26 + recompra 117 (optimizador) | `... .\grabar.ps1 -Version C` |
| **D** | ancla 29 + recompra 122 | `... .\grabar.ps1 -Version D` |
| **E** | la D, pero el ancla solo si el primer precio es ≥ 160 | `... .\grabar.ps1 -Version E` |
| **F** | si el primer precio es ≥ 170 compra todo y espera el 255; si no, la D (**la de la competencia**) | `... .\grabar.ps1 -Version F` |

Cada una se graba en segundos. **Al final dejar grabada la F** si coincide con la simulación (si no, la A).
La F gana o empata a la D en las 8 prácticas del profesor (promedio $23.031 contra $20.247) y le gana al
rival en más rondas en todas las simulaciones (docs/ruta-optimizacion.md, sección 29). Lo de más abajo sobre
la E y la D queda como historia.

## En cada práctica, anotar
| serie (acción y mes) | hora de inicio | comprar y mantener | fila | versión | patrimonio pantalla | órdenes | ¿sin atrasos? |
|---|---|---|---|---|---|---|---|
| | | | | | | | |
| | | | | | | | |
| | | | | | | | |

## Después, comparar con la simulación
```powershell
& "$env:USERPROFILE\anaconda3\python.exe" tools/simular.py --buscar AMD 2022-01 10:20 8315
```
(acción, mes, hora de inicio y "comprar y mantener" de la pantalla). Muestra lo que debería dar cada versión.
- Si el patrimonio de la pantalla coincide con el simulado → la placa funciona bien.
- Si no coincide → revisar GND y cables, y avisar.

## Qué decidir
**Competir con la E** si en las prácticas la placa coincide con la simulación. La E es la D con una
condición más: el ancla solo se arma si el primer precio p0 es ≥ 160. Con p0 bajo, la subida del comienzo
suele ser un rebote que vuelve a p0 y el ancla pierde. Con la condición, la E le gana al rival 100/255 en
las 22 acciones (también Amazon, Synopsys y Cadence, donde la D perdía), sube el neto contra los rivales
de +12,7 % a +15,4 % en las 5 de la competencia y no empeora la peor ronda (docs/ruta-optimizacion.md,
sección 23). Lo que sigue explica por qué la D le gana a la A: En 13.652 períodos reales la D es
mejor que la A en todo: promedio 2,0057 vs 2,0044, peor ronda −4,8 % vs −5,5 %, contra rivales +12,1/+12,4 %
vs +11,9/+12,1 %, y cara a cara contra la A gana +12,2 % neto en todos los años y empresas. Es el mismo programa
que la A con dos constantes distintas (ANCLA 29, RECOMPRA 122). Si algo no coincide, volver a la A (la ya probada
en la placa). Las diferencias entre versiones en pocas series de práctica son suerte: decidir por la coincidencia
con la simulación, no por cuál ganó una práctica.

## Resultado (25-nov)
Se probaron G, F y D con la maestra: **se compite con la D**, que fue la que mejor se comportó. Quedó grabada.
