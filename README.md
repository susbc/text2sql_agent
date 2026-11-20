<p align="center">
  <img src="assets/logo.png" alt="溯算编程 Logo" width="220">
</p>

# 溯算编程 · Text2SQL 智能体

基于本地知识库的 SQL 智能生成系统

**出品**: 溯算编程

> **最新版本**: v1.4
> **核心升级**: 多模型 UI 热切换 + 安全加固 + SQL 注入防护 + 全链路代码质量优化
>
> 2026-10-25 起的变更记录于 [CHANGELOG.md](CHANGELOG.md) 的 `[Unreleased]` 段（含项目整理、架构规范与 MySQL→SQLite 存储迁移）；
> 本文档基于实际代码核对重写，版本号保持 v1.4 不变。

## 📸 功能展示

**自然语言查询全链路** — 输入"查询所有黑名单用户及其加入时间"，自动生成 SQL 并执行返回结果：

![自然语言查询全链路](docs/screenshots/main-query-flow.png)

**查询输入界面** — 数据库选择、自然语言输入框与示例查询卡片：

![查询输入界面](docs/screenshots/query-input.png)

**SQL 生成页** — 选择目标数据库、输入自然语言后生成/执行/复制 SQL，并展示生成的 SQL：

![SQL 生成页](docs/screenshots/sql-generation.png)

**执行历史** — 完整的 SQL 生成/执行历史管理，支持复用、复制、删除与一键提取 JOIN 关系增强知识图谱：

![执行历史](docs/screenshots/execution-history.png)

**知识图谱构建** — 支持 DDL/JSON 文件与活体数据库两种构建方式，含 AI 语义增强：

![知识图谱构建](docs/screenshots/kg-builder.png)

**Neo4j 图谱状态** — 实时统计数据库/表/字段/关系边规模与节点分布：

![图谱状态](docs/screenshots/graph-status.png)

**系统信息** — LLM / Embedding 配置、数据库连接状态、混合检索与语义治理一览：

![系统信息](docs/screenshots/system-info.png)

## 🎯 功能特性

### 核心功能
- 📊 **自然语言转 SQL**: 输入自然语言查询，自动生成 SQL 语句
- 🧠 **知识库检索**: BM25 + FAISS 两路混合检索
- 🔍 **SQL 校验**: 使用 SQLFluff 进行语法校验
- 📜 **历史记录**: 完整的 SQL 生成和执行历史管理
- 🗄️ **数据库选择**: 支持选择不同数据库，生成对应方言的 SQL
- 🔗 **Neo4j 知识图谱**: 从图数据库同步元数据
- 💾 **SQLite 存储**: 单文件嵌入式库（默认 `data/text2sql.db`），历史数据和元数据持久化，无需数据库服务
- 🏗️ **知识图谱构建**: 支持 DDL 文件/活体数据库构建图谱

### 新增功能 (v1.4)

| 功能 | 说明 | 状态 |
|------|------|------|
| ⚙️ **多模型 UI 热切换** | 系统信息页新增模型配置面板，支持 UI 手动切换 LLM 和 Embedding 模型 | ✅ |
|  **7 大 LLM 提供商** | OpenAI / Ollama / Anthropic / DashScope / DeepSeek / 智谱 AI / Azure OpenAI | ✅ |
| 🧩 **3 大 Embedding 提供商** | DashScope / OpenAI / Ollama，支持本地 bge-m3、nomic-embed-text | ✅ |
| 🔄 **热重载** | 切换模型后自动重载相关组件，无需重启应用 | ✅ |
| 🔒 **SQL 注入防护** | `_is_safe_query` 改用 sqlglot AST 解析，杜绝字符串匹配绕过 | ✅ |
| 🛡️ **Cypher 注入防护** | Neo4j 标识符白名单校验，防止 label/rel_type 注入 | ✅ |
|  **SQL 参数绑定修复** | `update_sql_execution` 改用 SQLAlchemy 命名参数，修复运行时错误 | ✅ |
|  **连接泄漏修复** | `reset()` 先关闭连接再重置，消除重复初始化时的连接泄漏 | ✅ |
|  **日志脱敏** | Cypher 查询日志截断至 60 字符；SQL 日志不落原文，仅记 SHA-256 指纹（sql_id） | ✅ |
| 🗂️ **信息脱敏** | 系统信息页隐藏数据库主机/端口，仅显示连接状态 | ✅ |
| ⚡ **Embedding LRU 缓存** | `OrderedDict` 实现 LRU 淘汰，上限 10000 条，防止内存无限增长 | ✅ |
| 🔧 **文件上传安全** | 改用 `tempfile.NamedTemporaryFile` 唯一文件名，避免并发覆盖 | ✅ |
| 🔗 **URI 编码** | 活体数据库连接凭据使用 `quote_plus` URL 编码，支持特殊字符密码 | ✅ |
|  **Linter 缓存** | `validate_sql()` 按方言缓存 SQLValidator 实例（校验器对象复用；SQLFluff 简单 API 每次调用内部构造 Linter） | ✅ |
| 📊 **统计查询优化** | `get_statistics()` 5 次查询合并为 1 次 | ✅ |
| 🏭 **组件管理统一** | `kg_builder` 改用 `ApplicationContext`，消除双 driver 实例 | ✅ |

### 新增功能 (v1.3)

| 功能 | 说明 | 状态 |
|------|------|------|
| ⚖️ **关系权重追踪** | CONNECTS 关系新增 weight/occurrence_count/source 属性 | ✅ |
| 🔍 **JOIN 提取引擎** | 基于 sqlglot AST 从历史 SQL 中提取表关联关系 | ✅ |
| 🔄 **权重重平衡** | 历史记录驱动，平滑增量权重 + 新关系比例收缩 | ✅ |
| 💪 **提取&增强** | 历史页一键提取 JOIN 关系并增强知识图谱 | ✅ |
| 🧠 **权重感知 Prompt** | LLM 优先选择高权重关联关系，关系按权重降序展示 | ✅ |
| 🏗️ **应用上下文** | ApplicationContext 统一管理组件生命周期，消除全局单例 | ✅ |

### 新增功能 (v1.2)

| 功能 | 说明 | 状态 |
|------|------|------|
| 🏗️ **知识图谱构建** | 从 DDL/JSON 文件或活体数据库构建知识图谱 | ✅ |
| 🗄️ **多数据库支持** | UI 提供 MySQL、Oracle、Hive、PostgreSQL、SparkSQL 五种方言选项；MySQL/Oracle/Hive 走通完整校验执行链路；PostgreSQL/SparkSQL 因校验器方言名映射缺口当前生成后校验会失败（已知问题） | ✅ |
| 🎯 **数据库选择** | 前端可选择目标数据库，生成对应方言 SQL | ✅ |
| 🤖 **AI 语义增强** | LLM 自动推断表关系和生成业务标签 | ✅ |
| 📤 **图谱导出/导入** | 支持将知识图谱导出为 JSON 并重新导入 | ✅ |
| 🔄 **自动重试机制** | LLM 调用失败自动重试 | ✅ |
| 🧹 **一键清除** | 支持清除知识图谱数据 | ✅ |

### v1.1 功能

| 功能 | 说明 | 状态 |
|------|------|------|
| 🗄️ **MySQL 连接池** | SQLAlchemy QueuePool，支持高并发 | ✅ |
| 🔗 **Neo4j 连接池** | Driver 级别连接池管理 | ✅ |
| ⚡ **异步 LLM 调用 API** | 提供 ainvoke / generate_sql_async 异步入口（供脚本与测试使用），UI 主链路为同步 | ✅ |
| 🧠 **CoT 思维链** | XML 标签格式，先思考后输出 | ✅ |
| 📚 **Few-Shot 学习** | 从历史成功记录检索相似示例 | ✅ |
| 🔌 **真实 Embedding** | 通义千问 text-embedding-v1 (1536 维) | ✅ |

## 🏗️ 架构设计

### 分层结构

