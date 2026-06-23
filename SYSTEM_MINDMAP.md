# TestCase 管理系統運作心智圖

此心智圖以「功能使用」為主，用來描述目前系統可操作的功能範圍，並作為後續撰寫 TestCase 的依據。

狀態標示：

- `[已完成]`：目前系統已具備，或已有可操作的頁面/API
- `[未完成]`：已列入規劃，但尚未完成或仍需重構

```mermaid
mindmap
  root((TestCase 管理系統))
    已完成功能
      Product/Version 管理
        瀏覽 Product/Version 清單
        新增 Product/Version
        修改 Product/Version
        刪除 Product/Version
        搜尋 Product/Version
        進入 Module/TestCase 頁面
      Module 管理
        依 Product/Version 顯示 Module
        新增 Module
        修改 Module 名稱
        刪除 Module
        刪除 Module 時同步刪除底下 TestCase
        無 Module 時停用新增 TestCase
      TestCase 管理
        依 Module 顯示 TestCase 清單
        新增 TestCase
        修改 TestCase
        刪除 TestCase
        預覽 TestCase
        側邊面板編輯 TestCase
        顯示 Case
        顯示 Priority
        顯示 Remark
        顯示 Update 日期
      API 與系統工具
        API 文件頁面
        Product API
        Module API
        TestCase API
        TestCase Hierarchy API
        TestRun API
        Admin Reset API
      TestRun 管理
        主導覽入口
        瀏覽 TestRun 列表
        顯示進度百分比
        顯示狀態統計
        建立 TestRun
        依 Product/Version 選擇 TestCase
        預覽 TestCase
        更新執行狀態
        查看 TestRun 明細
        產出 HTML Report
      資料庫與設定
        SQLite 資料庫
        testcase_manager.db
        自動建立資料表
        schema.sql
        .env 設定
    未完成功能
      匯入匯出
        匯出 TestCase 功能
        匯入 TestCase 功能
        匯入資料檢核
        匯出欄位格式定義
      快捷操作
        快捷選單
        常用操作入口
        批次操作入口
      其他
        其他待規劃功能
        UI/UX 細節優化
        測試案例補齊
```

## 維護規則

每次完成或調整功能時，請同步更新此心智圖：

- 將完成的節點由 `[未完成]` 改為 `[已完成]`
- 新增功能時，先放入對應分類並標示狀態
- 若功能範圍改變，請同步調整節點名稱，避免後續 TestCase 依據過期
- 若功能已有明確測試情境，可在節點下方新增更細的操作項目
