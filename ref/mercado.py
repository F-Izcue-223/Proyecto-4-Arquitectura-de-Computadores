"""Reglas de la FPGA maestra, copiadas de tb/tb_proyecto_4.sv, y metricas.

Una transaccion por tick: la maestra baja CS_n, manda el precio p_n y en el mismo
momento ejecuta, al precio p_n, el byte que encontro en DECISION. Ese byte lo
escribio el programa despues de recibir p_{n-1}. Al partir, DECISION vale 0
(mantener), que es su valor de reset en pochoco_spi_slave.

Byte de decision: [7:6] accion (00 mantener, 01 comprar, 10 vender, 11 mantener),
[5:0] cantidad q (0 a 63).
"""
CAJA0 = 10_000
COMISION = 5

MANTENER, COMPRAR, VENDER = 0, 1, 2


def ejecutar(caja, acciones, dec, p):
    """Aplica el byte `dec` al precio p (tarea `ejecutar` del testbench).

    Compra: lo que alcance con la caja. Venta: lo que se tenga. Una orden que
    queda en 0 no se ejecuta y no paga comision. Devuelve (caja, acciones, q).
    """
    accion, q = dec >> 6, dec & 63
    if accion == COMPRAR:
        q = min(q, (caja - COMISION) // p)
        if q > 0:
            return caja - q * p - COMISION, acciones + q, q
    elif accion == VENDER:
        q = min(q, acciones)
        if q > 0 and caja + q * p >= COMISION:
            return caja + q * p - COMISION, acciones - q, q
    return caja, acciones, 0


def simular(precios, agente):
    """Corre un agente sobre la serie con las reglas de la maestra.

    `agente.tick(p, enviado)` recibe el precio del tick y el byte que la maestra
    ejecuto en esa misma transaccion, y devuelve el byte para la siguiente.
    """
    caja, acciones, registro = CAJA0, 0, 0
    W, decisiones, ordenes, dentro = [], [], 0, 0
    for p in precios:
        enviado = registro
        caja, acciones, q = ejecutar(caja, acciones, enviado, p)
        ordenes += q > 0
        dentro += acciones > 0
        W.append(caja + acciones * p)
        registro = agente.tick(p, enviado)
        decisiones.append(registro)
    return {'W': W, 'decisiones': decisiones, 'ordenes': ordenes, 'comisiones': ordenes * COMISION,
            'caja': caja, 'acciones': acciones, 'exposicion': dentro / len(precios)}


def caida_maxima(W):
    """Perdida maxima desde un peak de patrimonio, en pesos (como el testbench)."""
    peak, peor = W[0], 0
    for w in W:
        peak = max(peak, w)
        peor = max(peor, peak - w)
    return peor


def comprar_y_mantener(precios):
    """Referencia del testbench: todo lo que alcance al primer precio, una sola orden."""
    q = (CAJA0 - COMISION) // precios[0]
    return CAJA0 - COMISION - q * precios[0] + q * precios[-1]


class NoOperar:
    """Referencia: nunca manda una orden."""
    def tick(self, p, enviado):
        return 0
