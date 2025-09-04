use semver::{Version, Prerelease, BuildMetadata};

pub fn new() {
    let mut parsed_version = Version::parse("0.2.6").unwrap();

    assert_eq!(
        parsed_version,
        Version {
            major: 0,
            minor: 2,
            patch: 6,
            pre: Prerelease::EMPTY,
            build: BuildMetadata::EMPTY,
        }
    );

    // 手动递增 patch
    parsed_version.patch += 1;
    assert_eq!(parsed_version.to_string(), "0.2.7");
    println!("New patch release: v{}", parsed_version);

    // 手动递增 minor，重置 patch
    parsed_version.patch = 0;
    parsed_version.minor += 1;
    assert_eq!(parsed_version.to_string(), "0.3.0");
    println!("New minor release: v{}", parsed_version);

    // 手动递增 major，重置 minor 和 patch
    parsed_version.patch = 0;
    parsed_version.minor = 0;
    parsed_version.major += 1;
    assert_eq!(parsed_version.to_string(), "1.0.0");
    println!("New major release: v{}", parsed_version);
}