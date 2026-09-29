# Distribuidor de Eventos (pokeldn-distrib) - instalador completo para Windows 10/11.
#
#   Uma linha no PowerShell:
#     irm https://raw.githubusercontent.com/Carlos-Gabryel/pokeldn-distrib/master/instalar.ps1 | iex
#   ou dois cliques no arquivo (botao direito -> "Executar com o PowerShell").
#
# Pede administrador sozinho, pode ser rodado de novo (pula o que ja esta pronto; tambem serve
# para atualizar) e continua sozinho depois de um reinicio do Windows. Precisa de internet.
# Log: C:\ProgramData\pokeldn-distrib\instalar.log
#
# Este arquivo e ASCII puro de proposito: o PowerShell 5.1 estraga acentos em arquivos sem BOM,
# e um BOM quebra o "irm | iex".

$RepoUrl       = 'https://github.com/Carlos-Gabryel/pokeldn-distrib'
$RawUrl        = 'https://raw.githubusercontent.com/Carlos-Gabryel/pokeldn-distrib/master/instalar.ps1'
$PokeldnUrl    = 'https://github.com/Decryptu/pokeldn'
$PokeldnCommit = '89f761e'
$StateDir      = 'C:\ProgramData\pokeldn-distrib'
$BoardIds      = @('1a86:55d4', '10c4:ea60', '1a86:7523')   # CH9102, CP2102, CH340

# ---------------------------------------------------------------- funcoes puras (testadas)

# "wsl -l -q" sai em UTF-16; no PowerShell 5.1 chega com NULs entre as letras.
function Select-Distro([string[]] $WslListLines) {
    $names = @($WslListLines | ForEach-Object { ($_ -replace [char]0, '').Trim() } | Where-Object { $_ })
    foreach ($want in 'Ubuntu-24.04', 'Ubuntu') {
        if ($names -contains $want) { return $want }
    }
    return $null
}

# Igual a windows\usb.ps1 (este arquivo precisa funcionar sozinho, sem o resto do projeto).
function Get-BoardBusId([string[]] $UsbipdListLines) {
    foreach ($line in $UsbipdListLines) {
        if ($line -match '^(?<bus>\d+-\d+)\s+(?<id>[0-9a-f]{4}:[0-9a-f]{4})\s+.*?\s(?<state>Not shared|Shared|Attached)(?: \(forced\))?\s*$') {
            if ($BoardIds -contains $Matches.id) {
                return @{ BusId = $Matches.bus; State = $Matches.state }
            }
        }
    }
    return $null
}

# O wsl.exe engole as barras invertidas de um caminho do Windows; o wslpath aceita "C:/...".
function ConvertTo-WslArg([string] $WindowsPath) {
    return $WindowsPath -replace '\\', '/'
}

if ($env:DISTRIB_INSTALL_TEST) { return }      # os testes so carregam as funcoes acima

# ---------------------------------------------------------------- preparacao

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$Destino = if ($args.Count -gt 0) { $args[0] } elseif ($env:DISTRIB_DESTINO) { $env:DISTRIB_DESTINO } else { 'C:\pokeldn-distrib' }

New-Item -ItemType Directory -Force $StateDir | Out-Null
$Self = Join-Path $StateDir 'instalar.ps1'
if ($PSCommandPath) {
    if ($PSCommandPath -ne $Self) { Copy-Item $PSCommandPath $Self -Force }
} else {
    Invoke-WebRequest $RawUrl -OutFile $Self -UseBasicParsing     # veio pelo "irm | iex"
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host 'Pedindo permissao de administrador...'
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$Self`"", "`"$Destino`"")
    return
}

Start-Transcript -Path (Join-Path $StateDir 'instalar.log') -Append | Out-Null
$Distro = $null

function Say($n, $msg) { Write-Host "`n[$n/9] $msg" -ForegroundColor Cyan }
function Info($msg) { Write-Host "      $msg" }
function Fail($msg) {
    Write-Host "`nERRO: $msg" -ForegroundColor Red
    Write-Host "Log completo: $StateDir\instalar.log"
    try { Stop-Transcript | Out-Null } catch {}
    Read-Host 'Enter para fechar'
    exit 1
}
trap { Fail "$_" }

# Comandos no Linux: sem barras invertidas nem aspas duplas dentro (o wsl.exe e o PowerShell 5.1
# estragam as duas coisas). Use aspas simples no bash.
function Invoke-Wsl([string] $Cmd, [switch] $Root, [switch] $Soft) {
    $user = if ($Root) { @('-u', 'root') } else { @() }
    & wsl.exe -d $script:Distro @user -- bash -lc $Cmd
    if ($LASTEXITCODE -and -not $Soft) { Fail "comando no Linux falhou: $Cmd" }
    return $LASTEXITCODE
}
function Get-WslText([string] $Cmd) {
    return ((& wsl.exe -d $script:Distro -- bash -lc $Cmd) -join "`n").Trim()
}

