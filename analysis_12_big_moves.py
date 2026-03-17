#!/usr/bin/env python3
"""
川普密碼 分析 #12 — 只看大跌大漲
小漲小跌是雜訊，只有 >1% 的大波動才是能賺錢的訊號
重新定義「命中」= 預測到大漲(>1%)或大跌(<-1%)

⚡ 優化版：使用 bitmask 向量化加速暴力搜索
"""

import json
import re
from itertools import combinations
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent


def main():
    with open(BASE / "clean_president.json", 'r', encoding='utf-8') as f:
        posts = json.load(f)

    DATA = BASE / "data"

    with open(DATA / "market_SP500.json", 'r', encoding='utf-8') as f:
        sp500 = json.load(f)

    with open(DATA / "market_NASDAQ.json", 'r', encoding='utf-8') as f:
        nasdaq = json.load(f)

    sp_by_date = {r['date']: r for r in sp500}
    nq_by_date = {r['date']: r for r in nasdaq}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p.get('is_retweet', False)],
        key=lambda p: p['created_at']
    )

    daily_posts = defaultdict(list)
    for p in originals:
        daily_posts[p['created_at'][:10]].append(p)
    sorted_dates = sorted(daily_posts.keys())

    def next_td(date_str, market=None):
        if market is None:
            market = sp_by_date
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 6):
            d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
            if d in market:
                return d
        return None

    print("=" * 90)
    print("🎯 分析 #12: 只看大跌大漲（日波動 >1%）")
    print("=" * 90)

    # === 找出所有大波動日 ===
    big_up = []    # >1%
    big_down = []  # <-1%
    huge_up = []   # >2%
    huge_down = [] # <-2%
    normal = []    # -1% ~ +1%

    for sp in sp500:
        ret = (sp['close'] - sp['open']) / sp['open'] * 100
        sp['return'] = ret
        if ret > 2:
            huge_up.append(sp)
        elif ret > 1:
            big_up.append(sp)
        elif ret < -2:
            huge_down.append(sp)
        elif ret < -1:
            big_down.append(sp)
        else:
            normal.append(sp)

    print(f"\n📊 S&P500 日波動分布:")
    print(f"   暴漲 >2%:  {len(huge_up):3d} 天 ({len(huge_up)/len(sp500)*100:.1f}%)")
    print(f"   大漲 1~2%: {len(big_up):3d} 天 ({len(big_up)/len(sp500)*100:.1f}%)")
    print(f"   正常 ±1%:  {len(normal):3d} 天 ({len(normal)/len(sp500)*100:.1f}%)")
    print(f"   大跌 1~2%: {len(big_down):3d} 天 ({len(big_down)/len(sp500)*100:.1f}%)")
    print(f"   暴跌 >2%:  {len(huge_down):3d} 天 ({len(huge_down)/len(sp500)*100:.1f}%)")

    all_big = huge_up + big_up + huge_down + big_down
    print(f"\n   大波動天數: {len(all_big)} / {len(sp500)} ({len(all_big)/len(sp500)*100:.1f}%)")


    # === 大波動日的前一天，Trump 發了什麼？===
    print(f"\n{'='*90}")
    print("📊 大波動日 vs 前一天的推文特徵")
    print("=" * 90)

    def prev_td(date_str):
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        for i in range(1, 6):
            d = (dt - timedelta(days=i)).strftime('%Y-%m-%d')
            if d in sp_by_date:
                return d
        return None

    def day_features(date):
        """提取一天的推文特徵"""
        day_p = daily_posts.get(date, [])
        if not day_p:
            return None

        f = {}
        n = len(day_p)
        f['post_count'] = n

        all_text = ' '.join(p['content'].lower() for p in day_p)
        all_content = ' '.join(p['content'] for p in day_p)

        # 關鍵字計數
        f['tariff'] = sum(1 for w in ['tariff', 'tariffs', 'duty'] if w in all_text)
        f['deal'] = sum(1 for w in ['deal', 'agreement', 'negotiate', 'signed'] if w in all_text)
        f['relief'] = sum(1 for w in ['pause', 'exempt', 'suspend', 'delay'] if w in all_text)
        f['china'] = 1 if any(w in all_text for w in ['china', 'chinese', 'beijing']) else 0
        f['iran'] = 1 if any(w in all_text for w in ['iran', 'iranian']) else 0
        f['attack'] = sum(1 for w in ['fake news', 'corrupt', 'fraud', 'disgrace', 'witch hunt'] if w in all_text)
        f['positive'] = sum(1 for w in ['great', 'tremendous', 'incredible', 'historic', 'beautiful', 'amazing'] if w in all_text)
        f['market_brag'] = sum(1 for w in ['stock market', 'all time high', 'record', 'dow', 'nasdaq'] if w in all_text)
        f['action'] = sum(1 for w in ['immediately', 'executive order', 'just signed', 'hereby'] if w in all_text)

        # 大寫率
        caps = sum(1 for c in all_content if c.isupper())
        alpha = sum(1 for c in all_content if c.isalpha())
        f['caps_ratio'] = round(caps / max(alpha, 1) * 100, 1)

        # 驚嘆號
        f['excl'] = all_content.count('!')

        # 平均文長
        f['avg_len'] = round(sum(len(p['content']) for p in day_p) / n)

        # 簽名
        f['sig_djt'] = 1 if 'President DJT' in all_content else 0
        f['sig_potus'] = 1 if 'PRESIDENT OF THE UNITED STATES' in all_content else 0
        f['sig_tyfa'] = 1 if 'Thank you for your attention' in all_content else 0

        # 情緒淨值
        f['sentiment'] = f['positive'] - f['attack']

        # Deal vs Tariff 比
        f['deal_ratio'] = round(f['deal'] / max(f['tariff'] + f['deal'], 1) * 100)

        return f


    # 分析大漲日 vs 大跌日的前一天特徵差異
    print(f"\n📈 大漲日（>1%）前一天 vs 📉 大跌日（<-1%）前一天:")
    print(f"{'='*90}")

    up_features = []
    down_features = []

    for sp in huge_up + big_up:
        prev = prev_td(sp['date'])
        if prev:
            feat = day_features(prev)
            if feat:
                up_features.append(feat)

    for sp in huge_down + big_down:
        prev = prev_td(sp['date'])
        if prev:
            feat = day_features(prev)
            if feat:
                down_features.append(feat)

    def avg_feat(features, key):
        vals = [f[key] for f in features if key in f]
        return sum(vals) / max(len(vals), 1)

    print(f"\n  {'特徵':20s} | {'大漲前一天':>10s} | {'大跌前一天':>10s} | {'差異':>10s} | 解讀")
    print(f"  {'-'*20}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*30}")

    features_to_compare = [
        ('post_count', '發文量', '篇'),
        ('tariff', '提到關稅', '次'),
        ('deal', '提到Deal', '次'),
        ('relief', '提到暫緩', '次'),
        ('china', '提到中國', ''),
        ('attack', '攻擊用詞', '次'),
        ('positive', '正面用詞', '次'),
        ('market_brag', '炫耀股市', '次'),
        ('action', '行政命令', '次'),
        ('caps_ratio', '大寫率', '%'),
        ('excl', '驚嘆號', '個'),
        ('avg_len', '平均文長', '字'),
        ('sig_djt', 'DJT簽名', ''),
        ('sig_tyfa', 'TYFA簽名', ''),
        ('sentiment', '情緒淨值', ''),
        ('deal_ratio', 'Deal佔比', '%'),
    ]

    key_differences = []

    for key, label, unit in features_to_compare:
        up_avg = avg_feat(up_features, key)
        down_avg = avg_feat(down_features, key)
        diff = up_avg - down_avg

        # 解讀
        if abs(diff) < 0.01:
            interpretation = "無差異"
        elif key == 'tariff' and diff < -0.5:
            interpretation = "⚡ 關稅越多→越容易大跌"
        elif key == 'deal' and diff > 0.5:
            interpretation = "⚡ Deal越多→越容易大漲"
        elif key == 'post_count' and abs(diff) > 2:
            interpretation = "⚡ 發文量有差"
        elif key == 'caps_ratio' and abs(diff) > 1:
            interpretation = "⚡ 情緒激動程度有差"
        elif abs(diff) > 0.3:
            interpretation = f"{'大漲前較高' if diff > 0 else '大跌前較高'}"
        else:
            interpretation = "差異不大"

        if abs(diff) > 0.1:
            key_differences.append((key, label, diff, up_avg, down_avg))

        print(f"  {label:20s} | {up_avg:>9.1f}{unit} | {down_avg:>9.1f}{unit} | {diff:>+9.2f} | {interpretation}")


    # === 大波動預測模型 ===
    print(f"\n{'='*90}")
    print("📊 大波動預測暴力搜索")
    print("   目標：預測「明天是大漲日還是大跌日」")
    print("=" * 90)

    # 為每個交易日標記：大漲/大跌/普通
    day_labels = {}
    for sp in sp500:
        ret = sp['return']
        if ret > 1:
            day_labels[sp['date']] = 'BIG_UP'
        elif ret < -1:
            day_labels[sp['date']] = 'BIG_DOWN'
        else:
            day_labels[sp['date']] = 'NORMAL'

    # 特徵計算（用前一天的推文預測今天的股市）
    KEYWORDS = [
        'tariff', 'tariffs', 'deal', 'agreement', 'negotiate', 'signed',
        'pause', 'exempt', 'suspend', 'delay', 'reciprocal',
        'china', 'chinese', 'japan', 'mexico', 'iran', 'russia', 'europe', 'india',
        'great', 'tremendous', 'incredible', 'historic', 'beautiful',
        'fake', 'corrupt', 'terrible', 'disaster', 'disgrace',
        'stock market', 'all time high', 'record high', 'dow', 'nasdaq',
        'immediately', 'executive order', 'just signed', 'hereby',
        'oil', 'energy', 'border', 'military', 'nuclear',
        'save america', 'filibuster', 'maga',
        'president djt', 'thank you for your attention', 'never let you down',
    ]

    # 預先為每個日期生成文字快取，避免重複 join
    _text_cache = {}
    for date in sorted_dates:
        day_p = daily_posts.get(date, [])
        if day_p:
            _text_cache[date] = ' '.join(p['content'].lower() for p in day_p)

    def compute_binary_features(date, idx):
        day_p = daily_posts.get(date, [])
        if not day_p:
            return None

        f = {}
        n = len(day_p)
        all_text = _text_cache.get(date, '')
        all_content = ' '.join(p['content'] for p in day_p)

        f['posts_high'] = n >= 20
        f['posts_very_high'] = n >= 35
        f['posts_low'] = n <= 5

        caps = sum(1 for c in all_content if c.isupper())
        alpha = sum(1 for c in all_content if c.isalpha())
        cr = caps / max(alpha, 1)
        f['caps_high'] = cr > 0.18
        f['caps_very_high'] = cr > 0.25

        excl = all_content.count('!')
        f['excl_heavy'] = excl >= 5
        f['excl_extreme'] = excl >= 10

        avg_len = sum(len(p['content']) for p in day_p) / n
        f['long_posts'] = avg_len > 400
        f['short_posts'] = avg_len < 150

        for kw in KEYWORDS:
            kw_clean = kw.replace(' ', '_')
            count = all_text.count(kw)
            f[f'kw_{kw_clean}'] = count >= 1
            if count >= 2:
                f[f'kw_{kw_clean}_heavy'] = True

        # 組合
        has_t = any(w in all_text for w in ['tariff', 'tariffs'])
        has_d = 'deal' in all_text
        f['tariff_no_deal'] = has_t and not has_d
        f['deal_no_tariff'] = has_d and not has_t
        f['both_tariff_deal'] = has_t and has_d

        # 趨勢
        if idx >= 3:
            prev_tariff = sum(
                1 for j in range(max(0, idx-3), idx)
                if 'tariff' in _text_cache.get(sorted_dates[j], '')
            )
            f['tariff_streak'] = prev_tariff >= 2

        if idx >= 7:
            prev_counts = [len(daily_posts.get(sorted_dates[j], [])) for j in range(idx-7, idx)]
            avg_7 = sum(prev_counts) / 7
            f['volume_spike'] = n > avg_7 * 2 if avg_7 > 0 else False

        # 只保留 True
        return {k: v for k, v in f.items() if v is True}

    # 計算所有天的特徵
    log_features = {}
    for idx, date in enumerate(sorted_dates):
        feat = compute_binary_features(date, idx)
        if feat:
            log_features[date] = feat

    # 有效特徵
    feat_counts = Counter()
    for feat in log_features.values():
        feat_counts.update(feat.keys())
    useful = sorted([f for f, c in feat_counts.items() if 5 <= c <= 200])
    print(f"   有效特徵: {len(useful)} 個")

    # 分割：動態計算後 25% 為驗證集
    _all_valid = [d for d in sorted_dates if d in log_features]
    n_dates = len(_all_valid)
    cutoff_idx = int(n_dates * 0.75)
    cutoff = _all_valid[cutoff_idx] if n_dates > 0 else "2025-12-01"
    train_dates = _all_valid[:cutoff_idx]
    test_dates = _all_valid[cutoff_idx:]

    # =========================================================
    # ⚡ 優化核心：bitmask 向量化暴力搜索
    # =========================================================
    # 把每個特徵在每組日期集上的出現情況編碼為 Python 大整數 bitmask
    # 這樣 "所有日期同時滿足多個特徵" = 多個 bitmask 做 AND
    # popcount = bin(mask).count('1')
    # =========================================================
    print(f"\n🔨 搜索中（bitmask 加速）...")

    n_feat = len(useful)

    # --- 預計算：每個日期的「下一個交易日」label ---
    def _precompute_next_labels(dates):
        """回傳一個 dict: date -> next_td_label"""
        result = {}
        for d in dates:
            ntd = next_td(d)
            if ntd and ntd in day_labels:
                result[d] = day_labels[ntd]
            else:
                result[d] = None
        return result

    train_next = _precompute_next_labels(train_dates)
    test_next = _precompute_next_labels(test_dates)

    # --- 建立 bitmask ---
    # 對 train / test 分別建立：
    #   feat_mask[feat_name] = 整數 bitmask, 第 i 位元 = 1 表示第 i 個 date 有此特徵
    #   target_mask['BIG_UP'] / target_mask['BIG_DOWN'] = bitmask, 表示下一交易日為大漲/大跌
    #   valid_mask = 所有有 next_td label 的日期

    def build_masks(dates, next_labels, feature_names, features_dict):
        feat_mask = {f: 0 for f in feature_names}
        target_up = 0
        target_down = 0
        valid = 0

        for i, d in enumerate(dates):
            bit = 1 << i
            feat = features_dict.get(d, {})
            # feat 只包含 True 的 key，直接遍歷比逐一查 feature_names 快
            for fname in feat:
                if fname in feat_mask:
                    feat_mask[fname] |= bit

            lbl = next_labels.get(d)
            if lbl is not None:
                valid |= bit
                if lbl == 'BIG_UP':
                    target_up |= bit
                elif lbl == 'BIG_DOWN':
                    target_down |= bit

        return feat_mask, {'BIG_UP': target_up, 'BIG_DOWN': target_down}, valid

    tr_feat_mask, tr_target, tr_valid = build_masks(
        train_dates, train_next, useful, log_features
    )
    te_feat_mask, te_target, te_valid = build_masks(
        test_dates, test_next, useful, log_features
    )

    # 使用 Python 3.10+ 內建的 int.bit_count()（C 實作，比 bin().count('1') 快）

    winners = []
    tested = 0

    # --- 預計算單特徵 mask ---
    # 不含 valid 的版本用於計算 total（與原版一致：total 包含沒有下一交易日的日期）
    # hits 計算時 AND target_mask（已是 valid 子集），自然只算有效日期
    tr_single = [tr_feat_mask[useful[i]] for i in range(n_feat)]
    te_single = [te_feat_mask[useful[i]] for i in range(n_feat)]

    # --- 2-combo ---
    for i in range(n_feat):
        tr_i = tr_single[i]
        te_i = te_single[i]
        for j in range(i + 1, n_feat):
            tr_match = tr_i & tr_single[j]
            tr_total = tr_match.bit_count()
            if tr_total < 3:
                tested += 2
                continue

            te_match = te_i & te_single[j]

            feature_combo = [useful[i], useful[j]]
            for target in ('BIG_UP', 'BIG_DOWN'):
                tested += 1
                tr_hits = (tr_match & tr_target[target]).bit_count()
                train_rate = tr_hits / tr_total * 100
                if train_rate < 50:
                    continue

                te_total = te_match.bit_count()
                if te_total < 2:
                    continue

                te_hits = (te_match & te_target[target]).bit_count()
                test_rate = te_hits / te_total * 100
                if test_rate >= 40:
                    winners.append({
                        'features': feature_combo,
                        'target': target,
                        'train_total': tr_total,
                        'train_hits': tr_hits,
                        'train_rate': round(train_rate, 1),
                        'test_total': te_total,
                        'test_hits': te_hits,
                        'test_rate': round(test_rate, 1),
                        'combined': round((train_rate + test_rate) / 2, 1),
                    })

    print(f"   2-combo 完成，測試 {tested:,} 組，候選 {len(winners)}", flush=True)

    # --- 3-combo ---
    tested_3 = 0
    for i in range(n_feat):
        tr_i = tr_single[i]
        te_i = te_single[i]
        for j in range(i + 1, n_feat):
            tr_ij = tr_i & tr_single[j]
            # 提前剪枝：2-combo 的 train_total 已經 < 3，3-combo 一定也 < 3
            if tr_ij.bit_count() < 3:
                tested_3 += (n_feat - j - 1) * 2
                continue
            te_ij = te_i & te_single[j]
            for k in range(j + 1, n_feat):
                tr_match = tr_ij & tr_single[k]
                tr_total = tr_match.bit_count()
                if tr_total < 3:
                    tested_3 += 2
                    continue

                te_match = te_ij & te_single[k]
                feature_combo = [useful[i], useful[j], useful[k]]

                for target in ('BIG_UP', 'BIG_DOWN'):
                    tested_3 += 1
                    tr_hits = (tr_match & tr_target[target]).bit_count()
                    train_rate = tr_hits / tr_total * 100
                    if train_rate < 50:
                        continue

                    te_total = te_match.bit_count()
                    if te_total < 2:
                        continue

                    te_hits = (te_match & te_target[target]).bit_count()
                    test_rate = te_hits / te_total * 100
                    if test_rate >= 40:
                        winners.append({
                            'features': feature_combo,
                            'target': target,
                            'train_total': tr_total,
                            'train_hits': tr_hits,
                            'train_rate': round(train_rate, 1),
                            'test_total': te_total,
                            'test_hits': te_hits,
                            'test_rate': round(test_rate, 1),
                            'combined': round((train_rate + test_rate) / 2, 1),
                        })

    tested += tested_3
    print(f"   3-combo 完成，累計 {tested:,} 組，候選 {len(winners)}", flush=True)

    print(f"\n✅ 完成！測試 {tested:,} 組")
    print(f"   大波動預測候選: {len(winners)} 組")

    # 分開看大漲和大跌
    up_winners = sorted([w for w in winners if w['target'] == 'BIG_UP'],
                        key=lambda w: -w['combined'])
    down_winners = sorted([w for w in winners if w['target'] == 'BIG_DOWN'],
                          key=lambda w: -w['combined'])

    print(f"   預測大漲: {len(up_winners)} 組")
    print(f"   預測大跌: {len(down_winners)} 組")

    # Top 20 大漲預測
    print(f"\n{'='*90}")
    print(f"🚀 Top 20: 預測大漲（隔天 >1%）的信號組合")
    print(f"{'='*90}")
    print(f"  {'#':>3s} | {'訓練':>10s} | {'驗證':>10s} | 條件")
    for i, w in enumerate(up_winners[:20], 1):
        feats = ' + '.join(w['features'])
        print(f"  {i:3d} | {w['train_hits']}/{w['train_total']} ({w['train_rate']:.0f}%) | {w['test_hits']}/{w['test_total']} ({w['test_rate']:.0f}%) | {feats}")

    # Top 20 大跌預測
    print(f"\n{'='*90}")
    print(f"💥 Top 20: 預測大跌（隔天 <-1%）的信號組合")
    print(f"{'='*90}")
    print(f"  {'#':>3s} | {'訓練':>10s} | {'驗證':>10s} | 條件")
    for i, w in enumerate(down_winners[:20], 1):
        feats = ' + '.join(w['features'])
        print(f"  {i:3d} | {w['train_hits']}/{w['train_total']} ({w['train_rate']:.0f}%) | {w['test_hits']}/{w['test_total']} ({w['test_rate']:.0f}%) | {feats}")

    # 大波動日全部列出 + 前一天有什麼信號
    print(f"\n{'='*90}")
    print(f"📋 每個大波動日的前一天推文信號")
    print(f"{'='*90}")

    all_big_days = sorted(huge_up + big_up + huge_down + big_down, key=lambda x: x['date'])

    print(f"  {'日期':12s} | {'S&P':>8s} | {'前天篇數':>6s} | {'關稅':>4s} | {'Deal':>4s} | {'攻擊':>4s} | {'正面':>4s} | {'前天摘要'}")
    print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*6}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*40}")

    for sp in all_big_days:
        prev = prev_td(sp['date'])
        feat = day_features(prev) if prev else None

        if feat:
            sample = daily_posts.get(prev, [{}])
            first_content = sample[0].get('content', '')[:40] if sample else ''
            arrow = "🚀" if sp['return'] > 0 else "💥"
            print(f"  {sp['date']:12s} | {sp['return']:+.2f}% {arrow} | {feat['post_count']:>5d} | {feat['tariff']:>4d} | {feat['deal']:>4d} | {feat['attack']:>4d} | {feat['positive']:>4d} | {first_content}")

    # === 最關鍵的特徵 ===
    print(f"\n{'='*90}")
    print("📊 大波動 DNA — 哪些特徵最能預測大漲/大跌")
    print("=" * 90)

    for label, group in [("🚀大漲", up_winners), ("💥大跌", down_winners)]:
        freq = Counter()
        for w in group:
            for f in w['features']:
                freq[f] += 1
        print(f"\n  {label} 預測中最常出現的特徵:")
        for fname, count in freq.most_common(15):
            pct = count / max(len(group), 1) * 100
            print(f"    {fname:35s} | {count:4d}次 ({pct:5.1f}%)")

    # 存結果
    output = {
        'big_move_stats': {
            'huge_up': len(huge_up), 'big_up': len(big_up),
            'huge_down': len(huge_down), 'big_down': len(big_down),
            'normal': len(normal),
        },
        'up_rules': [w for w in up_winners[:50]],
        'down_rules': [w for w in down_winners[:50]],
    }
    with open(DATA / 'results_12_bigmoves.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n💾 結果存入 results_12_bigmoves.json")


if __name__ == '__main__':
    main()
