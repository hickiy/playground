
fn execute_query(query: &str) {
    log::debug!("Executing query: {}", query.len());
}

pub fn new() {
    env_logger::init();

    execute_query("DROP TABLE students");
}
