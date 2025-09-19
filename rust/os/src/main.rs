#![allow(dead_code)]
mod git_log;
mod python;
mod pip;
mod ls;
mod journalctl;
mod read_env;
fn main() {
    // git_log::main().unwrap();
    // python::main().unwrap();
    // pip::main().unwrap();
    // ls::main().unwrap();
    // journalctl::main().unwrap();
    read_env::main().unwrap();
}
