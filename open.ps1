# Starts the Acronis dashboard if it is not already running, then opens it.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe" }

$running = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -and $_.CommandLine -like "*$root*" -and $_.CommandLine -like "*app:app*" }
if (-not $running) {
  Start-Process -FilePath $py -ArgumentList "-m","uvicorn","app:app","--host","127.0.0.1","--port","8001" `
    -WorkingDirectory $root -WindowStyle Hidden
  Start-Sleep -Seconds 2
}
Start-Process "http://127.0.0.1:8001"
