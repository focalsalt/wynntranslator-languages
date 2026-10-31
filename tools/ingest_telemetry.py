#!/usr/bin/env python3
"""
Telemetry Ingest Script for WynnTranslator
Fetches unclassified or frequently reported texts from Cloudflare D1 Telemetry Worker,
organizes them into standard Minecraft en_us language files, and triggers manifest update.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request

try:
    from update_manifest import update_manifest_for_locale
except ImportError:
    # If running from different workdir
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from update_manifest import update_manifest_for_locale


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]+", "-", name.strip().lower())
    cleaned = re.sub(r"-+", "-", cleaned).strip("-")
    return cleaned or "unclassified"


def is_valid_telemetry_entry(text: str) -> bool:
    if not text or len(text.strip()) <= 1:
        return False
    trimmed = text.strip()

    # Filter out Unicode PUA (e.g. \uE000-\uF8FF, \u000F0000-\u0010FFFF)
    if any((0xE000 <= ord(c) <= 0xF8FF) or (ord(c) >= 0xF0000) for c in trimmed):
        return False

    # Filter out block elements / health bars (\u2580-\u259F)
    if any(0x2580 <= ord(c) <= 0x259F for c in trimmed):
        return False

    # Filter out historical <num> fragments
    if "<num>" in trimmed:
        return False

    # Filter out pure numbers, percentages, health fragments, symbols
    if re.fullmatch(r"[\d\s.,/\-+%kM❤☠✖ⒸⓀ:;()\[\]{}#]+", trimmed):
        return False

    # Filter out pure health expressions like "15.2k/30.6k"
    if re.fullmatch(r"\d+(?:\.\d+)?[kM]?\s*/\s*\d+(?:\.\d+)?[kM]?", trimmed):
        return False

    # Filter out strings without at least two ASCII alphabetic letters (English source text)
    letters = [c for c in trimmed if c.isascii() and c.isalpha()]
    if len(letters) < 2:
        return False

    return True


def load_json_file(filepath: str) -> dict:
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warn] Failed to read {filepath}: {e}")
    return {}


def save_json_file(filepath: str, data: dict):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    # Sort keys for deterministic, minimal git diffs
    sorted_data = {k: data[k] for k in sorted(data.keys())}
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(sorted_data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def fetch_telemetry_items(endpoint: str, token: str, min_count: int, limit: int = 500) -> list:
    params = urllib.parse.urlencode({
        "min_count": min_count,
        "limit": limit
    })
    url = f"{endpoint.rstrip('/')}?{params}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "WynnTranslator-Ingest-Tool/1.0")
    if token:
        req.add_header("Authorization", f"Bearer {token}")

    print(f"[Info] Fetching telemetry from {url}...")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                print(f"[Error] Failed to fetch: HTTP {resp.status}")
                return []
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            if data.get("success"):
                return data.get("items", [])
            else:
                print(f"[Error] Telemetry API error: {data}")
                return []
    except Exception as e:
        print(f"[Error] Network or parsing error: {e}")
        return []


def clean_historical_data(languages_dir: str) -> int:
    removed_count = 0
    en_us_dir = os.path.join(languages_dir, "en_us")
    if not os.path.exists(en_us_dir):
        return 0

    # Remove deprecated npc directory completely
    npc_dir = os.path.join(en_us_dir, "npc")
    if os.path.exists(npc_dir):
        import shutil
        shutil.rmtree(npc_dir, ignore_errors=True)
        print(f"[Info] Removed deprecated directory: {npc_dir}")
        removed_count += 1

    for root, _, files in os.walk(en_us_dir):
        for file in files:
            if not file.endswith(".json") or file == "manifest.json":
                continue
            filepath = os.path.join(root, file)
            data = load_json_file(filepath)
            cleaned = {k: v for k, v in data.items() if is_valid_telemetry_entry(k)}
            diff = len(data) - len(cleaned)
            if diff > 0:
                removed_count += diff
                if cleaned:
                    save_json_file(filepath, cleaned)
                    print(f"[Info] Cleaned {diff} entries from {file}")
                else:
                    os.remove(filepath)
                    print(f"[Info] Removed empty polluted file: {filepath}")

    if removed_count > 0:
        print("[Success] Cleaned historical polluted entries.")
        update_manifest_for_locale(languages_dir, "en_us")

    return removed_count


def ingest(endpoint: str, token: str, min_count: int, languages_dir: str, clean_historical: bool = True) -> int:
    if clean_historical:
        clean_historical_data(languages_dir)

    items = fetch_telemetry_items(endpoint, token, min_count)
    if not items:
        print("[Info] No new telemetry items found meeting criteria.")
        return 0

    en_us_dir = os.path.join(languages_dir, "en_us")
    if not os.path.exists(en_us_dir):
        print(f"[Error] en_us directory not found at {en_us_dir}")
        return 0

    added_count = 0
    modified_files = set()

    for item in items:
        category = item.get("category", "").lower()
        source_text = item.get("sourceText", "").strip()
        speaker = item.get("speaker", "").strip()
        quest = item.get("quest", "").strip()

        if not source_text:
            continue

        # Drop deprecated NPC names
        if category == "npc":
            continue

        # Filter out junk, health bars, PUA characters, and <num> fragments
        if not is_valid_telemetry_entry(source_text):
            continue

        if category == "hints":
            target_file = os.path.join(en_us_dir, "hints", "hints.json")
            data = load_json_file(target_file)
            if source_text not in data:
                data[source_text] = source_text
                save_json_file(target_file, data)
                added_count += 1
                modified_files.add(target_file)

        elif category == "objectives":
            target_file = os.path.join(en_us_dir, "objectives", "objectives.json")
            data = load_json_file(target_file)
            if source_text not in data:
                data[source_text] = source_text
                save_json_file(target_file, data)
                added_count += 1
                modified_files.add(target_file)

        elif category == "quests":
            quest_filename = sanitize_filename(quest) if quest else "unclassified"
            target_file = os.path.join(en_us_dir, "quests", f"{quest_filename}.json")
            data = load_json_file(target_file)
            if source_text not in data:
                data[source_text] = source_text
                save_json_file(target_file, data)
                added_count += 1
                modified_files.add(target_file)

        else:
            # Default to gui/shared.json
            target_file = os.path.join(en_us_dir, "gui", "shared.json")
            data = load_json_file(target_file)
            if source_text not in data:
                data[source_text] = source_text
                save_json_file(target_file, data)
                added_count += 1
                modified_files.add(target_file)

    print(f"[Success] Ingested {added_count} new entries across {len(modified_files)} files.")

    if added_count > 0:
        print("[Info] Recomputing manifest for en_us...")
        update_manifest_for_locale(languages_dir, "en_us")

    return added_count


def main():
    parser = argparse.ArgumentParser(description="Ingest telemetry reports into en_us language pack")
    parser.add_argument("--url", default=os.getenv("TELEMETRY_EXPORT_URL", "https://telemetry-wynntranslator.focalsalt.net/api/telemetry/export"), help="Telemetry export endpoint")
    parser.add_argument("--token", default=os.getenv("TELEMETRY_ADMIN_KEY", ""), help="Admin bearer token for authorization")
    parser.add_argument("--min-count", type=int, default=2, help="Minimum report_count threshold")
    parser.add_argument("--languages-dir", default=None, help="Path to languages directory")
    parser.add_argument("--clean-only", action="store_true", help="Only clean historical corrupted data and exit")

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    languages_dir = args.languages_dir or os.path.join(base_dir, "languages")

    if args.clean_only:
        clean_historical_data(languages_dir)
        sys.exit(0)

    count = ingest(args.url, args.token, args.min_count, languages_dir)
    sys.exit(0)


if __name__ == "__main__":
    main()
