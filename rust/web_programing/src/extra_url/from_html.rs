use select::document::Document;
use select::predicate::Name;

#[tokio::main]
pub async fn main() {
    let res = reqwest::get("https://www.rust-lang.org/en-US/")
        .await.unwrap()
        .text()
        .await.unwrap();

    Document::from(res.as_str())
        .find(Name("a"))
        .filter_map(|n| n.attr("href"))
        .for_each(|x| println!("{}", x));
}
