# Leitura do "usbipd list": acha a placa ESP32 pelos VID:PID das pontes USB conhecidas.
$BoardIds = @('1a86:55d4', '10c4:ea60', '1a86:7523')   # CH9102, CP2102, CH340

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
