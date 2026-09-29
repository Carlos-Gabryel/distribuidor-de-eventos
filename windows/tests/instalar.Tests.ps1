$ErrorActionPreference = 'Stop'
$env:DISTRIB_INSTALL_TEST = '1'          # so carrega as funcoes, nao instala nada
. "$PSScriptRoot\..\..\instalar.ps1"
$ok = 0; $fail = 0
function Assert-Eq($got, $want, $name) {
    if ($got -eq $want) { $script:ok++ } else { $script:fail++; Write-Host "FALHOU $name : '$got' != '$want'" }
}

# wsl -l -q sai em UTF-16: no PowerShell 5.1 chega com NULs entre as letras
$nul = [char]0
$utf16 = "U${nul}b${nul}u${nul}n${nul}t${nul}u${nul}`r`n"
Assert-Eq (Select-Distro @($utf16)) 'Ubuntu' 'distro Ubuntu com NULs'
Assert-Eq (Select-Distro @('docker-desktop', 'Ubuntu-24.04', 'Ubuntu')) 'Ubuntu-24.04' 'prefere Ubuntu-24.04'
Assert-Eq (Select-Distro @('docker-desktop')) $null 'sem Ubuntu'
Assert-Eq (Select-Distro @()) $null 'lista vazia'

$lines = @('1-6    1a86:55d4  Dispositivo Serial USB (COM4)   Shared (forced)')
Assert-Eq (Get-BoardBusId $lines).State 'Shared' 'shared forced'
Assert-Eq (Get-BoardBusId @('1-5    10c4:ea60  CP2102 (COM3)   Not shared')).BusId '1-5' 'cp2102'
Assert-Eq (ConvertTo-WslArg 'C:\pokeldn-distrib') 'C:/pokeldn-distrib' 'caminho'

# Notebook sem WSL: o wsl.exe responde "nao esta instalado" no stderr e sai com erro.
# Com $ErrorActionPreference = 'Stop', o PowerShell 5.1 tratava isso como erro fatal.
$fake = Join-Path $env:TEMP 'fake-wsl-sem-instalar.cmd'
Set-Content $fake "@echo O Subsistema do Windows para Linux nao esta instalado. 1>&2`r`n@exit /b 1" -Encoding ASCII
$script:WslExe = $fake
$r = Invoke-Native $script:WslExe -l -q
Assert-Eq $r.ExitCode 1 'codigo de saida do wsl falso'
Assert-Eq (Select-Distro $r.Lines) $null 'sem distro quando o WSL falta'
Assert-Eq (@(Get-DistroList).Count) 0 'Get-DistroList vazio sem WSL'
Remove-Item $fake

$text = Get-Content -Raw -Encoding Byte "$PSScriptRoot\..\..\instalar.ps1"
Assert-Eq (@($text | Where-Object { $_ -gt 127 }).Count) 0 'instalar.ps1 so ASCII'

Write-Host "$ok ok, $fail falhas"
if ($fail) { exit 1 }
