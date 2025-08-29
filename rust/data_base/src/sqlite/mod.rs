mod data_base;
mod insert_query;
mod transaction;

pub fn main() {
    if std::path::Path::new("cats.db").exists() {
        std::fs::remove_file("cats.db").expect("Failed to delete cats.db");
    }
    data_base::new();
    insert_query::new();
    transaction::new();
}
