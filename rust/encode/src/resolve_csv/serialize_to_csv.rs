pub fn new() {
    let mut wtr = csv::Writer::from_writer(vec![]);

    wtr.write_record(&["Name", "Place", "ID"]).unwrap();

    wtr.serialize(("Mark", "Sydney", 87)).unwrap();
    wtr.serialize(("Ashley", "Dublin", 32)).unwrap();
    wtr.serialize(("Akshat", "Delhi", 11)).unwrap();

    wtr.flush().unwrap();

    let data = String::from_utf8(wtr.into_inner().unwrap()).unwrap();
    println!("{}", data);
}
