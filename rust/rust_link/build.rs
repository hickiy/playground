fn main() {
    // 编译静态库 libhello1.a
    cc::Build::new()
        .file("lib/lib.c")
        .compile("hello1");

    // 编译动态库 hello2.dll（Windows下）
    #[cfg(target_os = "windows")]
    {
        cc::Build::new()
            .file("lib/dll.c")
            .shared_flag(true)
            .compile("hello2");
    }
}
