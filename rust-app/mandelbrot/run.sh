#!/bin/bash
# 修改工作目录，使得脚本可以在任何地方运行
cd $(dirname $0)
# 编译
cargo build --release
time ./target/release/mandelbrot mandel.png 4000x3000 -1.20,0.35 -1,0.2
