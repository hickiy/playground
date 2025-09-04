use std::ffi::CString;
use std::os::raw::c_char;

fn prompt(s: &str) -> String {
    use std::io::Write;
    print!("{}", s);
    std::io::stdout().flush().unwrap();
    let mut input = String::new();
    std::io::stdin().read_line(&mut input).unwrap();
    input.trim().to_string()
}

#[link(name = "hello", kind = "static")]
unsafe extern "C" {
    fn hello();
    fn greet(name: *const c_char);
}

pub fn new()  {
    unsafe { hello() }
    let name = prompt("What's your name? ");
    let c_name = CString::new(name).unwrap();
    unsafe { greet(c_name.as_ptr()) }
}
