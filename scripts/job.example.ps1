# job.ps1  一次性任务模板：把要跑的命令写在下面，双击 templates\windows\run_job.cmd 执行；结果在 job_log.txt，结束标记 job_done.txt
# 注意：本文件必须保存为「UTF-8 with BOM」，否则 PowerShell 5.1 会把中文读错，脚本可能直接不执行。
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$root = Split-Path -Parent $PSCommandPath
Set-Location $root
Remove-Item "$root\job_done.txt" -ErrorAction SilentlyContinue
$py = "$root\.venv\Scripts\python.exe"
$log = "$root\job_log.txt"

# 例：完整跑一个企划的自动阶段（人工阶段：SNS 调研、分镜、prompt 另做）
cmd /c """$py"" pipeline.py init hakone-0928 --place ""箱根ガラスの森美術館"" --date 2026-09-28 --arrive 13:00 --hours 12-18 --elev-m 657 > ""$log"" 2>&1"
cmd /c """$py"" pipeline.py spots hakone-0928 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py sun hakone-0928 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py basemap hakone-0928 --meters 130 >> ""$log"" 2>&1"
cmd /c """$py"" pipeline.py stylize hakone-0928 >> ""$log"" 2>&1"

"done" | Out-File "$root\job_done.txt"
