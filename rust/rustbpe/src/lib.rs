use std::cmp::Ordering;
use std::collections::HashMap as StdHashMap;

use dary_heap::OctonaryHeap;
use fancy_regex::Regex;

use ahash::{AHashMap, AHashSet};
use compact_str::CompactString;
use rayon::prelude::*;

// 默认的 GPT-4 风格正则表达式模式，用于分割文本
const GPT4_PATTERN: &str = r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}+|\p{N}{1,3}| ?[^\s\p{L}\p{N}]++[\r\n]*|\s*[\r\n]|\s+(?!\S)|\s+";

type Pair = (u32, u32);

/// 一个匹配 GPT-4 风格实现的字节对编码 (BPE) 分词器
pub struct Tokenizer {
    /// 将 token ID 对映射到合并后的 token ID
    pub merges: StdHashMap<Pair, u32>,
    /// 用于文本分割的正则表达式模式
    pub pattern: String,
    /// 编译后的正则表达式，用于提高效率
    compiled_pattern: Regex,
}

// ------------------------ 内部辅助函数 ------------------------

#[derive(Clone, Debug)]
struct Word {
    ids: Vec<u32>,
}

impl Word {
    #[inline]
    fn new(ids: Vec<u32>) -> Self {
        Self { ids }
    }

    #[inline]
    fn pairs<'a>(&'a self) -> impl Iterator<Item = Pair> + 'a {
        self.ids.windows(2).map(|w| (w[0], w[1]))
    }

    /// 合并所有不重叠的 pair -> new_id 出现。
    /// 返回一个小的 Vec，包含仅针对此单词的本地 pair 计数变化：
    ///   -1 表示移除的 pair，+1 表示新创建的 pair。
    ///
    /// 注意：此版本故意避免在热循环中使用 HashMap。
    fn merge_pair(&mut self, pair: Pair, new_id: u32) -> Vec<(Pair, i32)> {
        let (a, b) = pair;
        let n = self.ids.len();
        if n < 2 {
            return Vec::new();
        }

        let mut out: Vec<u32> = Vec::with_capacity(n);
        let mut deltas: Vec<(Pair, i32)> = Vec::with_capacity(6);

        let mut i = 0;
        while i < n {
            if i + 1 < n && self.ids[i] == a && self.ids[i + 1] == b {
                let left = out.last().copied();
                let right = if i + 2 < n {
                    Some(self.ids[i + 2])
                } else {
                    None
                };

                // 移除旧的 pairs
                if let Some(x) = left {
                    deltas.push(((x, a), -1));
                    deltas.push(((x, new_id), 1));
                }
                deltas.push(((a, b), -1));
                if let Some(y) = right {
                    deltas.push(((b, y), -1));
                    deltas.push(((new_id, y), 1));
                }

                // 写入合并后的 token
                out.push(new_id);
                i += 2; // 跳过 'a' 和 'b'
            } else {
                out.push(self.ids[i]);
                i += 1;
            }
        }

        self.ids = out;
        deltas
    }
}

#[derive(Debug, Eq)]
struct MergeJob {
    pair: Pair,
    count: u64,
    /// 此 pair 可能出现并需要处理的单词索引集合
    pos: AHashSet<usize>,
}

impl PartialEq for MergeJob {
    fn eq(&self, other: &Self) -> bool {
        self.count == other.count && self.pair == other.pair
    }
}

impl PartialOrd for MergeJob {
    fn partial_cmp(&self, other: &Self) -> Option<Ordering> {
        Some(self.cmp(other))
    }
}

impl Ord for MergeJob {
    fn cmp(&self, other: &Self) -> Ordering {
        // 按 count 的最大堆；count 相同时按 pair 升序排列（确定性）
        if self.count != other.count {
            self.count.cmp(&other.count)
        } else {
            // count 相同时按 pair 升序
            other.pair.cmp(&self.pair)
        }
    }
}

#[inline]
fn count_pairs_parallel(
    words: &[Word],
    counts: &[i32],
) -> (AHashMap<Pair, i32>, AHashMap<Pair, AHashSet<usize>>) {
    words
        .par_iter()
        .enumerate()
        .map(|(i, w)| {
            let mut local_pc: AHashMap<Pair, i32> = AHashMap::new();
            let mut local_wtu: AHashMap<Pair, AHashSet<usize>> = AHashMap::new();
            if w.ids.len() >= 2 && counts[i] != 0 {
                for (a, b) in w.pairs() {
                    *local_pc.entry((a, b)).or_default() += counts[i];
                    local_wtu.entry((a, b)).or_default().insert(i);
                }
            }
            (local_pc, local_wtu)
        })
        .reduce(
            || (AHashMap::new(), AHashMap::new()),
            |(mut acc_pc, mut acc_wtu), (pc, wtu)| {
                for (k, v) in pc {
                    *acc_pc.entry(k).or_default() += v;
                }
                for (k, s) in wtu {
                    acc_wtu.entry(k).or_default().extend(s);
                }
                (acc_pc, acc_wtu)
            },
        )
}

