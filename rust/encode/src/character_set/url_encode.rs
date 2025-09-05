use percent_encoding::{AsciiSet, CONTROLS, percent_decode, utf8_percent_encode};

const FRAGMENT: &AsciiSet = &CONTROLS.add(b' ').add(b'"').add(b'<').add(b'>').add(b'`');

pub fn new() {
    let input = "confident, productive systems programming";

    let iter = utf8_percent_encode(input, FRAGMENT);
    let encoded: String = iter.collect();
    assert_eq!(encoded, "confident,%20productive%20systems%20programming");

    let iter = percent_decode(encoded.as_bytes());
    let decoded = iter.decode_utf8().unwrap();
    assert_eq!(decoded, "confident, productive systems programming");
}
