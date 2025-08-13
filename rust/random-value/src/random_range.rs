use rand::distributions::{Distribution, Uniform};

pub fn new<T: rand::distributions::uniform::SampleUniform>(start: T, end: T) -> T {
    let mut rng = rand::thread_rng();
    let die = Uniform::from(start..end);
    die.sample(&mut rng)
}
