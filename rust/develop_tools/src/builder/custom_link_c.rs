#[link(name = "bar", kind = "static")]
unsafe extern "C" {
    fn print_app_info();
}

pub fn new() {
    unsafe {
        print_app_info();
    }
}
