use ndarray::arr2;

pub fn main() {
    let a = arr2(&[[1, 3], [4, 6]]);

    let b = arr2(&[[6, 3], [4, 1]]);

    println!("{}", a.dot(&b));
    println!("{}", b.dot(&a));
}
