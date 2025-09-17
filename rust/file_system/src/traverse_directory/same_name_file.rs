use std::collections::HashMap;
use walkdir::WalkDir;

pub fn new() {
    let mut filenames = HashMap::new();

    for entry in WalkDir::new("tmp")
        .into_iter()
        .filter_map(Result::ok)
        .filter(|e| !e.file_type().is_dir())
    {
        let f_name = String::from(entry.file_name().to_string_lossy());
        let counter = filenames.entry(f_name.clone()).or_insert(0);
        *counter += 1;

        println!("{}, {}", f_name, counter);
    }
}
