#!/usr/bin/env python3
"""Sapporo Chuo Info v2.3 collector + LINE notification.

Environment variables:
  LINE_CHANNEL_ACCESS_TOKEN
  LINE_TO_USER_ID

Optional:
  MAX_ITEMS=5     # 通知1カテゴリあたりの最大件数
  MAX_STORE=300   # data/items.json に保持する最大件数
  MAX_AGE_DAYS=30 # これより古い記事は対象外

新着判定は data/items.json に保存済みのIDと突き合わせて行う。
このファイルはワークフロー側でリポジトリにコミットして永続化する前提
（daily.yml の "Commit updated data" ステップ）。
これにより、Google Newsに載り続けている記事を毎日重複通知することを防ぐ。
"""
import os, re, json, hashlib, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
MAX_ITEMS = int(os.getenv("MAX_ITEMS", "5"))
MAX_STORE = int(os.getenv("MAX_STORE", "300"))
MAX_AGE_DAYS = int(os.getenv("MAX_AGE_DAYS", "30"))
MAX_TITLE_LEN = 36
DATA_PATH = os.path.join("data", "items.json")

QUERIES = [
 ("new", "札幌市中央区 飲食店 開店 OR オープン"),
 ("close", "札幌市中央区 飲食店 閉店 OR 閉店予定"),
 ("event", "札幌市中央区 アニメ イベント 2026"),
 ("new", "すすきの 飲食店 オープン"),
 ("close", "すすきの 飲食店 閉店"),
 ("event", "すすきの アニメ イベント 2026"),
 ("new", "麻生 飲食店 オープン"),
 ("close", "麻生 飲食店 閉店"),
 ("event", "麻生 アニメ イベント 2026"),
]
CHUO = ["すすきの", "大通", "狸小路", "円山", "中島公園", "二条市場", "創成川",
        "サッポロファクトリー", "麻生", "札幌市中央区", "中央区"]
GENERIC_AREA = {"札幌市中央区", "中央区"}
FOOD = ["飲食", "レストラン", "居酒屋", "バー", "BAR", "カフェ", "喫茶", "ラーメン", "焼肉",
        "寿司", "うどん", "そば", "カレー", "スイーツ", "ベーカリー", "パン", "食堂", "料理"]
ANIME = ["アニメ", "漫画", "マンガ", "声優", "コスプレ", "フィギュア", "同人",
         "コラボカフェ", "ポップアップストア", "キャラクター", "原画", "上映会"]


def fetch(q):
    u = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": "ja", "gl": "JP", "ceid": "JP:ja"})
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def clean(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()


def category(text, hint):
    if any(k in text for k in ["閉店", "営業終了", "閉業", "閉店予定"]):
        return "close"
    if any(k in text for k in ["開店", "オープン", "OPEN", "open", "開業", "新店舗"]):
        return "new"
    return hint


def guess_area(text):
    matches = [k for k in CHUO if k in text]
    specific = [k for k in matches if k not in GENERIC_AREA]
    if specific:
        return specific[0]
    return matches[0] if matches else "中央区"


def parse_pubdate(pubdate):
    try:
        return parsedate_to_datetime(pubdate).astimezone(JST)
    except Exception:
        return None


def parse(data, hint):
    root = ET.fromstring(data)
    out = []
    now = datetime.now(JST)
    for it in root.findall(".//item"):
        title = it.findtext("title", "")
        desc = clean(it.findtext("description", ""))
        link = it.findtext("link", "")
        pub = it.findtext("pubDate", "")
        text = title + " " + desc

        pub_dt = parse_pubdate(pub)
        # 公開日が分からない記事は除外しすぎないよう許容するが、
        # 分かる場合は MAX_AGE_DAYS より古ければ対象外にする
        if pub_dt is not None and (now - pub_dt).days > MAX_AGE_DAYS:
            continue

        if not any(k.lower() in text.lower() for k in CHUO):
            continue
        cat = category(text, hint)
        if cat in ("new", "close") and not any(k.lower() in text.lower() for k in FOOD):
            continue
        if cat == "event" and not any(k.lower() in text.lower() for k in ANIME):
            continue

        uid = hashlib.sha1((title + link).encode()).hexdigest()[:16]
        out.append({
            "id": uid,
            "category": cat,
            "title": title,
            "shop": "",
            "area": guess_area(text),
            "date": pub_dt.strftime("%Y-%m-%d") if pub_dt else now.strftime("%Y-%m-%d"),
            "summary": desc[:300],
            "source": "Google News",
            "url": link,
            "favorite": False,
            "read": False,
        })
    return out


def collect():
    items = {}
    for hint, q in QUERIES:
        try:
            for x in parse(fetch(q), hint):
                items[x["id"]] = x
        except Exception as e:
            print("collector error:", q, e)
    return list(items.values())


def load_store():
    if os.path.exists(DATA_PATH):
        try:
            with open(DATA_PATH, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print("failed to read store:", e)
    return []


def save_store(items):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def merge_and_find_new(collected, stored):
    known_ids = {x["id"] for x in stored}
    new_items = [x for x in collected if x["id"] not in known_ids]
    merged = (new_items + stored)[:MAX_STORE]
    return merged, new_items


def digest(new_items):
    if not new_items:
        return None  # 新着なしの日は送らない
    labels = {"new": "🟢新店", "close": "🔴閉店", "event": "🔵アニメ"}
    parts = [datetime.now(JST).strftime("%m/%d") + " 札幌中央区"]
    for cat in ("new", "close", "event"):
        group = [x for x in new_items if x["category"] == cat][:MAX_ITEMS]
        if not group:
            continue
        parts.append(labels[cat])
        for x in group:
            title = x["title"][:MAX_TITLE_LEN]
            parts.append(f"[{x['area']}]{title}")
    return "\n".join(parts)[:4900]


def line_push(text):
    token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
    to = os.environ["LINE_TO_USER_ID"]
    payload = json.dumps({"to": to, "messages": [{"type": "text", "text": text}]},
                          ensure_ascii=False).encode()
    req = urllib.request.Request(
        "https://api.line.me/v2/bot/message/push",
        data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + token},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            print("LINE status:", r.status)
    except urllib.error.HTTPError as e:
        print("LINE push failed:", e.code, e.read().decode(errors="replace"))
        raise


if __name__ == "__main__":
    collected = collect()
    stored = load_store()
    merged, new_items = merge_and_find_new(collected, stored)
    save_store(merged)

    print(f"collected={len(collected)} stored_before={len(stored)} "
          f"new={len(new_items)} stored_after={len(merged)}")

    text = digest(new_items)
    if text:
        print(text)
        if os.getenv("LINE_CHANNEL_ACCESS_TOKEN") and os.getenv("LINE_TO_USER_ID"):
            line_push(text)
        else:
            print("\nLINE credentials are not set; notification skipped.")
    else:
        print("新着なし。通知はスキップしました。")
