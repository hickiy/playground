use thiserror::Error;
use serde::Deserialize;

use std::fmt;

#[derive(Error, Debug)]
pub enum MyError {
    #[error("CSV reader error: {0}")]
    Reader(#[from] csv::Error),
    #[error("Custom error: {0}")]
    Custom(String),
}

#[derive(Debug, Deserialize)]
struct Rgb {
    red: u8,
    blue: u8,
    green: u8,
}

impl Rgb {
    fn from_reader(csv_data: &[u8]) -> Result<Rgb, MyError> {
        let color: Rgb = csv::Reader::from_reader(csv_data)
            .deserialize()
            .nth(0)
            .ok_or_else(|| MyError::Custom("Cannot deserialize the first CSV record".to_string()))?
            .map_err(|e| MyError::Custom(format!("Cannot deserialize RGB color: {}", e)))?;

        Ok(color)
    }
}

impl fmt::UpperHex for Rgb {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        let hexa = u32::from(self.red) << 16 | u32::from(self.blue) << 8 | u32::from(self.green);
        write!(f, "{:X}", hexa)
    }
}

fn run() -> Result<(), MyError> {
    let csv = "red,blue,green
102,256,204";

    let rgb = Rgb::from_reader(csv.as_bytes()).map_err(|e| MyError::Custom(format!("Cannot read CSV data: {}", e)))?;
    println!("{:?} to hexadecimal #{:X}", rgb, rgb);

    Ok(())
}

pub fn new() {
    if let Err(error) = run() {
        // Print the error and its source chain
        let mut current_error: &dyn std::error::Error = &error;
        let mut level = 0;
        
        loop {
            eprintln!("└> {} - {}", level, current_error);
            
            if let Some(source) = current_error.source() {
                current_error = source;
                level += 1;
            } else {
                break;
            }
        }

        // Note: thiserror doesn't provide automatic backtrace like error_chain
        // You can enable backtrace by setting RUST_BACKTRACE=1 environment variable
        
        // In a real use case, errors should handled. For example:
        // ::std::process::exit(1);
    }
}
