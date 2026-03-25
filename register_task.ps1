Unregister-ScheduledTask -TaskName "HermesMonitor" -Confirm:$false -ErrorAction SilentlyContinue

$pythonExe = "C:\Users\atsur\AppData\Local\Programs\Python\Python310\python.exe"
$scriptPath = "C:\Users\atsur\Documents\my-first-project\monitor_hermes.py"
$workDir = "C:\Users\atsur\Documents\my-first-project"

$action = New-ScheduledTaskAction -Execute $pythonExe -Argument $scriptPath -WorkingDirectory $workDir
$trigger = New-ScheduledTaskTrigger -RepetitionInterval ([TimeSpan]::FromMinutes(5)) -Once -At (Get-Date)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::FromMinutes(4)) -StartWhenAvailable

Register-ScheduledTask -TaskName "HermesMonitor" -Action $action -Trigger $trigger -Settings $settings -Force

Get-ScheduledTask -TaskName "HermesMonitor" | Get-ScheduledTaskInfo | Select-Object NextRunTime
