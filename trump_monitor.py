#!/usr/bin/env python3
"""
川普密碼 — 即時監控 + 多組預測引擎
每 5 分鐘抓最新推文，跑 12 組預測模型，追蹤哪組命中

用法:
  python3 trump_monitor.py              # 即時監控（持續運行）
  python3 trump_monitor.py --backtest   # 用歷史資料回測所有預測組
  python3 trump_monitor.py --status     # 看目前各組預測命中率
"""

import json
import csv
import re
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.csv"
PREDICTIONS_FILE = BASE / "predictions_log.json"
SCORES_FILE = BASE / "prediction_scores.json"
ALERTS_FILE = BASE / "alerts_log.json"
LAST_POST_FILE = BASE / "last_seen_post.txt"

# ============================================================
# 信號分類器
# ============================================================

def classify_signals(content):
    """把一篇貼文分類成多種信號"""
    cl = content.lower()
    signals = set()

    # 政策信號
    if any(w in cl for w in ['tariff', 'tariffs', 'duty', 'duties', 'reciprocal']):
        signals.add('TARIFF')
    if any(w in cl for w in ['deal', 'agreement', 'negotiate', 'talks', 'signed']):
        signals.add('DEAL')
    if any(w in cl for w in ['pause', 'delay', 'exempt', 'exception', 'suspend', 'postpone']):
        signals.add('RELIEF')
    if any(w in cl for w in ['immediately', 'effective', 'hereby', 'executive order', 'just signed', 'i have directed']):
        signals.add('ACTION')
    if any(w in cl for w in ['ban', 'block', 'restrict', 'sanction', 'punish']):
        signals.add('THREAT')

    # 情緒信號
    if any(w in cl for w in ['stock market', 'all time high', 'record high', 'dow', 'nasdaq', 'market up']):
        signals.add('MARKET_BRAG')
    if any(w in cl for w in ['fake news', 'corrupt', 'fraud', 'witch hunt', 'disgrace', 'hoax']):
        signals.add('ATTACK')
    if any(w in cl for w in ['great', 'tremendous', 'incredible', 'historic', 'beautiful', 'amazing']):
        signals.add('POSITIVE')

    # 地緣信號
    if any(w in cl for w in ['china', 'chinese', 'beijing', 'xi jinping']):
        signals.add('CHINA')
    if any(w in cl for w in ['iran', 'iranian', 'tehran']):
        signals.add('IRAN')
    if any(w in cl for w in ['russia', 'russian', 'putin', 'ukraine', 'zelensky']):
        signals.add('RUSSIA')

    # 新密碼追蹤
    if 'save america act' in cl:
        signals.add('NEW_SAVE_ACT')
    if 'president djt' in cl:
        signals.add('SIG_DJT')
    if 'president of the united states' in cl:
        signals.add('SIG_POTUS')
    if 'thank you for your attention' in cl:
        signals.add('SIG_TYFA')

    return signals


def est_hour(utc_str):
    dt = datetime.fromisoformat(utc_str.replace('Z', '+00:00'))
    return (dt.hour - 5) % 24, dt.minute


def market_session(utc_str):
    h, m = est_hour(utc_str)
    if h < 9 or (h == 9 and m < 30):
        return 'PRE_MARKET'
    elif h < 16:
        return 'MARKET_OPEN'
    elif h < 20:
        return 'AFTER_HOURS'
    else:
        return 'OVERNIGHT'


def emotion_score(content):
    score = 0
    upper = sum(1 for c in content if c.isupper())
    total = sum(1 for c in content if c.isalpha())
    score += (upper / max(total, 1)) * 30
    score += min(content.count('!') / max(len(content), 1) * 1000, 25)
    caps_words = len(re.findall(r'\b[A-Z]{3,}\b', content))
    score += min(caps_words * 2, 20)
    return min(round(score, 1), 100)


# ============================================================
# 12 組預測模型
# ============================================================

