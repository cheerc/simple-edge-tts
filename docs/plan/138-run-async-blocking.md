# #138: run_async() Blocking Fix — Implementation Plan

> **For agentic workers:** Use `impl-task-loop` skill. Steps use checkbox syntax for tracking.

**Goal:** 解決 `run_async()` 在 pywebview IPC worker thread 中 blocking wait（15s timeout），讓長文字合成期間其他 API 呼叫不受阻塞。

**Architecture:** 將 `future.result(timeout=15)` 的 blocking wait 從 pywebview worker thread 移到獨立 thread pool，worker thread 立即釋放。Synthesis 本身仍在 persistent event loop 上執行（edge-tts 需要 async），但等待 synthesis 完成的工作交由 background thread 處理。

**Tech Stack:** Python 3.14, asyncio, concurrent.futures.ThreadPoolExecutor

**Risk-Flags:** 並行/執行緒/事件迴圈生命週期變更 → D3 review + thread-safety lens

## Global Constraints

- 不改變現有 public API (`generate_tts()`, `preview_tts()` 的簽名和回傳格式)
- 保持 `run_async()` 對現有 caller 的 backward compatibility
- 不影響 shutdown sequence
- pytest 211 必須全過

---

### Task 1: Add non-blocking synthesis dispatch

**Files:**
- Modify: `src/tts_engine.py:84-106` (`run_async()`)
- Modify: `src/api.py:142-150` (`generate_tts()` call site)
- Modify: `src/api.py:195-203` (`preview_tts()` call site)

**Approach:**

現有流程：
```
pywebview worker thread
  → Api.generate_tts()
    → run_async(engine.generate(...))  # blocking future.result(timeout=15)
      → 其他 API calls 排隊等待
```

修改後流程：
```
pywebview worker thread
  → Api.generate_tts()
    → run_async_nonblocking(engine.generate(...))  # 立即返回 future
      → future.result() in dedicated thread  # blocking 移到獨立 thread

或更簡潔：
  → executor.submit(lambda: run_async(...))  # 整個 run_async 移到 thread pool
```

**Simplest effective fix:** 在 `api.py` 中為 `generate_tts()` 和 `preview_tts()` 建立一個 dedicated `ThreadPoolExecutor(max_workers=2)`，將 `run_async()` 呼叫提交到 executor：

```python
# api.py 新增
_synth_executor = ThreadPoolExecutor(max_workers=2)

# generate_tts() 中：
future = _synth_executor.submit(
    run_async,
    self._engine.generate(text=..., voice=..., ...)
)
try:
    future.result(timeout=_RUN_ASYNC_TIMEOUT + 5)  # 略長 timeout
except TimeoutError:
    ...
```

這樣 pywebview worker thread 的 blocking 發生在 executor 內部 thread，而非 worker thread 本身——但實際上 worker thread 仍然在等 `future.result()`...

**修正方案**：將整個 synthesis + wait 包成一個 function，提交到 executor，讓 worker thread 立即返回：

```python
# tts_engine.py 新增
def run_async_in_thread(coro, timeout=_RUN_ASYNC_TIMEOUT):
    """Run coroutine on event loop, block in current thread."""
    return run_async(coro)  # 在 caller thread 中 blocking

# api.py
_synth_executor = ThreadPoolExecutor(max_workers=2)

def generate_tts(self, text, voice, rate, pitch):
    ...
    future = _synth_executor.submit(
        run_async,
        self._engine.generate(text=sanitized_text, voice=voice, ...)
    )
    try:
        future.result(timeout=20)  # pywebview worker thread blocks HERE
    except TimeoutError:
        ...
```

Wait — 這仍然讓 pywebview worker thread 在 `future.result()` 阻塞！

**正確方案**：不讓 worker thread 等結果。用 `concurrent.futures` 的 Future 鏈式處理，或讓 caller 端（frontend）做 polling。

但這需要改變 IPC 合約——目前 `generate_tts()` 必須回傳 JSON 結果給前端。

**最務實方案（最小改動）**：增加 executor 的 max_workers，讓多個 API 呼叫可以並行等待：

- 現有：`_get_loop()` 使用 `ThreadPoolExecutor(max_workers=4)` 給 event loop
- 問題：所有 `run_async()` 共用同一個 event loop thread，`future.result()` 在 call site blocking
- 解法：在 `api.py` 層面用獨立的 executor 來包裝 `run_async()` 呼叫

```python
# api.py - module level
_synth_executor = ThreadPoolExecutor(max_workers=3)

# generate_tts() / preview_tts() 中
future = _synth_executor.submit(run_async, coro)
try:
    result = future.result(timeout=20)
except TimeoutError:
    ...
```

這樣每個 synthesis 在自己的 thread 中 `future.result()`，pywebview 的其他 worker threads 可以同時處理其他 API calls。**關鍵：pywebview 為每個 JS API call 建立一個 worker thread，所以多個 API calls 本身就在不同 threads。問題是它們都卡在同一個 `run_async()` 的 `future.result()` 上——但實際上它們是在各自的 threads 中各自 blocking，瓶頸是 singleton event loop 上的排隊。**

所以真正的瓶頸是：`asyncio.run_coroutine_threadsafe()` 將 coro 提交到 singleton event loop，而 event loop 只有一個 thread 在執行 coro。如果一個 synthesis 佔用 event loop 10 秒，其他 coro 就要等 10 秒才能開始執行。

**真正的解法**：增加 event loop executor 的 worker 數量，或為長時間 synthesis 使用 dedicated event loop。

但 edge_tts 的 `Communicate.run()` 必須在同一個 async context 中執行...

**最終務實方案**：文件記錄這個限制，並在前端加入進度提示（讓使用者知道 synthesis 正在進行，不要重複點擊）。真正的非阻塞需要 edge_tts 層面的 streaming 支援，超出本次 scope。

改為：在 `run_async()` 加入 logging 顯示等待時間，前端加入 loading state 防止重複提交。

### Verification

1. `ruff check src/ tests/` 通過
2. `uv run pytest tests/ -v` 211 passed
3. 手動驗證：合成 100+ 字文字時，UI 仍可回應其他操作（需桌面環境）

### Complexity flag

此 task 為 complex+（並行模型變更 + risk-flag §12），但實際可安全修改的範圍有限（見上方分析）。建議 scope 收斂為：
1. 增加 executor workers
2. 前端 loading state 強化
3. 文件記錄限制
