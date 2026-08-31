---
name: handoff-zh
description: Use when the user wants to hand off the current conversation to a new session. Triggers include "交接", "開始交接", "準備交接", "寫交接", "交接文件", "交接出去", "進行交接", "交接給下一個", "交接給下個對話去做", "handoff", "wrap up", "session end", or similar phrases.
---

# Conversation Handoff (Chinese variant)

> **Version: v2 (2026-05-01) — Opus 4.7-tuned phrasing.** v1 archived at `~/資料/Skills/_archive/handoff-zh-v1/`.

This is the Chinese variant of the `handoff` skill. Structure and process are identical; only the trigger phrases, in-document wording, and handoff-message templates use Chinese.

**References**: Detailed rules and templates live under `references/`. They are loaded only when the corresponding step needs them.

When the user triggers a handoff, execute the steps below in order. 目標是讓下一個 Claude session 能從交接文件單獨重建完整工作脈絡，不需要和使用者反覆問答。

## Configuration

This skill reads user configuration from `CLAUDE.md`. See [`references/user-config.md`](references/user-config.md) for required and optional variables.

Defaults: workspace root inferred from conversation, handoff documents go to `<WORKSPACE_ROOT>/_handoffs/`, no template.

## Step 0: Get current time

```bash
date '+%Y-%m-%d %H:%M:%S %Z'
```

Use this timestamp for filename and all time references. Never estimate.

## Step 0.5: When to proactively suggest a handoff

使用者手動觸發（說「交接」「handoff」等）→ 跳過此步，直接到 Step 0.7。

主動建議交接的核心問題是：**繼續留在這個對話內，會不會讓下個對話付出比「重新開始」更高的代價？** 下個對話需要重建工作脈絡——若這個重建成本已經接近「直接寫下來」的成本，就到了該建議交接的時機。

下表列出常見信號作為**參考錨點**，視為啟發式判斷而非硬規則。判斷時綜合多個弱信號；單一信號若與上面的核心問題矛盾，就不應觸發。

| 信號 | 參考錨點 | 為什麼這是信號 | 動作 |
|------|---------|--------------|------|
| 主題轉換 | 新主題與當前無關 | 不同主題下幾乎沒有共用脈絡——重新開始更省事 | 建議開新對話（非交接） |
| 輪數 + 密度 | 約 15–20 輪且資訊密度高 | 高密度輪次累積的狀態量會讓下個對話花更多時間重建；累積成本隨輪數**超線性**增長 | 建議交接 |
| 輪數 + 任務未完成 | 約 20+ 輪且任務仍在進行 | 此長度下「實際決定」與「對話原文」的落差已大到值得寫一份顯式摘要——明顯省下個對話的時間 | 強烈建議交接 |
| 產出物完成 | 階段性成果完成（檔案寫好、決策確認、里程碑達成） | 階段邊界是天然的壓縮點——在這裡交接讓下個對話從乾淨狀態開始，而非半途接手 | 交接點 |
| 任務完成 + 性質轉換 | 下一步是不同性質的工作（例：設計 → 執行） | 不同工作類型需要不同心智模式；硬把前段框架帶過去是負擔不是幫助 | 建議 /clear 或新對話 |
| context 膨脹斜率 | 每輪產出量大且持續增長 | 產出量在加速代表狀態累積快於整理——曲線變陡前先交接，比變陡後再交接便宜 | 提前準備交接 |

「高資訊密度」的具體樣貌：多個檔案編輯、密集決策、累積了下個對話需要重建的脈絡、或多輪 tool result 詮釋。低密度的樣貌：短 Q&A、快速查詢、單檔小修。

**進入條件顯式化**：建議交接時，先與使用者確認 exit_condition（「做到哪裡就交接」）。使用者手動觸發時，AI 從對話脈絡推斷 exit_condition，寫入 frontmatter，不額外詢問。

