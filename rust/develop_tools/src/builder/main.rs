#![allow(dead_code)]
mod link_c;
mod link_cpp;
mod custom_link_c;
fn main() {
    // link_c::new();
    // link_cpp::new();
    custom_link_c::new();
}
