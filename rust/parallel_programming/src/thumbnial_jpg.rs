use image::imageops::FilterType;
use rayon::prelude::*;
use std::fs::{create_dir_all, read_dir};
use std::path::Path;

fn make_thumbnail<PA, PB>(original: PA, thumb_dir: PB, longest_edge: u32)
where
    PA: AsRef<Path>,
    PB: AsRef<Path>,
{
    let img = image::open(original.as_ref()).unwrap();
    // 获取原图文件名
    let filename = original.as_ref().file_name().unwrap();
    // 拼接缩略图完整路径
    let file_path = thumb_dir.as_ref().join(filename);
    // 保存缩略图
    img.resize(longest_edge, longest_edge, FilterType::Nearest)
        .save(file_path)
        .unwrap();
}

pub fn new() {
    let files: Vec<_> = read_dir("./image")
        .unwrap()
        .filter_map(|entry| {
            let entry = entry.ok()?;
            let path = entry.path();
            if path
                .extension()
                .and_then(|s| s.to_str())
                .map_or(false, |ext| ext.eq_ignore_ascii_case("jpg"))
            {
                Some(path)
            } else {
                None
            }
        })
        .collect();
    let thumbnails = "./thumbnials";
    create_dir_all(thumbnails).unwrap();
    files
        .par_iter()
        .for_each(|path| make_thumbnail(path, thumbnails, 300));

    println!("{} thumbnails saved successfully", files.len());
}