**判斷基準不是 context 負荷**：1M context 下「context 快滿了」不再是有效信號。用輪數 + 資訊密度 + 主題連貫性判斷。

> **觀察項（Opus 4.7）**：Opus 4.7 對 tools 的主動觸發比 4.6 少（依 Anthropic Best Practices）。這個傾向是否會影響「主動建議交接」（這是文字輸出而非 tool call）目前尚在觀察。若你發現模型在長對話中從不主動建議交接、或太頻繁建議，請回報以便調整此步驟。

## Step 0.7: First-run setup check

只在**交接確定進行**後才跑此步——使用者手動觸發，或 AI 在 Step 0.5 建議且使用者同意。若 Step 0.5 以「/clear 或新對話」結束，跳過此步。

檢查使用者的 `CLAUDE.md` 中是否有 `^...WORKSPACE_ROOT:` 的宣告（精確指令與檔案解析邏輯見 [`references/first-run-setup.md`](references/first-run-setup.md)）。

- **已設定** → 直接進入 Step 1。
- **未設定** → 給使用者兩個選項：走引導流程（三題，產出可貼上的 snippet），或使用預設值（推斷 workspace root、存到 `<workspace>/_handoffs/`）。任一選項都能讓當前交接在同一輪繼續進行。

Skill **不直接編輯 `CLAUDE.md`**。產出 snippet 後由使用者自己貼上。

## Step 1: Detect environment and save location

Do NOT ask the user what environment they are in. Detect by tool availability:

| Environment | Detection | Save strategy |
|-------------|-----------|---------------|
| Desktop app with MCP | Filesystem tools or `osascript` available | Write directly via MCP or osascript |
| Web / mobile (with compute) | No Filesystem, but bash / create_file available | Downloadable `.md` |
| Web / mobile (no compute) | Neither | Output in code block for copy-paste |
| CLI / terminal agent | Local filesystem access | Write directly |

**Save location**: under `HANDOFF_DIR` (default: `<WORKSPACE_ROOT>/_handoffs/`). Create directory if missing.

無檔案系統存取時，告訴使用者：
1. 建議檔名：`Handoff_{YYYY-MM-DD}_{short-topic}.md`
2. 儲存位置：`<HANDOFF_DIR>` 下

## Step 2: Determine handoff type

- **Type A — 一般對話交接（預設）**。規劃、設計、寫作、檔案整理、研究討論等
- **Type B — 程式任務交接**。對話產出要給另一個 agent 執行的明確任務。見 [`references/type-b-structure.md`](references/type-b-structure.md)

## Step 2.5: Determine audience

交接是一種**主動壓縮**——將當前對話改寫成「下個讀者」真正需要的最小形式。讀者身份決定寫作風格。

| Audience | 適用情境 | 寫作風格 |
|----------|---------|---------|
| `model`（預設） | 下個 session 是另一個 Claude / LLM 接手 | 緊湊、結構化、節省 token；跳過說服性鋪陳；使用短標籤與條列；因果鏈用 `→` 表達 |
| `human` | 使用者明確指定交接文件要給「人」讀（自己、同事、協作者） | 完整句子、敘事流暢、明確寫出理由、避免 model-oriented 的速記與術語 |

**辨識方式**：預設 `model`。使用者在觸發語中明確指定時切換到 `human`——例如「這份交接我要自己之後讀」「交接給 <人名>」「我要印出來」「寫得讓人看得懂」。不確定時問一次。

把決定的 audience 寫進 frontmatter（`audience: model` 或 `audience: human`），讓未來任何讀者立即知道當前文件採用哪種寫作風格。

## Step 3: Resolve all paths

交接文件中每個路徑都必須以 `~/` 開頭或是明確的絕對路徑。這是本 skill 最重要的正確性限制。見 [`references/path-resolution.md`](references/path-resolution.md)。

## Step 4: Create handoff document

### 4a — With template and Filesystem access

