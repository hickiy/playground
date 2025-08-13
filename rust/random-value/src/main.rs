mod random;
mod random_normal;
mod random_range;
mod random_val;
mod random_str;
mod random_password;
fn main() {
    random();
    random_range();
    random_normal();
    random_val();
    random_str();
    random_password();
}

fn random() {
    println!("Random u8: {}", random::new::<u8>());
    println!("Random u16: {}", random::new::<u16>());
    println!("Random u32: {}", random::new::<u32>());
    println!("Random i32: {}", random::new::<i32>());
    println!("Random f64: {}", random::new::<f64>());
}

fn random_range() {
    println!("Integer {}", random_range::new::<i32>(0, 10));
    println!("Float {}", random_range::new::<f64>(0.0, 10.0));
    loop {
        let throw = random_range::new::<i32>(1, 7);
        println!("Roll the die: {}", throw);
        if throw == 6 {
            break;
        }
    }
}

fn random_normal() {
    println!(
        "{} is from a N(2, 9) distribution",
        random_normal::new::<f64>(2.0, 3.0).unwrap()
    );
}

fn random_val() {
    println!("Random tuple: {:?}", random_val::new::<(i32, bool, f64)>());
    let point: random_val::Point = random_val::new();
    println!("the value of point is {:?} ", point);
    let state: random_val::State = random_val::new();
    println!("the value of state is {:?}", state)
}

fn random_str() {
    println!("the random str is {}", random_str::new(30))
}

fn random_password() {
    println!("the random password is {}", random_password::new(8));
}