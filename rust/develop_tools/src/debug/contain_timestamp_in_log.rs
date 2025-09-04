use chrono::Local;
use env_logger::Builder;
use log::LevelFilter;
use std::io::Write;
pub fn new() {
    Builder::new()
        .format(|buf, record| {
            let color = match record.level() {
                log::Level::Error => "\x1b[31m", // 红色
                log::Level::Warn => "\x1b[33m",  // 黄色
                log::Level::Info => "\x1b[32m",  // 绿色
                log::Level::Debug => "\x1b[34m", // 蓝色
                _ => "\x1b[0m",                  // 重置
            };
            writeln!(
                buf,
                "{} {}[{}]\x1b[0m - {}",
                Local::now().format("%Y-%m-%dT%H:%M:%S"),
                color,
                record.level(),
                record.args()
            )
        })
        .filter(None, LevelFilter::Debug)
        .init();
    
    log::error!("error");
    log::warn!("warn");
    log::info!("info");
    log::debug!("debug");
}
