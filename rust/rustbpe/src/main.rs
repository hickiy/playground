use rustbpe::Tokenizer;
use std::fs;
use std::io::{self, BufRead};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 初始化日志
    env_logger::Builder::from_default_env()
        .filter_level(log::LevelFilter::Info)
        .init();

    // 读取 sample.txt 文件
    let file_path = "sample.txt";
    log::info!("开始从文件读取：{}", file_path);

    let file = fs::File::open(file_path)?;
    let reader = io::BufReader::new(file);

    // 创建 Tokenizer 实例
    let mut tokenizer = Tokenizer::new();

    // 从迭代器构建词表，设置目标词汇大小为 512
    let vocab_size = 512;
    log::info!("开始训练词表，目标词汇大小：{}", vocab_size);

    // 将 BufReader 转换为迭代器
    let iterator = reader.lines().map(|line| line.unwrap_or_default());
    tokenizer.train_from_iterator(iterator, vocab_size, None, false)?;

    log::info!("词表训练完成！");
    log::info!("词表大小：{}", tokenizer.get_mergeable_ranks().len());
    log::info!("正则表达式模式：{}", tokenizer.get_pattern());

    // 测试编码
    let test_text = "Hello world";
    let encoded = tokenizer.encode(test_text);
    log::info!("测试文本：'{}'", test_text);
    log::info!("编码结果：{:?}", encoded);

    Ok(())
}
