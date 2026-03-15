#!/usr/bin/env python3
"""
川普密碼 — 閉環學習引擎（Closed-Loop Learning Engine）

每日管線跑完驗證後，自動執行：
  ① 算成績：每個模型/規則的最新命中率、連勝/連敗、報酬趨勢
  ② 調權重：升級強者、降級弱者、淘汰廢物
  ③ 調信號：信號信心度根據歷史表現動態調整
  ④ 發現：從最近的錯誤中學習新特徵組合
  ⑤ 記帳：所有調整都有紀錄，可追溯

設計原則：
  - 保守調整（每次最多 ±20%），避免過度反應
  - 滾動窗口（最近 30 天），適應模式變化
  - 最低樣本量（≥5 筆驗證才調整），避免噪音
  - 人話日誌，讓非工程師也看得懂發生什麼事
"""

from __future__ import annotations

import json
import copy
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# === 設定 ===

BASE = Path(__file__).parent
DATA = BASE / "data"

# 檔案路徑
PREDICTIONS_LOG = DATA / "predictions_log.json"       # 11 個人設模型的預測紀錄
PREDICTION_HISTORY = DATA / "prediction_history.json"  # 500 條暴力規則的預測紀錄
SURVIVING_RULES = DATA / "surviving_rules.json"        # 暴力搜索存活的 Top 500 規則
LEARNING_LOG = DATA / "learning_log.json"
SIGNAL_CONFIDENCE = DATA / "signal_confidence.json"
RULES_WEIGHTED = DATA / "rules_weighted.json"          # 加上權重的規則（學習後輸出）

# 學習參數
MIN_SAMPLES = 5          # 至少幾筆驗證才開始調整
ROLLING_WINDOW = 30      # 最近 N 筆做判斷（每個模型獨立）
PROMOTE_STREAK = 4       # 連對 N 次 → 升級
DEMOTE_STREAK = 3        # 連錯 N 次 → 降級
ELIMINATE_RATE = 0.38     # 命中率低於此 → 淘汰（略低於隨機 50%，給一些容忍）
PROMOTE_RATE = 0.65       # 命中率高於此 → 升級
WEIGHT_UP = 1.15          # 升級時權重乘數
WEIGHT_DOWN = 0.75        # 降級時權重乘數
WEIGHT_MIN = 0.1          # 權重下限（低於此就淘汰）
WEIGHT_MAX = 3.0          # 權重上限（防止單一模型過度主導）
CONFIDENCE_ADJUST = 0.05  # 信號信心度每次調整幅度

NOW = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')


def log(msg: str) -> None:
    print(f"[學習] {msg}", flush=True)


# =====================================================================
# ① 算成績：分析每個模型的表現
# =====================================================================

