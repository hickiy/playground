#![allow(dead_code)]
mod get_mime;
mod get_mime_from_filename;
mod get_mime_form_res;

fn main() {
    // get_mime::main();
    // get_mime_from_filename::main();
    get_mime_form_res::main().unwrap();
}
