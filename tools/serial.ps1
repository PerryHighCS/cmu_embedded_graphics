# Capture the EyePi's serial console on Windows (no extra software needed).
#
#   .\tools\serial.ps1                         read COM29 for 20 s
#   .\tools\serial.ps1 -CopyFrom tests\bringup_display.py
#                                              install a file as D:\code.py
#                                              (auto-reloads), then read
#   .\tools\serial.ps1 -Send '^^~'             Ctrl-C twice, Ctrl-D (restart)
#
# In -Send, ^ = Ctrl-C and ~ = Ctrl-D; other characters are typed as-is.
# Find the port in Device Manager: "USB Serial Device", USB\VID_2E8A&PID_1003.
param([string]$Port = 'COM29', [string]$CopyFrom = '', [int]$Seconds = 20, [string]$Send = '')
$sp = New-Object System.IO.Ports.SerialPort $Port, 115200
$sp.DtrEnable = $true
$sp.ReadTimeout = 200
$sp.Open()
Start-Sleep -Milliseconds 300
$null = $sp.ReadExisting()
if ($Send -ne '') {
    foreach ($ch in $Send.ToCharArray()) {
        if ($ch -eq '^') { $sp.Write([char]3) } elseif ($ch -eq '~') { $sp.Write([char]4) } else { $sp.Write([string]$ch) }
        Start-Sleep -Milliseconds 100
    }
}
if ($CopyFrom -ne '') { Copy-Item -LiteralPath $CopyFrom -Destination 'D:\code.py' -Force }
$out = New-Object System.Text.StringBuilder
$end = (Get-Date).AddSeconds($Seconds)
while ((Get-Date) -lt $end) {
    $s = $sp.ReadExisting()
    if ($s) { [void]$out.Append($s) }
    Start-Sleep -Milliseconds 100
}
$sp.Close()
$out.ToString()
