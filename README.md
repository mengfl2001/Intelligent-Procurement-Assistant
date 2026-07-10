# Intelligent-Procurement-Assistant
智能采购助手
一款基于 **AI Agent + 浏览器自动化** 的桌面应用，用于在 1688.com（阿里巴巴批发平台）上批量自动采购商品。通过 LLM 决策与浏览器自动化相结合，实现采购流程的全自动化。

## 功能特性

- **AI 智能决策**：使用 Qwen 大语言模型理解采购意图并做出智能决策
- **浏览器自动化**：基于 Playwright + browser_use 实现可靠的网页交互
- **批量处理**：单次运行可处理数百个 SKU 商品
- **智能 SKU 选择**：通过元素标注系统自动选择颜色、尺码、数量
- **登录态保持**：单例浏览器模式在任务间保持登录会话
- **实时 UI**：CustomTkinter 界面，支持实时日志和进度跟踪
- **自动生成报告**：Excel 报告包含成功/失败状态和截图
- **多层错误处理**：重试机制和回退策略确保稳定性

## 技术栈

| 分类         | 技术                       | 用途                           |
| ------------ | -------------------------- | ------------------------------ |
| UI 框架      | CustomTkinter              | 桌面 GUI（白底浅蓝主题）       |
| 数据处理     | pandas + openpyxl          | Excel 读取、校验、报告生成     |
| 异步框架     | asyncio                    | 异步任务调度，避免 UI 卡死     |
| 浏览器自动化 | browser_use + Playwright   | 浏览器控制、DOM 操作、元素标注 |
| LLM 服务     | 阿里云百炼 (qwen3.6-flash) | 自然语言理解、工具调用决策     |
| HTTP 客户端  | aiohttp                    | 异步调用 LLM API               |
| 配置管理     | PyYAML                     | config.yaml 配置文件管理       |
| 日志系统     | logging + 文件输出         | 运行日志、截图存档             |

## 快速开始

### 前置条件

- Python 3.12+
- 阿里云百炼 API Key（已授权模型）
- 1688.com 账号

### 安装

```bash
# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 配置

1. 复制配置模板：

   ```bash
   cp config/config.example.yaml config/config.yaml
   ```

2. 编辑 `config/config.yaml`：

   ```yaml
   api:
     api_key: 'sk-your-api-key-here'  # 你的 DashScope API Key
     base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1'
     model_name: 'qwen3.6-flash'
   ```

3. **重要步骤**：在阿里云控制台授权模型：

   - 登录百炼控制台 → 业务空间 → 模型授权
   - 为你的工作空间启用 `qwen3.6-flash` 模型

### 运行

```bash
python main.py
```

### 使用流程

1. **配置 API**：输入 DashScope API Key 并测试连通性
2. **上传 Excel**：上传采购清单（格式见下方说明）
3. **登录**：在打开的浏览器中手动登录 1688.com
4. **开始采购**：点击"开始采购"按钮启动自动化流程
5. **查看结果**：实时查看日志，下载采购报告

## Excel 格式

Excel 文件应包含以下列（支持中英文别名）：

| 列名         | 别名           | 必填 | 说明               |
| ------------ | -------------- | ---- | ------------------ |
| url          | 网址, 链接     | ✅    | 1688 商品链接      |
| item_name    | 商品名称, 名称 | ✅    | 商品名称（参考用） |
| quantity     | 数量           | ✅    | 采购数量（1-999）  |
| color        | 颜色           | ❌    | 颜色选项           |
| size         | 尺码, 规格     | ❌    | 尺码选项           |
| product_type | 款式, 类型     | ❌    | 商品类型选项       |

**Excel 示例结构：**

| url                         | item_name | quantity | color | size | product_type |
| --------------------------- | --------- | -------- | ----- | ---- | ------------ |
| https://detail.1688.com/... | 运动鞋    | 5        | 黑色  | 37   | -            |
| https://detail.1688.com/... | T恤       | 10       | 白色  | L    | Premium      |

## 配置参考

| 配置段  | 键名          | 默认值                                            | 说明                     |
| ------- | ------------- | ------------------------------------------------- | ------------------------ |
| api     | api_key       | -                                                 | DashScope API Key        |
| api     | base_url      | https://dashscope.aliyuncs.com/compatible-mode/v1 | OpenAI 兼容接口地址      |
| api     | model_name    | qwen3.6-flash                                     | LLM 模型名称             |
| ui      | app_title     | SmartPurchaseAgent                                | 窗口标题                 |
| ui      | window_width  | 1200                                              | 主窗口宽度               |
| ui      | window_height | 800                                               | 主窗口高度               |
| browser | headless      | false                                             | 无头模式运行浏览器       |
| browser | timeout       | 120                                               | 浏览器操作超时时间（秒） |
| task    | max_retries   | 3                                                 | 任务最大重试次数         |

## 项目架构

```
SmartPurchaseAgent/
├── main.py                    # 程序入口
├── config/
│   ├── config.py             # 配置加载模块
│   ├── config.yaml           # 用户配置（已加入 .gitignore）
│   └── config.example.yaml   # 配置模板
├── ui/
│   └── main_window.py        # 主界面（配置区 + 任务区 + 日志区）
├── core/
│   ├── api_client.py         # LLM API 客户端（连接测试、对话补全）
│   ├── async_runner.py       # 异步事件循环管理（后台线程）
│   ├── data_processor.py     # Excel 数据读取与校验
│   └── task_manager.py       # 任务队列调度、并发控制、报告生成
├── agent/
│   └── purchase_agent.py     # 采购 Agent 核心（LLM 决策 + 工具调用循环）
├── tools/
│   └── browser_tools.py      # 浏览器工具集（导航、标注、点击、截图）
├── utils/
│   └── logger.py             # 日志工具
├── logs/
│   └── screenshots/          # 任务截图存档
└── reports/                  # 采购报告输出目录
```

## 核心技术方案

### 1. 元素标注系统

通过 JavaScript 注入在 1688 商品页右侧绘制带编号的方框，将"模糊的 LLM 意图"转化为"精确的索引点击"。

### 2. 单例浏览器模式

使用单例模式共享浏览器实例，避免每个任务都重新打开浏览器和登录，大幅提升效率。

### 3. 原生 JavaScript 点击

使用 `dispatchEvent(new MouseEvent('click'))` 替代 Playwright 的 `click()`，防止触发外层 `<a>` 标签导致的意外跳转。

### 4. 同行尺码选择

选择尺码时自动点击该行最后一个元素（加号按钮），将"选尺码"和"加购"合并为一步操作。

### 5. 异步 UI 解耦

在后台线程运行 asyncio 事件循环，通过 `after()` 方法实现线程安全的 UI 更新。

## 故障排查

### 常见问题

| 问题           | 解决方案                                                 |
| -------------- | -------------------------------------------------------- |
| API 404 错误   | 检查 base_url 和 model_name（必须小写：`qwen3.6-flash`） |
| API 403 错误   | 在百炼业务空间控制台授权模型                             |
| 浏览器立即关闭 | 确保配置中 `headless: false`，检查单例模式是否正常工作   |
| 元素点击失败   | 检查元素是否在页面右侧 50% 区域内                        |
| 数量未更新     | React 受控输入框需要使用原生 setter + 事件触发           |

### 日志

日志保存在 `logs/smart_purchase_agent.log`。截图保存在 `logs/screenshots/`，用于调试失败任务。