```
┌──────────────────────────────────────────────────────────────────┐
│ UI 层        app.py（薄入口）+ app/                                │
│              styles / state / bootstrap / sidebar / model_config │
│              ui_icons + pages/（SQL 生成 / 执行历史 /              │
│              知识图谱构建 / 系统信息 四个 Tab）                     │
├──────────────────────────────────────────────────────────────────┤
│ 应用层       core/app_context.ApplicationContext                  │
│              组件装配与生命周期、config 只读快照、                  │
│              事务式热重载 reload_llm / reload_embedding /          │
│              reload_governance（候选构建成功后原子发布）            │
├──────────────────────────────────────────────────────────────────┤
│ 领域层       core/ 各子包                                          │
│              sql（生成/校验/正确性内核/预检）  chain（提示词/LLM 链）│
│              retrieval（混合检索/Few-Shot）   semantic（语义治理）  │
│              graph_builder（图谱构建）        history（历史/证明）  │
│              knowledge（Neo4j 图谱）          evaluation（Golden）  │
│              utils（脱敏/上传/治理面板辅助）                        │
├──────────────────────────────────────────────────────────────────┤
│ 基础设施     config.py（环境变量加载 + 启动校验）                   │
│              core/provider_catalog + core/config_validation       │
│              SQLite（SQLAlchemy 单文件库）  Neo4j（Driver 连接池）  │
│              LLM 提供商（LangChain）        Embedding 提供商        │
└──────────────────────────────────────────────────────────────────┘
```

- UI 层只负责渲染与会话状态：`app.py` 依次完成页面配置、图标/CSS 注入、会话状态初始化、
  侧栏渲染与四个 Tab 分发；系统初始化由 `app/bootstrap.initialize_system()` 委托
  `ApplicationContext` 完成，实例存入 `st.session_state.app_context`。
- 应用层是唯一组件入口：LLM、Neo4j、SQLite、Embedding、检索器、SQL 链、语义注册表、
  正确性内核、SQL 生成器均由 `ApplicationContext` 延迟初始化并持有；热重载先构建完整候选
  组件图、校验一致性后再原子发布，失败时旧组件保持不变。
- 领域层不反向依赖 UI；`core/` 各子包之间通过构造注入协作（如 `SQLGenerator` 接收
  检索器、SQL 链、SQLite/Neo4j 客户端与正确性内核）。

### 目录结构

```
text2sql_agent/
├── app.py                      # Streamlit 薄入口：页面配置 → 样式/状态 → 侧栏 → 4 Tab 分发 → footer
├── app/                        # UI 层模块
│   ├── styles.py               # 全局自定义 CSS 注入
│   ├── state.py                # session state 初始化（session_id / app_context / history 等）
│   ├── bootstrap.py            # initialize_system()：由 config.py 构建 ApplicationContext 并写入会话
│   ├── sidebar.py              # 品牌 logo、系统状态、重新初始化、知识库管理（导出/导入/清除）
│   ├── model_config.py         # 模型配置面板：LLM/Embedding UI 热切换与控件重新播种
│   ├── ui_icons.py             # Fluent Color 内联 SVG 图标库（MIT，运行时零外部请求）
│   └── pages/
│       ├── sql_generation.py   # Tab 1 SQL 生成：数据库选择、生成/执行/复制、CoT 与校验展示
│       ├── history.py          # Tab 2 执行历史：复用/复制/删除、JOIN 提取&增强
│       ├── kg_builder.py       # Tab 3 知识图谱构建：DDL/JSON/活体数据库构建与图谱统计
│       ├── system_info.py      # Tab 4 系统信息：配置一览、模型/治理面板、统计与最近日志
│       └── governance_settings.py  # 语义治理与执行预检面板（16 项可编辑配置 + 2 项只读）
├── config.py                   # 环境变量加载与模块级启动校验；重导出提供商目录
├── core/                       # 领域层
│   ├── app_context.py          # 应用层 ApplicationContext：组件生命周期与事务式热重载
│   ├── provider_catalog.py     # LLM/Embedding 提供商目录（推荐模型、密钥/URL 需求）
│   ├── config_validation.py    # 启动与热重载共用的严格配置校验（错误消息只含键名）
│   ├── llm_factory.py          # LLM 工厂：7 提供商，DashScope/DeepSeek/智谱复用 OpenAI 兼容接口
│   ├── embedding_factory.py    # Embedding 工厂：3 提供商 + OrderedDict LRU 缓存（上限 10000）
│   ├── chain/
│   │   ├── prompts.py          # CoT 提示词模板：数据标签隔离、关系按权重降序、提示词预算
│   │   └── sql_chain.py        # SQL 生成链：LLM 重试、XML 提取、修复/解释/查询改写链
│   ├── retrieval/
│   │   └── bm25_tfidf.py       # BM25+FAISS 两路混合检索、Few-Shot 索引、索引磁盘持久化
│   ├── sql/
│   │   ├── generator.py        # SQLGenerator：生成/执行/历史主流程与治理历史绑定
│   │   ├── correctness.py      # 正确性内核 CorrectnessPipeline：快照钉住、fail-closed、一次纠错
│   │   ├── validator.py        # SQLFluff 语法校验、sqlglot 只读/范围校验、行数与超时约束
│   │   ├── preflight.py        # MySQL EXPLAIN 预检（mysql-only 休眠内核；墙钟超时、并发上限、fail-closed）
│   │   ├── dialect_detector.py # 目标方言/数据库检测（Neo4j 元数据 + 关键词/表名模式）
│   │   ├── field_validator.py  # sqlglot AST 字段验证器（含 NEON_DB_URL 手动演示入口）
│   │   ├── join_extractor.py   # JOIN 提取引擎（sqlglot AST，支持复杂 ON 条件拆分）
│   │   └── error_codes.py      # 生成与评测共用的稳定公开错误码契约
│   ├── semantic/               # 语义治理：Git YAML → 不可变快照 → 确定性校验
│   │   ├── models.py           # pydantic 语义模型与校验报告模型（深度不可变）
│   │   ├── compiler.py         # YAML 编译为不可变 JSON 快照（semantic_models/.compiled/）
│   │   ├── registry.py         # 线程安全加载激活快照（版本/内容摘要校验）
│   │   ├── storage.py          # 防符号链接跟随的文件系统原语与编译锁
│   │   ├── context.py          # 有界、确定性的中文语义上下文（提示词切片）
│   │   ├── validator.py        # 不依赖数据库的语义 SQL 校验（表/字段/关联/指标/维度/策略）
│   │   ├── terms.py            # 语义术语的 fail-closed 解析器
│   │   ├── relationship_predicates.py  # 治理关系谓词的规范语法
│   │   └── publisher.py        # 快照投影为 Neo4j v2 导入格式（仅派生检索索引）
│   ├── knowledge/
│   │   └── neo4j_client.py     # Neo4j 客户端：Driver 连接池、标识符白名单、图谱导出/导入/清除
│   ├── history/
│   │   ├── sqlite_client.py    # SQLite 客户端：单文件库、6 应用表幂等自建+种子加载、历史与元数据读写
│   │   ├── identity.py         # 治理历史不可变身份（数据源/方言/语义版本/内容摘要）
│   │   └── proof.py            # 进程内短时效 HMAC 证明（治理历史写入/终态化防伪造）
│   ├── graph_builder/          # 知识图谱构建流水线
│   │   ├── main.py             # GraphBuilderPipeline：抽取 → 增强 → 预编译 → 装载（原子批次+校验）
│   │   ├── models.py           # IR 数据模型（Database/Table/Column/Relationship/Concept）
│   │   ├── extractors/         # 抽取器：DDL 文件 / JSON 文件 / 活体数据库
│   │   ├── enrichment/         # AI 语义增强：业务概念生成 + 表关系推断
│   │   ├── compiler/           # JOIN SQL 预编译
│   │   └── loader/             # Neo4j 批量装载（UNWIND+MERGE）+ 权重初始化/重平衡
│   ├── evaluation/
│   │   └── golden.py           # Golden Set 离线结构化评测（隐私安全，不调 LLM/数据库）
│   └── utils/
│       ├── log_sanitizer.py    # 日志脱敏：字面量占位、截断、文本指纹、错误编号
│       ├── governance_settings.py  # 治理面板纯函数辅助层（取值范围与跨字段规则）
│       ├── correctness_ui.py   # 公开错误码 → 中文提示的展示辅助
│       └── upload_limits.py    # 上传文件大小与 UTF-8 编码校验
├── scripts/
│   ├── start_server.sh         # 一键部署：.env 兜底创建、依赖哈希安装、streamlit 启动
│   ├── migrate_mysql_to_sqlite.py  # 一次性 MySQL→SQLite 迁移（历史工具，种子已提交入库）
│   ├── 01_export_graph_to_md.py    # Neo4j 图谱导出为 Markdown 快照
│   ├── 02_schema_search_cli.py     # Schema Agent CLI（供外部 AI Agent 调用）
│   ├── compile_semantic_models.py  # 语义模型 YAML 命令行编译器
│   ├── publish_semantic_model.py   # 将激活快照发布到 Neo4j
│   └── evaluate_golden.py      # Golden Set 评测入口（离线，不调 LLM/数据库）
├── tests/                      # 离线单测 + 开关 gated 集成测试 + 架构守护
│   ├── conftest.py             # 仅做 sys.path 设置（不含测试开关逻辑）
│   ├── test_architecture.py    # 架构守护：薄入口行数/模块入口/无循环 import/CSS 注入
│   ├── test_core.py            # 核心模块单元测试
│   ├── test_offline.py         # 离线脚本式测试（不依赖外部服务）
│   ├── test_comprehensive.py   # 综合测试；SQLite 用临时文件库，真实 Neo4j 集成由 TEXT2SQL_RUN_DB_TESTS 开关 gated
│   ├── test_graph_builder.py   # 图谱构建测试；真实 Neo4j 装载同上开关（另需 NEO4J_ENABLED=true）
│   ├── test_regressions.py     # 已修复缺陷的回归测试
│   ├── test_sqlite_client.py   # SQLiteClient 单测（DDL/种子门控/schema 迁移/看门狗/治理往返）
│   ├── test_migration_reconciliation.py  # 迁移种子行数/方言对账
│   ├── test_sqlite_execution_security.py # SQLite 执行安全边界（应用表禁查）
│   ├── test_few_shot_dialect_filter.py   # Few-Shot 按生成方言过滤
│   ├── test_model_config_panel.py  # 模型配置面板 Streamlit AppTest 集成（密封上下文，不连真实 DB）
│   ├── test_governance_panel.py    # 治理面板 Streamlit AppTest 集成
│   ├── test_governance_settings.py # 治理面板辅助层单元测试
│   ├── test_provider_credentials.py# 提供商凭据校验单元测试
│   ├── test_history_governance_proof.py  # 治理历史证明单元测试
│   ├── sql/                    # SQL 域测试：正确性内核/预检/生成器治理/治理提示词/配置严格性/日志安全
│   ├── semantic/               # 语义域测试：编译/上下文/模型/发布/注册表/存储/校验
│   └── evaluation/             # Golden 评测测试
├── semantic_models/            # Git 管理的语义模型 YAML（default.yaml）+ JSON Schema；.compiled/ 为运行时产物
├── eval/                       # Golden Set 评测用例（golden/）与结果示例（examples/）
├── schema.sql                  # SQLite 应用表参考 DDL（镜像 seed_history.sql；首次连接自动幂等建表）
├── requirements.txt            # 运行依赖
├── pyproject.toml              # ruff 门禁（E4/E7/E9/F）+ pytest testpaths 配置
├── CHANGELOG.md                # Keep-a-Changelog 变更记录（[Unreleased] 段）
├── env.example                 # 环境变量模板
├── assets/                     # 品牌资源（logo.png / logo_icon.png / logo_full.png）
├── docs/                       # 功能截图、语义治理运维手册、设计文档
└── data/                       # seed_business.sql / seed_history.sql 部署种子 + 运行时 SQLite 库
    └── schemas/                # 图谱导出的 Markdown 快照
```

