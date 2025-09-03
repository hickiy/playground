use chrono::{DateTime, FixedOffset, Local, Utc};

pub fn new() {
    let local_time = Local::now();
    let utc_time = DateTime::<Utc>::from_naive_utc_and_offset(local_time.naive_utc(), Utc);
    let china_timezone = FixedOffset::east_opt(8 * 3600).unwrap();
    let rio_timezone = FixedOffset::west_opt(2 * 3600).unwrap();
    println!("Local time now is {}", local_time);
    println!("UTC time now is {}", utc_time);
    println!("Time in Hong Kong now is {}", utc_time.with_timezone(&china_timezone));
    println!("Time in Rio de Janeiro now is {}", utc_time.with_timezone(&rio_timezone));
}
