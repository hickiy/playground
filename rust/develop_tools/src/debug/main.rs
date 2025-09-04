#![allow(dead_code)]
mod to_unix_sys_log;
mod contain_timestamp_in_log;
mod custom_env;
mod custom_logger;
mod err_to_console;
mod err_to_console_by_stdout;
mod log_to_console;
mod log_to_file;
mod module_level_log;

fn main() {
    // log_to_console::new();
    // err_to_console::new();
    // err_to_console_by_stdout::new();
    // custom_logger::new();
    // to_unix_sys_log::new();
    // module_level_log::new();
    // custom_env::new();
    // contain_timestamp_in_log::new();
    log_to_file::new();
}