运行时产物不在 git 跟踪中：`.gitignore` 以文件模式覆盖 `logs/*.log` 与 `logs/*.log.*`
（非整目录），并覆盖 `data/index_cache/`、`python_deps/`、`.pip_cache/`、
`semantic_models/.compiled/`、`.env` 等。

### 自然语言查询数据流

以下流程按 `core/sql/generator.py` 与 `core/app_context.py` 的实际代码核对
（UI 的 SQL 生成页走同步入口 `generate_sql`，异步入口 `generate_sql_async` 阶段相同）。

**生成阶段**

```
用户自然语言（SQL 生成页）
   ↓
目标数据库/方言确定
   ├─ UI 选择的数据库（Neo4j Database 节点）优先
   ├─ 否则 SQLDialectDetector：库名 / 类型关键词 / 表名模式
   └─ 兜底 config.SQL_DIALECT（默认 sqlite；启用治理时强制 mysql）
   ↓
查询改写（QueryRewriteChain；ApplicationContext 默认 enable_rewrite=False，即不启用）
   ↓
生成上下文组装
   ├─ 混合检索 retrieve_all：BM25 + FAISS 归一化加权融合（默认 0.6/0.4），按 database_id 过滤
   ├─ Few-Shot 示例：FAISS 历史索引（仅"校验+执行双成功"记录，按当前生成方言过滤；治理开启时初始为空索引）
   └─ Schema 信息：Neo4j 表/列/CONNECTS 权重关系优先，未启用或失败回退 SQLite 元数据
   ↓
[治理开启] CorrectnessPipeline.prepare_generation
   在 LLM 调用前钉住不可变语义快照并渲染有界语义上下文（预算不足直接拒绝）
   ↓
SQLGenerationChain.generate / generate_async
   提示词（schema/knowledge/few_shot/semantic 数据标签 + CoT 指令，关系按权重降序）
   → LLM invoke/ainvoke（最多重试 2 次；认证/配额类错误不重试）
   → 提取 <thinking> / <sql>（回退：代码块 / SQL 关键字定位）
   ↓
附加执行边界（allowed_tables / allowed_schemas，供校验与执行复核复用）
   ↓
校验分支
   ├─ 治理关闭：validate_sql（SQLFluff 语法 + 只读安全）
   │            → validate_query_scope（sqlglot AST：内部表黑名单/系统 schema/允许表）
   └─ 治理开启：CorrectnessPipeline.process_prepared 依次
        长度 → SQLFluff+只读 → 查询范围 → 语义快照校验 → EXPLAIN 预检（若启用）
        失败时至多 1 次结构化纠错（fix_sql_governed）后重新全量校验；任一环节异常 fail-closed
   ↓
历史落库（validation_status = success / fail / pending）
   ├─ 普通路径 save_sql_history
   └─ 治理路径 save_governed_sql_history（进程内 HMAC 证明）
   （此阶段不进入 Few-Shot 索引）
```

**执行阶段**

```
执行 SQL（execute_sql）
   ↓
[治理开启] authorize_execution：按当前快照重新校验
   语义版本 + 内容摘要必须与生成时一致，否则拒绝执行
   ↓
历史绑定校验（传 history_id 时）
   session / SQL 规范形 / 校验状态必须匹配；治理模式另消费一次性进程内绑定（TTL 默认 900s）
   ↓
只读安全复核（单条 SELECT/集合查询，禁副作用节点与函数）+ 查询范围复核
   ↓
constrain_read_query：外层 LIMIT 收紧至 max_rows+1（默认 501，用于截断判定）
   mysql 方言追加 MAX_EXECUTION_TIME 提示（治理/mysql 生成方言路径）
   ↓
SQLite execute_query_limited 执行（threading.Timer+interrupt 看门狗，
   预算 SQL_QUERY_TIMEOUT_MS 默认 10000ms；返回 truncated 截断标记）
   ↓
历史回写（success / fail；治理路径 finalize_governed_sql_execution + 证明）
   ↓
执行成功 → 该历史记录晋升 Few-Shot 索引（add_history_record，闭环增强）
```

要点：检索与 Schema 都有 Neo4j → SQLite 的回退路径；治理关闭时保留既有生成/执行行为，
治理开启时所有校验 fail-closed（快照不可用、证明缺失、绑定不匹配一律拒绝而非放行）。

### 知识图谱构建流水线（v1.2 新增）

```
┌─────────────────────────────────────────────────────┐
│                 GraphBuilder Pipeline               │
├─────────────────────────────────────────────────────┤
│  Extractor 层 → Enrichment 层 → Compiler 层 → Loader 层 │
│  (多源抽取)    (AI 增强)      (SQL 预编译)  (Neo4j 装载) │
└─────────────────────────────────────────────────────┘

数据源:
├── DDL 文件 (.sql)
├── JSON 文件 (.json)
└── 活体数据库 (仅支持 SQLite；其他方言使用 DDL/JSON 导入)

输出:
└── Neo4j 知识图谱
    ├── Database 节点
    ├── Table 节点
    ├── Column 节点
    ├── BusinessConcept 节点
    └── CONNECTS 关系边
```

装载阶段把写操作收集为批次统一提交：单批 ≤2000 条写操作在单个事务中原子提交
（块内抛异常则整批不生效）；超过 chunk_size=2000 时按顺序分多个事务提交，整体不再原子。
提交后按 `database_id` 范围核对实际写入数量，最后对同一表对的多条 CONNECTS 关系做权重规范化。

### 知识图谱权重架构（v1.3 新增）

