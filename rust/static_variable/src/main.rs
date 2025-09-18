use lazy_static::lazy_static;
use std::collections::HashMap;
use std::sync::Mutex;

lazy_static! {
    static ref PRIVILEGES: Mutex<HashMap<&'static str, Vec<&'static str>>> = {
        let mut map = HashMap::new();
        map.insert("James", vec!["user", "admin"]);
        map.insert("Jim", vec!["user"]);
        Mutex::new(map)
    };
}

fn main() {
    {
        let privileges = PRIVILEGES.lock().unwrap();
        let access = privileges.get("James");
        println!("James: {:?}", access);
    }

    {
        let mut privileges = PRIVILEGES.lock().unwrap();
        privileges.insert("Jack", vec!["user"]);
    }

    {
        let privileges = PRIVILEGES.lock().unwrap();
        let access = privileges.get("Jack");
        println!("Jack: {:?}", access);
    }
}