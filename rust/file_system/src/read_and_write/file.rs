use same_file::Handle;
use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

pub fn new() {
    let path_to_read = Path::new("lines.txt");

    let stdout_handle = Handle::stdout().unwrap();
    let handle = Handle::from_path(path_to_read).unwrap();

    if stdout_handle == handle {
        println!("You are reading and writing to the same file");
    } else {
        let file = File::open(&path_to_read).unwrap();
        let file = BufReader::new(file);
        for (num, line) in file.lines().enumerate() {
            println!("{} : {}", num, line.unwrap().to_uppercase());
        }
    }
}
