@echo off
REM 切换到当前目录
cd /d %~dp0
REM 编译
REM cargo build --release
REM 运行
cargo run "world" "rust" .\test.txt .\copy.txt
type .\copy.txt