def compute_model_stats(predictions: list[dict]) -> dict[str, dict]:
    """
    計算每個模型的績效統計。

    回傳結構：
    {
        "model_id": {
            "total": int,
            "correct": int,
            "wrong": int,
            "win_rate": float,
            "avg_return": float,
            "recent_correct": int,     # 最近 ROLLING_WINDOW 筆
            "recent_wrong": int,
            "recent_win_rate": float,
            "streak": int,             # 正=連對, 負=連錯
            "trend": str,              # "improving" / "declining" / "stable"
            "returns": list[float],
        }
    }
    """
    # 按模型分組，保持時間順序
    by_model: dict[str, list[dict]] = defaultdict(list)
    for p in predictions:
        if p.get('status') != 'VERIFIED':
            continue
        by_model[p.get('model_id', 'unknown')].append(p)

    stats: dict[str, dict] = {}

    for mid, preds in by_model.items():
        # 按日期排序
        preds.sort(key=lambda p: p.get('date_signal', '') or p.get('signal_date', ''))

        total = len(preds)
        correct = sum(1 for p in preds if p.get('correct'))
        wrong = total - correct
        returns = [p.get('actual_return', 0) for p in preds]

        # 最近 N 筆
        recent = preds[-ROLLING_WINDOW:]
        recent_correct = sum(1 for p in recent if p.get('correct'))
        recent_wrong = len(recent) - recent_correct

        # 連勝/連敗（從最新往回數）
        streak = 0
        for p in reversed(preds):
            if p.get('correct'):
                if streak >= 0:
                    streak += 1
                else:
                    break
            else:
                if streak <= 0:
                    streak -= 1
                else:
                    break

        # 趨勢：前半 vs 後半的命中率
        if total >= 10:
            half = total // 2
            first_half_rate = sum(1 for p in preds[:half] if p.get('correct')) / half
            second_half_rate = sum(1 for p in preds[half:] if p.get('correct')) / (total - half)
            if second_half_rate > first_half_rate + 0.05:
                trend = "improving"
            elif second_half_rate < first_half_rate - 0.05:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "insufficient_data"

        stats[mid] = {
            'total': total,
            'correct': correct,
            'wrong': wrong,
            'win_rate': correct / total * 100 if total > 0 else 0,
            'avg_return': sum(returns) / len(returns) if returns else 0,
            'recent_correct': recent_correct,
            'recent_wrong': recent_wrong,
            'recent_win_rate': recent_correct / len(recent) * 100 if recent else 0,
            'streak': streak,
            'trend': trend,
            'returns': returns,
        }

    return stats


# =====================================================================
# ② 調權重：升級/降級/淘汰
# =====================================================================

def adjust_model_weights(
    stats: dict[str, dict],
    rules: list[dict],
) -> tuple[list[dict], list[dict]]:
    """
    根據績效調整模型權重。

    回傳：(更新後的規則列表, 調整紀錄列表)
    """
    adjustments: list[dict] = []
    updated_rules = copy.deepcopy(rules)

    # 建立 model_id → 規則的映射
    # surviving_rules 裡的規則沒有 model_id，用 features+direction+hold 做 key
    # predictions_log 裡的是固定模型（A1~D3），跟 surviving_rules 不同系統
    # 這裡同時處理兩套

    for mid, s in stats.items():
        if s['total'] < MIN_SAMPLES:
            continue  # 樣本不足，不調

        current_weight = 1.0  # 預設權重

        # 判斷動作
        action = "HOLD"
        reason = ""
        new_weight = current_weight

        # 淘汰條件
        if s['recent_win_rate'] < ELIMINATE_RATE * 100 and len(stats) > 3:
            action = "ELIMINATE"
            reason = f"近期命中率 {s['recent_win_rate']:.1f}% < {ELIMINATE_RATE*100:.0f}% 門檻"
            new_weight = 0

        # 降級條件（連錯 or 持續下滑）
        elif s['streak'] <= -DEMOTE_STREAK:
            action = "DEMOTE"
            reason = f"連錯 {abs(s['streak'])} 次"
            new_weight = max(WEIGHT_MIN, current_weight * WEIGHT_DOWN)

        elif s['trend'] == 'declining' and s['recent_win_rate'] < 50:
            action = "DEMOTE"
            reason = f"趨勢下滑且近期命中率 {s['recent_win_rate']:.1f}%"
            new_weight = max(WEIGHT_MIN, current_weight * WEIGHT_DOWN)

        # 升級條件（連對 or 持續上升）
        elif s['streak'] >= PROMOTE_STREAK:
            action = "PROMOTE"
            reason = f"連對 {s['streak']} 次"
            new_weight = min(WEIGHT_MAX, current_weight * WEIGHT_UP)

        elif s['recent_win_rate'] >= PROMOTE_RATE * 100 and s['trend'] != 'declining':
            action = "PROMOTE"
            reason = f"近期命中率 {s['recent_win_rate']:.1f}% 優秀"
            new_weight = min(WEIGHT_MAX, current_weight * WEIGHT_UP)

        if action != "HOLD":
            adjustments.append({
                'date': TODAY,
                'model_id': mid,
                'action': action,
                'reason': reason,
                'old_weight': round(current_weight, 3),
                'new_weight': round(new_weight, 3),
                'stats_snapshot': {
                    'total': s['total'],
                    'win_rate': round(s['win_rate'], 1),
                    'recent_win_rate': round(s['recent_win_rate'], 1),
                    'streak': s['streak'],
                    'trend': s['trend'],
                    'avg_return': round(s['avg_return'], 3),
                },
            })

    return updated_rules, adjustments


