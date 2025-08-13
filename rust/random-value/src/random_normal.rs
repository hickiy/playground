use rand::thread_rng;
use rand_distr::{Distribution, Normal, NormalError, StandardNormal, num_traits::Float};

pub fn new<T>(mean: T, dev: T) -> Result<T, NormalError>
where
    T: Float,
    StandardNormal: Distribution<T>,
{
    let mut rng = thread_rng();
    let normal = Normal::new(mean, dev)?;
    let v = normal.sample(&mut rng);
    Ok(v)
}
