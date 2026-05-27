$ProjectDir = "C:\Users\User\shopee-dashboard"
$LogFile = "$ProjectDir\output\run_log.txt"

Set-Location $ProjectDir

if (-not (Test-Path "$ProjectDir\output")) { New-Item -ItemType Directory "$ProjectDir\output" | Out-Null }

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts $msg" | Tee-Object -Append -FilePath $LogFile
}

Log "=== Shopee Dashboard Auto Update ==="

# 1. git pull
Log "Pulling latest from main..."
$pullOutput = cmd /c "git pull origin main 2>&1"
Log ($pullOutput -join "`n")

# 2. Run collector + dashboard
Log "Running collector + dashboard..."
$runOutput = cmd /c "python run.py 30 2>&1"
Log ($runOutput -join "`n")

# 3. Find latest HTML
$latest = Get-ChildItem "$ProjectDir\output\shopee_dashboard_*.html" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
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
cmd /c "git add docs/index.html 2>&1" | Out-Null
$diff = cmd /c "git diff --cached --quiet 2>&1"
if ($LASTEXITCODE -ne 0) {
    $date = Get-Date -Format "yyyy-MM-dd"
    cmd /c "chcp 65001 >nul && git commit -m `"chore: dashboard auto update $date`" 2>&1"
    $pushOutput = cmd /c "git push origin main 2>&1"
    Log ($pushOutput -join "`n")
    Log "Pushed to GitHub. Pages will update shortly."
} else {
    Log "No changes to push."
}

Log "=== Done ==="
