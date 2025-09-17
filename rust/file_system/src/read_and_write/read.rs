use std::fs::File;
use std::io::{BufRead, BufReader, Write};

pub fn new() {
    let path = "lines.txt";

    let mut output = File::create(path).unwrap();
    write!(output, "Rust\n💖\nFun").unwrap();

    let input = File::open(path).unwrap();
    let buffered = BufReader::new(input);

    for line in buffered.lines() {
        println!("{}", line.unwrap());
    }
}
