use rusqlite::{Connection, Result};

pub fn new() {
    let mut conn = Connection::open("cats.db").unwrap();

    successful_tx(&mut conn);

    let res = rolled_back_tx(&mut conn);

    println!("the value of res is: {}", res.is_err());
}

fn successful_tx(conn: &mut Connection) {
    let tx = conn.transaction().unwrap();

    tx.execute("delete from cats", []).unwrap();
    tx.execute("delete from cat_colors", []).unwrap();
    tx.execute("insert into cat_colors (name) values (?1)", &[&"lavender"])
        .unwrap();
    tx.execute("insert into cat_colors (name) values (?1)", &[&"blue"])
        .unwrap();

    let _ = tx.commit();
}

fn rolled_back_tx(conn: &mut Connection) -> Result<()> {
    let tx = conn.transaction().unwrap();

    tx.execute("delete from cat_colors", []).unwrap();
    tx.execute("insert into cat_colors (name) values (?1)", &[&"lavender"])
        .unwrap();
    tx.execute("insert into cat_colors (name) values (?1)", &[&"blue"])
        .unwrap();
    tx.commit()
}
