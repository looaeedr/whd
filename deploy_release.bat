@echo off
chcp 65001 >nul
echo ========================================================
echo   WHD-CORNER 自動化 Git Push / PR / Release 發布腳本
echo ========================================================

REM 步驟 1: 檢查是否有 Git 儲存庫
if not exist ".git" (
    echo [錯誤] 目前目錄非 Git 儲存庫！
    pause
    exit /b 1
)

REM 步驟 2: 執行單元測試驗證
echo.
echo [1/5] 執行單元測試驗證 (pytest)...
pytest
if %errorlevel% neq 0 (
    echo [警告] 單元測試未通過！請檢查後再繼續。
    pause
    exit /b 1
)
echo [成功] 單元測試全數通過！

REM 步驟 3: 推送當前分支至遠端
echo.
echo [2/5] 推送當前分支 (new-engine) 至遠端 origin...
git push origin new-engine
if %errorlevel% neq 0 (
    echo [錯誤] git push 失敗！請檢查遠端權限或網路連線。
    pause
    exit /b 1
)
echo [成功] 已完成 git push origin new-engine

REM 步驟 4: 打上 Version Tag 並推送到遠端 (Release 標籤)
echo.
echo [3/5] 打上記號標籤 (Tag v0.0.14)...
git tag -a v0.0.14 -m "Release v0.0.14: 完整拓撲幾何引擎、GUI 結構預覽與統一開孔編輯器"
git push origin v0.0.14
echo [成功] Tag v0.0.14 已成功推送到遠端！

REM 步驟 5: 提示 PR (Pull Request) 與 Gitea / GitHub 操作說明
echo.
echo ========================================================
echo [4/5] PR (Pull Request) 發布提示
echo ========================================================
echo 遠端儲存庫位址: http://192.168.0.103:3030/looaeedr/whd-corner
echo.
echo 由於當前環境採用自建 Gitea/GitLab 服務且未安裝 gh CLI，
echo 請至瀏覽器開啟上方網址，執行以下動作完成 PR 與 Release:
echo.
echo   1. 點擊 「Pull Requests」 -> 「New Pull Request」
echo   2. 選擇 compare: new-engine -> target: main (或 master)
echo   3. 填入標題: "feat: 完整拓撲幾何引擎、GUI 結構預覽與統一開孔編輯器"
echo   4. 點擊 「Create Pull Request」 並進行合併 (Merge)
echo.
echo ========================================================
echo [5/5] Release 發布提示
echo ========================================================
echo   1. 在 Gitea 頁面點擊 「Releases」 -> 「Create a new release」
echo   2. 選擇標籤 Tag: v0.0.14
echo   3. 標題: Release v0.0.14
echo   4. 說明內容可複製本專案 handoff/ 相關文件摘要。
echo ========================================================
echo.
echo [完成] 所有自動化推送到遠端與 Tag 建立流程均已執行完畢！
pause
