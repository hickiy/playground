use std::env;
use std::fs;
use std::io::Error;

pub fn main() -> Result<(), Error> {
    // 从环境变量 `CONFIG` 读取配置路径 `config_path`。
    // 如果 `CONFIG` 未设置，采用默认配置路径。
    let config_path = env::var("CONFIG")
        .unwrap_or("/etc/hosts".to_string());

    let config: String = fs::read_to_string(config_path)?;
    println!("Config: {}", config);

    Ok(())
}
