use memmap::Mmap;
use std::fs::File;
use std::io::Write;

pub fn new() {
    write!(
        File::create("content.txt").unwrap(),
        "My hovercraft is full of eels!"
    )
    .unwrap();

    let file = File::open("content.txt").unwrap();
    let map = unsafe { Mmap::map(&file).unwrap() };

    let random_indexes = (0..30).collect::<Vec<_>>();
    let random_bytes: Vec<u8> = random_indexes.iter().map(|&idx| map[idx]).collect();
    let s = String::from_utf8(random_bytes).unwrap();
    println!("{}", s);
}
