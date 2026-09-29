$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\..\usb.ps1"
$ok = 0; $fail = 0
function Assert-Eq($got, $want, $name) {
    if ($got -eq $want) { $script:ok++ } else { $script:fail++; Write-Host "FALHOU $name : '$got' != '$want'" }
}
$lines = @(
  'Connected:',
  'BUSID  VID:PID    DEVICE                                                        STATE',
  '1-4    0d8c:0005  Blue Snowball, Dispositivo de Entrada USB                     Not shared',
  '1-6    1a86:55d4  Dispositivo Serial USB (COM4)                                 Shared',
  '',
  'Persisted:'
)
$b = Get-BoardBusId $lines
Assert-Eq $b.BusId '1-6' 'busid'
Assert-Eq $b.State 'Shared' 'state'
$b = Get-BoardBusId @('1-5    10c4:ea60  CP2102 USB to UART Bridge Controller (COM3)   Attached')
Assert-Eq $b.State 'Attached' 'cp2102 attached'
$b = Get-BoardBusId @('1-5    10c4:ea60  CP2102 USB to UART Bridge Controller (COM3)   Not shared')
Assert-Eq $b.State 'Not shared' 'not shared'
Assert-Eq (Get-BoardBusId @('1-4    0d8c:0005  Blue Snowball   Not shared')) $null 'sem placa'
Assert-Eq (ConvertTo-WslArg 'C:\Gabry\Projects\pokeldn-distrib') 'C:/Gabry/Projects/pokeldn-distrib' 'caminho para wslpath'
Assert-Eq (Get-BoardBusId @('1-6    1a86:55d4  Serial (COM4)   Shared (forced)')).State 'Shared' 'shared forced'
Write-Host "$ok ok, $fail falhas"
if ($fail) { exit 1 }
