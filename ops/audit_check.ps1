# AutoStock mechanism audit daily check
# Called by Windows Task Scheduler at weekday 09:05 KST.
# Saves output to ops/audit_logs/YYYY-MM-DD.txt

$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\Users\windg\Desktop\PROJECT\AutoStock"
$LogDir = Join-Path $ProjectRoot "ops\audit_logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

$Date = Get-Date -Format "yyyy-MM-dd"
$DateKstNow = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
$LogFile = Join-Path $LogDir "$Date.txt"

function Write-Section {
    param([string]$Title, [string]$Content)
    Add-Content -Path $LogFile -Value "===== $Title =====" -Encoding UTF8
    Add-Content -Path $LogFile -Value $Content -Encoding UTF8
    Add-Content -Path $LogFile -Value "" -Encoding UTF8
}

# Header
Set-Content -Path $LogFile -Value "AutoStock mechanism audit check -- $DateKstNow" -Encoding UTF8
Add-Content -Path $LogFile -Value "" -Encoding UTF8

# 1. beat fire log (last 10m)
$beatLog = (docker logs autostock-celery-beat --since 10m 2>&1 | Select-String "audit-mechanisms") -join "`n"
if ([string]::IsNullOrWhiteSpace($beatLog)) { $beatLog = "(no audit-mechanisms fire log -- 09:00 KST schedule miss suspected)" }
Write-Section "1. beat fire log (last 10m)" $beatLog

# 2. worker run_audit log (last 10m)
$workerLog = (docker logs autostock-celery-worker --since 10m 2>&1 | Select-String "mechanism_audit|run_audit") -join "`n"
if ([string]::IsNullOrWhiteSpace($workerLog)) { $workerLog = "(no worker run_audit log)" }
Write-Section "2. worker run_audit (last 10m)" $workerLog

# 3. recent alerts (top 20)
$alerts = docker exec autostock-redis redis-cli LRANGE autostock:alerts 0 19 2>&1
$alertsStr = ($alerts | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($alertsStr)) { $alertsStr = "(0 alerts)" }
Write-Section "3. autostock:alerts top 20" $alertsStr

# 4. today's violation fingerprints
$todayKey = "autostock:audit:violations:$Date"
$violations = docker exec autostock-redis redis-cli SMEMBERS $todayKey 2>&1
$violStr = ($violations | Out-String).Trim()
if ([string]::IsNullOrWhiteSpace($violStr)) { $violStr = "(0 violations -- GO mechanism stable)" }
Write-Section "4. today's violations ($todayKey)" $violStr

# 5. monitored bots status
$botStatus = docker exec autostock-postgres psql -U autostock -d autostock -t -c "SELECT id, name, status, mode FROM trading_bots WHERE id IN (19,20,21,22) ORDER BY id;" 2>&1
Write-Section "5. bot 19-22 status" (($botStatus | Out-String).Trim())

# 6. price_stream heartbeat
$hbRaw = docker exec autostock-redis redis-cli GET autostock:price_stream_heartbeat 2>&1
$hbStr = ($hbRaw | Out-String).Trim()
if ($hbStr -match '^\d+$') {
    # PowerShell 5.1: Get-Date -UFormat %s returns local-time seconds (broken). Use UTC epoch.
    $nowEpoch = [int][DateTimeOffset]::Now.ToUnixTimeSeconds()
    $age = $nowEpoch - [int]$hbStr
    $hbVerdict = if ($age -gt 180) { "STALE -- VIOLATION" } else { "fresh" }
    $hbReport = "last_ts=$hbStr  age=${age}s  ($hbVerdict)"
} else {
    $hbReport = "(heartbeat key missing or parse failed: $hbStr)"
}
Write-Section "6. price_stream heartbeat" $hbReport

# 7. CB state
$cbRaw = docker exec autostock-redis redis-cli GET autostock:cb:state 2>&1
Write-Section "7. autostock:cb:state" (($cbRaw | Out-String).Trim())

# Summary
$violCount = if ($violStr -eq "(0 violations -- GO mechanism stable)") { 0 } else { ($violations | Measure-Object).Count }
$verdict = if ($violCount -eq 0) { "GO -- mechanism stable" } else { "NO-GO -- inspect violation fingerprints above" }
$summary = "violation count: $violCount`nresult: $verdict"
Write-Section "SUMMARY" $summary

Write-Host "audit result saved: $LogFile"