class PredictionEngine:
    """多組預測模型同時運行"""

    def __init__(self):
        self.models = {
            # --- A 組：單信號模型 ---
            'A1_tariff_bearish': {
                'name': '盤中關稅→隔天跌',
                'desc': '盤中出現 TARIFF 信號 ≥2 次 → 預測隔天 S&P 收跌',
                'direction': 'SHORT',
                'hold': 1,
                'trigger': self._trigger_a1,
            },
            'A2_deal_bullish': {
                'name': 'DEAL 出現→隔天漲',
                'desc': '出現 DEAL 信號且無 TARIFF → 預測隔天 S&P 收漲',
                'direction': 'LONG',
                'hold': 1,
                'trigger': self._trigger_a2,
            },
            'A3_relief_rocket': {
                'name': '盤前 RELIEF→當天飆',
                'desc': '盤前出現暫緩/豁免 → 預測當天 S&P 大漲',
                'direction': 'LONG',
                'hold': 0,  # 0 = 當天
                'trigger': self._trigger_a3,
            },

            # --- B 組：多信號組合模型 ---
            'B1_triple_signal': {
                'name': '三信號齊發→買3天',
                'desc': 'TARIFF+DEAL+RELIEF 同天 → 底部信號，3 天內漲',
                'direction': 'LONG',
                'hold': 3,
                'trigger': self._trigger_b1,
            },
            'B2_tariff_to_deal': {
                'name': '連3天關稅→出現Deal→轉折',
                'desc': '連續 3 天 TARIFF 後出現 DEAL → 轉折買入',
                'direction': 'LONG',
                'hold': 2,
                'trigger': self._trigger_b2,
            },
            'B3_action_pre': {
                'name': '盤前 ACTION+正面情緒→漲',
                'desc': '盤前簽署行政命令 + 正面情緒 → 看多',
                'direction': 'LONG',
                'hold': 1,
                'trigger': self._trigger_b3,
            },

            # --- C 組：行為異常模型 ---
            'C1_burst_silence': {
                'name': '轟炸→長沉默→做多',
                'desc': '1 小時 ≥5 篇後沉默 ≥3 小時 → 波動率上升',
                'direction': 'LONG',
                'hold': 1,
                'trigger': self._trigger_c1,
            },
            'C2_brag_top': {
                'name': '炫耀股市→短期到頂',
                'desc': '一天炫耀股市 ≥3 次 → 短期高點',
                'direction': 'SHORT',
                'hold': 2,
                'trigger': self._trigger_c2,
            },
            'C3_night_alert': {
                'name': '深夜關稅推文→開盤跳空',
                'desc': '深夜/凌晨提關稅 → 隔天開盤跳空',
                'direction': 'SHORT',
                'hold': 1,
                'trigger': self._trigger_c3,
            },

            # --- D 組：換碼偵測模型 ---
            'D1_new_phrase': {
                'name': '新口號出現→波動加大',
                'desc': '出現過去 30 天沒出現過的新政策詞彙 → 波動率上升',
                'direction': 'VOLATILE',
                'hold': 3,
                'trigger': self._trigger_d1,
            },
            'D2_sig_change': {
                'name': '簽名切換→正式聲明',
                'desc': '使用 POTUS 級簽名 → 重大政策即將落地',
                'direction': 'VOLATILE',
                'hold': 2,
                'trigger': self._trigger_d2,
            },
            'D3_volume_spike': {
                'name': '發文量暴增→恐慌底部',
                'desc': '日發文量 > 過去7天均值×2 → 恐慌極值',
                'direction': 'LONG',
                'hold': 3,
                'trigger': self._trigger_d3,
            },
        }

        # 各模型累計成績
        self.scores = self._load_scores()
        # 歷史上下文
        self.context = {
            'prev_days': [],    # 前 7 天的每日摘要
            'recent_phrases': set(),  # 近 30 天出現過的 phrase
        }

    def _load_scores(self):
        if SCORES_FILE.exists():
            with open(SCORES_FILE) as f:
                return json.load(f)
        return {m: {'predictions': 0, 'correct': 0, 'wrong': 0, 'pending': 0,
                     'total_return': 0, 'trades': []}
                for m in self.models}

    def save_scores(self):
        with open(SCORES_FILE, 'w') as f:
            json.dump(self.scores, f, ensure_ascii=False, indent=2)

    # --- 觸發條件 ---

    def _trigger_a1(self, day_summary):
        """盤中 TARIFF ≥2"""
        return day_summary.get('open_tariff', 0) >= 2

    def _trigger_a2(self, day_summary):
        """DEAL 出現且 TARIFF=0"""
        return day_summary.get('deal', 0) >= 1 and day_summary.get('tariff', 0) == 0

    def _trigger_a3(self, day_summary):
        """盤前 RELIEF"""
        return day_summary.get('pre_relief', 0) >= 1

    def _trigger_b1(self, day_summary):
        """三信號齊發"""
        return (day_summary.get('tariff', 0) >= 1 and
                day_summary.get('deal', 0) >= 1 and
                day_summary.get('relief', 0) >= 1)

    def _trigger_b2(self, day_summary):
        """連3天TARIFF後出現DEAL"""
        prev = self.context.get('prev_days', [])
        if len(prev) < 3:
            return False
        streak = all(d.get('tariff', 0) >= 1 for d in prev[-3:])
        return streak and day_summary.get('deal', 0) >= 1

    def _trigger_b3(self, day_summary):
        """盤前ACTION + 正面"""
        return (day_summary.get('pre_action', 0) >= 1 and
                day_summary.get('positive', 0) >= 2)

    def _trigger_c1(self, day_summary):
        """轟炸後沉默"""
        return day_summary.get('burst_then_silence', False)

    def _trigger_c2(self, day_summary):
        """炫耀股市 ≥3"""
        return day_summary.get('market_brag', 0) >= 3

    def _trigger_c3(self, day_summary):
        """深夜關稅"""
        return day_summary.get('night_tariff', 0) >= 1

    def _trigger_d1(self, day_summary):
        """新口號出現"""
        return day_summary.get('new_phrase_detected', False)

    def _trigger_d2(self, day_summary):
        """POTUS 級簽名"""
        return day_summary.get('sig_potus', 0) >= 1

    def _trigger_d3(self, day_summary):
        """發文量暴增"""
        prev = self.context.get('prev_days', [])
        if len(prev) < 7:
            return False
        avg = sum(d.get('post_count', 0) for d in prev[-7:]) / 7
        return avg > 0 and day_summary.get('post_count', 0) > avg * 2

    def run_predictions(self, day_summary, date):
        """對今天的數據跑所有模型，產生預測"""
        predictions = []

        for model_id, model in self.models.items():
            try:
                if model['trigger'](day_summary):
                    pred = {
                        'model_id': model_id,
                        'model_name': model['name'],
                        'date_signal': date,
                        'direction': model['direction'],
                        'hold_days': model['hold'],
                        'status': 'PENDING',
                        'created_at': datetime.utcnow().isoformat() + 'Z',
                        'day_summary': {k: v for k, v in day_summary.items()
                                       if not isinstance(v, (set, list))},
                    }
                    predictions.append(pred)

                    # 更新計分
                    if model_id not in self.scores:
                        self.scores[model_id] = {
                            'predictions': 0, 'correct': 0, 'wrong': 0,
                            'pending': 0, 'total_return': 0, 'trades': []
                        }
                    self.scores[model_id]['predictions'] += 1
                    self.scores[model_id]['pending'] += 1

            except Exception as e:
                pass

        return predictions


