use bcrypt::{ hash, DEFAULT_COST };
fn main() {
    let my_password = std::env
        ::args()
        .nth(1)
        .unwrap_or_else(|| {
            eprintln!("Usage: {} <password>", std::env::args().next().unwrap());
            std::process::exit(1);
        });
    let hashed_password = hash(my_password, DEFAULT_COST).unwrap();
    println!("Hashed password: {}", &hashed_password);
    std::fs::write("hashed_password.txt", hashed_password).unwrap();
    std::process::exit(0);
    // To run this code, you need to add the bcrypt crate to your Cargo.toml file:
}
