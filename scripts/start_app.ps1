$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtimePath = Join-Path $repoRoot 'backend\data\app_runtime'
New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
foreach ($port in @(8000,5173)) {
    $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($listener) { throw ('Port ' + $port + ' is already in use; leaving the existing process untouched.') }
}
$pythonPath = (Get-Command python).Source
$nodePath = (Get-Command node).Source
$env:VITE_API_URL = '/api'
$backend = Start-Process -FilePath $pythonPath -ArgumentList @('-m','uvicorn','main:app','--app-dir','backend','--host','127.0.0.1','--port','8000') -WorkingDirectory $repoRoot -RedirectStandardOutput (Join-Path $runtimePath 'backend.log') -RedirectStandardError (Join-Path $runtimePath 'backend.stderr.log') -WindowStyle Hidden -PassThru
$vitePath = Join-Path $repoRoot 'Frontend\node_modules\vite\bin\vite.js'
$frontend = Start-Process -FilePath $nodePath -ArgumentList @(('"' + $vitePath + '"'),'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory (Join-Path $repoRoot 'Frontend') -RedirectStandardOutput (Join-Path $runtimePath 'frontend.log') -RedirectStandardError (Join-Path $runtimePath 'frontend.stderr.log') -WindowStyle Hidden -PassThru
@{backend_pid=$backend.Id;frontend_pid=$frontend.Id;backend_started=$backend.StartTime.ToUniversalTime().ToString('o');frontend_started=$frontend.StartTime.ToUniversalTime().ToString('o');url='http://127.0.0.1:5173';api='http://127.0.0.1:8000/api'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimePath 'launch.json') -Encoding UTF8
Write-Output 'Started app at http://127.0.0.1:5173 and backend at http://127.0.0.1:8000'
