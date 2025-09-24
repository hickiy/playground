use thiserror::Error;
use url::Url;

#[derive(Debug, Error)]
pub enum Error {
    #[error("Failed to parse URL")]
    UrlParse(#[from] url::ParseError),
    #[error("Cannot be a base URL")]
    CannotBeABase,
}
type Result<T> = std::result::Result<T, Error>;

pub fn main() -> Result<()> {
    let full = "https://github.com/rust-lang/cargo?asdf";

    let url = Url::parse(full)?;
    let base = base_url(url)?;

    assert_eq!(base.as_str(), "https://github.com/");
    println!("The base of the URL is: {}", base);

    Ok(())
}

fn base_url(mut url: Url) -> Result<Url> {
    match url.path_segments_mut() {
        Ok(mut path) => {
            path.clear();
        }
        Err(_) => {
            return Err(Error::CannotBeABase);
        }
    }

    url.set_query(None);

    Ok(url)
}
