#![allow(dead_code)]
mod deser_json;
mod deser_toml;
mod deser_toml_custom;
mod io_number_lowwer_order;
fn main() {
    // deserialize_json::new();
    // deser_toml::new();
    // deser_toml_custom::new();
    io_number_lowwer_order::new();
}
