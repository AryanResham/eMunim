$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $repoRoot 'backend\data\app_runtime'
$launchPath = Join-Path $runtimePath 'launch.json'
$launchInfo = Get-Content -LiteralPath $launchPath -Raw | ConvertFrom-Json
$worker = Get-Process -Id $launchInfo.backend_pid -ErrorAction SilentlyContinue
if ($worker) {
    if ($worker.StartTime.ToUniversalTime().ToString('o') -ne $launchInfo.backend_started) { throw 'Backend process identity changed; leaving it untouched.' }
    Stop-Process -Id $worker.Id -ErrorAction Stop
}
$pythonPath = (Get-Command python).Source
$backend = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','main:app','--app-dir','backend','--host','127.0.0.1','--port','8000') -WorkingDirectory $repoRoot -RedirectStandardOutput (Join-Path $runtimePath 'backend.log') -RedirectStandardError (Join-Path $runtimePath 'backend.stderr.log') -WindowStyle Hidden -PassThru
$launchInfo.backend_pid = $backend.Id
$launchInfo.backend_started = $backend.StartTime.ToUniversalTime().ToString('o')
$launchInfo | ConvertTo-Json | Set-Content -LiteralPath $launchPath -Encoding UTF8
Write-Output 'Restarted only the identified eMunim backend process.'
