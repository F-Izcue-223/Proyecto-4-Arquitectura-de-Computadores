"""Sintetiza todas las variantes y arma la tabla de recursos y frecuencia.

Para cada variante: Yosys (synth_ice40) -> nextpnr-ice40 (HX1K, VQ100) -> icepack.
Reporta celdas logicas (LC = LUT4 + carry + flip-flop), LUT4, flip-flops, BRAM y
la frecuencia maxima que da nextpnr. Fmax cambia con la semilla del place & route,
asi que se corre con 3 semillas y se informa el rango.

Cada variante se arma en su propia carpeta (build/syn/<tag>/) con su sw/trade.hex,
para no pisar el sw/trade.hex de la competencia.

Uso:  python ref/sintesis.py [tag ...]      (sin argumentos: todas)
Escribe resultados/sintesis.csv y deja los bitstreams en build/syn_<tag>.bin.
"""
import csv
import os
import re
import shutil
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.abspath(os.path.join(AQUI, '..'))
sys.path.insert(0, os.path.join(RAIZ, 'tools'))
import pochoasm  # noqa: E402

RTL = ['rtl/pochoco_soc.v', 'rtl/pochoco_periph.v', 'rtl/pochoco_ram.v', 'rtl/pochoco_spi_slave.v',
       'rtl/espino_core/espino_core.v', 'rtl/espino_core/espino_if_stage.v',
       'rtl/espino_core/espino_id_stage.v', 'rtl/espino_core/espino_decoder.v',
       'rtl/espino_core/espino_alu.v', 'rtl/espino_core/espino_controller.v',
       'rtl/espino_core/espino_load_store_unit.v', 'rtl/espino_core/espino_register_file.v',
       'rtl/espino_core/espino_mul8.v']
# tag: (defines de Verilog, defines del assembler, MHz objetivo)
VARIANTES = {
    'base_original': (['-DORIGINAL_RAM'], {}, 25.0),
    'sw':            ([], {}, 25.0),                               # la de la competencia
    'shift':         (['-DESPINO_SHIFTER'], {}, 25.0),
    'mul8':          (['-DESPINO_MUL8'], {}, 25.0),
    'mul8shift':     (['-DESPINO_MUL8', '-DESPINO_SHIFTER'], {}, 25.0),
}
SEMILLAS = (1, 2, 3)


class NoCabe(Exception):
    """nextpnr no pudo ubicar el diseno: pide mas celdas de las que tiene la HX1K."""