# ============================================================
# 資料抓取
# ============================================================

def fetch_latest_posts(limit=50):
    """從 CNN Archive 抓最新推文"""
    try:
        req = urllib.request.Request(ARCHIVE_URL)
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode('utf-8')

        reader = csv.DictReader(content.splitlines())
        rows = list(reader)

        # 只取最新 N 篇有文字、非 RT 的
        results = []
        for row in rows[:limit * 3]:
            if row['content'].strip() and not row['content'].strip().startswith('RT @'):
                results.append({
                    'id': row['id'],
                    'created_at': row['created_at'],
                    'content': row['content'],
                    'url': row.get('url', ''),
                })
            if len(results) >= limit:
                break

        return results

    except Exception as e:
        print(f"  ⚠️ 抓取失敗: {e}")
        return []


def summarize_day(day_posts):
    """把一天的推文彙整成 day_summary"""
    summary = defaultdict(int)
    summary['post_count'] = len(day_posts)
    summary['contents'] = []

    intervals = []
    burst_then_silence = False

    for i, p in enumerate(day_posts):
        content = p['content']
        signals = classify_signals(content)
        session = market_session(p['created_at'])
        h, m = est_hour(p['created_at'])

        for sig in signals:
            summary[sig.lower()] += 1
            if session == 'PRE_MARKET':
                summary[f'pre_{sig.lower()}'] += 1
            elif session == 'MARKET_OPEN':
                summary[f'open_{sig.lower()}'] += 1

        # 深夜推文
        if h < 5 or h >= 23:
            if 'TARIFF' in signals:
                summary['night_tariff'] += 1

        summary['emotion_sum'] += emotion_score(content)
        summary['contents'].append(content[:80])

        # 計算間隔
        if i > 0:
            dt1 = datetime.fromisoformat(day_posts[i-1]['created_at'].replace('Z', '+00:00'))
            dt2 = datetime.fromisoformat(p['created_at'].replace('Z', '+00:00'))
            gap = (dt2 - dt1).total_seconds() / 60
            intervals.append(gap)

    # 偵測轟炸→沉默
    if intervals:
        burst_count = sum(1 for g in intervals if g < 5)
        silence = max(intervals) if intervals else 0
        if burst_count >= 3 and silence >= 180:
            summary['burst_then_silence'] = True

    # 簽名偵測
    for p in day_posts:
        c = p['content']
        if 'PRESIDENT OF THE UNITED STATES' in c:
            summary['sig_potus'] += 1
        if 'President DJT' in c:
            summary['sig_djt'] += 1

    summary['avg_emotion'] = summary['emotion_sum'] / max(len(day_posts), 1)

    return dict(summary)


