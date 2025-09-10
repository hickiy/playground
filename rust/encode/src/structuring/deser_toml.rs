use toml::{Value};

pub fn new()  {
    let toml_content = r#"
          [package]
          name = "your_package"
          version = "0.1.0"
          authors = ["You! <you@example.org>"]

          [dependencies]
          serde = "1.0"
          "#;

    let package_info: Value = toml::from_str(toml_content).unwrap();
    println!("{}", package_info["package"]["name"]);
    println!("{}", package_info["package"]["version"]);
    println!("{}", package_info["package"]["authors"][0]);
    println!("{}", package_info["dependencies"]["serde"]);
}
