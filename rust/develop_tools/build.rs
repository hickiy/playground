fn main() {
    cc::Build::new().file("hello.c").compile("hello"); // 输出 `libhello.a`
    cc::Build::new()
        .cpp(true)
        .file("foo.cpp")
        .compile("foo");
}
