#!/usr/bin/env python3
"""
川普密碼計畫 — 資料清洗腳本
從 CNN Truth Social Archive 下載原始資料，清洗後輸出乾淨版本

來源: https://ix.cnn.io/data/truth-social/truth_archive.csv
更新頻率: 每 5 分鐘
"""

import csv
import json
import html
import re
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
RAW_FILE = BASE_DIR / "raw_archive.csv"
CLEAN_CSV = BASE_DIR / "clean_all.csv"
CLEAN_JSON = BASE_DIR / "clean_all.json"
PRESIDENT_CSV = BASE_DIR / "clean_president.csv"  # 就任後
PRESIDENT_JSON = BASE_DIR / "clean_president.json"
STATS_FILE = BASE_DIR / "data_stats.json"

# 就任日期 (第二任)
INAUGURATION = "2025-01-20T00:00:00.000Z"


def fix_encoding(text: str) -> str:
    """修復 UTF-8 被當成 Latin-1 讀取造成的亂碼
    例如: â\x80\x9d → " (右引號)
         â\x80\x99 → ' (右撇號)
         â\x80\x94 → — (長破折號)
    """
    try:
        # 嘗試把被錯誤解碼的文字還原
        fixed = text.encode('latin-1').decode('utf-8')
        return fixed
    except (UnicodeDecodeError, UnicodeEncodeError):
        return text


def clean_content(raw: str) -> str:
    """清洗貼文內容"""
    text = raw

    # 步驟 1: 修復編碼問題
    text = fix_encoding(text)

    # 步驟 2: 解碼 HTML entities (&amp; → &, &lt; → <, etc.)
    text = html.unescape(text)

    # 步驟 3: 移除多餘空白但保留換行結構
    text = re.sub(r' +', ' ', text)  # 多個空格 → 一個
    text = text.strip()

    return text


def parse_media(media_str: str) -> list:
    """把 media 欄位解析成清單"""
    if not media_str.strip():
        return []
    return [url.strip() for url in media_str.split(',') if url.strip()]


def main():
    print("📥 讀取原始資料...")
    with open(RAW_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)
    print(f"   原始: {len(raw_rows)} 篇")

    print("🧹 清洗中...")
    clean_rows = []
    encoding_fixed = 0
    entity_fixed = 0

    for row in raw_rows:
        original = row['content']
        cleaned = clean_content(original)

        # 統計修復數量
        if cleaned != original and cleaned != html.unescape(original):
            encoding_fixed += 1
        if '&amp;' in original or '&lt;' in original or '&gt;' in original:
            entity_fixed += 1

        clean_row = {
            'id': row['id'],
            'created_at': row['created_at'],
            'content': cleaned,
            'content_length': len(cleaned),
            'url': row['url'],
            'media': parse_media(row.get('media', '')),
            'media_count': len(parse_media(row.get('media', ''))),
            'replies_count': int(row.get('replies_count', 0) or 0),
            'reblogs_count': int(row.get('reblogs_count', 0) or 0),
            'favourites_count': int(row.get('favourites_count', 0) or 0),
            # 分類標記
            'is_retweet': cleaned.startswith('RT @'),
            'has_text': len(cleaned) > 0,
            'has_media': len(parse_media(row.get('media', ''))) > 0,
        }
        clean_rows.append(clean_row)

    # 按時間排序（最新在前）
    clean_rows.sort(key=lambda r: r['created_at'], reverse=True)

    # 就任後子集
    president_rows = [r for r in clean_rows if r['created_at'] >= INAUGURATION]

    print(f"   清洗完成: {len(clean_rows)} 篇")
    print(f"   編碼修復: {encoding_fixed} 篇")
    print(f"   Entity 修復: {entity_fixed} 篇")
    print(f"   就任後: {len(president_rows)} 篇")

    # 輸出 CSV（全部）
    print("💾 儲存 CSV...")
    csv_fields = ['id', 'created_at', 'content', 'content_length', 'url',
                  'replies_count', 'reblogs_count', 'favourites_count',
                  'is_retweet', 'has_text', 'has_media', 'media_count']

    for filepath, data in [(CLEAN_CSV, clean_rows), (PRESIDENT_CSV, president_rows)]:
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(data)
        print(f"   ✅ {filepath.name}: {len(data)} 篇")

    # 輸出 JSON（全部）
    print("💾 儲存 JSON...")
    for filepath, data in [(CLEAN_JSON, clean_rows), (PRESIDENT_JSON, president_rows)]:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   ✅ {filepath.name}: {len(data)} 篇")

    # 統計資訊
    stats = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'source': 'https://ix.cnn.io/data/truth-social/truth_archive.csv',
        'total_posts': len(clean_rows),
        'date_range': {
            'earliest': clean_rows[-1]['created_at'],
            'latest': clean_rows[0]['created_at'],
        },
        'president_term2': {
            'start': INAUGURATION,
            'total_posts': len(president_rows),
            'with_text': len([r for r in president_rows if r['has_text']]),
            'pure_media': len([r for r in president_rows if not r['has_text'] and r['has_media']]),
            'retweets': len([r for r in president_rows if r['is_retweet']]),
        },
        'cleanup': {
            'encoding_fixed': encoding_fixed,
            'entity_fixed': entity_fixed,
        },
        'files': {
            'clean_all_csv': str(CLEAN_CSV),
            'clean_all_json': str(CLEAN_JSON),
            'clean_president_csv': str(PRESIDENT_CSV),
            'clean_president_json': str(PRESIDENT_JSON),
        }
    }

    with open(STATS_FILE, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"📊 統計: {STATS_FILE.name}")

    # 打印摘要
    print("\n" + "=" * 60)
    print("📋 川普密碼 — 資料集摘要")
    print("=" * 60)
    print(f"總篇數:      {stats['total_posts']:,}")
    print(f"時間範圍:     {stats['date_range']['earliest'][:10]} ~ {stats['date_range']['latest'][:10]}")
    print(f"就任後總計:   {stats['president_term2']['total_posts']:,} 篇")
    print(f"  有文字:     {stats['president_term2']['with_text']:,} 篇")
    print(f"  純圖片:     {stats['president_term2']['pure_media']:,} 篇")
    print(f"  轉發(RT):   {stats['president_term2']['retweets']:,} 篇")
    print(f"編碼修復:     {stats['cleanup']['encoding_fixed']:,} 篇")
    print(f"Entity修復:   {stats['cleanup']['entity_fixed']:,} 篇")
    print("=" * 60)
    print("✅ 資料已就緒，可以開始分析！")


if __name__ == '__main__':
    main()