# ============================================================
# 回測模式
# ============================================================

def run_backtest():
    """用歷史資料回測所有 12 組預測模型"""
    print("=" * 90)
    print("🔬 回測模式：用歷史資料驗證 12 組預測模型")
    print("=" * 90)

    # 載入資料
    with open(BASE / "clean_president.json") as f:
        posts = json.load(f)

    with open(BASE / "market_SP500.json") as f:
        sp500 = json.load(f)

    sp_by_date = {r['date']: r for r in sp500}

    originals = sorted(
        [p for p in posts if p['has_text'] and not p['is_retweet']],
        key=lambda p: p['created_at']
    )

    # 按天分組
    daily_posts = defaultdict(list)
    for p in originals:
        daily_posts[p['created_at'][:10]].append(p)

    engine = PredictionEngine()
    all_predictions = []
    sorted_dates = sorted(daily_posts.keys())

    for idx, date in enumerate(sorted_dates):
        day_summary = summarize_day(daily_posts[date])

        # 更新上下文
        engine.context['prev_days'] = [
            summarize_day(daily_posts.get(sorted_dates[j], []))
            for j in range(max(0, idx-7), idx)
        ]

        # 跑預測
        preds = engine.run_predictions(day_summary, date)

        # 驗證預測
        for pred in preds:
            hold = pred['hold_days']
            direction = pred['direction']

            # 找入場/出場日
            td = date
            if td not in sp_by_date:
                dt = datetime.strptime(td, '%Y-%m-%d')
                for i in range(1, 5):
                    d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
                    if d in sp_by_date:
                        td = d
                        break
                else:
                    continue

            if hold == 0:
                # 當天
                if td in sp_by_date:
                    sp = sp_by_date[td]
                    ret = (sp['close'] - sp['open']) / sp['open'] * 100
                else:
                    continue
            else:
                # N天後
                entry_day = td
                exit_day = entry_day
                for _ in range(hold):
                    dt = datetime.strptime(exit_day, '%Y-%m-%d')
                    for i in range(1, 6):
                        d = (dt + timedelta(days=i)).strftime('%Y-%m-%d')
                        if d in sp_by_date:
                            exit_day = d
                            break

                if exit_day not in sp_by_date or entry_day not in sp_by_date:
                    continue

                entry_p = sp_by_date[entry_day]['open']
                exit_p = sp_by_date[exit_day]['close']
                ret = (exit_p - entry_p) / entry_p * 100

            # 判斷預測是否正確
            if direction == 'LONG':
                correct = ret > 0
            elif direction == 'SHORT':
                correct = ret < 0
            elif direction == 'VOLATILE':
                correct = abs(ret) > 0.5  # 波動超過 0.5%
            else:
                correct = False

            pred['actual_return'] = round(ret, 3)
            pred['correct'] = correct
            pred['status'] = 'VERIFIED'

            # 更新計分
            mid = pred['model_id']
            if mid in engine.scores:
                engine.scores[mid]['pending'] -= 1
                if correct:
                    engine.scores[mid]['correct'] += 1
                else:
                    engine.scores[mid]['wrong'] += 1
                engine.scores[mid]['total_return'] += ret
                engine.scores[mid]['trades'].append({
                    'date': date, 'return': round(ret, 3), 'correct': correct
                })

        all_predictions.extend(preds)

    # === 打印成績單 ===
    print(f"\n📊 12 組預測模型成績單")
    print(f"{'='*90}")
    print(f"  {'模型':4s} {'名稱':25s} | {'預測':>4s} | {'命中':>4s} | {'命中率':>6s} | {'平均報酬':>8s} | {'累積':>8s} | 判定")
    print(f"  {'-'*4} {'-'*25}-+-{'-'*4}-+-{'-'*4}-+-{'-'*6}-+-{'-'*8}-+-{'-'*8}-+-{'-'*6}")

    rankings = []
    for mid, model in engine.models.items():
        s = engine.scores.get(mid, {})
        total = s.get('predictions', 0)
        correct = s.get('correct', 0)
        wrong = s.get('wrong', 0)
        total_ret = s.get('total_return', 0)

        if total == 0:
            continue

        hit_rate = correct / total * 100 if total > 0 else 0
        avg_ret = total_ret / total if total > 0 else 0

        # 判定
        if hit_rate >= 60 and avg_ret > 0:
            verdict = "⭐有效"
        elif hit_rate >= 55:
            verdict = "🟡待觀察"
        elif hit_rate >= 50:
            verdict = "➡️中性"
        else:
            verdict = "❌無效"

        rankings.append((mid, model['name'], total, correct, hit_rate, avg_ret, total_ret, verdict))

    # 按命中率排序
    rankings.sort(key=lambda x: (-x[4], -x[5]))

    for mid, name, total, correct, hit_rate, avg_ret, total_ret, verdict in rankings:
        print(f"  {mid:4s} {name:25s} | {total:4d} | {correct:4d} | {hit_rate:5.1f}% | {avg_ret:+.3f}% | {total_ret:+.2f}% | {verdict}")

    # 存檔
    engine.save_scores()

    # 存所有預測
    with open(PREDICTIONS_FILE, 'w') as f:
        json.dump(all_predictions, f, ensure_ascii=False, indent=2)

    print(f"\n💾 預測記錄存入 {PREDICTIONS_FILE.name}")
    print(f"💾 成績存入 {SCORES_FILE.name}")

    # === 最佳組合 ===
    print(f"\n{'='*90}")
    print("🏆 最佳組合策略：取命中率 Top 3 模型同時確認才動手")
    print("=" * 90)

    top3 = [r[0] for r in rankings[:3]]
    print(f"  Top 3: {', '.join(top3)}")

    # 找三個模型同一天都觸發的日子
    pred_by_date = defaultdict(set)
    pred_ret_by_date = {}
    for p in all_predictions:
        if p.get('status') == 'VERIFIED':
            pred_by_date[p['date_signal']].add(p['model_id'])
            pred_ret_by_date[(p['date_signal'], p['model_id'])] = p.get('actual_return', 0)

    combo_days = []
    for date, models in pred_by_date.items():
        overlap = set(top3) & models
        if len(overlap) >= 2:  # 至少 2 個 Top 模型同意
            rets = [pred_ret_by_date.get((date, m), 0) for m in overlap]
            avg_r = sum(rets) / len(rets) if rets else 0
            combo_days.append((date, len(overlap), avg_r, overlap))

    if combo_days:
        combo_days.sort(key=lambda x: x[0])
        wins = sum(1 for _, _, r, _ in combo_days if r > 0)
        total_r = sum(r for _, _, r, _ in combo_days)
        avg_combo = total_r / len(combo_days)

        print(f"  同時觸發天數: {len(combo_days)}")
        print(f"  勝率: {wins/len(combo_days)*100:.1f}%")
        print(f"  平均報酬: {avg_combo:+.3f}%")
        print(f"\n  明細:")
        for date, n_models, ret, models in combo_days:
            arrow = "✅" if ret > 0 else "❌"
            print(f"    {date} | {n_models}模型同意 | {ret:+.3f}% {arrow} | {','.join(sorted(models))}")

    return engine


