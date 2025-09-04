use env_logger::Builder;

pub fn new() {
    let mut builder = Builder::new();
    builder.parse_env("MY_APP_LOG").init();

    log::error!("this is an error {}", "message");
    log::warn!("warning message");
    log::info!("informational message");
    log::debug!("debug message");
}
