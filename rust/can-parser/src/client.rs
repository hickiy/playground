use anyhow::Result;
use tokio::net::TcpStream;
use tokio::io::{AsyncBufReadExt, AsyncWriteExt, BufReader};
use std::io;

#[tokio::main]
async fn main() -> Result<()> {
    println!("CAN Parser Client");
    println!("Connecting to server...");
    
    let stream = TcpStream::connect("127.0.0.1:8080").await?;
    println!("Connected to CAN Parser Service");
    
    let (reader, mut writer) = stream.into_split();
    let mut buf_reader = BufReader::new(reader);
    let mut response = String::new();
    
    // 读取欢迎消息
    buf_reader.read_line(&mut response).await?;
    print!("{}", response);
    
    loop {
        // 读取用户输入
        let mut input = String::new();
        io::stdin().read_line(&mut input)?;
        
        // 发送到服务器
        writer.write_all(input.as_bytes()).await?;
        
        if input.trim().eq_ignore_ascii_case("quit") || input.trim().eq_ignore_ascii_case("exit") {
            break;
        }
        
        // 读取服务器响应
        response.clear();
        loop {
            let mut line = String::new();
            buf_reader.read_line(&mut line).await?;
            response.push_str(&line);
            
            if line.trim().ends_with(">") {
                break;
            }
        }
        
        print!("{}", response);
    }
    
    println!("Disconnected from server");
    Ok(())
}
