fn main() {
    cc::Build::new().file("hello.c").compile("hello");
    cc::Build::new().cpp(true).file("foo.cpp").compile("foo");

    cc::Build::new()
        .define("APP_NAME", "\"bar\"")
        .define(
            "VERSION",
            format!("\"{}\"", env!("CARGO_PKG_VERSION")).as_str(),
        )
        .define("WELCOME", None)
        .file("bar.c")
        .compile("bar");
}
