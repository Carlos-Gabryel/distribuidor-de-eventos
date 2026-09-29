# Prepara o Windows e abre o Distribuidor de Eventos como root no WSL.
$ErrorActionPreference = 'Stop'
trap { Write-Host "`nErro: $_" -ForegroundColor Red; Read-Host 'Enter para fechar'; exit 1 }
. "$PSScriptRoot\usb.ps1"
$project = Split-Path $PSScriptRoot -Parent

function Fail($msg) { Write-Host "`n$msg" -ForegroundColor Red; Read-Host 'Enter para fechar'; exit 1 }

if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    Fail 'usbipd não está instalado. Rode windows\instalar.ps1 (veja docs\instalacao.md).'
}
# O usbipd attach exige uma distro do WSL rodando: deixamos uma sessão aberta em segundo plano.
$keep = Start-Process wsl.exe -ArgumentList '--', 'sleep', 'infinity' -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 2

$board = Get-BoardBusId (usbipd list)
if ($null -eq $board) { Fail 'Placa ESP32 não encontrada. Plugue a placa (cabo de dados) e abra de novo.' }
if ($board.State -eq 'Not shared') {
    Fail "A placa ($($board.BusId)) ainda não foi compartilhada. Abra um PowerShell como administrador e rode:`n  usbipd bind --busid $($board.BusId)"
}
if ($board.State -eq 'Shared') { usbipd attach --wsl --busid $board.BusId | Out-Null }

# Laço de re-attach: se a placa for replugada, ela volta para o WSL sozinha.
$loop = Start-Job -ArgumentList $PSScriptRoot -ScriptBlock {
    param($dir)
    . "$dir\usb.ps1"
    while ($true) {
        $b = Get-BoardBusId (usbipd list)
        if ($b -and $b.State -eq 'Shared') { usbipd attach --wsl --busid $b.BusId | Out-Null }
        Start-Sleep -Seconds 5
    }
}

$userHome = (wsl.exe -- bash -lc 'echo $HOME').Trim()
$wslProject = (wsl.exe -- wslpath -a (ConvertTo-WslArg $project)).Trim()
if (-not $wslProject) { Fail "Não consegui converter o caminho $project para o WSL." }
$python = (wsl.exe -- python3 "$wslProject/windows/caminho_python.py" "$wslProject").Trim()
try {
    wsl.exe -u root -- bash -lc "cd '$wslProject' && DISTRIB_USER_HOME='$userHome' '$python' -m distrib"
} finally {
    Stop-Job $loop -ErrorAction SilentlyContinue; Remove-Job $loop -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $keep.Id -ErrorAction SilentlyContinue
}
