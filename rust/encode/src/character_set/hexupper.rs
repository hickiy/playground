use data_encoding::{HEXUPPER};

pub fn new() {
    let original = b"The quick brown fox jumps over the lazy dog.";
    let expected = "54686520717569636B2062726F776E20666F78206A756D7073206F76\
        657220746865206C617A7920646F672E";

    println!("ASCLL code for T is {}, and it's hex code is {}", original[0], &expected[0..2]);    

    let encoded = HEXUPPER.encode(original);
    assert_eq!(encoded, expected);

    let decoded = HEXUPPER.decode(&encoded.into_bytes()).unwrap();
    assert_eq!(&decoded[..], &original[..]);
}