// ------------------------ 结束辅助函数 ------------------------

impl Tokenizer {
    /// 给定唯一单词及其计数的核心增量 BPE 训练。
    /// `words`: 每个唯一块一个条目 (Vec<u32> 的 token-ids/bytes)。
    /// `counts`: 与 `words` 长度相同，每个块的计数。
    fn train_core_incremental(&mut self, mut words: Vec<Word>, counts: Vec<i32>, vocab_size: u32) {
        assert!(vocab_size >= 256, "vocab_size must be at least 256");
        let num_merges = vocab_size - 256;
        log::info!("开始 BPE 训练：需要计算 {} 次合并", num_merges);
        self.merges.clear();

        // ---- 初始 pair_counts 和 where_to_update（并行） ----
        log::info!("从 {} 个唯一序列计算初始 pair 计数", words.len());
        let (mut pair_counts, mut where_to_update) = count_pairs_parallel(&words, &counts);

        // ---- 构建堆 ----
        log::info!("使用 {} 个唯一 pair 构建堆", pair_counts.len());
        let mut heap = OctonaryHeap::with_capacity(pair_counts.len());
        for (pair, pos) in where_to_update.drain() {
            let c = *pair_counts.get(&pair).unwrap_or(&0);
            if c > 0 {
                heap.push(MergeJob {
                    pair,
                    count: c as u64,
                    pos,
                });
            }
        }

        // ---- 合并循环 ----
        log::info!("开始合并循环");
        let mut merges_done = 0u32;
        let mut last_log_percent = 0u32;

        while merges_done < num_merges {
            let Some(mut top) = heap.pop() else {
                break;
            };

            // 延迟刷新
            let current = *pair_counts.get(&top.pair).unwrap_or(&0);
            if top.count != current as u64 {
                top.count = current as u64;
                if top.count > 0 {
                    heap.push(top);
                }
                continue;
            }
            if top.count == 0 {
                break;
            }

            // 记录合并
            let new_id = 256 + merges_done;
            self.merges.insert(top.pair, new_id);

            // 在所有出现此 pair 的单词中合并
            let mut local_pos_updates: AHashMap<Pair, AHashSet<usize>> = AHashMap::new();
            for &word_idx in &top.pos {
                // 对此单词应用合并并收集 pair 计数变化
                let changes = words[word_idx].merge_pair(top.pair, new_id);
                // 根据此单词的计数更新全局 pair 计数
                for (pair, delta) in changes {
                    let delta_total = delta * counts[word_idx];
                    if delta_total != 0 {
                        *pair_counts.entry(pair).or_default() += delta_total;
                        if delta > 0 {
                            local_pos_updates.entry(pair).or_default().insert(word_idx);
                        }
                    }
                }
            }

            // 将更新后的 pair 计数添加回堆
            for (pair, pos) in local_pos_updates {
                let cnt = *pair_counts.get(&pair).unwrap_or(&0);
                if cnt > 0 {
                    heap.push(MergeJob {
                        pair,
                        count: cnt as u64,
                        pos,
                    });
                }
            }

            merges_done += 1;

            // 每 1% 记录进度
            let current_percent = (merges_done * 100) / num_merges;
            if current_percent > last_log_percent {
                log::info!(
                    "进度: {}% ({}/{} 次合并) - 最后一次合并: {:?} -> {} (频率: {})",
                    current_percent,
                    merges_done,
                    num_merges,
                    top.pair,
                    new_id,
                    top.count
                );
                last_log_percent = current_percent;
            }
        }

        log::info!("训练完成: 完成了 {} 次合并", merges_done);
    }
}

impl Default for Tokenizer {
    fn default() -> Self {
        Self::new()
    }
}

impl Tokenizer {
    /// 创建一个新的 Tokenizer
    pub fn new() -> Self {
        Self {
            merges: StdHashMap::new(),
            pattern: String::new(),
            compiled_pattern: Regex::new("").expect("Empty regex should be valid"),
        }
    }