# =====================================================================
# ③ 調信號信心度
# =====================================================================

def adjust_signal_confidence(
    predictions: list[dict],
) -> tuple[dict[str, float], list[dict]]:
    """
    根據各信號類型的歷史表現，調整信心度。

    分析每種信號出現時的平均命中率，
    命中率高的信號 → 提高信心度，
    命中率低的信號 → 降低信心度。

    回傳：(信號信心度 dict, 調整紀錄)
    """
    # 載入現有信心度（或用預設值）
    default_confidence = {
        'TARIFF': 0.70,
        'DEAL': 0.65,
        'RELIEF': 0.60,
        'ACTION': 0.75,
        'THREAT': 0.55,
        'CHINA': 0.60,
        'IRAN': 0.55,
        'TARIFF_ONLY': 0.70,
        'DEAL_ONLY': 0.65,
    }

    if SIGNAL_CONFIDENCE.exists():
        with open(SIGNAL_CONFIDENCE, encoding='utf-8') as f:
            current = json.load(f)
    else:
        current = copy.deepcopy(default_confidence)

    # 分析每個信號出現時的命中率
    # predictions_log 的 day_summary 裡有哪些信號被觸發
    signal_performance: dict[str, dict] = defaultdict(lambda: {'correct': 0, 'total': 0})

    for p in predictions:
        if p.get('status') != 'VERIFIED':
            continue

        # 從 model_id 推斷信號類型
        mid = p.get('model_id', '')
        signals_implied = []

        if 'tariff' in mid.lower():
            signals_implied.append('TARIFF')
        if 'deal' in mid.lower():
            signals_implied.append('DEAL')
        if 'relief' in mid.lower():
            signals_implied.append('RELIEF')
        if 'action' in mid.lower():
            signals_implied.append('ACTION')

        # 從 day_summary 提取更多
        summary = p.get('day_summary', {})
        if summary.get('burst_then_silence'):
            signals_implied.append('ACTION')

        for sig in signals_implied:
            signal_performance[sig]['total'] += 1
            if p.get('correct'):
                signal_performance[sig]['correct'] += 1

    # 調整信心度
    adjustments: list[dict] = []
    new_confidence = copy.deepcopy(current)

    for sig, perf in signal_performance.items():
        if perf['total'] < MIN_SAMPLES:
            continue

        hit_rate = perf['correct'] / perf['total']
        old_conf = current.get(sig, 0.5)

        # 高於 60% → 微升，低於 45% → 微降
        if hit_rate > 0.60:
            delta = min(CONFIDENCE_ADJUST, (hit_rate - 0.60) * 0.5)
            new_conf = min(0.95, old_conf + delta)
        elif hit_rate < 0.45:
            delta = min(CONFIDENCE_ADJUST, (0.45 - hit_rate) * 0.5)
            new_conf = max(0.20, old_conf - delta)
        else:
            new_conf = old_conf  # 中間地帶不動

        if abs(new_conf - old_conf) > 0.001:
            new_confidence[sig] = round(new_conf, 3)
            adjustments.append({
                'date': TODAY,
                'signal': sig,
                'old_confidence': round(old_conf, 3),
                'new_confidence': round(new_conf, 3),
                'hit_rate': round(hit_rate * 100, 1),
                'samples': perf['total'],
            })

    return new_confidence, adjustments


# =====================================================================
# ④ 學習報告
# =====================================================================

