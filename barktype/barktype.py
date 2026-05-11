"""barktype CLI -- 台灣 狗叫聲 voice signal 分類 (FFT + autocorrelation + kNN).

Usage:
    python3 barktype.py --data samples/bark_dataset.json --no-ai

If --wav is given, runs the full real-audio FFT pipeline on that WAV file
and uses the extracted features as the query.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import wave
from pathlib import Path

from voice import (
    BarkFeatures, extract_features_from_signal, knn_predict,
    fit_feature_scales, synthesise_bark,
    KNNPrediction,
)


CLASS_DESCRIPTIONS: dict[str, dict[str, str]] = {
    "警戒吠叫": {
        "emoji": "🚨",
        "context": "陌生人 / 陌生狗 / 噪音 接近, 狗在保護領域",
        "owner_action": "確認沒安全威脅後, 用「不可以」短指令 + 把狗帶離視野點 30 秒",
        "do_not": "不要安撫 (會強化反應), 不要對狗大叫 (狗以為你也加入警戒)",
    },
    "焦慮孤獨": {
        "emoji": "😟",
        "context": "分離焦慮 / 主人剛離開 / 長時間獨處",
        "owner_action": "出門前 5 分鐘冷處理 + 留嗅聞玩具 / Kong 填食 + 慢慢延長獨處時間",
        "do_not": "不要回家立刻熱情打招呼 (強化『主人回來=超興奮』循環)",
    },
    "玩耍興奮": {
        "emoji": "🎾",
        "context": "看到主人 / 同伴狗 / 玩具, 興奮邀玩",
        "owner_action": "看狀況回應 (互動 / 散步), 或用「等等」訓練 impulse control",
        "do_not": "若處在公共場合要管理 (對其他狗 / 人會嚇到)",
    },
    "痛苦不適": {
        "emoji": "🏥",
        "context": "受傷 / 慢性疼痛 / 內臟不適 / 老年退化",
        "owner_action": "**24 小時內就醫**;檢查觸碰反應、進食、排便、走路姿勢",
        "do_not": "不要強迫吃藥 (人類止痛藥對狗多半毒);不要拖延以為「過幾天就好」",
    },
}


def load_data(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def read_wav_file(path: Path) -> tuple[list[float], int]:
    """Read mono 16-bit PCM WAV using stdlib `wave` module."""
    with wave.open(str(path), "rb") as w:
        n_channels = w.getnchannels()
        sample_width = w.getsampwidth()
        sample_rate = w.getframerate()
        n_frames = w.getnframes()
        raw = w.readframes(n_frames)
    import struct
    if sample_width == 2:
        fmt = f"<{n_frames * n_channels}h"
        samples = list(struct.unpack(fmt, raw))
        # Normalise to [-1, 1]
        samples = [s / 32768.0 for s in samples]
    elif sample_width == 1:
        fmt = f"<{n_frames * n_channels}B"
        samples = list(struct.unpack(fmt, raw))
        samples = [(s - 128) / 128.0 for s in samples]
    else:
        raise ValueError(f"unsupported sample width: {sample_width}")
    if n_channels == 2:
        samples = [(samples[i] + samples[i + 1]) / 2.0 for i in range(0, len(samples), 2)]
    return samples, sample_rate


def render_no_ai(data: dict, pred: KNNPrediction,
                  query_features: BarkFeatures, training_count: int) -> str:
    winner = pred.predicted_class
    advice = CLASS_DESCRIPTIONS.get(winner, {})
    emoji = advice.get("emoji", "🐕")

    lines = [
        f"# barktype -- 台灣 狗叫聲 voice signal 分類",
        "",
        f"**訓練樣本**: {training_count} 個 bark (10 個 × 4 類)",
        f"**Feature pipeline**: Cooley-Tukey FFT + 自相關 pitch 偵測 + RMS 能量 + 頻譜質心 + 過零率 + 頻譜 rolloff",
        f"**Classifier**: kNN (k=3) with per-feature stdev normalisation",
        "",
        "## 🎤 查詢 bark features (從 WAV / 預抽取)",
        "",
        f"_{data.get('query', {}).get('_meta', '')}_",
        "",
        "| Feature | 值 | 物理意義 |",
        "|---|---|---|",
        f"| pitch_mean_hz | {query_features.pitch_mean_hz:.1f} | 主頻 (越高 = 越尖) |",
        f"| pitch_std_hz | {query_features.pitch_std_hz:.1f} | pitch 變化 (越大 = 越多變) |",
        f"| duration_ms | {query_features.duration_ms:.0f} | 整段長度 |",
        f"| energy_mean | {query_features.energy_mean:.3f} | RMS 平均能量 |",
        f"| spectral_centroid_hz | {query_features.spectral_centroid_hz:.0f} | 頻譜「重心」 |",
        f"| zero_crossing_rate | {query_features.zero_crossing_rate:.3f} | 過零率 (越大 = 越雜) |",
        f"| bark_rate_per_sec | {query_features.bark_rate_per_sec:.2f} | 每秒爆發數 |",
        f"| spectral_rolloff_hz | {query_features.spectral_rolloff_hz:.0f} | 85% 能量截止 |",
        "",
        f"## {emoji} kNN 預測 (k=3)",
        "",
        f"### **{winner}** (信心 {pred.confidence:.0%})",
        "",
        f"- **常見情境**: {advice.get('context', '')}",
        f"- **飼主可做**: {advice.get('owner_action', '')}",
        f"- **不要做**: {advice.get('do_not', '')}",
        "",
        "## 🗳️ Vote 分布",
        "",
        "| 類別 | 票數 | 視覺 |",
        "|---|---|---|",
    ]
    for cls, n in sorted(pred.vote_counts.items(), key=lambda kv: -kv[1]):
        bar = "█" * (n * 5)
        marker = "⭐" if cls == winner else "  "
        lines.append(f"| {marker} {cls} | {n} | `{bar}` |")

    lines.extend([
        "",
        "## 🔍 Top 5 訓練樣本 (按 normalised Euclidean distance)",
        "",
        "| Rank | 類別 | 距離 |",
        "|---|---|---|",
    ])
    for i, (lab, d) in enumerate(pred.distances[:5]):
        lines.append(f"| #{i + 1} | {lab} | {d:.3f} |")

    lines.extend([
        "",
        "## ⚠️ Voice signal + kNN 模型假設與限制",
        "",
        "- **FFT 假設 stationarity**: 單一 FFT 假設信號頻譜在 window 內穩定; 真實叫聲頻譜會變動, Pro 版用 STFT (Short-Time FFT)",
        "- **自相關 pitch 對噪音敏感**: 環境噪音大 (車流 / 風) 時 pitch 估計失準; Pro 版加 cepstral pitch detection",
        "- **kNN 對 feature scale 敏感**: 已用 per-feature stdev 正規化, 但若新資料分布變動需重訓",
        "- **訓練樣本不大**: prototype 40 件, real launch 需 ≥ 500 件 各品種 (柴犬 / 黃金 / 米克斯 / 貴賓 / 馬爾濟斯 / 比熊 / 邊牧)",
        "- **品種差異大**: 中大型犬基頻 200-400 Hz / 小型犬 600-1200 Hz, prototype 沒分品種, Pro 版加品種 feature",
        "- **不取代獸醫 / 訓練師**: 工具給「分流參考」, 痛苦不適 / 嚴重焦慮 仍需專業評估; 連續吠叫 > 30 分 → 24h 內看獸醫",
        "- **個別狗差異**: 有些狗一輩子只用 1-2 種叫聲, 模型對「沉默型」「碎念型」極端狗準確度差",
        "- **隱私敏感**: 音訊資料涉個人空間, 本地版完全在設備不上傳; 雲端版需加密 + 用戶同意",
        "",
        "---",
        "*barktype = Cooley-Tukey FFT + 自相關 pitch 偵測 + kNN × 台灣 狗叫聲 voice signal 分類 niche = "
        "純函式 FFT 抽取 8 個 voice features (pitch / energy / centroid / ZCR / rolloff / bark_rate / duration / std), "
        "kNN 從 40+ 個訓練 bark 學「警戒 / 焦慮 / 玩耍 / 痛苦」4 類分類, "
        "飼主拿到「我家狗為什麼叫」客觀建議 + 飼主動作 SOP + 紅旗 24h 就醫。*",
    ])
    return "\n".join(lines)


def render_with_ai(data, pred, query_features, training_count):
    try:
        from anthropic import Anthropic
    except ImportError:
        print("⚠️ anthropic SDK 未安裝, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, pred, query_features, training_count)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("⚠️ ANTHROPIC_API_KEY 未設定, 退回 --no-ai", file=sys.stderr)
        return render_no_ai(data, pred, query_features, training_count)

    base = render_no_ai(data, pred, query_features, training_count)

    feature_summary = (
        f"pitch={query_features.pitch_mean_hz:.0f}Hz "
        f"(std {query_features.pitch_std_hz:.0f}), "
        f"duration={query_features.duration_ms:.0f}ms, "
        f"energy={query_features.energy_mean:.3f}, "
        f"bark_rate={query_features.bark_rate_per_sec:.1f}/s"
    )

    prompt = f"""你是台灣資深犬行為訓練師 + 動物溝通師 (15+ 年, 訓練過 1000+ 犬隻). 下面是用 FFT + 自相關 pitch + kNN 純函式分析的結果:

