# 本地前端套件

版本固定在 [package.json](package.json) 與 [package-lock.json](package-lock.json)，`npm ci` 重建。執行頁面不依賴 CDN。

| 套件 | 用途 | License | 官方 API |
|---|---|---|---|
| ECharts 6.1.0 | SVG 時間軸、CPU 趨勢與 response 圖 | Apache-2.0 | https://echarts.apache.org/en/option.html |
| Tabulator 6.6.1 | 遠端分頁、排序、移動／調整欄位 | MIT | https://tabulator.info/docs/6.3 |
| esbuild 0.28.2 | 本地打包 | MIT | https://esbuild.github.io/api/ |
| Playwright 1.63.0 | 瀏覽器驗收 | Apache-2.0 | https://playwright.dev/docs/api/class-page |
| csv-parse 7.0.3 | 測試 CSV 引號、換行與完整資料 | MIT | https://csv.js.org/parse/ |

Runtime license 原文保存在 `licenses/`；transitive dependencies 的授權與版本隨 npm lock 及安裝後套件保存。字型只使用本機系統字型，不另下載或散布字型。
