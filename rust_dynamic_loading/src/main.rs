use libloading::{ Library, Symbol };
use std::path::PathBuf;

fn main() {
    // 构建动态库的相对路径
    let mut lib_path = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    lib_path.push(r"src\hello.dll");
    println!("{:?}", lib_path);
    // 获取函数指针
    unsafe {
        // 加载动态库
        let lib = Library::new(lib_path).unwrap();
        let hello_from_c: Symbol<unsafe extern "C" fn()> = lib.get(b"hello_from_c").unwrap();
        // 调用函数
        hello_from_c();
    }
}
