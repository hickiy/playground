#![allow(dead_code)]
mod postgres;
mod sqlite;
fn main() {
    sqlite::new();
    postgres::new();
}
