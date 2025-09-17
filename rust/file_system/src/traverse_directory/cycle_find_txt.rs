use glob::glob;

pub fn new()  {
    for entry in glob("**/*.toml").unwrap() {
        println!("{}", entry.unwrap().display());
    }
}
