#[link(name = "hello1", kind = "static")]
extern "C" {
    fn hello1();
}

#[link(name = "hello2", kind = "dylib")]
extern "C" {
    fn hello2();
}

use libloading::{ Library, Symbol };
use std::path::PathBuf;
use std::env;

fn main() {
    unsafe {
        hello1();
        hello2();
    }
    // 构建动态库的相对路径
    let mut lib_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    let out_dir = env::var("OUT_DIR").unwrap();
    lib_path.push(out_dir + r"\hello2.dll");
    // 获取函数指针
    unsafe {
        // 加载动态库
        let lib = Library::new(lib_path).unwrap();
        let hello2: Symbol<unsafe extern "C" fn()> = lib.get(b"hello2").unwrap();
        // 调用函数
        hello2();
    }
}
