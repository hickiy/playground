#![allow(dead_code)]
mod check_prerelease;
mod parse_complex_str;
mod parse;
mod specific_version;
mod check_version_compatibility;

fn main() {
    // parse::new();
    // parse_complex_str::new();
    // check_prerelease::new();
    // specific_version::new();
    check_version_compatibility::new();
}
