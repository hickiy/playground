pub fn new() {
    let query = "CA";
    let data = "\
City,State,Population,Latitude,Longitude
Kenai,AK,7610,60.5544444,-151.2583333
Oakman,AL,,33.7133333,-87.3886111
Sandfort,AL,,32.3380556,-85.2233333
West Hollywood,CA,37031,34.0900000,-118.3608333";

    let mut rdr = csv::ReaderBuilder::new().from_reader(data.as_bytes());
    let mut wtr = csv::Writer::from_writer(vec![]);

    wtr.write_record(rdr.headers().unwrap()).unwrap();

    for result in rdr.records() {
        let record = result.unwrap();
        if record.iter().any(|field| field == query) {
            wtr.write_record(&record).unwrap();
        }
    }
    wtr.flush().unwrap();

    let data = String::from_utf8(wtr.into_inner().unwrap()).unwrap();
    println!("{}", data);
}
