use glob::{MatchOptions, glob_with};

pub fn new() {
    let options = MatchOptions {
        case_sensitive: false,
        ..Default::default()
    };

    for entry in glob_with("**/*.toml", options).unwrap() {
        println!("{}", entry.unwrap().display());
    }
}
