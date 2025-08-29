use postgres::{Client, NoTls};

pub fn new() {
    let mut client = Client::connect("postgresql://postgres:245786@localhost:5432", NoTls).unwrap();

    client
        .batch_execute(
            "
        CREATE TABLE IF NOT EXISTS author (
            id              SERIAL PRIMARY KEY,
            name            VARCHAR NOT NULL,
            country         VARCHAR NOT NULL
            )
    ",
        )
        .unwrap();

    client
        .batch_execute(
            "
        CREATE TABLE IF NOT EXISTS book  (
            id              SERIAL PRIMARY KEY,
            title           VARCHAR NOT NULL,
            author_id       INTEGER NOT NULL REFERENCES author
            )
    ",
        )
        .unwrap();
}
