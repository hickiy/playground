use semver::{Version, VersionReq};
use std::process::Command;

pub fn new() {
    let version_constraint: &'static str = "> 1.12.0";
    let version_test = VersionReq::parse(version_constraint).unwrap();
    let output = Command::new("git").arg("--version").output().unwrap();

    let stdout = String::from_utf8(output.stdout).unwrap();
    let version = stdout.split(" ").last().ok_or_else(|| "Invalid command output").unwrap();
    let parsed_version = Version::parse(&version[..6]).unwrap();

    if version_test.matches(&parsed_version) {
      println!("Version matches the constraint");
    } else {
      println!("Version does not match the constraint");
    }
}
