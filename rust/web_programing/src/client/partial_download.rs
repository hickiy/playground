use reqwest::StatusCode;
use reqwest::header::{CONTENT_LENGTH, HeaderValue, RANGE};
use std::fs::File;
use std::str::FromStr;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum Error {
    #[error("General error: {0}")]
    General(String),
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Reqwest error: {0}")]
    Reqwest(#[from] reqwest::Error),
    #[error("Header error: {0}")]
    Header(#[from] reqwest::header::ToStrError),
}

struct PartialRangeIter {
    start: u64,
    end: u64,
    buffer_size: u32,
}

impl PartialRangeIter {
    pub fn new(start: u64, end: u64, buffer_size: u32) -> Result<Self, Error> {
        if buffer_size == 0 {
            Err(Error::General("invalid buffer_size, give a value greater than zero.".to_string()))?;
        }
        Ok(PartialRangeIter {
            start,
            end,
            buffer_size,
        })
    }
}

impl Iterator for PartialRangeIter {
    type Item = HeaderValue;
    fn next(&mut self) -> Option<Self::Item> {
        if self.start > self.end {
            None
        } else {
            let prev_start = self.start;
            self.start += std::cmp::min(self.buffer_size as u64, self.end - self.start + 1);
            Some(
                HeaderValue::from_str(&format!("bytes={}-{}", prev_start, self.start - 1))
                    .expect("string provided by format!"),
            )
        }
    }
}

pub fn main() -> Result<(), Error> {
    let url = "https://httpbin.org/range/102400?duration=2";
    const CHUNK_SIZE: u32 = 10240;

    let client = reqwest::blocking::Client::new();
    let response = client.head(url).send()?;
    let length = response
        .headers()
        .get(CONTENT_LENGTH)
        .ok_or(Error::General("response doesn't include the content length".to_string()))?;
    let length = u64::from_str(length.to_str()?).map_err(|_| Error::General("invalid Content-Length header".to_string()))?;

    let mut output_file = File::create("download.bin")?;

    println!("starting download...");
    for range in PartialRangeIter::new(0, length - 1, CHUNK_SIZE)? {
        println!("range {:?}", range);
        let mut response = client.get(url).header(RANGE, range).send()?;

        let status = response.status();
        if !(status == StatusCode::OK || status == StatusCode::PARTIAL_CONTENT) {
            let err = format!("Unexpected server response: {}", status);
            return Err(Error::General(err));
        }
        std::io::copy(&mut response, &mut output_file)?;
    }

    let content = response.text()?;
    std::io::copy(&mut content.as_bytes(), &mut output_file)?;

    println!("Finished with success!");
    Ok(())
}
