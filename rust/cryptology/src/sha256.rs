use data_encoding::HEXUPPER;
use ring::digest::{Context, Digest, SHA256};
use std::fs::File;
use std::io::{BufReader, Read};

fn sha256_digest<R: Read>(mut reader: R) -> Digest {
    let mut context = Context::new(&SHA256);
    let mut buffer = [0; 1024];
    loop {
        let count = reader.read(&mut buffer).unwrap();
        if count == 0 {
            break;
        }
        context.update(&buffer[..count]);
    }
    context.finish()
}

pub fn new() {
    let path = "电子发票.pdf";

    let input = File::open(path).unwrap();
    let reader = BufReader::new(input);
    let digest = sha256_digest(reader);

    println!("SHA-256 digest is {}", HEXUPPER.encode(digest.as_ref()));
}
