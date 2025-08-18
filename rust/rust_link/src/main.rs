#[link(name = "hello1", kind = "static")]
extern "C" {
    fn hello1();
}

#[link(name = "hello2", kind = "dylib")]
extern "C" {
    fn hello2();
}

fn main() {
    unsafe {
        hello1();
        hello2();
    }
}
