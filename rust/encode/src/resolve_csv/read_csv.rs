use csv::Reader;
pub fn new() {
    let csv = "year,make,model,description\n1948,Porsche,356,Luxury sports car\n1967,Ford,Mustang fastback 1967,American car";

    let mut reader = Reader::from_reader(csv.as_bytes());
    for record in reader.records() {
        let record = record.unwrap();
        println!(
            "In {}, {} built the {} model. It is a {}.",
            &record[0], &record[1], &record[2], &record[3]
        );
    }
}
