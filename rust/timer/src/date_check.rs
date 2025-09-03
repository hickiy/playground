use chrono::{DateTime, Duration, Utc};

fn day_earlier(date_time: DateTime<Utc>) -> Option<DateTime<Utc>> {
    date_time.checked_sub_signed(Duration::days(1))
}

pub fn new() {
    let now = Utc::now();
    println!("{}", now);

    let almost_three_weeks_from_now = now
        .checked_add_signed(Duration::weeks(2))
        .and_then(|in_2weeks| in_2weeks.checked_add_signed(Duration::weeks(1)))
        .and_then(day_earlier);

    match almost_three_weeks_from_now {
        Some(x) => println!("{}", x),
        None => eprintln!("Almost three weeks from now overflows"),
    }

    match now.checked_add_signed(Duration::MAX) {
        Some(x) => println!("{}", x),
        None => eprintln!(
            "We can't use chorno to tell the time for the solar system to complete more then one full orbit around the galactic center."
        ),
    }
}
