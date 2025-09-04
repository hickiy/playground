use semver::Version;

pub fn new() {
    let version_1 = Version::parse("1.0.0-alpha").unwrap();
    let version_2 = Version::parse("1.0.0").unwrap();

    assert_eq!(version_1.pre.to_string(), "alpha");
    assert_eq!(version_2.pre.to_string(), "");
}
