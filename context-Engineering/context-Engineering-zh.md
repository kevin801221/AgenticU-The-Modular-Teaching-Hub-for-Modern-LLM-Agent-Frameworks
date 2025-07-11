# AI智能體情境工程：完整教學指南

## 目錄
1. [簡介](#簡介)
2. [理解情境類型](#理解情境類型)
3. [情境工程四大支柱](#情境工程四大支柱)
4. [實作策略](#實作策略)
5. [最佳實踐](#最佳實踐)
6. [結論](#結論)

## 簡介

隨著AI智能體變得越來越複雜，有效管理其情境已成為關鍵課題。**情境工程**是在智能體執行的每個步驟中，精確地將正確資訊填入大型語言模型情境窗口的藝術與科學。

### 為什麼情境工程很重要

可以將LLM想像成一種新的作業系統：
- **LLM** 充當CPU
- **情境窗口** 作為RAM（工作記憶體）
- **情境工程** 如同OS管理哪些內容適合載入RAM

如Andrej Karpathy所描述：情境工程是*「為下一個步驟填入情境窗口中恰當資訊的精妙藝術與科學」*。

### 常見情境挑戰

長時間運行的智能體任務常導致：
- **情境污染**：幻覺進入情境中
- **情境干擾**：情境壓制了訓練效果
- **情境混淆**：多餘情境影響回應
- **情境衝突**：情境中資訊相互矛盾

## 理解情境類型

在深入策略之前，讓我們先識別LLM應用中的主要情境類型：

### 1. 指令類型
- 提示詞和系統訊息
- 少樣本學習範例
- 工具描述
- 行為準則

### 2. 知識類型
- 事實和資訊
- 領域專業數據
- 歷史情境

### 3. 工具類型
- 工具調用回饋
- API回應
- 環境狀態

## 情境工程四大支柱

### 1. 寫入情境 📝

**目的**：將資訊保存在情境窗口外以供未來使用。

#### 暫存記錄
智能體可以在執行任務時做「筆記」，類似人類解決問題的方式。

**實現方法**：
- 寫入檔案的工具調用
- 運行時狀態物件欄位
- 持久化會話儲存

**使用案例範例**：
當Anthropic的多智能體研究員超過200,000個令牌時，它會將計劃保存到記憶體中以防止截斷損失。

#### 記憶體
跨多個會話持久化資訊以進行長期學習。

**記憶體類型**：
- **情節記憶**：特定經驗和範例
- **程序記憶**：指令和行為模式
- **語義記憶**：事實和關係

**真實世界範例**：
- ChatGPT的自動生成用戶記憶
- Cursor的規則檔案
- Windsurf的持久情境

### 2. 選擇情境 🎯

**目的**：在需要時將相關資訊拉入情境窗口。

#### 從暫存記錄選擇
- **基於工具**：智能體透過工具調用讀取
- **基於狀態**：開發者控制暴露哪些狀態

#### 從記憶體選擇
選擇與當前任務相關的記憶：
- 期望行為的少樣本範例
- 行為引導的指令
- 任務相關情境的事實

**選擇挑戰**：
- 確保相關性（避免意外注入）
- 管理大型記憶體集合
- 維護用戶對情境的控制

**選擇方法**：
- 基於嵌入的相似性搜尋
- 知識圖譜遍歷
- 基於規則的過濾

#### 工具選擇
對工具描述使用RAG來避免工具過載和混淆。

**優點**：
- 工具選擇準確性提升3倍
- 減少模型混淆
- 更好的任務表現

### 3. 壓縮情境 🗜️

**目的**：只保留完成任務必需的令牌。

#### 情境摘要
**何時使用**：
- 跨越數百次互動的多輪對話
- 令牌密集的工具調用結果
- 智能體間知識交接

**摘要策略**：
- **遞歸式**：對摘要進行摘要以實現深度壓縮
- **階層式**：多層級摘要
- **目標式**：專注於特定事件或決策

**範例**：Claude Code的自動壓縮功能在接近情境限制時摘要完整的互動軌跡。

#### 情境修剪
**方法**：
- **硬編碼啟發式**：移除較舊的訊息
- **訓練修剪器**：用於智能過濾的ML模型
- **基於規則的過濾**：根據內容類型或相關性移除

### 4. 隔離情境 🏗️

**目的**：將情境分割到不同空間以管理複雜性。

#### 多智能體架構
將情境分佈到專門的子智能體中。

**優點**：
- 每個智能體專注於狹窄的子任務
- 不同方面的並行處理
- 更清潔的關注點分離

**挑戰**：
- 令牌使用量增加（高達15倍）
- 複雜的協調需求
- 需要謹慎的提示工程

#### 環境隔離
使用沙盒將令牌密集的物件與LLM隔離。

**範例**：HuggingFace的CodeAgent在沙盒中運行工具調用，只將選定的結果傳回LLM。

**優勢**：
- 更好的狀態管理
- 大型物件（圖像、音頻、數據）的隔離
- 減少情境污染

#### 基於狀態的隔離
使用結構化狀態物件與選擇性欄位暴露。

**實現**：
- 為不同情境類型設計特定欄位的架構
- 在每個步驟只向LLM暴露相關欄位
- 維護隔離儲存供後續使用

## 實作策略

### 開始步驟

#### 1. 優先建立可觀測性
- 追蹤智能體互動中的令牌使用
- 監控情境窗口利用率
- 識別瓶頸和低效率

#### 2. 建立測試框架
- 為智能體性能創建評估指標
- 系統性測試情境工程變更
- 測量對任務成功率的影響

### LangGraph實現範例

#### 寫入情境
```python
# 短期記憶（暫存記錄）
class AgentState(TypedDict):
    messages: List[BaseMessage]
    scratchpad: Dict[str, Any]
    
# 長期記憶
memory = LangGraphMemory()
memory.save("user_preferences", user_data)
```

#### 選擇情境
```python
# 細粒度狀態控制
def agent_node(state: AgentState):
    relevant_context = select_relevant_memories(state.current_task)
    # 只包含此步驟需要的內容
    return {"context": relevant_context}
```

#### 壓縮情境
```python
# 定期摘要
def summarize_if_needed(state: AgentState):
    if len(state.messages) > threshold:
        summary = summarize_conversation(state.messages)
        return {"messages": [summary] + state.messages[-5:]}
    return state
```

#### 隔離情境
```python
# 多智能體隔離
supervisor = SupervisorAgent()
research_agent = ResearchAgent()
writing_agent = WritingAgent()

# 每個智能體維護獨立情境
```

## 最佳實踐

### 1. 情境審計
- 定期檢查情境中的內容
- 移除冗餘或過時資訊
- 監控情境污染

### 2. 選擇性暴露
- 不要將所有內容都倒入情境
- 使用相關性評分進行記憶選擇
- 實現情境新鮮度追蹤

### 3. 階層組織
- 將情境結構化為層次（即時、會話、長期）
- 對不同情境類型使用不同策略
- 維護情境類別間的清晰分離

### 4. 性能監控
- 追蹤情境與性能的關係
- A/B測試不同情境策略
- 監控令牌成本和延遲

### 5. 用戶控制
- 允許用戶影響情境選擇
- 提供使用哪些情境的透明度
- 使用戶能夠糾正或覆蓋情境決策

## 常見陷阱避免

### ❌ 情境過載
不要「以防萬一」就包含所有內容 - 要有選擇性和目的性。

### ❌ 陳舊情境
定期刷新和驗證情境相關性。

### ❌ 忽略用戶意圖
確保情境選擇與用戶目標和期望一致。

### ❌ 過度壓縮
不要為了追求令牌效率而丟失關鍵資訊。

### ❌ 隔離不當
在不同類型的情境間維護清晰邊界。

## 結論

情境工程正成為AI智能體開發者的必備技能。四大支柱 - **寫入**、**選擇**、**壓縮**和**隔離** - 提供了有效管理情境的全面框架。

### 關鍵要點

1. **情境是有限的** - 將其視為珍貴資源
2. **策略很重要** - 不同情境類型需要不同方法
3. **可觀測性至關重要** - 無法測量就無法優化
4. **測試必不可少** - 始終驗證情境變更是否提升性能
5. **用戶體驗重要** - 情境決策應該增強而非驚嚇用戶

### 下一步行動

1. 審計你當前智能體的情境使用
2. 識別最大的情境低效率問題
3. 一次實現一個支柱
4. 測量和迭代改進
5. 將成功模式擴展到整個智能體架構

記住：情境工程既是藝術也是科學。從穩固的可觀測性開始，系統性地實驗，並始終將最終用戶體驗放在心上。

---

*如需更高級的實現和範例，請探索LangGraph的文檔，並考慮使用LangSmith平台進行全面的智能體可觀測性和測試。*