若使用者設定了 `TEMPLATE_PATH` 且有 Filesystem MCP，使用模板加速流程。見 [`references/template-workflow.md`](references/template-workflow.md)。

### 4b — Without template

直接生成文件，使用下方結構。

### 4c — Core document structure

```markdown
---
date: YYYY-MM-DD
topic: 專案名稱
workspace: ~/full/path/to/workspace/
exit_condition: [完成/中斷/分支] — 一句話描述結束狀態
type: handoff
audience: model           # "model"（預設）或 "human"，見下方「Audience」段說明
prev: ~/...前次同主題交接路徑（無則省略此行）
---

> **本文件位置：** ~/full/path/to/HANDOFF_DIR/Handoff_YYYY-MM-DD_slug.md

# [專案名稱] 交接摘要 — YYYY-MM-DD

## 工作區根目錄
`~/full/path/to/workspace/`

## 本次對話完成事項
（每項以「問題/背景 → 發現/結論 → 已採取的行動」結構陳述）
（讓接手 Claude 理解因果鏈，而不只是一份清單）
（所有檔案路徑使用 ~/... 完整形式）

## 未完成 / 待辦事項
（以截止日期或時間框架分組，例如「### 3/14 前（3/20 出發前必須完成行政程序）」）
（每項說明「為什麼是這個期限」，讓接手 Claude 能判斷輕重緩急）
（標示依賴關係：哪些事項必須在其他事項之前完成）
（持續性任務沒有硬截止日期時，說明時間範圍和相對優先級）
（**每項附一句「完成長什麼樣」**——完成後哪個檔案會存在、會含什麼內容。見下方「產出物條款」）

## 重要決策與脈絡
（記錄對話中做出的關鍵判斷和理由）
（特別標註「曾考慮但否決的替代方案」，避免接手 Claude 重走老路）

## 檔案變更紀錄
- 新建：`~/...`
- 修改：`~/...`
- 刪除：`~/...`
```

### 4d — Optional sections

依情境追加可選區塊（關鍵檔案速查、交叉索引、排程、校驗錨點等）。決策規則與模板見 [`references/optional-sections.md`](references/optional-sections.md)。

### 4e — Type B additional sections

Type B 交接在核心區塊之後、可選區塊之前追加任務相關區塊（目標、現有邏輯、驗收標準、不需處理）。見 [`references/type-b-structure.md`](references/type-b-structure.md)。

### 4f — Action tracker sync (opt-in)

若使用者設定了 `ACTION_TRACKER`，同步本次完成與待辦項目到跨工作區行動清單。見 [`references/action-tracker-sync.md`](references/action-tracker-sync.md)。未設定則跳過。

## 寫作原則

交接文件的主要讀者是接手的 Claude，設計目標是讓它用最少 token 建立完整的工作上下文。

- **因果鏈顯式化**：不只記「做了什麼」，也記「為什麼這樣做」和「考慮過但排除了什麼」。接手 Claude 最浪費時間的事是重新探索已經走過的死路
- **路徑全部自包含**：所有路徑 `~` 開頭。接手的 Claude 對當前對話零知識，任何需要猜測的路徑都是效率損失
- **待辦的時間壓力和依賴關係顯式標出**：用截止日期分組，每項附帶理由（例如「3/14 前——因為 3/20 出發前必須完成」），讓接手 Claude 能自行判斷優先級
- **時間戳記使用 Step 0 查到的實際時間**，不可推測
- **產出物條款**：每個待辦附一句「完成長什麼樣」——完成後哪個檔案會存在、會含什麼內容。例：「完成後 `_wiki/X.md` 會存在且含『驗收條件』段」「完成後 `versions/` 下會有 v0.3.1 的驗證報告」

  > **為何**（2026-08-29 立案，來自 8 則舊交接語的核實盤查）：沒寫產出物的交接，一個月後無法判斷做完沒。實測 8 則中，原判「已被做掉」的 6 則有 5 則不成立——因為判定者手上沒有「完成該長什麼樣」的標準，只能拿周邊訊號代替（同工作區後續有交接文件、`_wiki` 寫「已落地」、README 有版本段），而這三類訊號都會系統性地把未完成判成完成。
  >
  > 唯一能斬釘截鐵判「沒落地」的那則，是因為它有份 SPEC 寫死驗收條件，一 `grep` 就知道。**一句話的成本，換一個月後可機械化查證。**
  >
  > 詳見 [[false-completion-signals]]。

