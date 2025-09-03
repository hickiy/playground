#[cfg(target_os = "linux")]
#[cfg(target_os = "linux")]
use syslog::{Facility, Error};

#[cfg(target_os = "linux")]
pub fn new() -> Result<(), Error> {
    syslog::init(Facility::LOG_USER,
                 log::LevelFilter::Debug,
                 Some("My app name"))?;
    log::debug!("this is a debug {}", "message");
    log::error!("this is an error!");
    Ok(())
}

#[cfg(not(target_os = "linux"))]
pub fn new() {
    println!("So far, only Linux systems are supported.");
}
