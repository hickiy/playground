#[link(name = "foo", kind = "static")]
unsafe extern "C" {
    fn multiply(x : i32, y : i32) -> i32;
}

pub fn new(){
    unsafe {
        println!("{}", multiply(5,7));
    }   
}
