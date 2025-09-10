use serde::Deserialize;
use serde_json::from_str;

pub fn new() {
    #[derive(Deserialize, Debug)]
    struct User {
        userid: u64,
        verified: bool,
        access_privileges: Vec<String>,
    }

    impl std::fmt::Display for User {
        fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
            write!(f, "User {{\n")?;
            write!(f, "    userid: {},\n", self.userid)?;
            write!(f, "    verified: {},\n", self.verified)?;
            write!(f, "    access_privileges: [\n")?;
            for privilege in &self.access_privileges {
                write!(f, "        \"{}\",\n", privilege)?;
            }
            write!(f, "    ]\n")?;
            write!(f, "}}")
        }
    }

    let j = r#"{
                 "userid": 103609,
                 "verified": true,
                 "access_privileges": [
                   "user",
                   "admin"
                 ]
               }"#;

    let parsed: User = from_str(j).unwrap();
    println!("{}", parsed);
}