def correr(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    salida = r.stdout + r.stderr
    if r.returncode:
        m = re.search(r'Failed to expand region .* of (\d+) ICESTORM_LCs', salida)
        if m:
            raise NoCabe(int(m[1]))
        print(salida[-3000:])
        raise SystemExit(f'fallo: {cmd[0]}')
    return salida


def sintetizar(tag):
    vdefs, adefs, mhz = VARIANTES[tag]
    d = os.path.join(RAIZ, 'build', 'syn', tag)
    os.makedirs(os.path.join(d, 'sw'), exist_ok=True)
    with open(os.path.join(RAIZ, 'sw', 'trade.s'), encoding='utf-8') as f:
        words, _ = pochoasm.assemble(f.read(), adefs)
    with open(os.path.join(d, 'sw', 'trade.hex'), 'w', newline='\n') as f:
        f.writelines(f'{w:08x}\n' for _, w, _ in words)

    rtl = ' '.join(os.path.join(RAIZ, r).replace('\\', '/') for r in RTL)
    if '-DORIGINAL_RAM' in vdefs:
        # El SoC tal como vino del Proyecto 2: sin no_rw_check en la RAM
        orig = os.path.join(d, 'pochoco_ram_original.v')
        with open(os.path.join(RAIZ, 'rtl', 'pochoco_ram.v'), encoding='utf-8') as f:
            src = f.read().replace('(* no_rw_check *)', '')
        with open(orig, 'w', newline='\n') as f:
            f.write(src)
        rtl = rtl.replace(os.path.join(RAIZ, 'rtl', 'pochoco_ram.v').replace('\\', '/'), orig.replace('\\', '/'))
    defs = ' '.join(x for x in vdefs if x != '-DORIGINAL_RAM')
    out = correr(['yosys', '-q', '-p', f'read_verilog {defs} {rtl}; synth_ice40 -top pochoco_soc '
                  f'-json soc.json; tee -q -o yosys_stat.txt stat'], d)
    stat = open(os.path.join(d, 'yosys_stat.txt')).read()

    def cuenta(celda):
        return sum(int(m) for m in re.findall(rf'^\s+(\d+)\s+{celda}\w*\s*$', stat, re.M))

    fila = {'variante': tag, 'MHz_objetivo': mhz, 'LUT4': cuenta('SB_LUT4'),
            'CARRY': cuenta('SB_CARRY'), 'FF': cuenta('SB_DFF'), 'BRAM': cuenta('SB_RAM40_4K')}
    fmax = []
    try:
        log = correr(['nextpnr-ice40', '--hx1k', '--package', 'vq100', '--json', 'soc.json',
                      '--pcf', os.path.join(RAIZ, 'goboard.pcf'), '--pack-only'], d)
    except NoCabe as e:
        log = ''
    m = re.search(r'ICESTORM_LC:\s+(\d+)/\s*(\d+)', log)
    if m and int(m[1]) > int(m[2]):
        fila.update(LC=int(m[1]), LC_total=int(m[2]), LC_pct=round(100 * int(m[1]) / int(m[2]), 1),
                    Fmax_min='', Fmax_max='', cierra_timing='no cabe')
        return fila
    for s in SEMILLAS:
        log = correr(['nextpnr-ice40', '--hx1k', '--package', 'vq100', '--json', 'soc.json',
                      '--pcf', os.path.join(RAIZ, 'goboard.pcf'), '--asc', f'soc_{s}.asc',
                      '--freq', str(mhz), '--seed', str(s)], d)
        lc = re.search(r'ICESTORM_LC:\s+(\d+)/\s*(\d+)', log)
        fm = re.findall(r'Max frequency for clock .*?: ([\d.]+) MHz', log)
        fila['LC'], fila['LC_total'] = int(lc[1]), int(lc[2])
        fmax.append(float(fm[-1]))
    fila['LC_pct'] = round(100 * fila['LC'] / fila['LC_total'], 1)
    fila['Fmax_min'], fila['Fmax_max'] = min(fmax), max(fmax)
    fila['cierra_timing'] = min(fmax) >= mhz
    # bitstream con la semilla de mejor Fmax
    mejor = SEMILLAS[fmax.index(max(fmax))]
    correr(['icepack', f'soc_{mejor}.asc', os.path.join(RAIZ, 'build', f'syn_{tag}.bin')], d)
    return fila


def main():
    tags = sys.argv[1:] or list(VARIANTES)
    filas = []
    for t in tags:
        f = sintetizar(t)
        filas.append(f)
        if f['cierra_timing'] == 'no cabe':
            print(f"{t:14s} LC {f['LC']:4d}/{f['LC_total']} ({f['LC_pct']:5.1f} %)  NO CABE en la HX1K")
            continue
        print(f"{t:14s} LC {f['LC']:4d}/{f['LC_total']} ({f['LC_pct']:4.1f} %)  LUT4 {f['LUT4']:4d}  "
              f"FF {f['FF']:3d}  BRAM {f['BRAM']:2d}  Fmax {f['Fmax_min']:.1f}-{f['Fmax_max']:.1f} MHz "
              f"(objetivo {f['MHz_objetivo']}: {'OK' if f['cierra_timing'] else 'NO'})")
    os.makedirs(os.path.join(RAIZ, 'resultados'), exist_ok=True)
    ruta = os.path.join(RAIZ, 'resultados', 'sintesis.csv')
    previas = {}
    if os.path.exists(ruta) and sys.argv[1:]:
        with open(ruta) as fh:
            previas = {r['variante']: r for r in csv.DictReader(fh)}
    for f in filas:
        previas[f['variante']] = f
    campos = ['variante', 'MHz_objetivo', 'LC', 'LC_total', 'LC_pct', 'LUT4', 'CARRY', 'FF', 'BRAM',
              'Fmax_min', 'Fmax_max', 'cierra_timing']
    with open(ruta, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        for t in VARIANTES:
            if t in previas:
                w.writerow({k: previas[t][k] for k in campos})


if __name__ == '__main__':
    main()
