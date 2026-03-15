#!/usr/bin/env python3
"""
川普密碼 — 規則進化引擎（Rule Evolver）

從 500 條存活規則中，自動發現新的更好規則。

三種進化方式：
  ① 交配（Crossover）：把兩條好規則的特徵混在一起，生出新規則
  ② 突變（Mutation）：拿一條好規則，加一個新特徵或換掉一個
  ③ 精煉（Distill）：找出「明星特徵」，用它們組出新的簡單規則

全部用歷史數據回測驗證，只有通過的才會加入規則庫。
不用外部套件，純 Python。
"""

from __future__ import annotations

import json
import random
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta
from itertools import combinations
from pathlib import Path
from typing import Any

BASE = Path(__file__).parent
DATA = BASE / "data"

NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')

# === 參數 ===
MIN_TRAIN_TRADES = 5       # 訓練期至少幾筆交易
MIN_TEST_TRADES = 3        # 驗證期至少幾筆交易
TRAIN_WIN_RATE = 60.0      # 訓練期勝率門檻 %
TEST_WIN_RATE = 55.0       # 驗證期勝率門檻 %
MIN_AVG_RETURN = 0.05      # 最低平均報酬 %
MAX_NEW_RULES = 50         # 每次最多產生幾條新規則
CROSSOVER_ATTEMPTS = 200   # 交配嘗試次數
MUTATION_ATTEMPTS = 200    # 突變嘗試次數
DISTILL_TOP_N = 15         # 精煉時用前 N 個明星特徵


def log(msg: str) -> None:
    print(f"[進化] {msg}", flush=True)


