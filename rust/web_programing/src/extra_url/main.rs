#![allow(dead_code)]
mod from_html;
mod detect_dead_link;
mod extra_unique_url;
fn main() {
    // from_html::main();
    // detect_dead_link::main().unwrap();
    extra_unique_url::main().unwrap();
}
