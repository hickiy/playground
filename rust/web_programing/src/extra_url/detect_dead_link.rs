use reqwest::StatusCode;
use select::document::Document;
use select::predicate::Name;
use std::collections::HashSet;
use thiserror::Error;
use url::{Position, Url};

#[derive(Error, Debug)]
pub enum DetectDeadLinkError {
    #[error("URL parsing error: {0}")]
    UrlParse(#[from] url::ParseError),
    
    #[error("HTTP request error: {0}")]
    Request(#[from] reqwest::Error),
    
    #[error("Task join error: {0}")]
    TaskJoin(#[from] tokio::task::JoinError),
    
    #[error("Link checking failed for URL: {url}")]
    LinkCheckFailed { url: String },
    
    #[error("Base URL extraction failed")]
    BaseUrlExtraction,
}

type Result<T> = std::result::Result<T, DetectDeadLinkError>;


async fn get_base_url(url: &Url, doc: &Document) -> Result<Url> {
    let base_tag_href = doc.find(Name("base")).filter_map(|n| n.attr("href")).nth(0);
    let base_url = match base_tag_href {
        Some(href) => Url::parse(href)?,
        None => Url::parse(&url[..Position::BeforePath])?,
    };
    Ok(base_url)
}

async fn check_link(url: &Url) -> Result<bool> {
    let res = reqwest::get(url.as_ref()).await?;
    Ok(res.status() != StatusCode::NOT_FOUND)
}

#[tokio::main]
pub async fn main() -> Result<()> {
    let url = Url::parse("https://www.rust-lang.org/en-US/")?;
    let res = reqwest::get(url.as_ref()).await?.text().await?;
    let document = Document::from(res.as_str());
    let base_url = get_base_url(&url, &document).await?;
    let base_parser = Url::options().base_url(Some(&base_url));
    
    let links: HashSet<Url> = document
        .find(Name("a"))
        .filter_map(|n| n.attr("href"))
        .filter_map(|link| base_parser.parse(link).ok())
        .collect();
    
    let mut tasks = vec![];

    for link in links {
        tasks.push(tokio::spawn(async move {
            match check_link(&link).await {
                Ok(true) => println!("{} is OK", link),
                Ok(false) => println!("{} is Broken", link),
                Err(e) => eprintln!("Error checking {}: {}", link, e),
            }
        }));
    }

    for task in tasks {
        task.await?;
    }

    Ok(())
}
