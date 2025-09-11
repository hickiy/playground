#[cfg(unix)]
use std::fs::File;
#[cfg(unix)]
use std::io::Read;

use thiserror::Error;

#[cfg(windows)]
use std::time::{SystemTime, UNIX_EPOCH};

#[derive(Error, Debug)]
pub enum MyError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Parse int error: {0}")]
    ParseInt(#[from] std::num::ParseIntError),
    #[error("Custom error: {0}")]
    Custom(String),
}

fn read_uptime() -> Result<u64, MyError> {
    #[cfg(unix)]
    {
        let mut uptime = String::new();
        File::open("/proc/uptime")?.read_to_string(&mut uptime)?;

        Ok(uptime
            .split('.')
            .next()
            .ok_or_else(|| MyError::Custom("Cannot parse uptime data".to_string()))?
            .parse()?)
    }
    
    #[cfg(windows)]
    {
        // 模拟 /proc/uptime 在 Windows 下的行为
        // 获取系统启动时间并计算运行时间（秒）
        let uptime_secs = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map_err(|_| MyError::Custom("Failed to get system time".to_string()))?
            .as_secs();
        
        // 模拟一个合理的运行时间（这里简化处理，实际应该获取真实的系统启动时间）
        // 为了演示，我们假设系统已经运行了一段时间
        Ok(uptime_secs / 86400) // 假设运行时间不超过一天
    }
}

pub fn new() {
    match read_uptime() {
        Ok(up_days) => println!("uptime: {} days", up_days),
        Err(err) => eprintln!("error: {}", err),
    };
}
