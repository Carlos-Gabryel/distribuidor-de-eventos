# Instalação do Distribuidor de Eventos num notebook (rodar como administrador, com internet).
# Pré-requisitos manuais (docs\instalacao.md): WSL com Ubuntu 24.04 instalado e o prod.keys copiado.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\usb.ps1"
$project = Split-Path $PSScriptRoot -Parent
$POKELDN_COMMIT = '89f761e'

Write-Host '1/6 usbipd-win'
if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    winget install --exact --id dorssel.usbipd-win --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine')
}

Write-Host '2/6 pacotes do Ubuntu'
wsl.exe -u root -- bash -lc 'apt-get update -qq && apt-get install -y -qq git python3-venv'

Write-Host "3/6 pokeldn fixado em $POKELDN_COMMIT"
wsl.exe -- bash -lc "test -d ~/pokeldn || git -c core.autocrlf=false clone https://github.com/Decryptu/pokeldn ~/pokeldn; cd ~/pokeldn && git config core.autocrlf false && git fetch -q && git checkout -q $POKELDN_COMMIT"

Write-Host '4/6 venv e dependências'
$wslProject = (wsl.exe -- wslpath -a (ConvertTo-WslArg $project)).Trim()
wsl.exe -- bash -lc "test -x ~/.venvs/pokeldn/bin/python || python3 -m venv ~/.venvs/pokeldn; cd ~/pokeldn && ~/.venvs/pokeldn/bin/pip install -q -r requirements.txt && ~/.venvs/pokeldn/bin/pip install -q -r '$wslProject/requirements.txt'"
$user = (wsl.exe -- whoami).Trim()
wsl.exe -u root -- usermod -aG dialout $user

Write-Host '5/6 catálogos (Events Gallery, ~56 MB)'
wsl.exe -- bash -lc "cd '$wslProject' && ~/.venvs/pokeldn/bin/python -m distrib atualizar-catalogo"

Write-Host '6/6 placa e atalho'
$board = Get-BoardBusId (usbipd list)
if ($board -and $board.State -eq 'Not shared') { usbipd bind --busid $board.BusId }
elseif (-not $board) { Write-Host 'Placa não plugada: depois rode "usbipd bind --busid <X>" como admin.' -ForegroundColor Yellow }
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Distribuidor de Eventos.lnk'
$shell = New-Object -ComObject WScript.Shell
$s = $shell.CreateShortcut($lnk)
$s.TargetPath = Join-Path $project 'Iniciar Distribuicao.bat'
$s.WorkingDirectory = $project
$s.Save()
Write-Host "Pronto. Atalho criado em $lnk" -ForegroundColor Green
