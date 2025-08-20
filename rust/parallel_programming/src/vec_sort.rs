
use rand::{Rng, thread_rng};
use rand::distributions::Alphanumeric;
use rayon::prelude::*;

pub fn new() {
  let mut vec = vec![String::new(); 10];
  vec.par_iter_mut().for_each(|p| {
    let mut rng = thread_rng();
    *p = (0..10)
      .map(|_| rng.sample(&Alphanumeric) as char)
      .collect()
  });
  println!("{:?}", vec);
  vec.par_sort_unstable();
  println!("{:?}", vec);
}
