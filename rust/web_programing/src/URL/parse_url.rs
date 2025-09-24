
use url::{Url, ParseError};

pub fn main() -> Result<(), ParseError> {
    let s = "ftp://rust-lang.org/examples";

    let url = Url::parse(s)?;

    println!("{:#?}", url);

    Ok(())
}
