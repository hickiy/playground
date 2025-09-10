use byteorder::{BigEndian, ReadBytesExt, WriteBytesExt};
use std::io::Error;

#[derive(Default, PartialEq, Debug)]
struct Payload {
    kind: u8,
    value: u16,
}

pub fn new() {
    let original_payload = Payload {
        kind: 255,
        value: 511,
    };
    let encoded_bytes = encode(&original_payload).unwrap();
    let decoded_payload = decode(&encoded_bytes).unwrap();
    println!("original: {:?}", original_payload);
    println!("encoded u8: {:08b}", encoded_bytes[0]);
    println!(
        "encoded u16: {:08b},{:08b}",
        encoded_bytes[1], encoded_bytes[2]
    );
    println!("decoded: {:?}", decoded_payload);
}

fn encode(payload: &Payload) -> Result<Vec<u8>, Error> {
    let mut bytes = vec![];
    bytes.write_u8(payload.kind)?;
    bytes.write_u16::<BigEndian>(payload.value)?;
    Ok(bytes)
}

fn decode(mut bytes: &[u8]) -> Result<Payload, Error> {
    let payload = Payload {
        kind: bytes.read_u8()?,
        value: bytes.read_u16::<BigEndian>()?,
    };
    Ok(payload)
}
