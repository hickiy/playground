use same_file::is_same_file;
use std::io;
use std::path::{Path, PathBuf};

fn contains_loop<P: AsRef<Path>>(path: P) -> io::Result<Option<(PathBuf, PathBuf)>> {
    let path = path.as_ref();
    let mut path_buf = path.to_path_buf();
    while path_buf.pop() {
        if is_same_file(&path_buf, path)? {
            return Ok(Some((path_buf, path.to_path_buf())));
        }
    }
    return Ok(None);
}

pub fn new() {
    println!("{:?}", contains_loop("tmp/foo/qux/bar").unwrap());
}