飼主回報: {data['query'].get('_meta', '')}
特徵摘要: {feature_summary}
分類結果: {pred.predicted_class} (信心 {pred.confidence:.0%})
Top 3 票數: {pred.vote_counts}

請寫 250-330 字 給飼主深夜讀的「我家狗為什麼叫」實用 SOP:
1. 一句解讀 (避免「FFT」「pitch」「kNN」這類術語): 我家狗在叫什麼意思
2. **3 個今晚 / 明天可做的具體行為調整** (情境管理 / 環境調整 / 訓練起手式)
3. **就醫 / 找專業訓練師紅旗** (任一出現就要找專業)
4. 1 個容易做錯的事 (好心做壞事; e.g. 安撫反強化焦慮 / 處罰焦慮狗)

**嚴格規則**:
- 不要重算 % / 信心 / pitch, 引用 facts
- 不要套話 ("祝您與毛孩感情更好")
- 不超過 330 字
- 不要 markdown 標題
- 強調「狗叫分類是分流參考, 不是診斷, 連續叫 30 分鐘以上要看獸醫」
- 若信心 < 50% 直接建議找專業訓練師

直接寫 SOP。"""

    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return base + "\n\n## 🤖 AI 犬行為訓練師 SOP\n\n" + resp.content[0].text + "\n"


def main():
    p = argparse.ArgumentParser(description="barktype -- 狗叫聲 voice signal 分類")
    p.add_argument("--data", default="samples/bark_dataset.json")
    p.add_argument("--wav", default=None, help="optional WAV file to extract features from")
    p.add_argument("-k", "--n-neighbors", type=int, default=3)
    p.add_argument("--no-ai", action="store_true")
    args = p.parse_args()

    data = load_data(Path(args.data))
    training = data["training_barks"]
    training_X = [list(t["features"].values()) for t in training]
    training_y = [t["label"] for t in training]
    scales = fit_feature_scales(training_X)

    if args.wav:
        samples, sr = read_wav_file(Path(args.wav))
        query_features = extract_features_from_signal(samples, sr)
        query_vec = query_features.as_vector()
    else:
        q = data["query"]["features"]
        query_features = BarkFeatures(**q)
        query_vec = query_features.as_vector()

    pred = knn_predict(training_X, training_y, query_vec, scales, k=args.n_neighbors)

    if args.no_ai:
        print(render_no_ai(data, pred, query_features, len(training)))
    else:
        print(render_with_ai(data, pred, query_features, len(training)))


if __name__ == "__main__":
    main()
