$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$pgctl = Join-Path $root '.local/postgres/pgsql/bin/pg_ctl.exe'
$pgdata = Join-Path $root '.local/pgdata'
$python = Join-Path $root 'backend/.venv/Scripts/python.exe'
$vite = Join-Path $root 'Frontend/node_modules/vite/bin/vite.js'
if (!(Test-Path $python)) { throw 'Install the backend environment first: python -m venv backend/.venv, then backend/.venv/Scripts/pip install -r backend/requirements-dev.txt.' }
if (!(Test-Path $vite)) { throw 'Install frontend dependencies first with npm ci in Frontend/.' }
if (Test-Path $pgctl) {
    & $pgctl -D $pgdata status *> $null
    if ($LASTEXITCODE -ne 0) {
    & $pgctl -D $pgdata -l "$root/.local/postgres-server.log" -o '-h 127.0.0.1 -p 55432' start
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL failed to start.' }
    }
} elseif (!(Get-NetTCPConnection -LocalPort 55432 -State Listen -ErrorAction SilentlyContinue)) {
    throw 'Local PostgreSQL is unavailable. Install/start PostgreSQL or provide the project local PostgreSQL bundle and data directory under .local/.'
}
New-Item -ItemType Directory -Path (Join-Path $root '.local') -Force | Out-Null
if (!(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath $python -ArgumentList '-m','uvicorn','app.main:app','--host','127.0.0.1','--port','8000' -WorkingDirectory "$root/backend" -WindowStyle Hidden -RedirectStandardOutput "$root/.local/backend.stdout.log" -RedirectStandardError "$root/.local/backend.stderr.log"
}
if (!(Get-NetTCPConnection -LocalPort 5173 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList $vite -WorkingDirectory "$root/Frontend" -WindowStyle Hidden -RedirectStandardOutput "$root/.local/frontend.stdout.log" -RedirectStandardError "$root/.local/frontend.stderr.log"
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
