use postgres::{Client, NoTls};
use std::collections::HashMap;

struct Author {
    _id: i32,
    name: String,
    country: String,
}

pub fn new() {
    let mut client = Client::connect("postgresql://postgres:245786@localhost:5432", NoTls).unwrap();

    let mut authors = HashMap::new();
    authors.insert(String::from("Chinua Achebe"), "Nigeria");
    authors.insert(String::from("Rabindranath Tagore"), "India");
    authors.insert(String::from("Anita Nair"), "India");

    for (key, value) in &authors {
        let author = Author {
            _id: 0,
            name: key.to_string(),
            country: value.to_string(),
        };

        client.execute(
            "INSERT INTO author (name, country) VALUES ($1, $2)",
            &[&author.name, &author.country],
        ).unwrap();
    }

    for row in client.query("SELECT id, name, country FROM author", &[]).unwrap() {
        let author = Author {
            _id: row.get(0),
            name: row.get(1),
            country: row.get(2),
        };
        println!("Author {} is from {}", author.name, author.country);
    }
}