def generate_learning_report(
    stats: dict[str, dict],
    weight_adjustments: list[dict],
    signal_adjustments: list[dict],
) -> dict[str, Any]:
    """產出人話學習報告。"""

    # 排行榜
    ranked = sorted(
        stats.items(),
        key=lambda x: (x[1]['recent_win_rate'], x[1]['avg_return']),
        reverse=True,
    )

    # 三語摘要
    n_promote = sum(1 for a in weight_adjustments if a['action'] == 'PROMOTE')
    n_demote = sum(1 for a in weight_adjustments if a['action'] == 'DEMOTE')
    n_eliminate = sum(1 for a in weight_adjustments if a['action'] == 'ELIMINATE')

    best = ranked[0] if ranked else ('N/A', {'recent_win_rate': 0})
    worst = ranked[-1] if ranked else ('N/A', {'recent_win_rate': 0})

    report = {
        'date': TODAY,
        'generated_at': NOW,
        'total_models': len(stats),
        'total_verified': sum(s['total'] for s in stats.values()),

        'ranking': [
            {
                'rank': i + 1,
                'model_id': mid,
                'win_rate': round(s['win_rate'], 1),
                'recent_win_rate': round(s['recent_win_rate'], 1),
                'streak': s['streak'],
                'trend': s['trend'],
                'total': s['total'],
                'avg_return': round(s['avg_return'], 3),
            }
            for i, (mid, s) in enumerate(ranked)
        ],

        'adjustments': {
            'weights': weight_adjustments,
            'signals': signal_adjustments,
            'summary': {
                'promoted': n_promote,
                'demoted': n_demote,
                'eliminated': n_eliminate,
                'signal_adjusted': len(signal_adjustments),
            },
        },

        'summary': {
            'en': (
                f"Learning Report — {TODAY}\n"
                f"Models: {len(stats)} | Verified: {sum(s['total'] for s in stats.values())}\n"
                f"Best: {best[0]} ({best[1]['recent_win_rate']:.1f}% recent)\n"
                f"Worst: {worst[0]} ({worst[1]['recent_win_rate']:.1f}% recent)\n"
                f"Actions: {n_promote} promoted, {n_demote} demoted, {n_eliminate} eliminated\n"
                f"Signal adjustments: {len(signal_adjustments)}"
            ),
            'zh': (
                f"學習報告 — {TODAY}\n"
                f"模型數: {len(stats)} | 已驗證: {sum(s['total'] for s in stats.values())} 筆\n"
                f"最強: {best[0]}（近期 {best[1]['recent_win_rate']:.1f}%）\n"
                f"最弱: {worst[0]}（近期 {worst[1]['recent_win_rate']:.1f}%）\n"
                f"調整: {n_promote} 升級 / {n_demote} 降級 / {n_eliminate} 淘汰\n"
                f"信號信心度調整: {len(signal_adjustments)} 項"
            ),
            'ja': (
                f"学習レポート — {TODAY}\n"
                f"モデル数: {len(stats)} | 検証済み: {sum(s['total'] for s in stats.values())}件\n"
                f"最強: {best[0]}（直近 {best[1]['recent_win_rate']:.1f}%）\n"
                f"最弱: {worst[0]}（直近 {worst[1]['recent_win_rate']:.1f}%）\n"
                f"調整: {n_promote}昇格 / {n_demote}降格 / {n_eliminate}除外\n"
                f"シグナル信頼度調整: {len(signal_adjustments)}件"
            ),
        },
    }

    return report


# =====================================================================
# ⑤ 暴力規則的學習（surviving_rules × prediction_history）
# =====================================================================

def _make_rule_id(rule: dict) -> str:
    """
    用規則的 features+direction+hold 生成唯一 ID。
    例: "SHORT_3d_both_tariff_and_deal+kw_disaster+kw_jobs"
    """
    feats = '+'.join(sorted(rule.get('features', [])))
    direction = rule.get('direction', 'LONG')
    hold = rule.get('hold', 1)
    return f"{direction}_{hold}d_{feats}"


