use thiserror::Error;

#[derive(Error, Debug)]
pub enum MyError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),
    #[error("Reqwest error: {0}")]
    Reqwest(#[from] reqwest::Error),
    #[error("Parse int error: {0}")]
    ParseIntError(#[from] std::num::ParseIntError),
    #[error("Random response error: {0}")]
    RandomResponseError(String),
}

fn parse_response(response: reqwest::blocking::Response) -> Result<u32, MyError> {
  let mut body = response.text()?;
  body.pop();
  body
    .parse::<u32>()
    .map_err(|_| MyError::RandomResponseError(body))
}

fn run() -> Result<(), MyError> {
  let url =
    format!("https://www.random.org/integers/?num=1&min=0&max=10&col=1&base=10&format=plain");
  let response = reqwest::blocking::get(&url)?;
  let random_value: u32 = parse_response(response)?;
  println!("a random number between 0 and 10: {}", random_value);
  Ok(())
}

pub fn new() {
  if let Err(error) = run() {
    match error {
      MyError::Io(_) => println!("Standard IO error: {:?}", error),
      MyError::Reqwest(_) => println!("Reqwest error: {:?}", error),
      MyError::ParseIntError(_) => println!("Standard parse int error: {:?}", error),
      MyError::RandomResponseError(_) => println!("User defined error: {:?}", error),
    }
  }
}
