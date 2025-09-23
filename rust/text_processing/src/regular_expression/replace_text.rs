use lazy_static::lazy_static;

use std::borrow::Cow;
use regex::Regex;

fn reformat_dates<'a>(before: &'a str) -> Cow<'a, str> {
    lazy_static! {
        static ref ISO8601_DATE_REGEX : Regex = Regex::new(
            r"(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})"
            ).unwrap();
    }
    ISO8601_DATE_REGEX.replace_all(before, "$m/$d/$y")
}

pub fn main() {
    let before = "2012-03-14, 2013-01-15 and 2014-07-05";
    let after = reformat_dates(before);
    println!("Before: {}", before);
    println!("After:  {}", after);
}
