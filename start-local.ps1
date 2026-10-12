$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pgctl = Join-Path $root '.local/postgres/pgsql/bin/pg_ctl.exe'
$pgdata = Join-Path $root '.local/pgdata'
& $pgctl -D $pgdata status *> $null
if ($LASTEXITCODE -ne 0) {
    & $pgctl -D $pgdata -l "$root/.local/postgres-server.log" -o '-h 127.0.0.1 -p 55432' start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start.' }
}
if (!(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath "$root/.venv/Scripts/python.exe" -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory "$root/backend" -WindowStyle Hidden -RedirectStandardOutput "$root/.local/backend.stdout.log" -RedirectStandardError "$root/.local/backend.stderr.log"
}
if (!(Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList 'node_modules/vite/bin/vite.js' -WorkingDirectory "$root/frontend" -WindowStyle Hidden -RedirectStandardOutput "$root/.local/frontend.stdout.log" -RedirectStandardError "$root/.local/frontend.stderr.log"
}
foreach ($url in @('http://127.0.0.1:8000/health', 'http://127.0.0.1:5173')) {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try { $null = Invoke-WebRequest -Uri $url -UseBasicParsing; $ready = $true; break } catch { Start-Sleep -Seconds 1 }
    }
    if (!$ready) { throw "Service did not become ready: $url. Check .local logs." }
}
Write-Host 'Frontend: http://127.0.0.1:5173'
Write-Host 'API docs: http://127.0.0.1:8000/docs'
Write-Host 'PostgreSQL: 127.0.0.1:55432 / neoguard'
