#![allow(dead_code)]
mod deserialize_url;
mod creat_base_url;
mod creat_url_from_baseurl;
mod parse_url;
mod remove_some_params;

fn main() {
    // deserialize_url::main().unwrap();
    // creat_base_url::main().unwrap();
    // creat_url_from_baseurl::main().unwrap();
    // parse_url::main().unwrap();
    remove_some_params::main().unwrap();
}
