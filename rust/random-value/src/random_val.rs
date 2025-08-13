#![allow(dead_code)]
use rand::Rng;
use rand::distributions::{Distribution, Standard};
#[derive(Debug)]
pub struct Point {
    x: i32,
    y: i32,
}

impl Distribution<Point> for Standard {
    fn sample<R: Rng + ?Sized>(&self, rng: &mut R) -> Point {
        let (x, y) = rng.r#gen();
        Point { x, y }
    }
}

#[derive(Debug)]
pub enum State {
    Open(bool),
    Closed(bool),
}

impl Distribution<State> for Standard {
    fn sample<R: Rng + ?Sized>(&self, rng: &mut R) -> State {
        let (x, y) = rng.r#gen();
        if x {
            State::Open(y)
        } else {
            State::Closed(y)
        }
    }
}

pub fn new<T>() -> T
where
    Standard: Distribution<T>,
{
    let mut rng = rand::thread_rng();
    rng.r#gen::<T>()
}
