#![allow(dead_code)]
mod get_sync;
mod get_async;
mod custom_header;
mod query_github_api;
mod is_source_exist;
mod create_and_delete_gist;
mod pagination_by_rest_ful;
mod rate_limit_api;
mod download;
mod partial_download;
mod send_file_to_paste_rs;

fn main() {
    // get_sync::main().unwrap();
    // get_async::main().unwrap();
    // custom_header::main().unwrap();
    // query_github_api::main().unwrap();
    // is_source_exist::main().unwrap();
    // create_and_delete_gist::main().unwrap();
    // pagination_by_rest_ful::main().unwrap();
    // rate_limit_api::main().unwrap();
    // download::main().unwrap();
    // partial_download::main().unwrap();
    send_file_to_paste_rs::main().unwrap();
}
