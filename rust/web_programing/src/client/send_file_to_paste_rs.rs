use std::fs::File;
use std::io::Read;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("HTTP request error: {0}")]
    HttpRequest(#[from] reqwest::Error),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
}

#[tokio::main]
pub async fn main() -> Result<(), Error> {
    let paste_api = "https://paste.rs";
    let mut file = File::open("download.bin")?;

    let mut contents = String::new();
    file.read_to_string(&mut contents)?;

    let client = reqwest::Client::new();
    let res = client.post(paste_api).body(contents).send().await?;
    let response_text = res.text().await?;
    println!("Your paste is located at: {}", response_text);
    Ok(())
}
