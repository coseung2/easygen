param([Parameter(Mandatory = $true)][string]$Sql, [string]$Out = '')
$env:EOSEOWA_PROJECT_REF = 'fkaacgvqymimtzdlncmx'
$script = Join-Path $PSScriptRoot 'query_db.py'
$eoseowaRoot = $env:EOSEOWA_REPO_ROOT
if (-not $eoseowaRoot) { throw 'Set EOSEOWA_REPO_ROOT to the Eoseowa repository.' }
Push-Location $eoseowaRoot
try {
  if ($Out) {
    infisical run --projectId 296a334f-a9ef-4313-acfb-8ee9414595b0 --env prod --path /mobile --silent -- python $script sql $Sql $Out
  } else {
    infisical run --projectId 296a334f-a9ef-4313-acfb-8ee9414595b0 --env prod --path /mobile --silent -- python $script sql $Sql
  }
} finally { Pop-Location }
