# WynnTranslator Online Language Packs

本儲存庫是 WynnTranslator 的線上多語言包中心，負責提供 Minecraft 客戶端 OTA 自動更新與 Crowdin 社群翻譯雙向同步。

## 語言代碼規範
所有語言資料夾與代碼**嚴格對齊 Minecraft 原版規範**（全小寫與底線分隔）：
* `en_us`: 英文原文基準（English US）
* `zh_tw`: 繁體中文（繁體中文 / 台灣）
* 其他語系亦遵循 Minecraft 規範（如 `zh_cn`, `ja_jp` 等）

## 文本來源與工作流
本專案已**全面廢止 Wiki 爬取**，改採現代化雙軌流程：
1. **遊戲實機採集**：透過 WynnTranslator 客戶端遇未翻譯文本時，自動匿名遙測至後端，彙整入庫。
2. **Crowdin 社群協作**：以 `languages/en_us/` 為基準，譯者在 Crowdin 平台進行在地化，由 GitHub Actions 自動雙向同步。

## 更新 Manifest 與 SHA-256
在新增或修改任何翻譯 JSON 檔案後，執行維護腳本自動驗證語系格式並重新計算校驗碼：
```bash
python tools/update_manifest.py
```
該腳本亦已整合於 `.github/workflows/crowdin-sync.yml` 中，在 Crowdin 同步時自動執行並發起 PR。
