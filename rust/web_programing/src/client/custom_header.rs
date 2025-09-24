use serde::Deserialize;
use thiserror::Error;

use reqwest::Client;
use reqwest::header::{AUTHORIZATION, HeaderMap, HeaderValue, USER_AGENT};
use std::collections::HashMap;
use url::Url;

#[derive(Deserialize, Debug)]
pub struct HeadersEcho {
    pub headers: HashMap<String, String>,
}

#[derive(Error, Debug)]
pub enum Error {
    #[error("HTTP request error: {0}")]
    HttpRequest(#[from] reqwest::Error),
    #[error("URL parsing error: {0}")]
    UrlParse(#[from] url::ParseError),
}


#[tokio::main]
pub async fn main() -> Result<(), Error> {
    let url = Url::parse_with_params(
        "http://httpbin.org/headers",
        &[("lang", "rust"), ("browser", "servo")],
    )?;

    let mut headers = HeaderMap::new();
    headers.insert(USER_AGENT, HeaderValue::from_static("Rust-test"));
    headers.insert(
        AUTHORIZATION,
        HeaderValue::from_static("Bearer DEadBEEfc001cAFeEDEcafBAd"),
    );
    headers.insert(
        "X-Powered-By",
        HeaderValue::from_static("Guybrush Threepwood"),
    );

    let client = Client::new();
    let response = client.get(url).headers(headers).send().await?;

    println!("{:?}", response.url().as_str());
    let out: HeadersEcho = response.json().await?;
    println!("{:#?}", out);
    Ok(())
}
