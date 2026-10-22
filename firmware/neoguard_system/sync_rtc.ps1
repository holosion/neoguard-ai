[CmdletBinding()]
param(
    [string]$Port,
    [switch]$ListPorts,
    [switch]$ValidateOnly
)

$ErrorActionPreference = 'Stop'

function Get-NairobiClockCommand {
    $clockLocal = [TimeZoneInfo]::ConvertTimeBySystemTimeZoneId(
        [DateTime]::UtcNow, 'E. Africa Standard Time')
    return 'TIME ' + $clockLocal.ToString('yyyy-MM-dd HH:mm:ss', [Globalization.CultureInfo]::InvariantCulture)
}

if ($ValidateOnly) {
    $clockCommand = Get-NairobiClockCommand
    if ($clockCommand -notmatch '^TIME \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$') {
        throw 'Unexpected date/time command format.'
    }
    Write-Output "$clockCommand (Nairobi UTC+03:00; validation only, no device opened)"
    exit 0
}

$clockPorts = @([System.IO.Ports.SerialPort]::GetPortNames() | Sort-Object)
if ($ListPorts) {
    if ($clockPorts.Count -eq 0) { Write-Output 'No serial ports found.' }
    else { $clockPorts | ForEach-Object { Write-Output $_ } }
    exit 0
}
if (-not $Port) {
    if ($clockPorts.Count -ne 1) {
        throw "Choose the ESP32 port using -Port COM5. Available ports: $($clockPorts -join ', '). Close Arduino Serial Monitor first."
    }
    $Port = $clockPorts[0]
}
if ($clockPorts -notcontains $Port) { throw "Port $Port was not found. Available: $($clockPorts -join ', ')." }

$clockSerial = [System.IO.Ports.SerialPort]::new($Port, 115200, 'None', 8, 'One')
$clockSerial.NewLine = "`n"
$clockSerial.ReadTimeout = 300
$clockSerial.WriteTimeout = 1500
$clockSerial.DtrEnable = $true
$clockSerial.RtsEnable = $false
try {
    Write-Output "Opening $Port. Arduino Serial Monitor must be closed."
    $clockSerial.Open()
    # Some USB interfaces reset the board when the connection opens.
    Start-Sleep -Milliseconds 3500
    $clockSerial.DiscardInBuffer()
    # Capture current time after the startup wait, never before it.
    $clockCommand = Get-NairobiClockCommand
    $clockSerial.WriteLine($clockCommand)
    Write-Output "Sent $clockCommand (Nairobi UTC+03:00)"
    $clockResponse = ''
    $clockDeadline = [DateTime]::UtcNow.AddSeconds(8)
    while ([DateTime]::UtcNow -lt $clockDeadline) {
        $clockResponse += $clockSerial.ReadExisting()
        if ($clockResponse -match 'RTC SET OK \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[^\r\n]*\r?\n') {
            Write-Output $Matches[0].Trim()
            Write-Output 'Clock readback confirmed. You can reopen Serial Monitor at 115200 baud.'
            exit 0
        }
        if ($clockResponse -match 'RTC ERROR:[^\r\n]+\r?\n') { throw $Matches[0].Trim() }
        if ($clockResponse.Length -gt 8192) { $clockResponse = $clockResponse.Substring($clockResponse.Length - 4096) }
        Start-Sleep -Milliseconds 100
    }
    throw 'No RTC confirmation received. Check the selected port, upload the new firmware, and check DS1302 wiring.'
} finally {
    if ($clockSerial.IsOpen) { $clockSerial.Close() }
    $clockSerial.Dispose()
}