# ============================================================
# 即時監控模式
# ============================================================

def run_monitor():
    """即時監控（每 5 分鐘）"""
    print("=" * 90)
    print("🔴 川普密碼即時監控 — 啟動中")
    print(f"   更新頻率: 每 5 分鐘")
    print(f"   資料來源: CNN Truth Social Archive")
    print(f"   預測模型: 12 組同時運行")
    print("=" * 90)

    engine = PredictionEngine()

    # 讀取上次看到的最新推文
    last_seen = ""
    if LAST_POST_FILE.exists():
        last_seen = LAST_POST_FILE.read_text().strip()

    cycle = 0
    while True:
        cycle += 1
        now = datetime.utcnow()
        est_now = (now.hour - 5) % 24

        print(f"\n{'─'*60}")
        print(f"  ⏰ 第 {cycle} 輪 | UTC {now.strftime('%H:%M')} | EST {est_now:02d}:{now.minute:02d}")

        # 抓最新推文
        new_posts = fetch_latest_posts(20)
        if not new_posts:
            print("  ⚠️ 無法抓取，5 分鐘後重試")
            time.sleep(300)
            continue

        latest_id = new_posts[0]['id']
        latest_time = new_posts[0]['created_at']

        # 檢查是否有新推文
        if latest_id == last_seen:
            print(f"  💤 沒有新推文 (最新: {latest_time[:16]})")
            time.sleep(300)
            continue

        # 有新推文！
        new_count = 0
        for p in new_posts:
            if p['id'] == last_seen:
                break
            new_count += 1

        print(f"  🆕 發現 {new_count} 篇新推文！")

        # 顯示新推文
        for p in new_posts[:new_count]:
            signals = classify_signals(p['content'])
            session = market_session(p['created_at'])
            emo = emotion_score(p['content'])
            h, m = est_hour(p['created_at'])

            signal_str = ' '.join(f"[{s}]" for s in sorted(signals)) if signals else '(無信號)'

            print(f"\n  📝 EST {h:02d}:{m:02d} | {session} | 情緒:{emo:.0f}")
            print(f"     信號: {signal_str}")
            print(f"     內容: {p['content'][:120]}...")

        # 按今天分組彙整
        today = now.strftime('%Y-%m-%d')
        today_posts = [p for p in new_posts if p['created_at'][:10] == today]

        if today_posts:
            day_summary = summarize_day(today_posts)

            # 跑預測
            preds = engine.run_predictions(day_summary, today)

            if preds:
                print(f"\n  🎯 觸發 {len(preds)} 個預測模型:")
                for pred in preds:
                    dir_icon = {'LONG': '📈看多', 'SHORT': '📉看空', 'VOLATILE': '🌊波動'}
                    print(f"     [{pred['model_id']}] {pred['model_name']}")
                    print(f"       → {dir_icon.get(pred['direction'], '?')} | 持有 {pred['hold_days']} 天")
            else:
                print(f"\n  😴 今天暫無模型觸發")

        # 更新最新 ID
        last_seen = latest_id
        LAST_POST_FILE.write_text(latest_id)

        # 顯示各模型累計成績
        print(f"\n  📊 模型即時成績:")
        for mid, s in engine.scores.items():
            total = s['predictions']
            if total > 0:
                correct = s['correct']
                rate = correct / max(total - s['pending'], 1) * 100
                print(f"     {mid:20s} | {total}次 | 命中{rate:.0f}%")

        engine.save_scores()

        print(f"\n  ⏳ 等待 5 分鐘...")
        time.sleep(300)