Write-Host '=== Distribuidor de Eventos: instalacao ===' -ForegroundColor Green
Write-Host "Pasta do projeto: $Destino"

# ---------------------------------------------------------------- 1. WSL + Ubuntu

Say 1 'WSL e Ubuntu'
$Distro = Select-Distro @(& wsl.exe -l -q 2>$null)
if (-not $Distro) {
    Info 'Instalando o Ubuntu 24.04 (pode demorar)...'
    & wsl.exe --install -d Ubuntu-24.04 --no-launch
    $Distro = Select-Distro @(& wsl.exe -l -q 2>$null)
    if (-not $Distro) {
        $launcher = Get-Command ubuntu2404.exe -ErrorAction SilentlyContinue
        if ($launcher) { & $launcher.Source install --root | Out-Null }
        $Distro = Select-Distro @(& wsl.exe -l -q 2>$null)
    }
    if (-not $Distro) {
        # O Windows precisa reiniciar para ligar o WSL: continuamos sozinhos depois do reinicio.
        Set-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\RunOnce' 'pokeldn-distrib' `
            "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$Self`" `"$Destino`""
        Write-Host "`nO Windows precisa reiniciar para terminar de instalar o WSL." -ForegroundColor Yellow
        Write-Host 'Depois do reinicio, a instalacao continua sozinha (aceite o pedido de administrador).'
        if ((Read-Host 'Reiniciar agora? (s/n)') -match '^[sS]') { Restart-Computer -Force }
        try { Stop-Transcript | Out-Null } catch {}
        return
    }
}
& wsl.exe --set-default $Distro | Out-Null
Info "distro: $Distro"

$who = Get-WslText 'whoami'
if ($who -eq 'root') {
    Info 'Criando o usuario Linux "distrib"...'
    Invoke-Wsl -Root 'id -u distrib >/dev/null 2>&1 || useradd -m -s /bin/bash -G sudo,dialout distrib' | Out-Null
    Invoke-Wsl -Root "grep -q '^default=' /etc/wsl.conf 2>/dev/null || { echo '[user]' >> /etc/wsl.conf; echo 'default=distrib' >> /etc/wsl.conf; }" | Out-Null
    & wsl.exe --terminate $Distro | Out-Null
    $who = Get-WslText 'whoami'
}
Info "usuario Linux: $who"

# ---------------------------------------------------------------- 2. usbipd

Say 2 'usbipd-win (leva a placa USB para o Linux)'
if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Fail 'winget nao encontrado. Instale o "Instalador de Aplicativos" pela Microsoft Store e rode de novo.'
    }
    & winget install --exact --id dorssel.usbipd-win --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
    if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) { Fail 'o usbipd nao ficou disponivel; reinicie o Windows e rode de novo.' }
}
Info 'ok'

# ---------------------------------------------------------------- 3. pacotes do Ubuntu

Say 3 'Pacotes do Ubuntu (git, python)'
if ((Invoke-Wsl -Soft 'dpkg -s git python3-venv python3-pip >/dev/null 2>&1') -ne 0) {
    Invoke-Wsl -Root 'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git python3-venv python3-pip ca-certificates' | Out-Null
}
Invoke-Wsl -Root "usermod -aG dialout $who" | Out-Null
Info 'ok'

# ---------------------------------------------------------------- 4. o projeto

Say 4 "Projeto pokeldn-distrib em $Destino"
$wslDest = Get-WslText "wslpath -a '$(ConvertTo-WslArg $Destino)'"
if (Test-Path (Join-Path $Destino '.git')) {
    if ((Invoke-Wsl -Soft "git -C '$wslDest' pull -q --ff-only") -ne 0) {
        Write-Host '      aviso: nao consegui atualizar (sem internet ou alteracoes locais); seguindo com o que ja existe.' -ForegroundColor Yellow
    }
} elseif (Test-Path $Destino) {
    Fail "$Destino ja existe e nao e uma copia do projeto. Apague ou mova a pasta e rode de novo."
} else {
    Invoke-Wsl "git -c core.autocrlf=false clone -q $RepoUrl '$wslDest' && git -C '$wslDest' config core.autocrlf false" | Out-Null
}
Info 'ok'

# ---------------------------------------------------------------- 5. pokeldn + Python

Say 5 "pokeldn (versao $PokeldnCommit) e ambiente Python"
$pokeldn = Get-WslText "python3 '$wslDest/windows/config_valor.py' '$wslDest' pokeldn_dir"
$python  = Get-WslText "python3 '$wslDest/windows/config_valor.py' '$wslDest' python"
$venv    = $python -replace '/bin/python[0-9.]*$', ''
Invoke-Wsl ("test -f '$pokeldn/bin/swsh_gift_host.py' || { git -c core.autocrlf=false clone -q $PokeldnUrl '$pokeldn' " +
            "&& git -C '$pokeldn' config core.autocrlf false && git -C '$pokeldn' checkout -q $PokeldnCommit; }") | Out-Null
