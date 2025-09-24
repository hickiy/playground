use thiserror::Error;
use std::io::copy;
use std::fs::File;

#[derive(Error, Debug)]
pub enum DownloadError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("HTTP request error: {0}")]
    HttpRequest(#[from] reqwest::Error),
}

#[tokio::main]
pub async fn main() -> Result<(), DownloadError> {
    let target = "https://www.rust-lang.org/logos/rust-logo-512x512.png";
    let response = reqwest::get(target).await?;

    let mut dest = {
        let fname = response
            .url()
            .path_segments()
            .and_then(|segments| segments.last())
            .and_then(|name| if name.is_empty() { None } else { Some(name) })
            .unwrap_or("tmp.bin");

        println!("file to download: '{}'", fname);
        
        // 获取项目根目录路径
        let project_root = std::env::current_dir()?;
        let file_path = project_root.join(fname);
        
        println!("will be located under: '{:?}'", file_path);
        File::create(file_path)?
    };
    let content = response.bytes().await?;
    copy(&mut content.as_ref(), &mut dest)?;
    Ok(())
}
