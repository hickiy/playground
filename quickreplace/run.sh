#!/bin/bash
# 切换到当前目录
cd $(dirname $0)
# 编译
# cargo build --release
# 运行
cargo run "world" "rust" ./test.txt ./copy.txt
cat copy.txt