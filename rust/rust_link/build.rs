/* 
指定库的查找路径
println!("cargo:rustc-link-search=native=lib");

指定要链接的静态库
println!("cargo:rustc-link-lib=static=hello1");

指定要链接的动态库
println!("cargo:rustc-link-lib=dylib=hello2");
*/

use std::process::Command;
use std::env;

fn main() {
    // 编译静态库
    cc::Build::new().file("lib/lib.c").compile("hello1");
    // 编译动态库
    cc::Build::new().file("lib/dll.c").compile("hello2");
    // 编译动态库到dll格式
    let out_dir = env::var("OUT_DIR").unwrap();
    Command::new("gcc")
        .args(&["lib/dll.c", "-shared", "-o"])
        .arg(out_dir + "/hello2.dll")
        .output()
        .unwrap();
}