```
CONNECTS 关系属性:
├── relationship_type: foreign_key
├── join_type: LEFT JOIN / INNER JOIN / ...
├── join_sql: 预编译的 JOIN SQL
├── from_column / to_column: 关联字段
├── weight: 0.0 ~ 1.0 (构建装载规范化后同一表对权重和 = 1；提取&增强后可能暂时 ≠ 1)
├── occurrence_count: 出现次数
├── source: manual | history_extracted
└── updated_at: 最后更新时间

权重初始化:
  表 A → 表 B 有 N 条关系
  每条 weight = 1/N

权重更新 (历史记录驱动):
  已存在: new_weight = old_weight × (1 - η) + η
  新关系: weight = 1 / (已有数量 + 1)
         旧关系按比例收缩
```

权重和 = 1 由构建装载时的 `normalize_relationships` 维护；"提取&增强"的重平衡按
old×(1-η)+η 提升单侧权重、新关系按比例收缩旧关系，之后同一表对权重和可能 ≠ 1，
直到下次构建装载规范化。

### 存储与连接池架构

```
应用层
   ↓
SQLAlchemy SQLite 引擎 (core/history/sqlite_client.py，单文件嵌入式库)
   ├─ 文件库：NullPool（每次 checkout 新建连接、归还即关闭，
   │  避免池化连接残留 progress_handler/interrupt 状态）
   ├─ :memory:：StaticPool 单共享连接 + per-client RLock 序列化
   └─ 每连接 PRAGMA foreign_keys=ON（反馈表级联删除依赖）

Neo4j Driver Pool
   ├─ max_connection_pool_size = 50
   └─ connection_timeout = 30s
```

## 📦 下载安装（桌面安装包）

v1 提供 macOS / Windows / Linux 三平台安装包：双击启动本地服务并自动打开浏览器，
无需安装 Python。形态为 PyInstaller onedir + 每 OS 安装包，构建指南见
[docs/packaging.md](docs/packaging.md)。

> **v1 定位**：自带示例数据的自包含演示版——内置 8 张业务表、30 条示例记录
> （`data/seed_business.sql`），启动后即可提问（如「查询所有黑名单用户」），
> 无需安装任何数据库服务。**并非完全 turnkey**：包体不捆绑大模型，需按下方
> 前提准备本地 Ollama 或云端 API Key。v1 不引导把 `SQLITE_PATH` 指向任意自有库
> （避免种子注入污染）；接入自有数据属高级/后续能力（知识图谱 + 外部 Neo4j）。

### 获取安装包

安装包由 GitHub Actions 三 OS 矩阵构建（`.github/workflows/build.yml`，
tag `v*` 推送或手动触发；版本号单一事实源＝仓库根 `VERSION` 文件）：

| 平台 | 产物 | 说明 |
|------|------|------|
| macOS（Apple Silicon arm64） | `text2sql-agent-<版本>-macos-arm64.dmg` | 拖入 Applications 安装 |
| Windows x64 | `text2sql-agent-<版本>-windows-x64-setup.exe` | Inno Setup 向导安装 |
| Linux x86_64 | `text2sql-agent-<版本>-linux-x86_64.AppImage` | Ubuntu 22.04 构建，要求 glibc ≥ 2.35 |

当前 CI 产物上传至 GitHub Actions Artifacts（保留 14 天，含安装包与 onedir
目录）；附到 GitHub Releases 的发布流程为后续工作（现有 workflow 尚无 release
发布步骤）。每个安装包内附 `README_FIRST_RUN.txt` 首跑说明。Intel Mac /
Windows arm64 / 更旧 Linux 留后续。

### 前提（LLM / Embedding，二选一）

应用本身不捆绑大模型，首次运行前请准备任一路线：

