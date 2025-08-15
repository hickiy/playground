use std::fs::File;
use std::io::Error;
use flate2::Compression;
use flate2::write::GzEncoder;
use tar::Builder;

fn main() -> Result<(), Error> {
  let tar_gz = File::create("archive.tar.gz")?;
  let enc = GzEncoder::new(tar_gz, Compression::default());
  let mut tar = Builder::new(enc);
  tar.append_dir_all("archive_backup", "archive")?;
  Ok(())
}