def learn_surviving_rules() -> tuple[list[dict], list[dict]]:
    """
    學習暴力搜索的存活規則。

    流程：
      1. 載入 surviving_rules（500 條）
      2. 載入 prediction_history（每日預測的驗證紀錄）
      3. 給每條規則算命中率
      4. 調整權重：好的升級，爛的降級/淘汰
      5. 輸出加權後的規則（rules_weighted.json）

    回傳：(更新後的規則列表, 調整紀錄)
    """
    if not SURVIVING_RULES.exists():
        log("   surviving_rules.json 不存在，跳過暴力規則學習")
        return [], []

    with open(SURVIVING_RULES, encoding='utf-8') as f:
        data = json.load(f)
    rules = data.get('rules', [])

    if not rules:
        return [], []

    # 給每條規則加上 ID 和初始權重（如果還沒有的話）
    for r in rules:
        if 'id' not in r:
            r['id'] = _make_rule_id(r)
        if 'weight' not in r:
            r['weight'] = 1.0
        if 'learn_stats' not in r:
            r['learn_stats'] = {'correct': 0, 'wrong': 0, 'streak': 0}

    # 載入預測歷史
    if PREDICTION_HISTORY.exists():
        with open(PREDICTION_HISTORY, encoding='utf-8') as f:
            history = json.load(f)
    else:
        history = []

    # 建立 rule_id → 驗證紀錄的映射
    rule_records: dict[str, list[dict]] = defaultdict(list)
    for pred in history:
        if pred.get('status') != 'VERIFIED':
            continue
        # 從 features 重建 rule_id
        rid = _make_rule_id(pred)
        rule_records[rid].append(pred)

    # 對每條規則計算績效並調整權重
    adjustments: list[dict] = []
    rules_with_data = 0

    for r in rules:
        rid = r['id']
        records = rule_records.get(rid, [])

        if not records:
            continue  # 還沒有被驗證過，不動

        rules_with_data += 1

        # 最近 ROLLING_WINDOW 筆
        records.sort(key=lambda p: p.get('signal_date', '') or p.get('entry_date', ''))
        recent = records[-ROLLING_WINDOW:]
        correct = sum(1 for p in recent if p.get('correct'))
        wrong = len(recent) - correct
        win_rate = correct / len(recent) * 100

        # 計算連勝/連敗
        streak = 0
        for p in reversed(recent):
            if p.get('correct'):
                if streak >= 0:
                    streak += 1
                else:
                    break
            else:
                if streak <= 0:
                    streak -= 1
                else:
                    break

        # 更新統計
        r['learn_stats'] = {
            'correct': correct,
            'wrong': wrong,
            'total_verified': len(records),
            'recent_win_rate': round(win_rate, 1),
            'streak': streak,
        }

        old_weight = r['weight']
        action = 'HOLD'
        reason = ''

        # 淘汰
        if len(recent) >= MIN_SAMPLES and win_rate < ELIMINATE_RATE * 100:
            action = 'ELIMINATE'
            reason = f"命中率 {win_rate:.0f}% < {ELIMINATE_RATE*100:.0f}%（{correct}/{len(recent)}）"
            r['weight'] = 0

        # 降級
        elif streak <= -DEMOTE_STREAK:
            action = 'DEMOTE'
            reason = f"連錯 {abs(streak)} 次"
            r['weight'] = max(WEIGHT_MIN, old_weight * WEIGHT_DOWN)

        # 升級
        elif streak >= PROMOTE_STREAK:
            action = 'PROMOTE'
            reason = f"連對 {streak} 次"
            r['weight'] = min(WEIGHT_MAX, old_weight * WEIGHT_UP)

        elif len(recent) >= MIN_SAMPLES and win_rate >= PROMOTE_RATE * 100:
            action = 'PROMOTE'
            reason = f"命中率 {win_rate:.0f}%（{correct}/{len(recent)}）"
            r['weight'] = min(WEIGHT_MAX, old_weight * WEIGHT_UP)

        if action != 'HOLD':
            adjustments.append({
                'date': TODAY,
                'rule_id': rid,
                'action': action,
                'reason': reason,
                'old_weight': round(old_weight, 3),
                'new_weight': round(r['weight'], 3),
                'features': r.get('features', []),
                'win_rate': round(win_rate, 1),
                'streak': streak,
                'samples': len(recent),
            })

    # 淘汰 weight=0 的規則
    eliminated = [r for r in rules if r.get('weight', 1) <= 0]
    active_rules = [r for r in rules if r.get('weight', 1) > 0]

    # 按 weight 降序排列
    active_rules.sort(key=lambda r: r.get('weight', 1), reverse=True)

    log(f"   暴力規則: {len(rules)} 條 → 有驗證數據 {rules_with_data} 條")
    log(f"   淘汰 {len(eliminated)} 條 | 存活 {len(active_rules)} 條")

    # 存檔
    weighted_data = {
        'meta': {
            'updated_at': NOW,
            'total_rules': len(active_rules),
            'eliminated': len(eliminated),
            'rules_with_data': rules_with_data,
        },
        'rules': active_rules,
    }

    with open(RULES_WEIGHTED, 'w', encoding='utf-8') as f:
        json.dump(weighted_data, f, ensure_ascii=False, indent=2)

    # 也更新 surviving_rules.json（保持 active 的）
    data['rules'] = active_rules
    data['meta']['last_learning'] = NOW
    data['meta']['eliminated_count'] = data['meta'].get('eliminated_count', 0) + len(eliminated)
    with open(SURVIVING_RULES, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return active_rules, adjustments


# =====================================================================
# ⑥ 主流程
# =====================================================================

def run_learning_cycle() -> dict[str, Any]:
    """
    執行一次完整的學習循環。

    步驟：
      1. 載入預測紀錄
      2. 計算每個模型的績效
      3. 調整模型權重
      4. 調整信號信心度
      5. 產出學習報告
      6. 儲存所有調整
    """
    log("=" * 60)
    log(f"閉環學習循環 — {TODAY}")
    log("=" * 60)

    # 1. 載入數據
    if not PREDICTIONS_LOG.exists():
        log("⚠️ predictions_log.json 不存在，跳過學習")
        return {'error': 'no predictions log'}

    with open(PREDICTIONS_LOG, encoding='utf-8') as f:
        predictions = json.load(f)

    verified = [p for p in predictions if p.get('status') == 'VERIFIED']
    log(f"① 載入 {len(predictions)} 筆預測（{len(verified)} 筆已驗證）")

    if len(verified) < MIN_SAMPLES:
        log(f"⚠️ 已驗證不足 {MIN_SAMPLES} 筆，跳過學習")
        return {'error': 'insufficient verified predictions'}

    # 2. 算成績
    stats = compute_model_stats(predictions)
    log(f"② 分析了 {len(stats)} 個模型的績效")

    for mid in sorted(stats.keys()):
        s = stats[mid]
        streak_icon = "🔥" if s['streak'] >= PROMOTE_STREAK else ("💀" if s['streak'] <= -DEMOTE_STREAK else "")
        trend_icon = "📈" if s['trend'] == 'improving' else ("📉" if s['trend'] == 'declining' else "")
        log(f"   {mid:<25s} | 命中 {s['win_rate']:5.1f}% | 近期 {s['recent_win_rate']:5.1f}% | "
            f"連{'對' if s['streak']>0 else '錯'} {abs(s['streak'])} | {s['trend']} {streak_icon}{trend_icon}")

    # 3. 調權重
    rules = []
    if SURVIVING_RULES.exists():
        with open(SURVIVING_RULES, encoding='utf-8') as f:
            rules_data = json.load(f)
        rules = rules_data.get('rules', [])

    updated_rules, weight_adj = adjust_model_weights(stats, rules)
    log(f"③ 權重調整: {len(weight_adj)} 項")
    for adj in weight_adj:
        emoji = {"PROMOTE": "⬆️", "DEMOTE": "⬇️", "ELIMINATE": "🗑️"}.get(adj['action'], "")
        log(f"   {emoji} {adj['model_id']}: {adj['action']} — {adj['reason']}")

    # 4. 調信號信心度
    new_confidence, signal_adj = adjust_signal_confidence(predictions)
    log(f"④ 信號信心度調整: {len(signal_adj)} 項")
    for adj in signal_adj:
        direction = "⬆️" if adj['new_confidence'] > adj['old_confidence'] else "⬇️"
        log(f"   {direction} {adj['signal']}: {adj['old_confidence']:.2f} → {adj['new_confidence']:.2f} "
            f"（命中率 {adj['hit_rate']:.1f}%, 樣本 {adj['samples']}）")

    # 5. 暴力規則學習
    log(f"⑤ 暴力規則學習...")
    active_rules, rule_adj = learn_surviving_rules()
    rule_promote = sum(1 for a in rule_adj if a['action'] == 'PROMOTE')
    rule_demote = sum(1 for a in rule_adj if a['action'] == 'DEMOTE')
    rule_eliminate = sum(1 for a in rule_adj if a['action'] == 'ELIMINATE')
    if rule_adj:
        for adj in rule_adj[:10]:  # 只顯示前 10 條
            emoji = {"PROMOTE": "⬆️", "DEMOTE": "⬇️", "ELIMINATE": "🗑️"}.get(adj['action'], "")
            feats = ' + '.join(adj.get('features', [])[:3])
            log(f"   {emoji} [{adj['action']}] {feats}... — {adj['reason']}")
        if len(rule_adj) > 10:
            log(f"   ...還有 {len(rule_adj) - 10} 條調整")

    # 合併所有調整
    all_weight_adj = weight_adj + rule_adj

    # 6. 產出報告
    report = generate_learning_report(stats, all_weight_adj, signal_adj)
    log(f"⑥ 學習報告產出完成")
    print()
    print(report['summary']['zh'])

    # 7. 儲存
    # 學習報告
    report_file = DATA / 'learning_report.json'
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 學習歷史（累積）
    learning_history: list[dict] = []
    if LEARNING_LOG.exists():
        with open(LEARNING_LOG, encoding='utf-8') as f:
            learning_history = json.load(f)

    learning_history.append({
        'date': TODAY,
        'weight_adjustments': weight_adj,
        'signal_adjustments': signal_adj,
        'model_stats_snapshot': {
            mid: {
                'win_rate': round(s['win_rate'], 1),
                'recent_win_rate': round(s['recent_win_rate'], 1),
                'streak': s['streak'],
                'trend': s['trend'],
            }
            for mid, s in stats.items()
        },
    })
    with open(LEARNING_LOG, 'w', encoding='utf-8') as f:
        json.dump(learning_history, f, ensure_ascii=False, indent=2)

    # 信號信心度
    with open(SIGNAL_CONFIDENCE, 'w', encoding='utf-8') as f:
        json.dump(new_confidence, f, ensure_ascii=False, indent=2)

    # 8. 規則進化（每天嘗試產生新規則）
    log("⑧ 規則進化...")
    try:
        from rule_evolver import evolve
        evo_result = evolve()
        if evo_result and not evo_result.get('error'):
            log(f"   進化完成: 新增 {evo_result.get('total_new', 0)} 條規則")
        else:
            log(f"   進化跳過: {evo_result.get('error', '?')}")
            if evo_result.get('tip'):
                log(f"   💡 {evo_result['tip']}")
    except ImportError:
        log("   rule_evolver 未安裝，跳過進化")
    except Exception as e:
        log(f"   進化失敗（不影響學習）: {e}")

    log("=" * 60)
    log("✅ 學習循環完成")
    log("=" * 60)

    return report


# =====================================================================
# 入口
# =====================================================================

if __name__ == '__main__':
    report = run_learning_cycle()
