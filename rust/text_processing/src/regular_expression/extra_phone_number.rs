use regex::Regex;
use std::fmt;

struct PhoneNumber<'a> {
    area: &'a str,
    exchange: &'a str,
    subscriber: &'a str,
}

impl<'a> fmt::Display for PhoneNumber<'a> {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        write!(f, "1 ({}) {}-{}", self.area, self.exchange, self.subscriber)
    }
}

pub fn main() {
    let phone_text = "
    +1 505 881 9292 (v) +1 505 778 2212 (c) +1 505 881 9297 (f)
    (202) 991 9534
    Alex 5553920011
    1 (800) 233-2010
    1.299.339.1020";

    let re = Regex::new(
        r#"(?x)
          (?:\+?1)?                       # 国家代码，可选项
          [\s\.]?
          (([2-9]\d{2})|\(([2-9]\d{2})\)) # 地区代码
          [\s\.\-]?
          ([2-9]\d{2})                    # 交换代码
          [\s\.\-]?
          (\d{4})                         # 用户号码"#,
    )
    .unwrap();

    let phone_numbers = re.captures_iter(phone_text).filter_map(|cap| {
        let groups = (cap.get(2).or(cap.get(3)), cap.get(4), cap.get(5));
        match groups {
            (Some(area), Some(ext), Some(sub)) => Some(PhoneNumber {
                area: area.as_str(),
                exchange: ext.as_str(),
                subscriber: sub.as_str(),
            }),
            _ => None,
        }
    });

    println!(
        "Extracted phone numbers: {:?}",
        phone_numbers.map(|m| m.to_string()).collect::<Vec<_>>()
    );
}
