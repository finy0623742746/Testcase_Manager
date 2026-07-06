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
- `api-spec.yaml`：API 與資料模型規格
- `templates/`：Jinja2 頁面模板
- `static/`：CSS 與前端 JavaScript
- `SYSTEM_MINDMAP.md`：系統功能心智圖，標示已完成與未完成功能
- `規格紀錄.md`：功能調整與開發紀錄

## 快速開始

以下指令適用於 Windows PowerShell。

1. 建立虛擬環境

```powershell
python -m venv .venv
```

在專案目錄建立獨立的 Python 環境，避免套件與其他專案互相影響。

2. 啟用虛擬環境

```powershell
.\.venv\Scripts\activate
```

啟用成功後，終端機提示字元通常會出現 `(.venv)`。

3. 安裝相依套件

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

先將虛擬環境內的 `pip` 升級至新版，再安裝 Flask、python-dotenv 與 SQLAlchemy 等必要套件。

4. 建立本機環境設定

```powershell
Copy-Item .env.example .env
```

請勿將包含正式密鑰的 `.env` 提交至版本控制。

5. 啟動服務

```powershell
python -m flask --app app run --debug
```

`--debug` 適合本機開發，修改程式後會自動重新載入，並在錯誤發生時顯示詳細資訊。正式環境請勿使用除錯模式。

也可以直接使用：

```powershell
python app.py
```

6. 開啟瀏覽器

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

使用 `python -m flask --app app run --debug` 啟動時，不需要另外以 PowerShell 設定 `FLASK_APP` 或 `FLASK_ENV`。正式使用時，請自行替換 `SECRET_KEY`，不要沿用範例值。

## 開發中的注意事項

- `app.py` 的設定已改為透過 `.env` 載入，避免硬編碼敏感資訊
- 修改模板或樣式後，如果畫面沒有更新，通常需要重新啟動 Flask 並清除瀏覽器快取
- 每次完成或調整功能時，請同步更新 [`SYSTEM_MINDMAP.md`](./SYSTEM_MINDMAP.md)，讓功能狀態能作為後續 TestCase 撰寫依據
- 更新 [`規格紀錄.md`](./規格紀錄.md) 時，請使用三層結構：第一層 `# 規格紀錄`、第二層 `## yyyy-mm-dd` 日期、第三層 `### 主題`，主題內容以清單記錄
- 規格日期由新到舊排列；同日期的新主題置於該日期最上方，同主題的新條目置於該主題最上方
- 無法確認日期的既有內容統一放在 `## 未標日期`，並置於所有日期區段之後的檔案最下方
- 第三層主題需同時對應「功能範圍」與「改動類型」；同一頁面或同一天的改動不一定屬於相同主題
- 只有功能範圍及改動類型都相同時，才可將新增項目放入當日既有主題；否則應在同一日期下新增第三層主題
- 一次調整若跨越多個獨立頁面或系統層級，需拆分成多個第三層主題；全站共用樣式、單頁 UI、API 與資料庫規則原則上分開記錄
- 新增條目前需確認第三層標題能準確概括該主題下每一條紀錄；若無法概括，應拆分主題，不可只為容納新內容而擴大成籠統標題
- 若同一主題的實際功能範圍整體改變，可調整第三層主題名稱，但調整後仍須能準確描述該主題下所有條目
- 每個規格項目前方請標示影響範圍：`[前端]`、`[後端]` 或 `[前端/後端]`
- 若內容有變動或移除，已記錄的內容也要做相對應調整，避免規格紀錄與實際實作不一致
- 純 BUG 修正若只是恢復既有規格，不新增規格紀錄；若修正同時改變既有行為或規格，才更新對應條目
- 每次完成當日規格更新後，需重新檢查當日所有第三層標題與條目是否一致，並確認沒有跨主題混放
- 新增或調整 API 時，請同步更新 [`api-spec.yaml`](./api-spec.yaml)，讓 `http://127.0.0.1:5000/api` 的 API 文件保持最新
- 新功能或新頁面的後端資料必須透過 Fetch/XHR API 載入
- 純前端錯誤必須輸出至瀏覽器 Console，保留足以定位問題的錯誤資訊

## AI 協作說明

本專案在開發過程中有使用 AI 工具協助撰寫、修改與除錯；實際的架構選擇、功能整合與內容審查由作者完成。

## 規格與變更紀錄

- [`api-spec.yaml`](./api-spec.yaml)：API 與資料模型規格
- [`schema.sql`](./schema.sql)：資料表建立語法
- [`SYSTEM_MINDMAP.md`](./SYSTEM_MINDMAP.md)：系統功能心智圖與完成狀態
- [`規格紀錄.md`](./規格紀錄.md)：功能變更與 UI 調整紀錄

## 常見問題

### 為什麼看不到最新畫面？

先確認 Flask 服務已重新啟動，再用瀏覽器硬刷新。

### 為什麼資料庫裡沒有資料？

這個專案使用 SQLite，本機資料存在 `testcase_manager.db`。如果你刪掉資料庫檔，系統會重新建立空資料庫。

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
