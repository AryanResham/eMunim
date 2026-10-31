param([string]$RunId = ('cuda-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^[A-Za-z0-9_-]+$') { throw 'Invalid run ID' }
$trainingRoot = $PSScriptRoot
$runPath = Join-Path $trainingRoot ('runs\' + $RunId)
New-Item -ItemType Directory -Path $runPath -Force | Out-Null
$pythonPath = (Get-Command python).Source
$scriptPath = Join-Path $trainingRoot 'run_all.py'
$process = Start-Process -FilePath $pythonPath -ArgumentList @('-u', ('"' + $scriptPath + '"'), '--run-id', $RunId) -WorkingDirectory $trainingRoot -RedirectStandardOutput (Join-Path $runPath 'supervisor.log') -RedirectStandardError (Join-Path $runPath 'supervisor.stderr.log') -WindowStyle Hidden -PassThru
$launch = @{run_id=$RunId; pid=$process.Id; created_at=$process.StartTime.ToUniversalTime().ToString('o'); status_path=(Join-Path $runPath 'status.json')}
$launch | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runPath 'launch.json') -Encoding UTF8
$launch | ConvertTo-Json
