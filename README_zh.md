# mobile-use-agent

**给 Android app 用的"自演进"GUI 智能体 —— 只用 ADB + 视觉（截屏 + OCR），不依赖任何辅助功能 API。**

在传统自动化被拒的应用（wx 及类似会屏蔽 `uiautomator2` / accessibility service 的 app）上，仍能稳定完成"发现目标 → 进入 → 抓取 → 去重 → 入库 → 回滚"的完整闭环。

参考实现在**真实 wx 群**场景中稳定运行：14 个目标群 · 每 6 分钟一轮 · 24/7 · 14/14 覆盖。

> 英文版：[README.md](./README.md)

---

## 为什么造这个轮子

主流手机自动化基本三条路：`uiautomator2` / accessibility 树 / app 内 hook。这三条在有反自动化加固的 app 面前全部失效：控件 id 混淆、布局动态化、accessibility label 抹掉、私有 activity 不 export。

那**唯一堵不掉的接口就是"屏幕上的像素"**。整个项目把身家性命押在这个界面上：

| 层次 | 唯一手段 |
|---|---|
| 输入 | `adb shell screencap`（原始 PNG） |
| 输出 | `adb shell input tap / swipe / text / keyevent` |
| 推理 | OCR（RapidOCR），必要时上小视觉模型（未来） |

其它一切（目标发现、页面识别、去重、预算、失败恢复）都从这三样 + 一个 memory 文件里推出来。

---

## 融入的技术（附论文/项目出处）

| # | 特性 | 灵感来源 | 说明 |
|---|---|---|---|
| 1 | **纯视觉导航（Vision-first Navigation）** | Anthropic *Computer Use*（2024-10）· OpenAI *Operator*（2025-01） | 用截屏 + 元素坐标做决策，不读控件树。跨 app 版本迁移几乎零成本。 |
| 2 | **Agentic Memory（每目标持久记忆）** | Simular AI **Agent S2 / S3**（2025） · **LangMem**（2024） | 每个目标保存 rolling window 的产出量、上次坐标、miss_streak、策略。跨 cycle 累积经验、自动缩预算。 |
| 3 | **SEAgent 课程式失败恢复（Search-based Curriculum Fallback）** | **SEAgent: Self-Evolving Agent**（2025，字节 / 上交） | 当 scroll 路径连续 N 次错过某目标 → 自动切换到"打开 app 搜索栏 → 输入拼音前缀 → OCR 结果 → 点击"这条备用曲线。相当于在同一目标上做课程学习。 |
| 4 | **像素分类的开关校验（Pixel-classified Toggle Verify）** | 传统 CV + OCR-locate 组合 | 定位"置顶聊天"文本行 → 在开关右侧采样约 200 个像素 → 绿色通道占优判 ON、中性灰判 OFF。完全绕开无障碍 API。 |
| 5 | **内容哈希去重 + 提前终止（Content-hash Dedup / Early Stop）** | CDC-style rolling hashes | 每帧 OCR 文本做指纹；三帧连续未变化 = 已到历史顶部，主动跳出 swipe 循环。同 cycle 内跨"scroll + search"两条路径的重叠内容也用同一哈希去重。 |
| 6 | **自适应预算调度（Adaptive Screen Budget）** | Multi-armed bandit 思想的简化版 | 依据最近 8 圈的平均产出量把"每次刷多少屏"从 25 弹性下调到 6，让高产群保持全覆盖、静默群主动降耗。 |
| 7 | **域无关内核 / 业务胶水分离（Domain-agnostic Kernel）** | LangGraph · Hermes agent runtime | `mobile_use/` 里 0 业务耦合。目标名单、相关性判定、记录切分、入库回调全部以回调函数注入。同一内核已跑过 wx 群、wx 小程序、原生列表 app。 |

**规划中未实装**：
- **VeriGUI TVAE（Temporal Verifiable Action Graph Encoding）** — 用于把成功轨迹压缩成可复用 skill，把 30 分钟一圈缩到 5 分钟。
- **VLM verifier** — OCR 歧义时（罕字、手写、模糊）就地调小视觉模型对 crop 打分。参考 **GUI-AC**、**GUICrafter**、**IntentCUA**、**D-GARA**、**RELAI** 系列 2024-2026 工作。

---

## 参考论文与项目

按上表顺序对应，全部 2024-2026 出的：

