use postgres::{Client, NoTls};

struct CountryStats {
    country: String,
    book_count: i64,
}

pub fn new() {
    let mut client = Client::connect("postgresql://postgres:245786@localhost:5432", NoTls).unwrap();

    for row in client
        .query(
            "SELECT a.country, COUNT(b.id) AS book_count
    FROM author a
    LEFT JOIN book b ON a.id = b.author_id
    GROUP BY a.country
    ORDER BY book_count DESC",
            &[],
        )
        .unwrap()
    {
        let (country, book_count): (Option<String>, Option<i64>) = (row.get(0), row.get(1));

        if country.is_some() && book_count.is_some() {
            let stats = CountryStats {
                country: country.unwrap(),
                book_count: book_count.unwrap(),
            };
            println!("{}: {} books", stats.country, stats.book_count);
        }
    }
}
