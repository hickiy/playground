
use env_logger::{Builder, Target};

pub fn new() {
    Builder::new()
        .target(Target::Stdout)
        .init();

    log::error!("This error has been printed to Stdout");
}
