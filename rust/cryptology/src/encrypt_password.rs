use data_encoding::HEXUPPER;
use ring::pbkdf2::PBKDF2_HMAC_SHA512;
use ring::{digest, pbkdf2, rand};
use ring::rand::SecureRandom;
use std::num::NonZeroU32;


pub fn new() {
  const CREDENTIAL_LEN: usize = digest::SHA512_OUTPUT_LEN;
  let n_iter = NonZeroU32::new(100_00).unwrap();
  let rng = rand::SystemRandom::new();

  let mut salt = [0u8; CREDENTIAL_LEN];

  rng.fill(&mut salt).unwrap();

  let password = "Guess Me, If You Can!";

  let mut pbkdf2_hash = [0u8; CREDENTIAL_LEN];

  pbkdf2::derive(
    pbkdf2::PBKDF2_HMAC_SHA512,
    n_iter,
    &salt,
    password.as_bytes(),
    &mut pbkdf2_hash,
  );

  println!("Salt: {}", HEXUPPER.encode(&salt));
  println!("PBKDF2 hase: {}", HEXUPPER.encode(&pbkdf2_hash));

  let should_succeed = pbkdf2::verify(
    PBKDF2_HMAC_SHA512,
    n_iter,
    &salt,
    password.as_bytes(),
    &pbkdf2_hash,
  );

  if should_succeed.is_ok() {
    println!("verify is success")
  }

}