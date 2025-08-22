use ring::rand::SecureRandom;
use ring::{hmac, rand};

pub fn new() {
    let mut key_value = [0u8; 48];
    let rng = rand::SystemRandom::new();
    rng.fill(&mut key_value).unwrap();
    let key = hmac::Key::new(hmac::HMAC_SHA256, &key_value);

    let message = "Legitimate and important message.";
    let signature = hmac::sign(&key, message.as_bytes());
    println!("The signature value is {:?}", signature);
    hmac::verify(&key, message.as_bytes(), signature.as_ref()).unwrap();
}
