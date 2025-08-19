use ring::digest::{Context, Digest, SHA256};
use std::fs::File;
use std::io::{BufReader, Error, Read};
use std::path::Path;
use std::sync::mpsc::channel;
use threadpool::ThreadPool;
use walkdir::WalkDir;

fn comput_digest<P: AsRef<Path>>(filepath: P) -> Result<(Digest, P), Error> {
    let mut buf_reader = BufReader::new(File::open(&filepath)?);
    let mut context = Context::new(&SHA256);
    let mut buffer = [0; 1024];

    loop {
        let count = buf_reader.read(&mut buffer)?;
        if count == 0 {
            break;
        }
        context.update(&buffer[..count]);
    }

    Ok((context.finish(), filepath))
}

pub fn new() {
    let pool = ThreadPool::new(num_cpus::get());
    let (tx, rx) = channel();

    for entry in WalkDir::new("./svg").into_iter().filter_map(|e| e.ok()) {
        let path = entry.path().to_owned();
        let tx = tx.clone();
        pool.execute(move || {
            let digest = comput_digest(path);
            tx.send(digest).expect("Could not send data!");
        });
    }

    drop(tx);

    for t in rx.iter() {
        if let Ok((sha, path)) = t {
            println!("{:?} {:?}", sha, path);
        }
    }
}
