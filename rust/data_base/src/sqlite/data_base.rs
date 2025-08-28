use rusqlite::Connection;

pub fn new() {
    let conn = Connection::open("cats.db").unwrap();

    conn.execute(
        "create table if not exists cat_colors (
             id integer primary key,
             name text not null unique
         )",
        [],
    )
    .unwrap();
    conn.execute(
        "create table if not exists cats (
             id integer primary key,
             name text not null,
             color_id integer not null references cat_colors(id)
         )",
        [],
    )
    .unwrap();
}
