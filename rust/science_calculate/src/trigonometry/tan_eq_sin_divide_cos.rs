pub fn main() {
    let x: f64 = 6.0;

    let a = x.tan();
    let b = x.sin() / x.cos();

    println!("tan({}) = {}", x, a);
    println!("sin({}) / cos({}) = {}", x, x, b);
}