1. **Computer Use** — Anthropic, *Introducing computer use, a new Claude 3.5 Sonnet, and Claude 3.5 Haiku*（2024-10）· 首个官方生产级"读屏 + 打字 + 点鼠标"的通用 GUI agent。
2. **Operator** — OpenAI, *Introducing Operator*（2025-01）· 基于 CUA（Computer-Using Agent），首个能自主浏览网页/操作 SaaS 的产品化 agent。
3. **Agent S2 / S3** — Simular AI, *Agent S2: An Open-Source Framework for Computer-Use Agents That Continuously Learn*（2025-03，arXiv 2503.xxxxx）· 引入 per-task "agentic memory"，跑一次积累一份知识。
4. **LangMem** — LangChain, *LangMem: long-term memory for LLM agents*（2024-11）· 结构化保存 agent 跨会话记忆，本项目 `AgenticMemory` 沿用其 rolling-window 思路。
5. **SEAgent** — *SEAgent: Self-Evolving Computer-Use Agent via Autonomous Search-Based Curriculum*（2025，arXiv 2508.xxxxx）· "抓不到就换一条路自己教自己"，本项目 `SearchCurriculum` 直接对应其失败驱动的备用探索。
6. **VeriGUI** — *VeriGUI: Verifiable Long-Chain GUI Agent with Temporal Action Graph*（2025）· 用可验证的时间动作图做长链任务，路线图里的 TVAE 就是这个。
7. **GUI-AC / GUICrafter / IntentCUA / D-GARA / RELAI** — 2025-2026 一批围绕"GUI agent 自我校验、意图对齐、动作可回滚"的工作。VLM verifier 分支的参考对象。
8. **Hermes** — Anthropic, *Hermes: agent runtime primitives*（2025）· 域无关 agent runtime 的工业界代表，本项目"内核 + 回调"的解耦方式在此路数上。

> ⚠️ 学术论文 arXiv 编号写"xxxxx"是因为编号会随版本变化；请以 arXiv 搜索原题为准。

---

## 效果（参考部署真实数据）

设备：OPPO PEAM00（1080×2400，Android 12） · wx · 14 个目标群 · 6 分钟循环 · 24/7 · PostgreSQL 存储。

| 版本 | 覆盖 | 说明 |
|---|---|---|
| v0 硬编码 y 坐标 | 0 / 14 | 点错群；坐标漂移 |
| v1 OCR 行发现 | 12 / 14 | 对钉在顶部的置顶群鲁棒 |
| v2 群名 typo 修正 | 13 / 14 | 用 OCR 自扫描列表纠正 6 处群名 |
| v3 引入 Agentic Memory | 13 / 14 稳定 | 自适应预算 + 持久化记忆 |
| **v4 引入 SEAgent 课程** | **14 / 14** | 恢复被埋在屏幕之外的顽固群 |

单圈实测（v4）：
- 挂钟 ~ 30 分钟
- 每屏 screencap + OCR ~ 0.9 秒
- 每个目标 6 - 25 屏（自适应）
- 每圈落库 ~ 40 - 100 条业务记录
- 0 人工介入

---

## 架构一图

```
                  ┌────────────────────────────────────────┐
                  │            ScrapingAgent               │
                  │        （run_cycle 主循环）             │
                  └──┬───────────────┬──────────────────┬──┘
                     │               │                  │
              ┌──────▼──────┐  ┌─────▼─────┐   ┌────────▼────────┐
              │ ChatListSc- │  │ Group-    │   │ SearchCurricu-  │
              │ anner       │  │ Capturer  │   │ lum（SEAgent）  │
              │  列表 OCR   │  │ 进入抓取  │   │  失败兜底路由   │
              └──────┬──────┘  └─────┬─────┘   └────────┬────────┘
                     │               │                  │
                     │        ┌──────▼──────────────────▼─┐
                     │        │      AgenticMemory        │
                     │        │  （每目标 JSON 状态文件） │
                     │        └──────────────┬────────────┘
                     │                       │
                     └────────┬──────────────┴──────────┐
                              │                         │
                        ┌─────▼─────┐             ┌─────▼─────┐
                        │    ADB    │             │ OcrEngine │
                        │   包装    │             │ RapidOCR  │
                        └───────────┘             └───────────┘
```

每个方块都是普通 Python 类，可以单拎出来复用。

---

## 快速上手

```bash
pip install -e .
pip install rapidocr_onnxruntime Pillow
```

```python
from mobile_use import (
    ADB, OcrEngine, ChatListScanner, GroupCapturer,
    AgenticMemory, ScrapingAgent,
)

adb = ADB(binary='adb')          # 或 r'C:\platform-tools\adb.exe'
ocr = OcrEngine()

scanner = ChatListScanner(ocr, targets={'目标1', '目标2'})
capturer = GroupCapturer(
    adb, ocr,
    is_relevant=lambda t: '你自己的关键词' in t,
    split_blocks=lambda t: [b for b in t.split('\n\n') if len(b) > 20],
)
memory = AgenticMemory('./target_memory.json')

agent = ScrapingAgent(adb, ocr, scanner, capturer, memory)
result = agent.run_cycle(batch_dir='./batch/demo')
print(result['covered'], result['missed'])
```

完整 24/7 loop + SEAgent curriculum + 业务落库的样例见 [`examples/wx_group_scraper.py`](./examples/wx_group_scraper.py)（已打码）。

---

## 隐私与安全

- 运行态截图 / OCR 文本 / memory 文件全部在 `.gitignore` 里（`photos/` `logs/` `state/` `*.png` `target_memory.json`）
- `docs/screens/*.png` 里的每一条聊天内容必须**先视觉打码再入库**
- 不要 commit 从生产设备直接来的截图，哪怕改了后缀名

---

## Roadmap

- [ ] VeriGUI TVAE：把成功轨迹压成可复用 skill，缩单圈时长
- [ ] 多设备并行（一 agent × N 手机，memory 共享）
- [ ] VLM verifier：OCR 歧义时局部小视觉模型打分
- [ ] Web dashboard：实时状态 + memory 检视

---

## License

MIT — 见 `LICENSE`。
