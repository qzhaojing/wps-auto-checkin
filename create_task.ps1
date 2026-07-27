# 创建 Windows 任务计划程序：每天 08:30 运行 WPS 签到（含随机延迟防检测）
# 右键"以管理员身份运行" PowerShell，然后执行本脚本
# 实际签到将在 08:30 + 随机 0~115 秒内执行

$taskName = "WPS每日签到"
$scriptPath = Resolve-Path -Path "$PSScriptRoot\wps_checkin.py"
$pythonExe = (Get-Command python).Source

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument "`"$scriptPath`" --max-delay 115" -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At "08:30"
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Write-Host "已创建任务：$taskName，每天 08:30 触发（含随机延迟 0~115 秒，实际签到在 08:30~08:32 之间随机执行）。"
Write-Host "如需修改时间，打开 任务计划程序 → 找到 $taskName → 属性 → 触发器。"
pause
