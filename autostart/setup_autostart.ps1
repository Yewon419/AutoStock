# AutoStock - Register Windows Task Scheduler
# Run as Administrator

$TaskName = "AutoStock-Collector"
$ScriptPath = "C:\Users\windg\Desktop\PROJECT\AutoStock\autostart\start_collector.ps1"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task"
}

$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$trigger.Delay = "PT1M"

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -NonInteractive -WindowStyle Hidden -File `"$ScriptPath`""

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) `
    -RunOnlyIfNetworkAvailable `
    -StartWhenAvailable `
    -DontStopIfGoingOnBatteries `
    -AllowStartIfOnBatteries

Register-ScheduledTask `
    -TaskName $TaskName `
    -Trigger $trigger `
    -Action $action `
    -Settings $settings `
    -Description "AutoStock data collector auto-start (postgres, redis, celery)" `
    -Force | Out-Null

Write-Host "Task Scheduler registered: '$TaskName'"
Write-Host "The data collection service will auto-start on next login."