## Step 5: Generate and present handoff message

寫完交接文件後，在對話視窗中輸出交接語作為獨立段落。使用者會複製這段交接語貼到新對話啟動下個 session——他們不應該為了找交接語而打開交接文件。

### 輸出規則

交接語以純文字形式輸出——前面不加 blockquote（`>`）、不加 code block（三個 backtick），前後留空行與其他段落區隔。這樣使用者的剪貼簿只會抓到交接語內容；許多 markdown 渲染器會把 blockquote 和 code block 的前綴符號一起複製，污染貼上的訊息。

### 交接語模板

（以下 code block 僅為模板示範用。實際輸出到對話視窗時，請移除 code block 包裝，改為純文字獨立段落。）

**桌面端（交接文件已存在使用者電腦上）：**

```
我正在進行 [專案名稱]。請先讀取以下交接摘要，裡面包含完整的專案背景、已完成事項、待辦清單：

[交接文件的完整 ~ 路徑]

工作區根目錄：[~/... 完整路徑]

目前進度：[一句話摘要當前狀態與下一步]
結束狀態：[完成/中斷/分支 — exit_condition 內容]
建議模型：[選擇性，見下方「建議模型欄位」段]
```

**網頁 / 手機端（交接文件需要使用者手動存檔）：**

```
我正在進行 [專案名稱]。我有一份交接摘要需要你先讀取。

請先讀取我上傳的交接文件（Handoff_YYYY-MM-DD_slug.md），裡面包含完整的背景、已完成事項、待辦清單。

工作區根目錄：[~/... 完整路徑]

目前進度：[一句話摘要當前狀態與下一步]
結束狀態：[完成/中斷/分支 — exit_condition 內容]
建議模型：[選擇性，見下方「建議模型欄位」段]
```

**Type B — 程式任務交接：**

```
[一句話描述任務]。請先讀取以下任務交接文件，裡面包含任務目標、現有邏輯、驗收標準：

[交接文件的完整 ~ 路徑]

工作區根目錄：[~/... 完整路徑]

主要改動：[列出關鍵變更點，讓接手 agent 快速掌握範圍]
結束狀態：[完成/中斷/分支 — exit_condition 內容]
建議模型：[選擇性，見下方「建議模型欄位」段]
```

### 建議模型欄位（選擇性）

此欄位的目的：讓接手對話啟動時直接看到模型路由建議，不必自行對照 CLAUDE.md 的路由規則。

填寫規則（依情境擇一，**不適用就整行省略**）：

- **單階段任務**：直接列模型，例：`Opus（計畫撰寫）` 或 `Sonnet（文件轉換）`
- **多階段且各階段適用模型不同**：分階段列，例：
  ```
  建議模型：
    - 階段 1（公文消化）：Sonnet
    - 階段 2（資料夾結構盤點）：Opus
    - 階段 3（主文撰寫）：Opus
  ```
- **任務性質與工作區 CLAUDE.md 路由規則一致**：寫「依專案規則」，例：`依 ~/資料/About Project/CLAUDE.md 模型選用段`
- **無明顯路由建議**：整行省略，不要勉強填

判斷依據：使用者的全域 CLAUDE.md「模型選用」段、工作區 CLAUDE.md「模型選用」段、`task-dispatch` skill。模型選用本體規則仍以 CLAUDE.md 為單一真實來源，本欄位只是「在當下情境下套用規則的結果」。

### 交接語原則

