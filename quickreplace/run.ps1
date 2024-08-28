#!powershell
# 切换到当前目录
Set-Location -Path $PSScriptRoot
# 编译
# cargo build --release
# 运行
cargo run "world" "rust" ./test.txt ./copy.txt
Get-Content -Path ./copy.txt

