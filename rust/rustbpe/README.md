# rustbpe

> 缺失的 tiktoken 训练代码

一个非常轻量级的 Rust 库，用于训练 GPT 分词器。问题在于推理库 [tiktoken](https://github.com/openai/tiktoken) 很出色，但只支持推理。另一方面，Huggingface 的 [tokenizers](https://github.com/huggingface/tokenizers) 库支持训练，但它过于臃肿且难以导航，因为它必须支持多年来人们处理分词器的各种历史遗留问题。最近，我还编写了 [minbpe](https://github.com/karpathy/minbpe) 库，它既能训练也能推理，但只能用低效的 Python 实现。基本上，我真正想要的是一个非花哨、超级简单但仍然相对高效的 GPT 分词器训练代码（比 minbpe 更高效，比 tokenizers 清晰/简单得多），然后导出训练好的词汇表供 tiktoken 推理使用。这样有道理吗？所以我们现在就有了这个项目。这里还有更多的优化机会，我之所以停下来是因为与之前的 minbpe 不同，rustbpe 现在已经足够简单和快速，不再是 nanochat 的重大瓶颈。
