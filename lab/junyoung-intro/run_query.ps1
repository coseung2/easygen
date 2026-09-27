param([Parameter(Mandatory = $true)][string]$Sql, [string]$Out = '')
$env:EOSEOWA_PROJECT_REF = 'fkaacgvqymimtzdlncmx'
$script = 'C:/Users/coseung2/Desktop/Projects/modal-gui/lab/junyoung-intro/query_db.py'
Push-Location 'C:/Users/coseung2/Desktop/Projects/eoseowa'
try {
  if ($Out) {
    infisical run --projectId 296a334f-a9ef-4313-acfb-8ee9414595b0 --env prod --path /mobile --silent -- python $script sql $Sql $Out
  } else {
    infisical run --projectId 296a334f-a9ef-4313-acfb-8ee9414595b0 --env prod --path /mobile --silent -- python $script sql $Sql
  }
} finally { Pop-Location }
