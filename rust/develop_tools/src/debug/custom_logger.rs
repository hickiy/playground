use log::{Level, LevelFilter, Metadata, Record};

static CONSOLE_LOGGER: ConsoleLogger = ConsoleLogger;

struct ConsoleLogger;

impl log::Log for ConsoleLogger {
    fn enabled(&self, metadata: &Metadata) -> bool {
        metadata.level() <= Level::Info
    }

    fn log(&self, record: &Record) {
        if self.enabled(record.metadata()) {
            println!("Rust says: {} - {}", record.level(), record.args());
        }
    }

    fn flush(&self) {}
}

pub fn new() {
    log::set_logger(&CONSOLE_LOGGER).unwrap();
    log::set_max_level(LevelFilter::Info);

    log::info!("hello log");
    log::warn!("warning");
    log::error!("oops");
}
