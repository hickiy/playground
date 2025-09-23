use lazy_static::lazy_static;

use regex::Regex;

pub fn extract_login(input: &str) -> Option<&str> {
    lazy_static! {
        static ref RE: Regex = Regex::new(
            r"(?x)
            ^(?P<login>[^@\s]+)@
            ([[:word:]]+\.)*
            [[:word:]]+$
            "
        )
        .unwrap();
    }
    RE.captures(input)
        .and_then(|cap| cap.name("login").map(|login| login.as_str()))
}

pub fn main() {
    println!(
        "{}",
        extract_login(r"I❤email@example.com").unwrap_or("None")
    );
    println!(
        "{}",
        extract_login(r"sdf+sdsfsd.as.sdsd@jhkk.d.rl").unwrap_or("None")
    );
    println!(
        "{}",
        extract_login(r"More@Than@One@at.com").unwrap_or("None")
    );
    println!("{}", extract_login(r"Not an email@email").unwrap_or("None"));
}
