# AutoStock 데이터 수집 서비스 자동 시작 스크립트
# Windows 부팅 시 Task Scheduler에 의해 자동 실행됨

$ProjectPath = "C:\Users\windg\Desktop\PROJECT\AutoStock"
$LogFile = "$ProjectPath\autostart\startup.log"

function Write-Log($msg) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$timestamp $msg" | Tee-Object -FilePath $LogFile -Append
}

Write-Log "=== AutoStock Collector 시작 ==="

# 1. Docker Desktop이 실행 중인지 확인, 아니면 시작
$dockerRunning = $false
for ($i = 0; $i -lt 12; $i++) {
    try {
        docker info 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            $dockerRunning = $true
            break
        }
    } catch {}

    if ($i -eq 0) {
        Write-Log "Docker Desktop 시작 중..."
        Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    }
    Write-Log "Docker 준비 대기 중... ($($i+1)/12)"
    Start-Sleep -Seconds 10
}

if (-not $dockerRunning) {
    Write-Log "[오류] Docker Desktop 시작 실패 - 수동 확인 필요"
    exit 1
}
Write-Log "Docker 준비 완료"

# 2. 데이터 수집 서비스 시작 (postgres, redis, celery-worker, celery-beat)
Write-Log "데이터 수집 서비스 시작 중..."
Set-Location $ProjectPath
docker compose up -d postgres redis celery-worker celery-beat 2>&1 | ForEach-Object { Write-Log $_ }

if ($LASTEXITCODE -eq 0) {
    Write-Log "데이터 수집 서비스 시작 완료"
} else {
    Write-Log "[오류] 서비스 시작 실패 (exit code: $LASTEXITCODE)"
    exit 1
}

Write-Log "=== 초기화 완료 ==="
