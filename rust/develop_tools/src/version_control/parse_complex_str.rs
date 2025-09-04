use semver::{BuildMetadata, Prerelease, Version};

pub fn new() {
    let version_str = "1.0.49-125+g72ee7853";
    let parsed_version = Version::parse(version_str).unwrap();

    assert_eq!(
        parsed_version,
        Version {
            major: 1,
            minor: 0,
            patch: 49,
            pre: Prerelease::new("125").unwrap(),
            build: BuildMetadata::new("g72ee7853").unwrap(),
        }
    );
    assert_eq!(
        parsed_version.build,
        BuildMetadata::new("g72ee7853").unwrap()
    );

    let serialized_version = parsed_version.to_string();
    assert_eq!(&serialized_version, version_str);
}