    /// 从流式迭代器训练（并行摄入）。
    pub fn train_from_iterator(
        &mut self,
        iterator: impl Iterator<Item = String>,
        vocab_size: u32,
        pattern: Option<String>,
    ) -> Result<(), String> {
        // 使用提供的模式或默认使用 GPT-4 模式
        let pattern_str = pattern.unwrap_or_else(|| GPT4_PATTERN.to_string());

        // 更新存储的模式并编译它
        self.pattern = pattern_str.clone();
        self.compiled_pattern =
            Regex::new(&pattern_str).map_err(|e| format!("Invalid regex pattern: {}", e))?;

        // 全局块计数
        let mut counts: AHashMap<CompactString, i32> = AHashMap::new();

        log::info!("从迭代器处理序列");
        let mut total_sequences = 0u64;

        let pattern = self.compiled_pattern.clone();
        for s in iterator {
            total_sequences += 1;

            let local: AHashMap<CompactString, i32> = {
                let mut m: AHashMap<CompactString, i32> = AHashMap::new();
                for mat in pattern.find_iter(&s) {
                    let piece = mat.expect("regex match failed").as_str();
                    *m.entry(CompactString::from(piece)).or_default() += 1;
                }
                m
            };

            // 将本地合并到全局。
            for (k, v) in local {
                *counts.entry(k).or_default() += v;
            }
        }
        log::info!("共处理 {} 个序列，{} 个唯一", total_sequences, counts.len());

        // 实体化单词和计数
        let mut words = Vec::with_capacity(counts.len());
        let mut cvec = Vec::with_capacity(counts.len());
        for (chunk, c) in counts.into_iter() {
            words.push(Word::new(
                chunk.as_bytes().iter().map(|&b| b as u32).collect(),
            ));
            cvec.push(c);
        }

        self.train_core_incremental(words, cvec, vocab_size);
        Ok(())
    }

    /// 返回正则表达式模式
    pub fn get_pattern(&self) -> String {
        self.pattern.clone()
    }

    /// 返回可合并的 ranks (token bytes -> token id / rank)
    pub fn get_mergeable_ranks(&self) -> Vec<(Vec<u8>, u32)> {
        let mut mergeable_ranks = Vec::new();

        // 从低到高 token ID 增量构建词汇表
        let mut token_bytes: Vec<Vec<u8>> = (0..256_u32).map(|i| vec![i as u8]).collect();

        for (i, bytes) in token_bytes.iter().enumerate() {
            mergeable_ranks.push((bytes.clone(), i as u32));
        }

        // 按 token id 排序合并（这样我们可以逐步重建字节）
        let mut sorted_merges: Vec<_> = self.merges.iter().collect();
        sorted_merges.sort_by_key(|&(_, &token_id)| token_id);

        for (&pair, &merged_id) in sorted_merges {
            let (left, right) = pair;
            let mut merged_bytes = token_bytes[left as usize].clone();
            merged_bytes.extend(&token_bytes[right as usize]);

            if token_bytes.len() <= merged_id as usize {
                token_bytes.resize(merged_id as usize + 1, Vec::new());
            }
            token_bytes[merged_id as usize] = merged_bytes.clone();

            mergeable_ranks.push((merged_bytes, merged_id));
        }

        mergeable_ranks
    }

    /// 将字符串编码为 token ID
    pub fn encode(&self, text: &str) -> Vec<u32> {
        let mut all_ids = Vec::new();

        // 使用正则表达式模式分割文本
        for m in self.compiled_pattern.find_iter(text) {
            let chunk = m.expect("regex match failed").as_str();

            // 将块转换为字节然后转换为 u32 ID
            let mut ids: Vec<u32> = chunk.bytes().map(|b| b as u32).collect();

            // 迭代应用合并
            while ids.len() >= 2 {
                // 找到要合并的最佳 pair
                let mut best_pair: Option<(usize, Pair, u32)> = None;

                for i in 0..ids.len() - 1 {
                    let pair: Pair = (ids[i], ids[i + 1]);
                    if let Some(&new_id) = self.merges.get(&pair)
                        && (best_pair.is_none() || new_id < best_pair.unwrap().2)
                    {
                        best_pair = Some((i, pair, new_id));
                    }
                }

                // 如果找到要合并的 pair，应用它
                if let Some((idx, _pair, new_id)) = best_pair {
                    ids[idx] = new_id;
                    ids.remove(idx + 1);
                } else {
                    // 没有更多可以合并的
                    break;
                }
            }

            all_ids.extend(ids);
        }

        all_ids
    }
}
