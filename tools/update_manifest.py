#!/usr/bin/env python3
"""
Manifest & Checksum Generator for WynnTranslator Language Packs.
Ensures all language codes strictly match Minecraft locale format (e.g. zh_tw, en_us, zh_cn).
"""

import hashlib
import json
import os
import re
import sys

# Minecraft locale format: strictly lowercase with underscore, e.g. "zh_tw", "en_us", "ja_jp"
MC_LOCALE_PATTERN = re.compile(r"^[a-z]{2,3}_[a-z]{2,3}$")

LOCALE_DISPLAY_NAMES = {
    "zh_tw": "繁體中文",
    "zh_cn": "简体中文",
    "zh_hk": "香港繁體",
    "en_us": "English (US)",
    "en_gb": "English (UK)",
    "ja_jp": "日本語",
    "ko_kr": "한국어",
    "fr_fr": "Français",
    "de_de": "Deutsch",
    "ru_ru": "Русский"
}


def calculate_sha256(filepath: str) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def update_manifest_for_locale(languages_dir: str, locale: str) -> bool:
    if not MC_LOCALE_PATTERN.match(locale):
        print(f"[Error] Invalid Minecraft locale format: '{locale}'. Must be lowercase with underscore (e.g. zh_tw).")
        return False

    locale_path = os.path.join(languages_dir, locale)
    if not os.path.isdir(locale_path):
        return False

    files_list = []
    for root, _, files in sorted(os.walk(locale_path)):
        for file in sorted(files):
            if file == "manifest.json" or not file.endswith(".json"):
                continue

            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, locale_path).replace("\\", "/")
            sha256 = calculate_sha256(full_path)
            files_list.append({
                "path": rel_path,
                "sha256": sha256
            })

    manifest_path = os.path.join(locale_path, "manifest.json")
    version = "1.0.0"
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                version = old_data.get("version", version)
        except Exception:
            pass

    display_name = LOCALE_DISPLAY_NAMES.get(locale, locale)
    manifest = {
        "schema": 1,
        "locale": locale,
        "displayName": display_name,
        "version": version,
        "files": files_list
    }

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"[OK] Updated manifest for '{locale}' ({len(files_list)} files)")
    return True


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    languages_dir = os.path.join(base_dir, "languages")

    if not os.path.exists(languages_dir):
        print(f"[Error] languages directory not found at {languages_dir}")
        sys.exit(1)

    success = True
    for entry in sorted(os.listdir(languages_dir)):
        entry_path = os.path.join(languages_dir, entry)
        if os.path.isdir(entry_path):
            if not update_manifest_for_locale(languages_dir, entry):
                success = False

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
