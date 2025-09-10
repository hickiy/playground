use serde::Deserialize;
use std::collections::HashMap;

#[derive(Deserialize)]
struct Config {
    package: Package,
    dependencies: HashMap<String, String>,
}

#[derive(Deserialize)]
struct Package {
    name: String,
    version: String,
    authors: Vec<String>,
}

pub fn new() {
    let toml_content = r#"
          [package]
          name = "your_package"
          version = "0.1.0"
          authors = ["You! <you@example.org>"]

          [dependencies]
          serde = "1.0"
          "#;

    let package_info: Config = toml::from_str(toml_content).unwrap();
    println!("{}", package_info.package.name);
    println!("{}", package_info.package.version);
    println!("{}", package_info.package.authors[0]);
    package_info.dependencies.iter().for_each(|(k, v)| {
        println!("{}: {}", k, v);
    });
}
