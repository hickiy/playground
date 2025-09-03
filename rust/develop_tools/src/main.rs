#![allow(dead_code)]
mod log_to_console;
mod err_to_console;
mod err_to_console_by_stdout;
mod custom_logger;
mod to_unix_sys_log;
fn main() {
    // log_to_console::new();
    // err_to_console::new();
    // err_to_console_by_stdout::new();
    // custom_logger::new();
    to_unix_sys_log::new();
}
