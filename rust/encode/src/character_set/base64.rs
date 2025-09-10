use base64::engine::general_purpose::STANDARD;
use base64::Engine as _;
use std::str;

pub fn new() {
    let hello = b"hello rustaceans";
    let encoded = STANDARD.encode(hello);
    let decoded = STANDARD.decode(&encoded).unwrap();

    println!("origin: {}", str::from_utf8(hello).unwrap());
    println!("base64 encoded: {}", encoded);
    println!("back to origin: {}", str::from_utf8(&decoded).unwrap());
}
