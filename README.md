# TestCase 管理系統

一個以 Python Flask + SQLite 製作的 TestCase 管理系統，支援 `Product/Version > Module > TestCase` 的層級管理，以及 `TestRun` 相關功能。

> 目前專案仍在開發中，README 以「目前已可使用的功能」為主，後續變更請以 [`規格紀錄.md`](./規格紀錄.md) 為準。

## 目前功能

- `Product/Version` 列表管理：新增、修改、刪除與查詢
- `Module/TestCase` 分層瀏覽：依 `Product/Version` 分組顯示 Module 與 TestCase
- `TestCase` 新增、修改、刪除與預覽
- `TestCase` 支援 `Remark`、`Priority`、`updated_at` 等欄位
- `TestRun` 相關頁面與資料表
- API 文件頁面：`/api`
- SQLite 自動建表與資料庫初始化
- 支援 `POST /api/admin/reset` 重置全部資料

## 專案結構

- `app.py`：Flask 入口、路由與 API
- `database.py`：SQLite 初始化、欄位補齊與重置
- `models.py`：資料存取與業務邏輯
- `schema.sql`：資料表結構
- `openspec.yaml`：API 與資料模型規格
- `templates/`：Jinja2 頁面模板
- `static/`：CSS 與前端 JavaScript
- `SYSTEM_MINDMAP.md`：系統功能心智圖，標示已完成與未完成功能
- `規格紀錄.md`：功能調整與開發紀錄

## 快速開始

1. 建立虛擬環境

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

2. 設定環境變數

```powershell
copy .env.example .env
```

3. 啟動服務

```powershell
set FLASK_APP=app.py
set FLASK_ENV=development
flask run
```

或直接使用：

```powershell
python app.py
```

4. 開啟瀏覽器

```text
http://127.0.0.1:5000
```

第一次啟動時，系統會自動建立 SQLite 資料表，資料庫檔案預設為專案根目錄下的 `testcase_manager.db`。

## 環境設定

`.env.example` 目前提供的範例值如下：

```env
FLASK_ENV=development
FLASK_APP=app.py
SECRET_KEY=dev-secret-key
```

正式使用時，建議自行替換 `SECRET_KEY`，不要沿用範例值。

## 開發中的注意事項

- 這個專案目前仍在調整中，頁面與 API 規格可能持續變動
- `testcase_manager.db` 是本機 SQLite 資料庫，不建議提交到 GitHub
- `app.py` 的設定已改為透過 `.env` 載入，避免硬編碼敏感資訊
- 修改模板或樣式後，如果畫面沒有更新，通常需要重新啟動 Flask 並清除瀏覽器快取
- 每次完成或調整功能時，請同步更新 [`SYSTEM_MINDMAP.md`](./SYSTEM_MINDMAP.md)，讓功能狀態能作為後續 TestCase 撰寫依據
- 更新 [`規格紀錄.md`](./規格紀錄.md) 時，請使用 `yyyy-mm-dd` 日期標題並置頂新增；每個項目前方請標示影響範圍：`[前端]`、`[後端]` 或 `[前端/後端]`
- 若當日已存在相同或相關主題的規格紀錄，請將新增項目記錄在該日期主題區塊內；若改動與當日既有主題不相關，請在同一日期下另開新的主題區塊並置於上方
- 若內容有變動或移除，已記錄的內容也要做相對應調整，避免規格紀錄與實際實作不一致
- 新增或調整 API 時，請同步更新 [`openspec.yaml`](./openspec.yaml)，讓 `http://127.0.0.1:5000/api` 的 API 文件保持最新

## 規格與變更紀錄

- [`openspec.yaml`](./openspec.yaml)：API 與資料模型規格
- [`schema.sql`](./schema.sql)：資料表建立語法
- [`SYSTEM_MINDMAP.md`](./SYSTEM_MINDMAP.md)：系統功能心智圖與完成狀態
- [`規格紀錄.md`](./規格紀錄.md)：功能變更與 UI 調整紀錄

## 常見問題

### 為什麼看不到最新畫面？

先確認 Flask 服務已重新啟動，再用瀏覽器硬刷新。

### 為什麼資料庫裡沒有資料？

這個專案使用 SQLite，本機資料存在 `testcase_manager.db`。如果你刪掉資料庫檔，系統會重新建立空資料庫。

### 為什麼 GitHub 不應該上傳 `testcase_manager.db`？

因為那是本機資料檔，通常包含你的測試資料或開發過程中的內容，公開 repo 時應該保留程式與結構，不保留個人資料庫內容。

## 待補充

如果之後你想讓這份 README 更完整，可以再加入：

- API 範例
- 畫面截圖
- 部署方式
- License
