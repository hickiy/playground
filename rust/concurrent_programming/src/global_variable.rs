use lazy_static::lazy_static;
use std::sync::Mutex;

lazy_static! {
    static ref FRUIT: Mutex<Vec<String>> = Mutex::new(Vec::new());
}

fn insert(fruit: &str) {
    let db = FRUIT.lock().map_err(|_| "Failed to acquire MutexGuard");
    match db {
        Ok(mut db) => db.push(fruit.to_string()),
        Err(err) => println!("{}", err),
    }
}

pub fn new() {
    insert("apple");
    insert("orange");
    insert("peach");
    insert("grape");
    {
        let db = FRUIT.lock().map_err(|_| "Failed to acquire MutexGuard");
        match db {
            Ok(db) => {
                db.iter()
                    .enumerate()
                    .for_each(|(i, item)| println!("{}: {}", i, item));
            }
            Err(err) => println!("{}", err),
        }
    }
}