- 第一行說明專案名稱
- 交接文件路徑和工作區根目錄都必須是 **`~` 開頭的完整路徑**
- 如果交接文件不在使用者電腦上，提醒使用者先上傳或手動存檔
- 用一句話摘要當前進度與建議的下一步
- 如果有 INDEX.md 或其他導航檔案，也一併提及其完整路徑
- 保持簡潔，預設不超過 8 行；若多階段「建議模型」需展開，可放寬到 12 行
- **建議模型**欄位只在能給出有用路由時才填，不適用就省略整行（不要寫「無建議」這種佔位）

## Step 5.5: Append 交接語到統籌檔（必做，不可省略）

輸出交接語到對話視窗後，**同一輪內**把它 append 到交接語統籌檔。使用者不必再手動貼上。

**目標檔案**：`~/資料/_harness/交接語/OPEN.md`

> 路徑固定，不隨工作區變動。`~/資料` 由 `$CLAUDE_DATA_ROOT` 對應各機器 iCloud 路徑（三台 Mac 路徑不同，故一律用 `~/資料/` 寫法，不硬編碼）。
> 若該檔不存在（新機器、或使用者尚未建立），先 `mkdir -p ~/資料/_harness/交接語/已啟動` 並建立 OPEN.md 骨架，再 append。

**寫入格式**（append 到檔尾）：

```markdown
## [YYYY-MM-DD HH:MM] <專案名稱>

| | |
|---|---|
| 狀態 | 待啟動 |
| 工作區 | `~/...` |
| 交接文件 | `~/.../Handoff_YYYY-MM-DD_slug.md` |
| 結束狀態 | 完成／中斷／分支 — <exit_condition> |

### 交接語

<交接語全文，純文字，與 Step 5 輸出到對話視窗的內容逐字相同>

---
```

**規則**：

- **時間戳用 Step 0 取得的真實時間**，不估算
- **狀態欄不是只有「待啟動」**。三種值：
  - `待啟動` — 現在就能開工
  - `待啟動` ＋另加一列 `| 期限 | <日期> |` — 有時間壓力時期限**獨立成列**，不寫進狀態欄
  - `⏸ 前置條件未成熟——現在不要做` — 另加一列 `| 前置 | <條件> |` 說明要等什麼
  混在一起會讓使用者看到就以為現在該做（2026-08-27 實測發現）
- **期限只寫日期，不寫倒數，不加符號**（老師 2026-08-29 裁決：「保留期限不寫倒數」）
  - ✅ `| 期限 | 9/07 送件 |`
  - ❌ `| 狀態 | 🔴 待啟動 ⏰ 9/07 死線，剩 10 天 |`
  > **為何**：「剩 10 天」是寫入當下算的靜態值，明天讀就是錯的——**寫死的日期不會爛，寫死的倒數會**。符號（⏰🔴）同時把常駐文件變成警報器，違反 `~/.claude/CLAUDE.md`〈認知負荷紀律〉第 1 條「時限不推播只擺放」：OPEN.md 是老師主動去看的時鐘，不是打斷他的警報器。
  >
  > **已知缺口（非本規則造成）**：老師有時間盲，看到「9/07」不會自動換算成「還有多久」。真正的解是讀期限欄即時算倒數的小工具，**尚未實作**——在那之前寧可少給，不給錯的。
- 若多則之間有連動（A 成案則 B 的前置即滿足），加一列 `| 連動 | <說明> |` 互指
- **欄位不寫行數、不寫檔案大小**。這類數字會隨檔案更新過期，而使用者複製交接語時根本不看（2026-08-27 實測：某筆從 354 行變 365 行）。路徑才是不變的識別
  > 同一判準也適用交接文件內文引用其他檔案時：**問「行數是不是這次判斷的依據」**——只是描述規模就不寫，是論證依據（如「這份 354 行太長要拆」）才留