- **路线 A：本地 Ollama（无需 API Key）**——安装并启动 [Ollama](https://ollama.com)，
  拉取两个模型（缺一不可）：

  ```bash
  ollama pull gemma4:E4B      # LLM：负责 SQL 生成
  ollama pull bge-m3:latest   # Embedding：负责语义检索
  ```

  默认地址 http://localhost:11434，本机运行无需修改。
- **路线 B：云端 API Key**——在「模型配置」面板选择云端提供商（DashScope 通义千问 /
  OpenAI / DeepSeek / 智谱 AI / Azure OpenAI）并填写 API Key；Embedding 建议配
  DashScope `text-embedding-v3`（可与 LLM 用同一 Key）。
- **降级模式（如实说明）**：无 Ollama 且未配云端 Embedding 时，检索自动回退
  TF-IDF 关键词匹配——语义检索质量下降，应用仍可用（`core/embedding_factory.py`
  的降级路径）。
- **可选 Neo4j**：图谱增强检索默认关闭、非必需；需要时自备外部 Neo4j 服务，
  在数据目录 `.env` 设 `NEO4J_ENABLED=true` 并填写
  `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD`。
- 注意：v1 安装包未包含 Anthropic (Claude) 提供商（未捆绑 `langchain_anthropic`）。

### 安装与首跑向导

- **macOS**：打开 .dmg，把 `text2sql-agent.app` 拖入 Applications。v1 未签名，
  首次打开会提示「无法验证开发者」，绕过方法（任选其一）：
  右键（或 Control+点按）应用 →「打开」→ 弹窗中再点「打开」；
  或「系统设置 → 隐私与安全性」→ 找到拦截提示 →「仍要打开」。
- **Windows**：双击 setup.exe 按向导安装（默认 `C:\Program Files\text2sql-agent`）。
  v1 未签名，SmartScreen 提示「Windows 已保护你的电脑」时，
  点「更多信息」→「仍要运行」。用桌面/开始菜单快捷方式启动。
- **Linux**：`chmod +x text2sql-agent-<版本>-linux-x86_64.AppImage` 后直跑；
  需要 FUSE（缺 libfuse2 可安装之，或改用 `--appimage-extract-and-run`）。

启动后自动打开浏览器（http://127.0.0.1:8501；端口被占用时自动递增，以实际打开
的地址为准，实际端口见 `logs/app.log`）。首跑自动创建数据目录、写入 `.env`
默认模板、复制语义模型，并用内置种子数据建立 SQLite 库（幂等，重复启动不会
重复导入）。「系统信息」页出现「首次运行引导」时，在「模型配置」面板分别配置
LLM 与 Embedding（Ollama 或云端 Key），保存后自动写入数据目录 `.env`，
**跨重启不丢失**；也可直接编辑数据目录中的 `.env`，修改后重启应用生效。

### 数据目录（安装包本体只读）

| OS | 路径 |
|----|------|
| macOS | `~/Library/Application Support/text2sql-agent` |
| Windows | `%LOCALAPPDATA%\text2sql-agent`（通常即 `C:\Users\<用户名>\AppData\Local\text2sql-agent`） |
| Linux | `~/.local/share/text2sql-agent` |

内容：`.env`（配置，首跑模板生成，已有配置绝不覆盖）、`text2sql.db`（SQLite：
示例数据 + 查询历史 + 应用元数据）、`logs/app.log`（运行日志）、
`semantic_models/`（语义模型，首跑自安装包复制）、`index_cache/`（检索索引缓存，
可选）。卸载不会删除数据目录；如需彻底清理请手动删除。停止：v1 无原生退出
菜单，关闭浏览器标签后结束应用进程即可（macOS 右键 Dock 图标→退出；Windows
任务管理器结束 text2sql-agent.exe；Linux Ctrl+C 或 kill）。

### 已知限制（v1）

- 未签名/未公证（OS 警告按上文方法绕过）；不自动更新。
- 包体约 549MB（macOS .app 实测；dmg 压缩后约 188MB）。
- LLM 前提如上——非完全 turnkey（不捆绑 Ollama/模型/Neo4j）。
- Anthropic 提供商暂缺（`langchain_anthropic` 未捆绑，构建环境装上即自动收集）。
- 浏览器形态（非原生 GUI 窗口）；语义治理为 mysql-only 休眠能力，v1 SQLite
  演示模式下不可启用。

## 🚀 快速开始

> 桌面安装包用户请看上方「下载安装」章节；本节面向源码运行与开发。

### 1. 环境准备

本仓库在 **Python 3.12** 上开发与验证（本机 `.venv` 实测 3.12.10）；不声明未经核实的
最低支持版本，部署时可经 `PYTHON_BIN` 指定解释器（见下文启动脚本）。

```bash
# 使用 Python 3.12 创建隔离环境
python3.12 --version
cd /path/to/text2sql_agent
python3.12 -m venv .venv
source .venv/bin/activate

# Windows PowerShell:
# py -3.12 -m venv .venv
# .\.venv\Scripts\Activate.ps1
```

如果系统未提供 `python3.12`，可使用已安装的 [uv](https://docs.astral.sh/uv/) 获取同一版本；`--seed` 会在 `.venv` 中安装 `pip`，使后续命令保持一致：

```bash
uv venv --python 3.12 --seed .venv
source .venv/bin/activate
```

### 2. 安装依赖

```bash
python -m pip install -r requirements.txt

# 发布前运行 Ruff 门禁时，在同一个已激活环境安装已验收的版本
python -m pip install ruff==0.15.20
```

**关键依赖说明**:
- `faiss-cpu>=1.7.4` - FAISS 向量检索
- `dashscope>=1.14.0` - 通义千问 Embedding
- `sqlglot>=21.0.0` - SQL AST 解析

### 3. 配置环境变量

```bash
cp env.example .env
# 编辑 .env 文件，配置 SQLite 路径、Neo4j 和 LLM
```

`.env` 不被 git 跟踪；模板见 `env.example`，完整变量说明见下文"配置说明"章节。

### 4. 初始化数据库

无需手工步骤：应用首次连接成功即自动创建 SQLite 库（默认 `data/text2sql.db`，
`SQLITE_PATH` 可配），幂等创建 6 张应用表（`sql_generation_history`、`user_feedback`、
`table_schema`、`column_schema`、`knowledge_metadata`、`retrieval_terms`）、执行治理列
迁移，并原子加载 `data/seed_business.sql`（8 业务表 30 行）与 `data/seed_history.sql`
（历史 50 行）种子，开箱可用。

`schema.sql` 是 6 张应用表的 SQLite 参考 DDL（逐字镜像 `data/seed_history.sql` 的
canonical DDL）；如需手工建库可执行 `sqlite3 data/text2sql.db < schema.sql`，
种子加载仍由应用首次连接自动完成。

### 5. 启动应用

```bash
streamlit run app.py
```

访问 http://localhost:8501

服务器部署时可以使用一键启动脚本：

```bash
chmod +x scripts/start_server.sh
./scripts/start_server.sh
```

脚本会自动完成以下操作：

- 如果缺少 `.env`，从 `env.example` 创建一份，并把其中未被环境变量覆盖的键导入环境。
- 创建 `logs/`、`python_deps/` 和 `.pip_cache/`。
- 将 `requirements.txt` 依赖安装到项目内的 `python_deps/` 目录。
- 根据 `requirements.txt` 哈希判断依赖是否变化，未变化时跳过安装。
- 通过 `python -m streamlit run app.py` 启动服务，默认监听 `0.0.0.0:8501`。

知识库索引默认每次启动从 SQLite/Neo4j 重建（`INDEX_CACHE_ENABLED=false`），避免图谱
覆盖导入后仍命中旧缓存；这是应用行为，与启动脚本无关。

常用部署参数可以写入 `.env`，也可以临时通过环境变量覆盖。`PYTHON_BIN` 用于指定部署机
上的解释器（版本中性示例，不代表生产机版本）：

```bash
STREAMLIT_PORT=8502 ./scripts/start_server.sh
PYTHON_BIN=/path/to/python3 PYTHON_DEPS_DIR=/opt/text2sql/python_deps ./scripts/start_server.sh
INSTALL_DEPS=0 ./scripts/start_server.sh
```

### 6. 运行测试

```bash
# 离线单测 + 架构守护（默认不连接真实数据库）
.venv/bin/python -m pytest tests -q

# Ruff 门禁（pyproject.toml：target py312，select E4/E7/E9/F）
.venv/bin/python -m ruff check .

# 真实 Neo4j 集成测试（开关在各测试文件内，默认关闭）
TEXT2SQL_RUN_DB_TESTS=1 .venv/bin/python -m pytest tests/test_comprehensive.py tests/test_graph_builder.py -q
```

测试结构分三层：

- **离线单测**：`tests/sql/`、`tests/semantic/`、`tests/evaluation/` 与
  `test_core.py` / `test_offline.py` / `test_regressions.py` 等，不依赖外部服务；
  面板类集成测试（`test_model_config_panel.py` / `test_governance_panel.py`）用
  Streamlit AppTest 与密封上下文渲染，同样不连真实数据库。
- **开关 gated 集成测试**：`tests/conftest.py` 只做 `sys.path` 设置；是否连接真实
  Neo4j 由各测试文件内的 `TEXT2SQL_RUN_DB_TESTS` 开关决定（`!= "1"` 时跳过）。
  `test_comprehensive.py` 的 SQLite 集成用按实例临时文件库（无需外部服务）；
  `test_graph_builder.py` 的真实 Neo4j 装载测试另需 `NEO4J_ENABLED=true`。
  旧 Neon/Qwen 外部 LLM 实验链已删除，不存在"缺配置自动跳过的外部 LLM 测试"。
- **架构守护**：`tests/test_architecture.py` 4 项——`app.py` 薄入口行数上限、
  UI 模块入口函数可调用、`app/` 无循环 import、自定义 CSS 注入生效。

截至 SQLite 迁移完成，全量套件为 1067 passed / 9 skipped（计数随测试增删漂移，以结构说明为准）。

## 正确性内核

语义治理默认关闭，保留既有生成与执行行为：

```bash
SEMANTIC_GOVERNANCE_ENABLED=false
SQL_EXPLAIN_ENABLED=false
```

启用后，Git 管理的 `semantic_models/<datasource>.yaml` 会被编译为不可变快照；SQL 在生成和执行前都会基于该快照验证。Neo4j 只保存已发布快照的派生检索索引，不能覆盖 Git 语义定义。

这两个开关在内的 16 项可编辑治理配置（另含模型目录、SQL 方言 2 项只读展示）也可以在**系统信息页 → 语义治理与执行预检**面板中直接修改并热重载，无需改 `.env` 或重启；面板会在提交前校验跨字段约束（如 `EXPLAIN` 预检依赖语义治理、启用治理时方言必须为 `mysql`），校验不通过则不会触达后端。

作者、编译、激活、发布、热重载、一次纠错、执行再授权、回滚、Golden Set 评测和故障处理见[语义治理运维手册](docs/semantic-governance.md)。

## 📋 配置说明

### 环境变量完整列表

本表覆盖 `config.py` 与 `env.example` 解析的全部环境变量键；权威定义以 `config.py` / `env.example` 为准。

#### 数据库配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| SQLITE_PATH | SQLite 库文件路径（应用存储单文件库，首次连接自动建表+加载种子） | data/text2sql.db |
| HISTORY_MAX_RECORDS | SQL 历史保留上限（必须为 1–10000） | 1000 |
| HISTORY_AUTO_SAVE | 生成后自动保存历史记录 | true |
| TEXT2SQL_RUN_DB_TESTS | 是否运行真实 Neo4j 集成测试（测试文件内读取） | 0 |

#### Neo4j 配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| NEO4J_ENABLED | 是否启用 Neo4j | false |
| NEO4J_URI | Neo4j 连接 URI | bolt://localhost:7687 |
| NEO4J_USER | Neo4j 用户 | neo4j |
| NEO4J_PASSWORD | Neo4j 密码 | neo4j@123 |
| NEO4J_DATABASE | Neo4j 数据库名 | neo4j |
| **NEO4J_MAX_POOL_SIZE** | 最大连接池大小 | 50 |
| **NEO4J_CONNECTION_TIMEOUT** | 连接超时（秒） | 30 |

#### Neon 配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| NEON_DB_URL | Neon PostgreSQL 连接 URL，仅供 core/sql/field_validator.py 的手动演示使用（python core/sql/field_validator.py） | - |

#### 启动脚本配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| STREAMLIT_ADDRESS | Streamlit 监听地址 | 0.0.0.0 |
| STREAMLIT_PORT | Streamlit 监听端口 | 8501 |
| APP_ENTRY | Streamlit 入口文件 | app.py |
| PYTHON_BIN | 指定 Python 可执行文件 | 自动查找 python3/python |
| PYTHON_DEPS_DIR | Python 依赖安装目录 | python_deps |
| PIP_CACHE_DIR | pip 缓存目录 | .pip_cache |
| INSTALL_DEPS | 启动时是否检查并安装依赖 | 1 |

#### LLM 配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| LLM_PROVIDER | LLM 提供商（openai / ollama / anthropic / dashscope / deepseek / zhipu / azure） | ollama |
| LLM_MODEL | LLM 模型 | gemma4:E4B |
| LLM_API_KEY | LLM API Key | - |
| LLM_BASE_URL | LLM API 基础 URL（留空时 Ollama 回退 http://localhost:11434，兼容接口提供商回退各自默认地址） | 空 |

> 表中默认值为 `config.py` 的环境变量兜底值；`env.example` 模板另给出一组 OpenAI 示例值，复制后请按环境修改。

> **支持的 LLM 提供商**：
> - **OpenAI** — gpt-4o 等，使用 OpenAI 官方 API
> - **Ollama** — gemma4:E4B、qwen2.5、llama3 等，本地部署，无需 API Key
> - **Anthropic** — claude-sonnet-4-20250514 等，使用 Anthropic 官方 API
> - **DashScope** — qwen-max 等，阿里云通义千问（OpenAI 兼容接口）
> - **DeepSeek** — deepseek-chat 等，深度求索（OpenAI 兼容接口）
> - **智谱 AI** — glm-4-flash 等，智谱清言（OpenAI 兼容接口）
> - **Azure OpenAI** — gpt-4o 等，需 Azure 端点 URL

> **API Key / 地址回退**：`LLM_API_KEY` 留空时，openai / azure / anthropic 分别回退环境变量
> `OPENAI_API_KEY` / `AZURE_OPENAI_API_KEY` / `ANTHROPIC_API_KEY`；Ollama 的 `LLM_BASE_URL` 留空时
> 回退 `OLLAMA_HOST`，再回退 http://localhost:11434（core/llm_factory.py）。

> **也可在系统信息页通过 UI 直接切换模型，无需修改 `.env` 文件。**
>
> UI 面板的三点行为约定：
> - **API Key 输入框始终为空**，不回显已生效的密钥（`type="password"` 只遮蔽显示，值仍会随控件状态下发到浏览器，因此不预填）。**留空表示沿用当前密钥**，填写则替换。
> - 面板显示的是**运行时实际生效**的配置（读自 `ApplicationContext.config` 快照），而非 `.env` 的静态值。「恢复默认」会真正触发一次热重载把 `.env` 配置应用回去，不需要刷新页面。
> - 切换失败时会直接给出具体原因（如 `LLM_PROVIDER 指定的提供商需要非空的 LLM_API_KEY`）。该规则由 `core/config_validation.py` 统一校验，启动与热重载走同一条路径；错误消息只含配置键名、不含取值。注意未知提供商名仍按既有语义容错回退，只有目录内声明需要密钥的提供商才强制校验。

#### Embedding 配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| EMBEDDING_PROVIDER | Embedding 提供商（dashscope / openai / ollama） | ollama |
| EMBEDDING_MODEL | Embedding 模型 | bge-m3:latest |
| EMBEDDING_API_KEY | API Key | - |
| EMBEDDING_API_BASE | 可选 API Base URL | 空 |

> **支持的 Embedding 提供商**：
> - **DashScope** — text-embedding-v3 (1024 维)，通义千问
> - **OpenAI** — text-embedding-3-large (3072 维)
> - **Ollama** — bge-m3:latest (1024 维)、nomic-embed-text (768 维)，本地部署

#### Few-Shot 配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| FEW_SHOT_ENABLED | 启用 Few-Shot | true |
| FEW_SHOT_TOP_K | 检索示例数量 | 3 |
| FEW_SHOT_MIN_SIMILARITY | 最小相似度 | 0.5 |

#### 检索配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| RETRIEVAL_TOP_K | 知识库检索返回数量 | 5 |
| BM25_K1 | BM25 k1 参数 | 1.5 |
| BM25_B | BM25 b 参数 | 0.75 |
| BM25_WEIGHT | BM25 权重 | 0.6 |
| DENSE_WEIGHT | FAISS 权重 | 0.4 |
| FAISS_ENABLED | 是否启用 FAISS 向量检索 | true |
| FAISS_EMBEDDING_DIM | FAISS 向量维度，需要与 Embedding 模型一致 | 1024 |
| FAISS_INDEX_TYPE | FAISS 索引类型 | flat |
| INDEX_CACHE_ENABLED | 是否启用知识库索引磁盘缓存 | false |
| INDEX_CACHE_DIR | 知识库索引缓存目录 | data/index_cache |

> 图谱导入、覆盖数据库或切换 Embedding 模型后，建议保持 `INDEX_CACHE_ENABLED=false`，让系统从最新数据源重建索引。只有在生产图谱稳定、启动速度优先时再开启缓存。

#### 提示词、上传与图导入配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| PROMPT_MAX_LENGTH | 提示词预算上限（字符） | 4000 |
| UPLOAD_MAX_BYTES | 上传文件大小上限（字节，5 MiB） | 5242880 |
| GRAPH_MAX_NODES | 图谱导入 JSON 校验：节点数上限 | 10000 |
| GRAPH_MAX_EDGES | 图谱导入 JSON 校验：关系数上限 | 20000 |
| GRAPH_MAX_DEPTH | 图谱导入 JSON 校验：嵌套深度上限 | 20 |
| GRAPH_MAX_STRING_LENGTH | 图谱导入 JSON 校验：字符串长度上限 | 10000 |

#### 日志与应用配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| LOG_LEVEL | 日志级别（app.py 的 loguru sink 读取） | INFO |
| STREAMLIT_SERVER_PORT | 仅被 config.py 解析与范围校验，应用与启动脚本不读取；实际监听端口由 STREAMLIT_PORT 或 streamlit CLI 决定 | 8501 |
| STREAMLIT_HEAD | 仅被 config.py 解析与校验，应用与启动脚本不读取；启动脚本固定 --server.headless true | true |

#### SQL 执行与语义治理配置
| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| SQL_DIALECT | 默认 SQL 方言（默认 sqlite；启用治理时仅支持 mysql） | sqlite |
| SQL_VALIDATION_ENABLED | 生成后是否做 SQLFluff/只读校验 | true |
| SQL_MAX_LENGTH | SQL 长度上限（字符） | 2000 |
| SQL_QUERY_MAX_ROWS | 执行返回行数上限 | 500 |
| SQL_QUERY_TIMEOUT_MS | 执行超时预算（毫秒）：SQLite 看门狗 interrupt；mysql 方言为超时提示 | 10000 |
| SQL_SCOPE_ENFORCEMENT | 强制查询范围校验（允许表/系统 schema） | true |
| SQL_BLOCKED_TABLES | 应用表黑名单（逗号分隔，无条件生效，独立于 SQL_SCOPE_ENFORCEMENT） | knowledge_metadata,table_schema,column_schema,sql_generation_history,retrieval_terms,user_feedback |
| SEMANTIC_GOVERNANCE_ENABLED | 语义治理开关 | false |
| SEMANTIC_MODEL_DIR | 语义模型目录 | semantic_models |
| SEMANTIC_DATASOURCE | 语义数据源（对应 `<datasource>.yaml`） | default |
| SEMANTIC_CONTEXT_MAX_CHARS | 语义上下文最大字符 | 2400 |
| SEMANTIC_CONTEXT_MAX_ITEMS | 语义上下文最大条目 | 24 |
| SQL_REPAIR_MAX_ATTEMPTS | 治理纠错次数上限（0 或 1） | 1 |
| SQL_EXPLAIN_ENABLED | MySQL EXPLAIN 预检开关（mysql-only 休眠，依赖语义治理；SQLite 模式不可启用） | false |
| SQL_EXPLAIN_TIMEOUT_MS | EXPLAIN 预检超时（毫秒） | 3000 |
| SQL_EXPLAIN_MAX_ESTIMATED_ROWS | 估算扫描行数上限（0 表示不限制） | 0 |
| MAX_PREPARED_REQUESTS | 进程内已预备治理请求上限 | 256 |
| PREPARED_REQUEST_TTL_SECONDS | 已预备请求存活时间（秒） | 120 |
| GOVERNED_HISTORY_BINDING_TTL_SECONDS | 治理历史执行绑定存活时间（秒） | 900 |

### LLM 配置示例

```bash
# 本地 Ollama（config.py 默认）
LLM_PROVIDER=ollama
LLM_MODEL=gemma4:E4B
LLM_BASE_URL=http://localhost:11434

# OpenAI
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
LLM_API_KEY=sk-xxx

# Anthropic Claude
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-20250514
LLM_API_KEY=sk-ant-xxx

# Azure OpenAI
LLM_PROVIDER=azure
LLM_MODEL=gpt-4o
LLM_API_KEY=xxx
LLM_BASE_URL=https://xxx.openai.azure.com

# DashScope 通义千问
LLM_PROVIDER=dashscope
LLM_MODEL=qwen-max
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# DeepSeek 深度求索
LLM_PROVIDER=deepseek
LLM_MODEL=deepseek-chat
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.deepseek.com/v1

# 智谱 AI
LLM_PROVIDER=zhipu
LLM_MODEL=glm-4-flash
LLM_API_KEY=xxx
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

### Embedding 配置示例

```bash
# 本地 Ollama（默认）
EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=bge-m3:latest

# DashScope 通义千问
EMBEDDING_PROVIDER=dashscope
EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_API_KEY=sk-xxx

# OpenAI
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-large
EMBEDDING_API_KEY=sk-xxx
```

## 📖 使用示例

### 1. 提取&增强（v1.3 新增）

在"执行历史"页面：
1. 找到已执行的 SQL 记录
2. 点击"提取&增强"按钮
3. 系统自动提取 SQL 中的表关联关系（JOIN）
4. 确认无误后点击"确认增强到知识图谱"
5. 系统自动更新 Neo4j 中 CONNECTS 关系的权重

### 2. 知识图谱构建（v1.2 新增）

在"知识图谱构建"页面：
1. 上传 DDL 文件或 JSON 文件（文件类型可选自动检测/DDL/JSON）
2. 填写数据库名称和类型（可选 mysql、oracle、hive、postgresql、sparksql；postgresql/sparksql 的校验方言名映射缺口见"数据库选择"小节）
3. 选择是否"启用 AI 增强"
4. 点击"开始构建"（活体数据库方式填写 SQLite 文件路径后点击"连接并构建"；活体抽取仅支持 SQLite）
5. 构建成功后系统自动重置应用上下文并重新初始化（刷新检索索引）；侧边栏"重新初始化系统"按钮可手动触发同一流程，但非必经步骤

**DDL 文件示例**:
```sql
CREATE TABLE users (
    id INT PRIMARY KEY COMMENT '用户 ID',
    name VARCHAR(100) COMMENT '用户姓名',
    email VARCHAR(255) COMMENT '邮箱'
) COMMENT='用户表';

CREATE TABLE orders (
    id INT PRIMARY KEY COMMENT '订单 ID',
    user_id INT COMMENT '用户 ID',
    amount DECIMAL(10,2) COMMENT '订单金额',
    created_at DATETIME COMMENT '创建时间'
) COMMENT='订单表';
```

### 3. SQL 生成（带数据库选择）

在主页选择目标数据库，然后输入自然语言查询：
- 选择数据库：`ride_hailing_db (sparksql)`
- 查询："查询近 7 天接单量排名前 10 的司机"

**CoT 输出示例**:
```
🧠 思考过程:
用户意图：统计近 7 天接单量排名前 10 的司机
关键实体：司机、接单量、排名、近 7 天
需要用到的表：driver, order
关联关系：通过 driver_id 关联
SQL 结构:
1. 从 order 表中筛选近 7 天的记录
2. 按 driver_id 分组，计算 COUNT(*)
3. 使用 ORDER BY 降序排列
4. 使用 LIMIT 10 取前 10 名
```

### 4. 数据库选择（v1.2 新增）

在"SQL 生成"页面左侧，可以选择目标数据库：
- 下拉框显示：`数据库名 (数据库类型)`（列表来自 Neo4j Database 节点；Neo4j 未启用时不可选，兜底方言 sqlite）
- 选择不同数据库后，系统会生成对应方言的 SQL；迁移后配置库 Database 节点 db_type=sqlite
- 执行目标统一为 SQLite 业务库（页面注明"执行目标：SQLite 业务库"）；其他方言的 DDL 可经知识图谱构建页的离线通道导入（mysql、oracle、hive、postgresql、sparksql 五种选项）
- **已知问题**：MySQL/Oracle/Hive 走通完整校验链路；PostgreSQL/SparkSQL 因校验器方言名映射缺口（SQLFluff 需 `postgres`、sqlglot 需 `spark`），当前生成后校验会失败（fail-closed 拒绝），代码暂未修复

### 5. 图谱导出/导入（v1.2 新增）

在侧边栏"知识库管理"中（需启用 Neo4j）：
- **导出**：点击"导出"后下载知识图谱 JSON 文件；也可"下载模板"获取可导入的 JSON 模板
- **导入**：上传 JSON 文件，结构校验通过后"直接导入"；若库已存在，勾选"确认覆盖已存在数据库图谱"后"覆盖并导入"

### 6. 清除知识库（v1.2 新增）

在侧边栏"知识库管理"中：
1. 勾选"确认清除"
2. 点击"清除知识库"
3. 系统自动重新初始化

### 7. 查看历史

切换到"执行历史"标签页，查看历史生成记录。

## ⚡ 性能相关设计

以下为代码中实际存在的性能机制（不含未经复测的基准数字）：

| 机制 | 实现位置 | 作用 |
|------|----------|------|
| Neo4j 连接池 | `core/knowledge/neo4j_client.py` | 复用连接，避免每次请求新建（SQLite 为嵌入式单文件库，NullPool 归还即关闭） |
| 异步 LLM 调用 | `core/chain/sql_chain.py` `generate_async` | ainvoke 路径供异步调用方使用 |
| 两路混合检索 | `core/retrieval/bm25_tfidf.py` | BM25 词频 + FAISS 语义互补；FAISS 搜索上限 100 控制开销 |
| 权重优先关联 | `core/chain/prompts.py` | 关系按权重降序注入提示词，减少多表 JOIN 试错 |
| Embedding LRU 缓存 | `core/embedding_factory.py` | OrderedDict 淘汰，上限 10000 条，防内存无限增长 |
| Linter 按方言缓存 | `core/sql/validator.py` | 复用 SQLValidator 包装对象；SQLFluff 简单 API 每次调用内部构造 Linter |
| 统计单查询 | `core/history/sqlite_client.py` `get_statistics` | 5 项统计合并为 1 次带子查询的 SQL |
| 索引磁盘缓存（可选） | `core/retrieval/bm25_tfidf.py` | `INDEX_CACHE_ENABLED=true` 时跳过启动重建 |

## 🤖 AI Agent 专属技能

项目提供了命令行 Schema 检索工具，供外部 AI Agent（如 Claude Code）调用。

### Schema Agent CLI

**文件位置**: `scripts/02_schema_search_cli.py`

**基本用法**:

```bash
# 检索 Schema 并由 LLM 总结输出
python scripts/02_schema_search_cli.py "查询用户订单信息"

# 仅返回原始 Schema 信息（不加 LLM 总结）
python scripts/02_schema_search_cli.py "查询用户订单信息" --raw

# 指定返回结果数量
python scripts/02_schema_search_cli.py "查询用户订单信息" --top-k 10

# 指定数据库 ID
python scripts/02_schema_search_cli.py "查询用户订单信息" --database-id 2

# 以 JSON 格式输出（便于程序解析）
python scripts/02_schema_search_cli.py "查询用户订单信息" --json
```

**参数说明**:

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `query` | 自然语言查询语句（位置参数） | - |
| `--top-k` | 返回结果数量 | 5 |
| `--database-id` | 数据库 ID（用于过滤） | None |
| `--raw` | 仅返回原始 Schema 信息 | False |
| `--json` | 以 JSON 格式输出 | False |

**输出示例**:

```
根据您的需求"查询用户订单信息"，建议使用以下数据库表：

**建议使用的表**:
- `bas_user_info` - 用户基本信息表
- `bas_user_auth` - 用户认证信息表
- `acc_account_main` - 账户主表

**需要关注的核心字段**:
- `bas_user_info.user_id` - 用户 ID（主键）
- `bas_user_info.user_name` - 用户姓名
- `acc_account_main.account_id` - 账户 ID
- `acc_account_main.balance` - 账户余额

**表关联关系**:
- `bas_user_info` 和 `acc_account_main` 通过 `user_id` 字段关联
```

### Schema Export Tool（可选）

**文件位置**: `scripts/01_export_graph_to_md.py`

导出 Neo4j 知识图谱为 Markdown 文档，用于知识快照或离线查看：

```bash
python scripts/01_export_graph_to_md.py
```

输出文件：`data/schemas/schema_export_YYYYMMDD_HHMMSS.md`

## 🛠️ 技术栈

- **前端**: Streamlit
- **后端**: Python（在 Python 3.12 上开发验证；部署可经 `PYTHON_BIN` 指定解释器）
- **数据库**: SQLite (嵌入式单文件库), Neo4j (连接池)
- **LLM**: LangChain (异步调用)
- **检索**: BM25, FAISS
- **Embedding**: 多提供商（默认本地 Ollama bge-m3；可选 DashScope / OpenAI）
- **校验**: SQLFluff, sqlglot

## ⚠️ 注意事项

1. **安全性**: 只允许执行单条、无副作用的只读 SELECT/集合查询
2. **性能**: 执行自动收紧外层 LIMIT 至行数上限，SQLite 经看门狗（interrupt）实施超时预算；无 WHERE/LIMIT 的查询会给出全表扫描警告
3. **准确性**: 依赖知识库的完整性
4. **LLM 成本**: 注意 API 调用频率
5. **连接**: SQLite 为嵌入式单文件库，无服务端连接池；Neo4j 高并发场景可调大 NEO4J_MAX_POOL_SIZE
6. **凭据**: `.env` 不被 git 跟踪；历史上曾入库的凭据需轮换（见 CHANGELOG `[Unreleased]` Security 段）

## 📝 更新日志

### v1.4 (2026-07-24)

**多模型 UI 热切换**:
- ✅ 系统信息页新增「模型配置」面板，支持通过 UI 手动切换 LLM 和 Embedding 模型
- ✅ 支持 7 大 LLM 提供商：OpenAI、Ollama、Anthropic、DashScope、DeepSeek、智谱 AI、Azure OpenAI
- ✅ 支持 3 大 Embedding 提供商：DashScope、OpenAI、Ollama
- ✅ 切换后自动热重载相关组件（LLM 切换保留数据库连接，Embedding 切换重建知识库索引）
- ✅ 提供商切换时 API Key / Base URL 字段按需要自动显隐，带默认值提示
- ✅ 支持一键恢复为 `.env` 中的默认配置
- ✅ `llm_factory.py` 新增 DashScope / DeepSeek / 智谱 provider（复用 OpenAI 兼容 API）
- ✅ `embedding_factory.py` 新增 Ollama embedding provider（HTTP REST API 调用，无需额外 SDK）

**安全加固**:
- ✅ `_is_safe_query` 改用 sqlglot AST 解析判断顶层语句类型，仅允许 SELECT/WITH/UNION，杜绝字符串匹配绕过（注释、CTE、分号等）
- ✅ 回退模式增强：去除 SQL 注释 + 按分号拆分多语句逐条检查（该回退模式已在后续正确性内核加固中移除，现为 fail-closed 策略：解析失败或多语句直接拒绝，见 core/sql/validator.py）
- ✅ Neo4j `_safe_identifier` 白名单校验，label / rel_type 仅允许字母/数字/下划线
- ✅ `get_all_nodes`、`get_node_by_name`、`_merge_relationship` 全部接入标识符校验（get_all_nodes/get_node_by_name 已于 2026-11-19 死代码清理中移除；_merge_relationship 标识符校验保留）
- ✅ 系统信息页脱敏展示：隐藏 MySQL 主机/端口、Neo4j URI，仅显示连接状态
- ✅ 日志中 SQL/Cypher 查询截断至 60-80 字符，防止敏感数据泄露（现行实现：Cypher 截断 60 字符；SQL 日志不落原文、仅记 SHA-256 指纹 sql_id，sanitize_sql 已无生产调用）

**Bug 修复**:
- ✅ `update_sql_execution` 改用 SQLAlchemy 命名参数（`:name`），修复 `%s` 占位符导致运行时错误
- ✅ `reset()` 先调用 `shutdown()` 关闭连接再重置，消除重复初始化时的连接泄漏
- ✅ `kg_builder.py` 改用 `app_context.neo4j_client`，消除废弃全局单例导致的 Neo4j 双 driver 实例
- ✅ 文件上传改用 `tempfile.NamedTemporaryFile` 生成唯一文件名，避免并发覆盖
- ✅ 活体数据库连接 URI 使用 `urllib.parse.quote_plus` 编码凭据，支持含特殊字符的密码

**性能优化**:
- ✅ Embedding 缓存改用 `OrderedDict` LRU 淘汰，上限 10000 条，防止内存无限增长
- ✅ `validate_sql()` 按方言缓存 `SQLValidator` 实例，避免每次调用重建 Linter（现行实现缓存的是 SQLValidator 包装对象；SQLFluff 简单 API 每次调用内部仍构造 Linter，见 core/sql/validator.py）
- ✅ `get_statistics()` 5 次独立查询合并为 1 次带子查询的 SQL

**默认配置变更**:
- ✅ 默认 LLM 切换为本地 Ollama `gemma3:e4b`（2026-10-25 起默认更新为 gemma4:E4B，见 CHANGELOG [Unreleased]-2026-10-25 与 config.py）
- ✅ 默认 Embedding 切换为本地 Ollama `bge-m3:latest`（1024 维 dense）

### v1.3 (2026-04-12)

**关系权重追踪**:
- ✅ CONNECTS 关系新增 `weight`/`occurrence_count`/`source` 属性
- ✅ 图谱构建时自动平分同一表对之间的多条关系权重
- ✅ Neo4j 关系存储权重信息并支持查询排序

**JOIN 提取引擎**:
- ✅ 基于 sqlglot AST 解析从历史 SQL 中提取 JOIN 关系
- ✅ 提取 left_table、right_table、join_condition、join_type
- ✅ 支持复杂 ON 条件拆分（主关联 + 额外条件）
- ✅ 支持 LEFT/RIGHT/INNER/FULL/CROSS JOIN

**权重重平衡算法**:
- ✅ 平滑增量：`new_weight = old_weight × (1 - η) + η`
- ✅ 新关系创建时按比例收缩旧关系权重
- ✅ 自动维护同一表对权重之和 = 1（权重和 = 1 由构建装载时规范化保证；提取&增强重平衡后可能暂时 ≠ 1，见权重架构节）

**反馈驱动图谱增强**:
- ✅ 历史页新增"提取&增强"按钮
- ✅ 提取 JOIN → 展示确认 → 更新 Neo4j 权重
- ✅ 闭环优化知识图谱的表关联关系

**权重感知 Prompt**:
- ✅ 关系信息按权重降序排列
- ✅ LLM 优先选择高权重关联关系生成 SQL
- ✅ 提升多表 JOIN 场景的准确率

**架构优化**:
- ✅ ApplicationContext 统一管理组件生命周期
- ✅ 消除全局单例，改为依赖注入模式
- ✅ `_get_schema_from_neo4j` 修复关系类型查询
- ✅ 消除 sync/async 方法代码重复

### v1.2 (2026-04-01)

**知识图谱构建**:
- ✅ 新增 GraphBuilder Pipeline 模块
- ✅ 支持从 DDL 文件抽取元数据
- ✅ 支持从 JSON 文件抽取元数据
- ✅ 支持从 MySQL 活体数据库抽取元数据
- ✅ AI 语义增强：LLM 自动推断表关系
- ✅ AI 语义增强：LLM 生成业务概念标签
- ✅ SQL 预编译：生成 JOIN SQL 模板

**多数据库支持**:
- ✅ 支持 MySQL、Oracle、Hive、PostgreSQL、SparkSQL（五种方言选项；PostgreSQL/SparkSQL 现因校验器方言名映射缺口生成后校验会失败，已知问题）
- ✅ 数据库 ID 自增管理
- ✅ UNWIND + MERGE 批量装载模式

**前端功能**:
- ✅ 知识图谱构建页面
- ✅ 数据库选择下拉框
- ✅ 图谱导出为 JSON
- ✅ 从 JSON 导入图谱
- ✅ 一键清除知识库
- ✅ 重新初始化系统按钮

**优化改进**:
- ✅ LLM 调用增加重试机制
- ✅ 方言检测器支持多数据库
- ✅ 错误提示优化

### v1.1 (2026-03-25)

**数据库优化**:
- ✅ MySQL 使用 SQLAlchemy QueuePool 连接池
- ✅ Neo4j 配置 Driver 级别连接池
- ✅ 支持连接池参数配置（pool_size, max_overflow 等）

**异步改造**:
- ✅ SQLGenerationChain 新增 generate_async 方法
- ✅ QueryRewriteChain 新增 rewrite_async 方法
- ✅ SQLGenerator 新增 generate_sql_async 方法

**CoT 思维链**:
- ✅ 系统提示词支持 XML 标签格式
- ✅ 先生成思考过程，再生成 SQL
- ✅ 前端展示思考过程（可折叠）

**Few-Shot 学习**:
- ✅ 接入通义千问 Embedding (1536 维)
- ✅ 使用 FAISS 构建 Few-Shot 索引
- ✅ 自动从历史成功记录检索相似示例

**AST 解析**:
- ✅ 使用 sqlglot 替代正则提取表名/字段名
- ✅ 支持 CTE、子查询、Window 函数等复杂场景

### v1.0 (初始版本)

- ✅ 基础 SQL 生成功能
- ✅ BM25 + FAISS 混合检索
- ✅ Streamlit UI
- ✅ 历史记录管理

## 📄 许可证

本项目基于 **[Apache License 2.0](LICENSE)** 开源。

Copyright 2026 溯算编程。完整许可文本见 [LICENSE](LICENSE)。

> 第三方资产说明：内置 Fluent Color 图标源自 Microsoft Fluent UI（MIT 许可），
> 该图标资产适用其原始 MIT 许可；项目其余代码适用 Apache 2.0。
