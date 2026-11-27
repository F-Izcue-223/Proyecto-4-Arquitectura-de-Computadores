# grabar.ps1: arma el bitstream y lo graba en la Go Board (desde PowerShell).
#
#   .\grabar.ps1               diseno de la competencia (version D, build/pochoco.bin)
#   .\grabar.ps1 -Version D    otra version (A, B, C o D; ver tools/versiones.py). Si ya esta
#                              armada en build\versiones, la graba sin sintetizar (segundos).
#   .\grabar.ps1 -Prueba       prueba en placa: 4 LEDs fijos y "A1" en los displays = todo OK
#   .\grabar.ps1 -SoloArmar    arma build/pochoco.bin sin grabar
#
#   Versiones:  A = ancla 15   B = sin ancla (la mas segura)
#               C = ancla 26 + recompra 117   D = ancla 29 + recompra 122 (LA FINAL, la de sw/trade.s)
#               E = la D con ancla solo si p0 >= 160
#               F = si p0 >= 170 compra todo y espera el 255; si no, la D
#               G = compra todo si p0 >= 180 o si llega a 240 antes de los extremos; espera el 255
#
# Necesita: la Go Board conectada por USB, OSS CAD Suite en %USERPROFILE%\oss-cad-suite,
# Anaconda en %USERPROFILE%\anaconda3 y Git for Windows (su bash corre el Makefile).
param([switch]$Prueba, [switch]$SoloArmar, [ValidateSet('A', 'B', 'C', 'D', 'E', 'F', 'G')][string]$Version = '')
$ErrorActionPreference = 'Stop'

$raiz = $PSScriptRoot
$py   = Join-Path $env:USERPROFILE 'anaconda3\python.exe'
$bash = 'C:\Program Files\Git\bin\bash.exe'
foreach ($r in @($py, $bash)) {
    if (-not (Test-Path $r)) { throw "No encuentro $r" }
}

function Grabar($bin) {
    Write-Host "Grabando $bin en la Go Board..."
    Push-Location $raiz
    try { & $py tools/goboard_prog.py $bin } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw 'Fallo la grabacion (revisa el cable USB)' }
}

if ($Version) {
    $hecho = Get-ChildItem (Join-Path $raiz 'build\versiones') -Filter "$($Version)_*.bin" -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if (-not $hecho) {
        Write-Host 'Armando las tres versiones (tools/versiones.py, ~2 minutos)...'
        $cmd = 'export PATH="$HOME/oss-cad-suite/bin:$HOME/oss-cad-suite/lib:$PATH"; ' +
               "cd '$($raiz -replace '\\','/')' && ~/anaconda3/python.exe tools/versiones.py armar"
        & $bash -lc $cmd
        if ($LASTEXITCODE -ne 0) { throw 'Fallo el armado de las versiones' }
        $hecho = Get-ChildItem (Join-Path $raiz 'build\versiones') -Filter "$($Version)_*.bin" | Select-Object -First 1
    }
    Grabar ("build/versiones/" + $hecho.Name)
    Write-Host "Listo: la placa tiene la version $Version ($($hecho.BaseName))."
    exit 0
}

if (-not (Test-Path (Join-Path $env:USERPROFILE 'oss-cad-suite\bin\yosys.exe'))) { throw 'No encuentro OSS CAD Suite' }
$objetivo = if ($Prueba) { 'prueba-placa' } else { 'bin' }
$bin      = if ($Prueba) { 'build/prueba.bin' } else { 'build/pochoco.bin' }

# El Makefile usa sed, cp y mkdir: se corre dentro de Git Bash, con OSS CAD Suite en el PATH.
$cmd = 'export PATH="$HOME/oss-cad-suite/bin:$HOME/oss-cad-suite/lib:$PATH"; ' +
       "cd '$($raiz -replace '\\','/')' && make $objetivo PY=~/anaconda3/python.exe"
Write-Host "Armando $bin (sintesis + place & route, ~1 minuto)..."
& $bash -lc $cmd
if ($LASTEXITCODE -ne 0) { throw 'Fallo el armado del bitstream' }

if ($SoloArmar) { Write-Host "Listo: $bin"; exit 0 }

Grabar $bin
if ($Prueba) {
    Write-Host 'Mira la placa: 4 LEDs fijos y "A1" = OK; LEDs parpadeando = algun byte distinto.'
    Write-Host 'Despues vuelve a grabar el diseno de la competencia:  .\grabar.ps1'
} else {
    Write-Host 'Listo: la placa tiene el diseno de la competencia (displays en 00 hasta el primer precio).'
}
