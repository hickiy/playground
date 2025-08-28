use rusqlite::Connection;
use std::collections::HashMap;

struct Cat {
    name: String,
    color: String,
}

pub fn new() {
    let conn = Connection::open("cats.db").unwrap();

    let mut cat_colors = HashMap::new();
    cat_colors.insert(String::from("Blue"), vec!["Tigger", "Sammy"]);
    cat_colors.insert(String::from("Black"), vec!["Oreo", "Biscuit"]);

    for (color, catnames) in &cat_colors  {
        conn.execute(
            "INSERT INTO cat_colors (name) values (?1)",
            &[&color.to_string()],
        )
        .unwrap();

        let last_id: String = conn.last_insert_rowid().to_string();

        for cat in catnames {
            conn.execute(
                "INSERT INTO cats (name, color_id) values (?1, ?2)",
                &[&cat.to_string(), &last_id],
            )
            .unwrap();
        }
    }

    let mut stmt = conn
        .prepare(
            "SELECT c.name, cc.name from cats c
         INNER JOIN cat_colors cc
         ON cc.id = c.color_id;",
        )
        .unwrap();

    let cats = stmt
        .query_map([], |row| {
            Ok(Cat {
                name: row.get(0).unwrap(),
                color: row.get(1).unwrap(),
            })
        })
        .unwrap();

    for cat in cats {
        match cat {
            Ok(cat) => println!("Found Cat {} color is {}", cat.name, cat.color),
            Err(e) => eprintln!("Error reading cat: {}", e),
        }
    }
}