Invoke-Wsl "test -x '$python' || python3 -m venv '$venv'" | Out-Null
Info 'instalando as dependencias Python...'
Invoke-Wsl "cd '$pokeldn' && '$python' -m pip install -q -r requirements.txt && '$python' -m pip install -q -r '$wslDest/requirements.txt'" | Out-Null
Info 'ok'

# ---------------------------------------------------------------- 6. prod.keys

Say 6 'prod.keys (as chaves do seu console)'
$keys = Get-WslText "python3 '$wslDest/windows/config_valor.py' '$wslDest' keys"
if ((Invoke-Wsl -Soft "test -f '$keys'") -eq 0) {
    Info "ja instalado em $keys"
} else {
    Info 'Escolha o arquivo prod.keys na janela que abriu (pendrive, Downloads...).'
    Add-Type -AssemblyName System.Windows.Forms
    $owner = New-Object System.Windows.Forms.Form -Property @{ TopMost = $true }
    $dialog = New-Object System.Windows.Forms.OpenFileDialog -Property @{
        Title = 'Escolha o prod.keys do seu console'; Filter = 'prod.keys|*.keys|Todos os arquivos|*.*' }
    if ($dialog.ShowDialog($owner) -eq [System.Windows.Forms.DialogResult]::OK) {
        $src = Get-WslText "wslpath -a '$(ConvertTo-WslArg $dialog.FileName)'"
        $keysDir = $keys.Substring(0, $keys.LastIndexOf('/'))
        Invoke-Wsl "mkdir -p '$keysDir' && chmod 700 '$keysDir' && cp '$src' '$keys' && chmod 600 '$keys'" | Out-Null
        Info "copiado para $keys"
    } else {
        Write-Host '      aviso: sem prod.keys a distribuicao nao funciona. Rode o instalador de novo para escolher o arquivo.' -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------- 7. catalogo de eventos

Say 7 'Catalogo de eventos (Events Gallery, ~56 MB)'
$haveSwsh = Test-Path (Join-Path $Destino 'catalog\swsh\index.json')
$haveFrlg = Test-Path (Join-Path $Destino 'catalog\frlg\index.json')
if ($haveSwsh -and $haveFrlg -and -not $env:DISTRIB_ATUALIZAR_CATALOGO) {
    Info 'ja baixado (para baixar de novo: python -m distrib atualizar-catalogo)'
} else {
    Invoke-Wsl "cd '$wslDest' && '$python' -m distrib atualizar-catalogo" | Out-Null
}

# ---------------------------------------------------------------- 8. placa e atalho

Say 8 'Placa ESP32 e atalho na area de trabalho'
$board = Get-BoardBusId @(& usbipd list)
if (-not $board) {
    Write-Host '      aviso: placa nao plugada agora. Tudo bem: o atalho avisa e mostra o comando quando for usar.' -ForegroundColor Yellow
} elseif ($board.State -eq 'Not shared') {
    & usbipd bind --busid $board.BusId
    Info "placa compartilhada com o WSL (busid $($board.BusId))"
} else {
    Info "placa ja compartilhada (busid $($board.BusId))"
}
$lnk = Join-Path ([Environment]::GetFolderPath('Desktop')) 'Distribuidor de Eventos.lnk'
$shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($lnk)
$shortcut.TargetPath = Join-Path $Destino 'Iniciar Distribuicao.bat'
$shortcut.WorkingDirectory = $Destino
$shortcut.Save()
Info "atalho: $lnk"

# ---------------------------------------------------------------- 9. checagem final

Say 9 'Checagem final'
if ($board) {
    $keep = Start-Process wsl.exe -ArgumentList '-d', $Distro, '--', 'sleep', '60' -WindowStyle Hidden -PassThru
    Start-Sleep -Seconds 2
    $board = Get-BoardBusId @(& usbipd list)
    if ($board -and $board.State -eq 'Shared') { & usbipd attach --wsl --busid $board.BusId | Out-Null; Start-Sleep -Seconds 3 }
}
$userHome = Get-WslText 'echo $HOME'
& wsl.exe -d $Distro -u root -- bash -lc "cd '$wslDest' && DISTRIB_USER_HOME='$userHome' '$python' -m distrib checar"
if ($keep) { Stop-Process -Id $keep.Id -ErrorAction SilentlyContinue }

Write-Host "`n=== Pronto! ===" -ForegroundColor Green
Write-Host 'Para distribuir: plugue a placa e abra o atalho "Distribuidor de Eventos" na area de trabalho.'
Write-Host 'Os itens com X acima precisam ser resolvidos antes (veja docs\instalacao.md).'
try { Stop-Transcript | Out-Null } catch {}
Read-Host 'Enter para fechar'
