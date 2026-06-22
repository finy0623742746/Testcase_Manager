# TestCase 管理系統運作心智圖

此心智圖以「功能使用」為主，用來描述目前系統可操作的功能範圍，並作為後續撰寫 TestCase 的依據。

狀態標示：

- `[已完成]`：目前系統已具備，或已有可操作的頁面/API
- `[未完成]`：已列入規劃，但尚未完成或仍需重構

```mermaid
mindmap
  root((TestCase 管理系統))
    Product/Version 管理 [已完成]
      瀏覽 Product/Version 清單 [已完成]
      新增 Product/Version [已完成]
      修改 Product/Version [已完成]
      刪除 Product/Version [已完成]
      搜尋 Product/Version [已完成]
      進入 Module/TestCase 頁面 [已完成]
    Module 管理 [已完成]
      依 Product/Version 顯示 Module [已完成]
      新增 Module [已完成]
      修改 Module 名稱 [已完成]
      刪除 Module [已完成]
      刪除 Module 時同步刪除底下 TestCase [已完成]
      無 Module 時停用新增 TestCase [已完成]
    TestCase 管理 [已完成]
      依 Module 顯示 TestCase 清單 [已完成]
      新增 TestCase [已完成]
      修改 TestCase [已完成]
      刪除 TestCase [已完成]
      預覽 TestCase [已完成]
      側邊面板編輯 TestCase [已完成]
      顯示 Case [已完成]
      顯示 Priority [已完成]
      顯示 Remark [已完成]
      顯示 Update 日期 [已完成]
    TestRun 管理 [未完成]
      TestRun 重構 [未完成]
      建立 TestRun [未完成]
      引用 TestCase [未完成]
      更新執行狀態 [未完成]
      查看 TestRun 明細 [未完成]
    匯入匯出 [未完成]
      匯出 TestCase 功能 [未完成]
      匯入 TestCase 功能 [未完成]
      匯入資料檢核 [未完成]
      匯出欄位格式定義 [未完成]
    快捷操作 [未完成]
      快捷選單 [未完成]
      常用操作入口 [未完成]
      批次操作入口 [未完成]
    API 與系統工具 [已完成]
      API 文件頁面 [已完成]
      Product API [已完成]
      Module API [已完成]
      TestCase API [已完成]
      Admin Reset API [已完成]
      TestRun API [未完成]
    資料庫與設定 [已完成]
      SQLite 資料庫 [已完成]
      testcase_manager.db [已完成]
      自動建立資料表 [已完成]
      schema.sql [已完成]
      .env 設定 [已完成]
    其他 [未完成]
      其他待規劃功能 [未完成]
      UI/UX 細節優化 [未完成]
      測試案例補齊 [未完成]
```

## 維護規則

每次完成或調整功能時，請同步更新此心智圖：

- 將完成的節點由 `[未完成]` 改為 `[已完成]`
- 新增功能時，先放入對應分類並標示狀態
- 若功能範圍改變，請同步調整節點名稱，避免後續 TestCase 依據過期
- 若功能已有明確測試情境，可在節點下方新增更細的操作項目