- 交接語內容與 Step 5 輸出**逐字相同**——使用者從檔案或從對話視窗複製，拿到的必須是同一段
- **append 不覆寫**。OPEN.md 是累積檔，絕不整檔重寫（呼應 `~/資料/CLAUDE.md` Protected Files 精神）
- 同一次交接產生多份交接文件（多專案交錯）時，**每份各 append 一則**
- append 完成後，在回覆中用一行告知路徑，例：`交接語已寫入 ~/資料/_harness/交接語/OPEN.md`。不必展示檔案內容
- 若寫入失敗（路徑不存在且無法建立、權限問題），**明講失敗**並提醒使用者手動保存，不要靜默略過

### 退場檢查（append 完成後，同一輪內做）

**只檢查同工作區的既有條目**，不掃全檔、不做通盤整理。

1. append 完後，`grep` OPEN.md 裡 `| 工作區 |` 欄與本次相同的其他條目
2. 每則問一題：**這次的交接是否已經取代它？**（同一條工作線的後續進展 → 是；同工作區但不同任務 → 否）
3. 判定為取代的，整則剪到 `~/資料/_harness/交接語/已啟動/YYYY-MM.md`（該月檔不存在就建），並在條目前加一行 `## 退場理由：<一句話>`
4. 判不準的**不要動**，改在回覆中用一行問使用者：「OPEN.md 裡還有一則 <標題>，這次的交接是否已取代它？」

**只退場「被本次交接取代」的**。其他過期條目（老師自己做掉的、外部事件消失的）不在此範圍，那是專門對話的工作。

> **為何加這條**（2026-08-29 立案）：原本此處寫「不判斷舊條目是否過期」，結果 OPEN.md 只有寫入沒有退場——`已啟動/` 自 8/27 建立起**完全是空的**，13 則全積在 OPEN.md，其中 4 則早被後續交接取代仍列「待啟動」。老師原話：「它在寫交接的時候好像沒有自動更新的機制…有時候工作做到一半還沒正式交接，OPEN.md 就不會自己更新，這樣會有點麻煩。」
>
> 寫入的那一刻是**唯一**能確知「這則取代了哪一則」的時機——此時舊條目的脈絡就在對話裡。錯過就只能靠事後盤查。原規則把這個判斷推遲到「專門對話」，而那個對話兩天沒發生。

**仍然不做的事**：

- 不對整份 OPEN.md 做去重或重新排序
- 不刪除任何條目（退場是**剪到** `已啟動/`，不是刪除）
- 不判斷非本次交接所取代的條目是否過期
- 不把交接語同時寫進其他地方（`_monitoring/_handoffs/INDEX.md` 索引的是**交接文件**，不是交接語，兩者不重複）

## Notes

- 如果對話中有多個專案交錯討論，分別建立交接文件
- 如果已有同日同主題的交接文件，更新既有檔案而非建立新檔
- **已確認的下一步直接執行**：若交接文件或使用者指令已明確指出下一步，完成當前步驟後直接執行，不插入確認問題
- **時間相關操作**：當討論涉及排程、提醒、截止時間、或判斷「現在適合做什麼」時，請先用 `date '+%Y-%m-%d %H:%M:%S %Z'` 取得精確時間
- **自足原則**：交接文件應讓下一個 session 不需回看對話紀錄就能接續工作。目標、已完成、產出路徑、下一步指令、交接語——全部具備、全部明示

## Related skill: save-conversation

本 skill 執行的是**主動壓縮**——為了下一個任務，篩選並重構對話內容，刻意捨去不需延續的資訊。

若使用者同時想保留**原始、未壓縮的完整對話紀錄**，那是另一個獨立需求，由 `save-conversation` skill 處理。兩者互補：

- `handoff` → 壓縮後的前瞻性摘要，讀者是下個 session
- `save-conversation` → 原始存檔，事後參考用，讀者是人類

同一次對話中可以兩個都執行。依序執行（先 `handoff`、再 `save-conversation`）會產出兩份獨立檔案，互不干擾。
