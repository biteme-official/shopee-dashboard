$ErrorActionPreference = "Stop"
$ProjectDir = "C:\Users\User\shopee-dashboard"
$LogFile = "$ProjectDir\output\run_log.txt"

Set-Location $ProjectDir

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $msg" | Tee-Object -Append -FilePath $LogFile
}

Log "=== Shopee Dashboard Auto Update ==="

# 1. git pull
Log "Pulling latest from main..."
git pull origin main 2>&1 | Out-String | ForEach-Object { Log $_ }

# 2. Run collector + dashboard
Log "Running collector + dashboard..."
$result = & python run.py 30 2>&1 | Out-String
Log $result

# 3. Find latest HTML
$latest = Get-ChildItem "$ProjectDir\output\shopee_dashboard_*.html" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) {
    Log "ERROR: No dashboard HTML found. Aborting."
    exit 1
}
Log "Latest dashboard: $($latest.Name)"

# 4. Copy to docs/index.html
if (-not (Test-Path "$ProjectDir\docs")) { New-Item -ItemType Directory "$ProjectDir\docs" | Out-Null }
Copy-Item $latest.FullName "$ProjectDir\docs\index.html" -Force
Log "Copied to docs/index.html"

# 5. Git commit + push
git add docs/index.html
$hasChanges = git diff --cached --quiet 2>&1; $changed = -not $?
if ($changed) {
    $date = Get-Date -Format "yyyy-MM-dd"
    git commit -m "chore: 대시보드 자동 갱신 $date"
    git push origin main
    Log "Pushed to GitHub. Pages will update shortly."
} else {
    Log "No changes to push."
}

Log "=== Done ==="
