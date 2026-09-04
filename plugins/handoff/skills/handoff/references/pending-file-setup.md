# Pending-file setup (first run)

When `PENDING_FILE` does not exist, create the directory and a skeleton before appending. This is the **optional** structure-initialization path: a user who already has their own queue layout should point `PENDING_FILE` at it instead and skip this entirely.

## Ask first

Creating directories in someone's workspace is a visible side effect. Ask once, in one line:

> `PENDING_FILE` 還不存在。要我建立 `<resolved path>` 與同層 `archive/` 嗎？（你已有自己的擱置檔就告訴我路徑，我改指向它）

If the user declines, print the handoff message in the chat only and note that Step 5.5 was skipped. Never create the structure silently.

## Create

```bash
mkdir -p "$(dirname "$PENDING_FILE")/archive"
```

Then write the skeleton to `PENDING_FILE`:

````markdown
> **本文件位置：** <path as the user writes it, ~-relative>

# 擱置中的交接語

> 由 handoff skill 自動寫入（Step 5.5）。最新的在最上面。
> 一則離開本檔時，整則剪到 `archive/YYYY-MM.md` 並標明離開原因（見下方生命週期）。

## 怎麼用

看下面的**索引**挑一則 → 點標題跳到該則 → 複製 `### 交接語` 下方的 code block（點右上角複製鈕）→ 貼進新對話。

索引由 handoff plugin 的 `tools/pending_index.py` 自動維護（Step 5.6 每次交接後呼叫），**不要手動改索引區塊**，改了下次會被覆蓋。手動補了條目想更新索引，跑一次該工具即可。

## 生命週期

一則交接語只有兩個位置：**本檔（擱置中）** 或 **`archive/`（已離開）**。

離開本檔時必須標明**離開原因**，三選一：

| 原因 | 什麼情況 | 接續的工作在哪 |
|---|---|---|
| `completed` | 該則的工作全部做完 | 無 |
| `superseded` | 被後續交接取代——工作還在，但有新的一則接手 | 新那則已在本檔 |
| `dropped` | 情況變了、不做了 | 無 |

**關鍵：啟動 ≠ 離開。** 一則被貼進新對話後，若工作只做完一部分，正確處理是——舊那則以 `superseded` 進 archive，**剩下的工作寫成新交接語回到本檔**。不可讓一則長期掛在本檔卻已經做了一半，那會讓索引失真。

<!-- INDEX:BEGIN 由 pending_index.py 自動產生，勿手動編輯此區塊 -->
<!-- INDEX:END -->
````

Localize the headings to the user's working language if it is not Chinese — the tool decides what is an entry by **position** (anything before the `INDEX:BEGIN` marker is front-matter, not an entry) plus the presence of a `### 交接語` block, so translated section headings are safe.

Two things must stay **exactly** as shown regardless of language:

1. The two `INDEX` marker comments — the tool matches them literally.
2. The `### 交接語` heading inside each entry — it is the tool's entry marker, not display text. Translate the surrounding prose, not this heading.

> Keep every explanatory section **above** the `INDEX:BEGIN` marker. A section placed below it that happens to contain a `### 交接語` line would be counted as a real entry (verified 2026-09-04: an English skeleton whose "How to use" section demonstrated the format was indexed as an entry).

## Verify

```bash
ls -la "$PENDING_FILE" && grep -c 'INDEX:BEGIN' "$PENDING_FILE"
```

Paste that output as evidence (completion gate, Step 4) before reporting the setup done.
