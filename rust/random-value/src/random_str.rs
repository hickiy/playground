use rand::distributions::Alphanumeric;
use rand::{Rng, thread_rng};

pub fn new(len: usize) -> String {
    thread_rng()
        .sample_iter(&Alphanumeric)
        .take(len)
        .map(char::from)
        .collect()
}