def _build_daily_features() -> dict[str, dict]:
    """
    從 CNN 下載推文 → 用 daily_pipeline 的 compute_day_features 計算每日特徵。
    回傳 {日期: {特徵名: True, ...}, ...}
    """
    import csv
    import html
    import urllib.request
    from collections import defaultdict

    log("   📥 從 CNN 下載推文...")
    try:
        req = urllib.request.Request(
            "https://ix.cnn.io/data/truth-social/truth_archive.csv",
            headers={"User-Agent": "TrumpCode-Evolver/1.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode('utf-8')
    except Exception as e:
        log(f"   ⚠️ 下載失敗: {e}")
        return {}

    reader = csv.DictReader(raw.splitlines())
    posts = []
    for row in reader:
        if not row.get('content') or not row.get('created_at'):
            continue
        content = row['content'].strip()
        try:
            content = content.encode('latin-1').decode('utf-8')
        except (UnicodeDecodeError, UnicodeEncodeError):
            pass
        content = html.unescape(content)
        created = row.get('created_at', '')
        # 只要合法日期格式（排除 URL 等髒數據）
        if (created >= '2025-01-20'
                and created[:4].isdigit()
                and len(created) >= 10
                and not content.startswith('RT @')):
            posts.append({'created_at': created, 'content': content})

    log(f"   下載完成: {len(posts)} 篇推文")

    # 按日期分組
    daily: dict[str, list] = defaultdict(list)
    for p in posts:
        daily[p['created_at'][:10]].append(p)

    # 計算每日特徵（用 daily_pipeline 的函數）
    try:
        from daily_pipeline import compute_day_features
    except ImportError:
        log("   ⚠️ 無法 import daily_pipeline.compute_day_features")
        return {}

    sorted_days = sorted(daily.keys())
    all_features: dict[str, dict] = {}

    for idx, date in enumerate(sorted_days):
        feats = compute_day_features(daily[date], daily, sorted_days, idx)
        if feats:
            all_features[date] = feats

    log(f"   計算完成: {len(all_features)} 天有特徵")
    return all_features


def _rule_id(features: list[str], direction: str, hold: int) -> str:
    """產生規則的唯一 ID"""
    key = f"{direction}_{hold}d_{'|'.join(sorted(features))}"
    return hashlib.md5(key.encode()).hexdigest()[:12]


# =====================================================================
# 載入數據
# =====================================================================

def load_data() -> tuple[list[dict], dict[str, dict], list[str], list[str]]:
    """
    載入所有需要的數據。
    回傳：(存活規則, 每日特徵, 訓練日期, 驗證日期)
    """
    # 存活規則
    rules_file = DATA / "surviving_rules.json"
    if rules_file.exists():
        with open(rules_file, encoding='utf-8') as f:
            rules = json.load(f).get('rules', [])
    else:
        rules = []

    # 股市數據（用來回測）
    sp_file = DATA / "market_SP500.json"
    if sp_file.exists():
        with open(sp_file, encoding='utf-8') as f:
            sp_data = json.load(f)
    else:
        # fallback 到根目錄
        with open(BASE / "market_SP500.json", encoding='utf-8') as f:
            sp_data = json.load(f)
    sp_by_date = {r['date']: r for r in sp_data}

    # 推文特徵（從 overnight_results 或重新計算）
    # 嘗試載入預先計算好的每日特徵
    features_file = DATA / "daily_features.json"
    if features_file.exists():
        with open(features_file, encoding='utf-8') as f:
            all_features = json.load(f)
    else:
        # 沒有預算好的特徵 → 嘗試從 overnight_results 提取
        overnight_file = BASE / "overnight_results.json"
        if overnight_file.exists():
            with open(overnight_file, encoding='utf-8') as f:
                overnight = json.load(f)
            all_features = overnight.get('daily_features', {})
        else:
            all_features = {}

    if not all_features:
        log("   daily_features.json 不存在，自動從推文重新計算...")
        all_features = _build_daily_features()
        if all_features:
            # 快取起來，下次不用重算
            with open(features_file, 'w', encoding='utf-8') as f:
                json.dump(all_features, f, ensure_ascii=False)
            log(f"   已生成並快取 {len(all_features)} 天的特徵")

    if not all_features:
        log("⚠️ 無法取得或計算每日特徵數據")
        return rules, {}, [], []

    # 分割訓練/驗證
    sorted_dates = sorted(all_features.keys())
    n = len(sorted_dates)
    cutoff_idx = int(n * 0.75)
    train_dates = [d for d in sorted_dates[:cutoff_idx] if d in sp_by_date]
    test_dates = [d for d in sorted_dates[cutoff_idx:] if d in sp_by_date]

    # 預算每天的報酬（1/2/3 天持有）
    day_returns: dict[tuple[str, int], float] = {}
    sorted_sp_dates = sorted(sp_by_date.keys())

    for date in sorted_sp_dates:
        idx = sorted_sp_dates.index(date)
        for hold in [1, 2, 3]:
            exit_idx = idx + hold
            if exit_idx < len(sorted_sp_dates):
                exit_date = sorted_sp_dates[exit_idx]
                entry_price = sp_by_date[date]['open']
                exit_price = sp_by_date[exit_date]['close']
                if entry_price > 0:
                    day_returns[(date, hold)] = (exit_price - entry_price) / entry_price * 100

    return rules, all_features, train_dates, test_dates


# =====================================================================
# 回測引擎（簡化版）
# =====================================================================

# 把 sp_by_date 和 day_returns 存為模組級變數，避免重複載入
_sp_by_date: dict[str, dict] = {}
_day_returns: dict[tuple[str, int], float] = {}
_all_features: dict[str, dict] = {}


def _init_market_data():
    """初始化股市數據（只載一次）"""
    global _sp_by_date, _day_returns, _all_features

    sp_file = DATA / "market_SP500.json"
    if sp_file.exists():
        with open(sp_file, encoding='utf-8') as f:
            sp_data = json.load(f)
    else:
        with open(BASE / "market_SP500.json", encoding='utf-8') as f:
            sp_data = json.load(f)
    _sp_by_date = {r['date']: r for r in sp_data}

    sorted_dates = sorted(_sp_by_date.keys())
    for i, date in enumerate(sorted_dates):
        for hold in [1, 2, 3]:
            exit_idx = i + hold
            if exit_idx < len(sorted_dates):
                exit_date = sorted_dates[exit_idx]
                entry = _sp_by_date[date]['open']
                exit_p = _sp_by_date[exit_date]['close']
                if entry > 0:
                    _day_returns[(date, hold)] = (exit_p - entry) / entry * 100


def backtest(
    features: list[str],
    direction: str,
    hold: int,
    dates: list[str],
    all_features: dict[str, dict],
) -> dict[str, Any] | None:
    """
    快速回測一條規則。

    回傳 None 表示樣本不足。
    """
    rets: list[float] = []

    for date in dates:
        feat = all_features.get(date, {})
        if not feat:
            continue

        # 檢查所有條件是否成立
        if all(feat.get(f, False) for f in features):
            r = _day_returns.get((date, hold))
            if r is not None:
                if direction == 'SHORT':
                    rets.append(-r)
                else:
                    rets.append(r)

    if not rets:
        return None

    wins = sum(1 for r in rets if r > 0)
    return {
        'trades': len(rets),
        'wins': wins,
        'win_rate': wins / len(rets) * 100,
        'avg_return': sum(rets) / len(rets),
        'total_return': sum(rets),
    }


def validate_rule(
    features: list[str],
    direction: str,
    hold: int,
    train_dates: list[str],
    test_dates: list[str],
    all_features: dict[str, dict],
) -> dict[str, Any] | None:
    """
    完整驗證一條規則（訓練 + 驗證雙段）。
    通過回傳完整結果，不通過回傳 None。
    """
    train = backtest(features, direction, hold, train_dates, all_features)
    if not train or train['trades'] < MIN_TRAIN_TRADES:
        return None
    if train['win_rate'] < TRAIN_WIN_RATE or train['avg_return'] < MIN_AVG_RETURN:
        return None

    test = backtest(features, direction, hold, test_dates, all_features)
    if not test or test['trades'] < MIN_TEST_TRADES:
        return None
    if test['win_rate'] < TEST_WIN_RATE or test['avg_return'] < 0:
        return None

    return {
        'features': features,
        'direction': direction,
        'hold': hold,
        'id': _rule_id(features, direction, hold),
        'n_cond': len(features),
        'train_trades': train['trades'],
        'train_win_rate': round(train['win_rate'], 1),
        'train_avg': round(train['avg_return'], 3),
        'test_trades': test['trades'],
        'test_win_rate': round(test['win_rate'], 1),
        'test_avg': round(test['avg_return'], 3),
        'combined_score': round((train['win_rate'] + test['win_rate']) / 2, 1),
        'origin': 'evolved',  # 標記為進化產生的
        'born_date': TODAY,
        'weight': 1.0,
    }


# =====================================================================
# ① 交配（Crossover）
# =====================================================================

def crossover(
    rules: list[dict],
    train_dates: list[str],
    test_dates: list[str],
    all_features: dict[str, dict],
) -> list[dict]:
    """
    從兩條好規則各取一些特徵，組出新規則。

    策略：
      - 選兩條高分規則
      - 從 A 取 1-2 個特徵，從 B 取 1-2 個
      - 驗證新組合
    """
    if len(rules) < 2:
        return []

    # 按分數排序，只從 Top 50% 選
    sorted_rules = sorted(rules, key=lambda r: r.get('combined_score', 0), reverse=True)
    top_pool = sorted_rules[:max(10, len(sorted_rules) // 2)]

    existing_ids = {_rule_id(r['features'], r['direction'], r['hold']) for r in rules}
    new_rules: list[dict] = []
    attempts = 0

    while attempts < CROSSOVER_ATTEMPTS and len(new_rules) < MAX_NEW_RULES // 3:
        attempts += 1

        # 隨機選兩條不同的規則
        parent_a, parent_b = random.sample(top_pool, 2)
        feats_a = parent_a['features']
        feats_b = parent_b['features']

        # 從 A 取 1-2 個，從 B 取 1-2 個
        n_from_a = random.randint(1, min(2, len(feats_a)))
        n_from_b = random.randint(1, min(2, len(feats_b)))

        child_feats = list(set(
            random.sample(feats_a, n_from_a) +
            random.sample(feats_b, n_from_b)
        ))

        if len(child_feats) < 2 or len(child_feats) > 4:
            continue

        # 方向隨機繼承其中一個
        direction = random.choice([parent_a['direction'], parent_b['direction']])
        hold = random.choice([1, 2, 3])

        # 檢查是否已存在
        rid = _rule_id(child_feats, direction, hold)
        if rid in existing_ids:
            continue

        # 回測驗證
        result = validate_rule(child_feats, direction, hold, train_dates, test_dates, all_features)
        if result:
            result['origin'] = 'crossover'
            result['parents'] = [
                '+'.join(parent_a['features'][:2]),
                '+'.join(parent_b['features'][:2]),
            ]
            new_rules.append(result)
            existing_ids.add(rid)

    return new_rules


# =====================================================================
# ② 突變（Mutation）
# =====================================================================

def mutate(
    rules: list[dict],
    all_feature_names: list[str],
    train_dates: list[str],
    test_dates: list[str],
    all_features: dict[str, dict],
) -> list[dict]:
    """
    拿一條好規則，加一個特徵或換掉一個。

    策略：
      - 加法突變：加一個從未用過的明星特徵
      - 替換突變：換掉最弱的一個特徵
      - 減法突變：拿掉一個特徵（簡化規則）
    """
    if not rules or not all_feature_names:
        return []

    sorted_rules = sorted(rules, key=lambda r: r.get('combined_score', 0), reverse=True)
    top_pool = sorted_rules[:max(10, len(sorted_rules) // 2)]

    existing_ids = {_rule_id(r['features'], r['direction'], r['hold']) for r in rules}
    new_rules: list[dict] = []
    attempts = 0

    while attempts < MUTATION_ATTEMPTS and len(new_rules) < MAX_NEW_RULES // 3:
        attempts += 1

        parent = random.choice(top_pool)
        feats = list(parent['features'])
        mutation_type = random.choice(['add', 'replace', 'remove'])

        if mutation_type == 'add' and len(feats) < 4:
            # 加一個未用過的特徵
            unused = [f for f in all_feature_names if f not in feats]
            if not unused:
                continue
            new_feat = random.choice(unused)
            child_feats = feats + [new_feat]

        elif mutation_type == 'replace' and len(feats) >= 2:
            # 換掉一個
            idx = random.randint(0, len(feats) - 1)
            unused = [f for f in all_feature_names if f not in feats]
            if not unused:
                continue
            child_feats = feats[:idx] + [random.choice(unused)] + feats[idx+1:]

        elif mutation_type == 'remove' and len(feats) >= 3:
            # 拿掉一個（簡化）
            idx = random.randint(0, len(feats) - 1)
            child_feats = feats[:idx] + feats[idx+1:]

        else:
            continue

        child_feats = list(set(child_feats))  # 去重
        if len(child_feats) < 2:
            continue

        direction = parent['direction']
        hold = parent['hold']

        rid = _rule_id(child_feats, direction, hold)
        if rid in existing_ids:
            continue

        result = validate_rule(child_feats, direction, hold, train_dates, test_dates, all_features)
        if result:
            result['origin'] = f'mutation_{mutation_type}'
            result['parent'] = '+'.join(parent['features'][:3])
            new_rules.append(result)
            existing_ids.add(rid)

    return new_rules


# =====================================================================
# ③ 精煉（Distill）— 從明星特徵直接組合
# =====================================================================

def distill(
    rules: list[dict],
    train_dates: list[str],
    test_dates: list[str],
    all_features: dict[str, dict],
) -> list[dict]:
    """
    找出在高分規則中最常出現的特徵（明星特徵），
    用它們直接組出新的 2-3 條件規則。
    """
    if not rules:
        return []

    # 找出 Top 30% 規則中最常出現的特徵
    sorted_rules = sorted(rules, key=lambda r: r.get('combined_score', 0), reverse=True)
    top_rules = sorted_rules[:max(5, len(sorted_rules) // 3)]

    feat_score = Counter()
    for r in top_rules:
        score = r.get('combined_score', 50)
        for f in r.get('features', []):
            feat_score[f] += score  # 加權計數

    star_features = [f for f, _ in feat_score.most_common(DISTILL_TOP_N)]
    log(f"   明星特徵: {', '.join(star_features[:8])}...")

    existing_ids = {_rule_id(r['features'], r['direction'], r['hold']) for r in rules}
    new_rules: list[dict] = []

    # 用明星特徵的 2-3 條件組合
    for n_cond in [2, 3]:
        for combo in combinations(star_features, n_cond):
            if len(new_rules) >= MAX_NEW_RULES // 3:
                break

            for direction in ['LONG', 'SHORT']:
                for hold in [1, 2, 3]:
                    rid = _rule_id(list(combo), direction, hold)
                    if rid in existing_ids:
                        continue

                    result = validate_rule(
                        list(combo), direction, hold,
                        train_dates, test_dates, all_features,
                    )
                    if result:
                        result['origin'] = 'distilled'
                        new_rules.append(result)
                        existing_ids.add(rid)

    return new_rules


# =====================================================================
# 主流程
# =====================================================================

def evolve() -> dict[str, Any]:
    """
    執行一輪完整的規則進化。

    回傳進化報告。
    """
    log("=" * 60)
    log(f"規則進化引擎 — {TODAY}")
    log("=" * 60)

    # 載入數據
    rules, all_features, train_dates, test_dates = load_data()

    if not all_features:
        log("⚠️ 無每日特徵數據。需要先跑 overnight_search.py 產生 daily_features.json")
        log("   嘗試從存活規則的特徵空間自行回測...")

        # 即使沒有 daily_features.json，也可以用存活規則的特徵名來引導
        # 但沒有每日特徵數據就無法回測 → 跳過
        return {'error': 'no daily features data', 'tip': '需要 data/daily_features.json'}

    # 初始化股市數據
    _init_market_data()

    log(f"   存活規則: {len(rules)} 條")
    log(f"   特徵天數: {len(all_features)} 天")
    log(f"   訓練期: {len(train_dates)} 天 | 驗證期: {len(test_dates)} 天")

    # 收集所有已知特徵名
    all_feature_names = set()
    for day_feat in all_features.values():
        all_feature_names.update(day_feat.keys())
    all_feature_names = sorted(all_feature_names)
    log(f"   特徵空間: {len(all_feature_names)} 個特徵")

    # ① 交配
    log(f"\n① 交配（Crossover）— 嘗試 {CROSSOVER_ATTEMPTS} 次...")
    crossover_rules = crossover(rules, train_dates, test_dates, all_features)
    log(f"   產出 {len(crossover_rules)} 條新規則")
    for r in crossover_rules[:5]:
        log(f"   🧬 {r['direction']} {r['hold']}天 | 訓{r['train_win_rate']:.0f}% 驗{r['test_win_rate']:.0f}% | "
            f"{' + '.join(r['features'])}")

    # ② 突變
    log(f"\n② 突變（Mutation）— 嘗試 {MUTATION_ATTEMPTS} 次...")
    mutation_rules = mutate(rules, all_feature_names, train_dates, test_dates, all_features)
    log(f"   產出 {len(mutation_rules)} 條新規則")
    for r in mutation_rules[:5]:
        log(f"   🔀 [{r['origin']}] {r['direction']} {r['hold']}天 | 訓{r['train_win_rate']:.0f}% 驗{r['test_win_rate']:.0f}% | "
            f"{' + '.join(r['features'])}")

    # ③ 精煉
    log(f"\n③ 精煉（Distill）— 用 Top {DISTILL_TOP_N} 明星特徵...")
    distill_rules = distill(rules, train_dates, test_dates, all_features)
    log(f"   產出 {len(distill_rules)} 條新規則")
    for r in distill_rules[:5]:
        log(f"   ⭐ {r['direction']} {r['hold']}天 | 訓{r['train_win_rate']:.0f}% 驗{r['test_win_rate']:.0f}% | "
            f"{' + '.join(r['features'])}")

    # 合併所有新規則
    all_new = crossover_rules + mutation_rules + distill_rules

    # 按綜合分數排序
    all_new.sort(key=lambda r: r.get('combined_score', 0), reverse=True)

    # 限制數量
    all_new = all_new[:MAX_NEW_RULES]

    log(f"\n{'=' * 60}")
    log(f"📊 進化結果")
    log(f"{'=' * 60}")
    log(f"   交配產出: {len(crossover_rules)} 條")
    log(f"   突變產出: {len(mutation_rules)} 條")
    log(f"   精煉產出: {len(distill_rules)} 條")
    log(f"   合計（去重+限量）: {len(all_new)} 條")

    if all_new:
        best = all_new[0]
        log(f"\n   🏆 最強新規則:")
        log(f"      {best['direction']} {best['hold']}天 | 訓{best['train_win_rate']:.0f}% 驗{best['test_win_rate']:.0f}%")
        log(f"      特徵: {' + '.join(best['features'])}")
        log(f"      來源: {best.get('origin', '?')}")

    # 合併到存活規則
    if all_new:
        rules.extend(all_new)
        # 重新排序
        rules.sort(key=lambda r: r.get('combined_score', 0), reverse=True)
        # 限制總數到 600（原來 500 + 最多新增 100）
        rules = rules[:600]

        # 存檔
        rules_data = {
            'meta': {
                'total_surviving': len(rules),
                'last_evolution': NOW,
                'evolved_rules_added': len(all_new),
            },
            'rules': rules,
        }
        with open(DATA / 'surviving_rules.json', 'w', encoding='utf-8') as f:
            json.dump(rules_data, f, ensure_ascii=False, indent=2)

        log(f"\n   ✅ 已合併到 surviving_rules.json（現有 {len(rules)} 條）")

    # 存進化歷史
    evo_log_file = DATA / 'evolution_log.json'
    evo_history: list[dict] = []
    if evo_log_file.exists():
        with open(evo_log_file, encoding='utf-8') as f:
            evo_history = json.load(f)

    evo_record = {
        'date': TODAY,
        'crossover': len(crossover_rules),
        'mutation': len(mutation_rules),
        'distill': len(distill_rules),
        'total_new': len(all_new),
        'total_rules_after': len(rules),
        'top_3': [
            {
                'features': r['features'],
                'direction': r['direction'],
                'hold': r['hold'],
                'score': r['combined_score'],
                'origin': r.get('origin', '?'),
            }
            for r in all_new[:3]
        ] if all_new else [],
    }
    evo_history.append(evo_record)

    with open(evo_log_file, 'w', encoding='utf-8') as f:
        json.dump(evo_history, f, ensure_ascii=False, indent=2)

    log(f"\n{'=' * 60}")
    log(f"✅ 進化完成！")
    log(f"{'=' * 60}")

    return evo_record


if __name__ == '__main__':
    result = evolve()
