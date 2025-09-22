use ndarray::Array;

pub fn main() {
    let a = Array::from(vec![1., 2., 3., 4., 5.]);
    let b = Array::from(vec![5., 4., 3., 2., 1.]);
    let mut c = Array::from(vec![1., 2., 3., 4., 5.]);
    let mut d = Array::from(vec![5., 4., 3., 2., 1.]);

    let z = a + b;
    let w = &c + &d;

    println!("z = {}", z);
    println!("w = {}", w);

    c[0] = 10.;
    println!("c = {}", c);
    d[0] = 10.;
    println!("d = {}", d);
}
