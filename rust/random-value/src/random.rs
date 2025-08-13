use rand::Rng;

pub fn new<T>() -> T
where
    rand::distributions::Standard: rand::distributions::Distribution<T>,
{
    rand::thread_rng().r#gen::<T>()
}
