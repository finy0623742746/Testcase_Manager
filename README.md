# TestCase 管理系統

一個以 Python Flask + SQLite 製作的 TestCase 管理系統，支援 `Product/Version > Module > TestCase` 的層級管理，以及 `TestRun` 相關功能。

> 目前專案仍在開發中，README 以「目前已可使用的功能」為主，後續變更請以 [`規格紀錄.md`](./規格紀錄.md) 與 [`AGENTS.md`](./AGENTS.md) 為準。

## 目前功能

- `Product/Version` 列表管理：新增、修改、刪除與查詢
- `Module/TestCase` 分層瀏覽：依 `Product/Version` 分組顯示 Module 與 TestCase
- `TestCase` 新增、修改、刪除、預覽與側邊面板編輯
- `TestCase` 支援 `Remark`、`Priority`、`updated_at` 等欄位，並可依 Case 關鍵字搜尋
- `TestRun` 列表、建立、修改與刪除
- `TestRun` 明細頁：依 `Product/Version > Module` 分組顯示 TestCase，支援狀態更新、追加 TestCase 與移除關聯
- `TestRun` Report 頁與伺服器端 PDF 匯出
- API 文件頁面：`/api`
- REST API 支援 `Product`、`Module`、`TestCase`、`TestRun` 與 `TestRun` 狀態操作
- SQLite 自動建表、資料庫初始化與啟動時欄位補齊
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

## AI 協作說明

本專案在開發過程中有使用 AI 工具協助撰寫、修改與除錯；實際的架構選擇、功能整合與內容審查由作者完成。

## 規格與變更紀錄

- [`api-spec.yaml`](./api-spec.yaml)：API 與資料模型規格
- [`schema.sql`](./schema.sql)：資料表建立語法
- [`SYSTEM_MINDMAP.md`](./SYSTEM_MINDMAP.md)：系統功能心智圖與完成狀態
- [`規格紀錄.md`](./規格紀錄.md)：功能變更與 UI 調整紀錄
- [`AGENTS.md`](./AGENTS.md)：本專案的持久性開發與寫入規範

## 常見問題

### 為什麼看不到最新畫面？

先確認 Flask 服務已重新啟動，再用瀏覽器硬刷新。

### 為什麼資料庫裡沒有資料？

這個專案使用 SQLite，本機資料存在 `testcase_manager.db`。如果你刪掉資料庫檔，系統會重新建立空資料庫。

## License

This project is licensed under the MIT License. See the [LICENSE](./LICENSE) file for details.