# ============================================================
# 狀態查看
# ============================================================

def show_status():
    """顯示各模型目前成績"""
    print("=" * 90)
    print("📊 川普密碼 — 各模型預測成績")
    print("=" * 90)

    if not SCORES_FILE.exists():
        print("  尚未有成績，請先跑 --backtest")
        return

    with open(SCORES_FILE) as f:
        scores = json.load(f)

    engine = PredictionEngine()

    print(f"\n  {'模型':25s} | {'預測':>4s} | {'命中':>4s} | {'失敗':>4s} | {'命中率':>6s} | {'累積報酬':>8s}")
    print(f"  {'-'*25}-+-{'-'*4}-+-{'-'*4}-+-{'-'*4}-+-{'-'*6}-+-{'-'*8}")

    for mid, model in engine.models.items():
        s = scores.get(mid, {})
        total = s.get('predictions', 0)
        correct = s.get('correct', 0)
        wrong = s.get('wrong', 0)
        total_ret = s.get('total_return', 0)
        rate = correct / max(total - s.get('pending', 0), 1) * 100

        print(f"  {model['name']:25s} | {total:4d} | {correct:4d} | {wrong:4d} | {rate:5.1f}% | {total_ret:+.2f}%")


# ============================================================
# 主程式
# ============================================================

if __name__ == '__main__':
    if '--backtest' in sys.argv:
        run_backtest()
    elif '--status' in sys.argv:
        show_status()
    elif '--once' in sys.argv:
        # 只跑一次（不迴圈）
        print("🔍 單次掃描...")
        new_posts = fetch_latest_posts(30)
        if new_posts:
            today = new_posts[0]['created_at'][:10]
            today_posts = [p for p in new_posts if p['created_at'][:10] == today]
            day_summary = summarize_day(today_posts)

            engine = PredictionEngine()
            preds = engine.run_predictions(day_summary, today)

            print(f"\n📝 今天 ({today}) {len(today_posts)} 篇推文")
            print(f"🎯 觸發 {len(preds)} 個預測:")
            for pred in preds:
                dir_icon = {'LONG': '📈看多', 'SHORT': '📉看空', 'VOLATILE': '🌊波動'}
                print(f"   [{pred['model_id']}] {pred['model_name']} → {dir_icon.get(pred['direction'], '?')}")

            # 顯示今天的信號
            print(f"\n📊 今日信號:")
            for k, v in sorted(day_summary.items()):
                if isinstance(v, (int, float)) and v > 0 and k != 'post_count':
                    print(f"   {k}: {v}")
    else:
        run_monitor()
