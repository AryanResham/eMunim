param([string]$RunId = ('paper-' + (Get-Date -Format 'yyyyMMdd-HHmmss')))
$ErrorActionPreference = 'Stop'
if ($RunId -notmatch '^[A-Za-z0-9_-]+$') { throw 'Invalid run ID' }
$repoRoot = Split-Path -Parent $PSScriptRoot
$runPath = Join-Path $repoRoot ('backend\data\paper_runs\' + $RunId)
New-Item -ItemType Directory -Path $runPath -Force | Out-Null
$pythonPath = (Get-Command python).Source
$scriptPath = Join-Path $repoRoot 'research\paper_run.py'
$process = Start-Process -FilePath $pythonPath -ArgumentList @('-u', ('"' + $scriptPath + '"'), '--run-id', $RunId) -WorkingDirectory $repoRoot -RedirectStandardOutput (Join-Path $runPath 'supervisor.log') -RedirectStandardError (Join-Path $runPath 'supervisor.stderr.log') -WindowStyle Hidden -PassThru
@{run_id=$RunId;pid=$process.Id;created_at=$process.StartTime.ToUniversalTime().ToString('o');status_path=(Join-Path $runPath 'status.json')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runPath 'launch.json') -Encoding UTF8
Write-Output ('Paper run launched: ' + $RunId + ', PID ' + $process.Id)
