---
id: forest-guard-ai
order: 1
date: "2026-03-15"
category: "AI & IoT • Science Fair"
title_en: "ForestGuard AI: Multimodal Dual-Layer Early-Stage Wildfire Detection System"
title_zh-CN: "ForestGuard AI：多模态双层林火超早期预警系统"
title_zh-TW: "ForestGuard AI：多模態雙層森林火災超早期預警系統"
title_ja: "ForestGuard AI：マルチモーダル2段階早期山火事検知システム"
subtitle_en: "Pre-ignition chemical detection & vision confirmation IoT monorepo architecture"
subtitle_zh-CN: "基于起火前化学分解监测与视觉二次验证的高性能物联网架构"
subtitle_zh-TW: "基於燃燒前化學分解監測與視覺二次驗證的高性能物聯網架構"
subtitle_ja: "発火前の化学変化検知と画像検証を組み合わせた高性能IoTアーキテクチャ"
summary_en: "A resource-decoupled IoT wildfire early predictor designed to capture gaseous chemical anomalies at the pre-ignition stage before active flames emerge."
summary_zh-CN: "一款面向超早期林火监测的解耦式物联网预警系统，在明火与肉眼可见浓烟生成前的“化学热解阶段”即完成精准识别。"
summary_zh-TW: "一款針對超早期森林火災的解耦式物聯網預警系統，在明火與可見濃煙生成前的「化學熱解階段」即可實現即時捕捉與警報。"
summary_ja: "明火や白煙が発生する前の「発火前化学熱分解段階」でガス濃度の異常を捉える、省リソース・疎結合型のIoT早期山火事検知システム。"
link: "https://fg.scalexch.net"
image_type: svg
image_value: tree
---

<!-- lang:en -->
## Technical Architecture & Monorepo Overview
*A high-performance, resource-decoupled Internet of Things (IoT) wildfire predictor engineered to capture threats at the **pre-ignition chemical stage** before active flames emerge.*

***

## 👤 Project & Contributor Profile
* **Project ID:** #3302
* **Target Event:** Greater Vancouver Regional Science Fair (**GVRSF 2026**), University of British Columbia (UBC)
* **Alex Cheng (Project Lead):**
  * Grade 11 Student, Windsor Secondary School
  * Role: Cloud Platform Engineering & AI Analytics Pipeline
  * Web & Portfolio: [fg.scalexch.net](https://fg.scalexch.net) | [scalexch.net](https://scalexch.net)
  * GitHub: [@Snowy-Collie](https://github.com/Snowy-Collie) | YouTube: [@SnowyCollie](https://www.youtube.com/@SnowyCollie)
  * Email: `alex@scalexch.net`
* **John Cheng (Hardware & Firmware Lead):**
  * Role: Embedded Firmware & Hardware Edge Integration
  * Open Source Community: [wezhike.org](https://www.wezhike.org) | Website: [cx192.com](https://www.cx192.com)
  * GitHub: [@wezhike](https://github.com/wezhike) | YouTube: [@wezhike](https://www.youtube.com/@wezhike)

***

## 1. Background & Core Innovation

Conventional wildfire monitoring networks suffer from severe response latency. Relying on thermal orbital satellites or optical lookout towers means fires are often spotted only after reaching large-scale, active burning stages—making firefighting exponentially harder, riskier, and costlier.

**ForestGuard AI** shifts the focus to the **pre-ignition chemical stage**:
1. **Pyrolysis Decomposition Detection:** Before flames break out, decomposing organic forest fuels emit sub-ppm level gaseous anomalies (Total Volatile Organic Compounds / TVOC and Equivalent Carbon Dioxide / eCO2).
2. **Dual Confirmation Pipeline:** Gaseous anomalies trigger local camera capture, which is cross-verified via lightweight computer vision to prevent false positives from fertilizer or exhaust fumes.

***

## 2. Decoupled Monorepo Architecture

To allow seamless deployment on low-spec edge/cloud VMs (e.g., 2GB RAM instances) without Out-Of-Memory (OOM) failures or cellular NAT issues:


```

┌────────────────────────────────────────────────────────────────────────┐
│                          1. HARDWARE LAYER                             │
│  [Sensors: TVOC, eCO2, NH3, H2S, Temp, Hum] ──► [EG800Q 4G Module]     │
│  [OV2640 / SPI Camera Chunked Photo Stream]                            │
└──────────────────────────────────┬─────────────────────────────────────┘
│ Raw TCP Binary (ZProtocol Frames)
▼
┌────────────────────────────────────────────────────────────────────────┐
│                  2. INGESTION SERVICE (Port 20000)                     │
│  ┌──────────────────────┐  ┌────────────────────────────────────────┐  │
│  │ ZProtocol Decoder    │  │ Client Handler (Multi-threaded)        │  │
│  │ (0x31 Telemetry,     │  ├────────────────────────────────────────┤  │
│  │  0x33 Image Chunks)  │  │ GPS Fallback Logic & Image Assembler   │  │
│  └──────────┬───────────┘  └───────────────────┬────────────────────┘  │
└─────────────┼──────────────────────────────────┼───────────────────────┘
              │ Store Records & Image Files      │ Real-Time HTTP Push
              ▼                                  ▼ (/process)
┌─────────────────────────┐          ┌───────────────────────────────────┐
│     PostgreSQL DB       │          │   3. AI INFERENCE SERVICE         │
│     (data_upload)       │          │          (Port 8001)              │
│  ┌───────────────────┐  │          │  ┌─────────────────────────────┐  │
│  │ Telemetry Records │  │          │  │ Feature Extraction Pipeline │  │
│  │ GPS Coordinates   │  │          │  └──────────────┬──────────────┘  │
│  │ Image Paths       │  │          │                 ▼                 │
│  │ AI-1 & AI-2 Scores│  │          │  ┌─────────────────────────────┐  │
│  │ final_risk_level  │  │          │  │ AI-1 Model (XGBoost Booster)│  │
│  └─────────▲─────────┘  │          │  └──────────────┬──────────────┘  │
└────────────┼────────────┘          │                 ▼ (If AI-1 > 0.6) │
             │ Query & Update        │  ┌─────────────────────────────┐  │
             │                       │  │ AI-2 Model (Keras CNN .h5)  │  │
             │                       │  └──────────────┬──────────────┘  │
             │                       └─────────────────┼─────────────────┘
             │                                         │
             │ Async Callback (/api/ai_callback)       │
             └─────────────────────────────────────────┘
                                   ▲
                                   │ REST API & Real-Time GIS Updates
┌──────────────────────────────────┴─────────────────────────────────────┐
│                 4. WEB BACKEND & DASHBOARD (Port 8000)                 │
│  ┌──────────────────────────────────┐  ┌────────────────────────────┐  │
│  │ FastAPI Server (/api/data)       │  │ Leaflet.js Map Dashboard   │  │
│  │ Static Assets (/static mount)    │  │ Sidebar Device Details     │  │
│  │ Image Server (/api/images/{img}) │  │ Manual AI Override & Delete│  │
│  │ Pending Queue (/api/ai/pending)  │  │ Dynamic Risk Badges        │  │
│  └──────────────────────────────────┘  └────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘

```

### Key Subsystems
* **Ingestion Service (`src/ingestion/`)**: Multi-threaded TCP listener (Port 20000) decoding custom binary ZProtocol packets (`0x31` environmental data, `0x33` chunked photo frames) with automated GPS fallback.
* **AI Inference Service (`src/ai_service/`)**: Dedicated FastAPI microservice (Port 8001) evaluating tabular environmental indicators and conditionally running MobileNetV2 image verification.
* **Web Backend & GIS Dashboard (`src/web_backend/` & `web_frontend/`)**: FastAPI platform serving Leaflet.js map tiles, risk badges, device telemetry cards, and manual override controls.

***

## 3. Dual-Layer AI Model Stack & Fusion Logic

1. **AI-1 Tabular Classifier (XGBoost C++ Booster)**:
   * Evaluates physical telemetry (`TVOC`, `eCO2`, `NH3`, `H2S`, temperature, and humidity) mapped to Blattmann's Kaggle Smoke Detection feature schema.
   * Outputs continuous probability score `[0.0, 1.0]`.
2. **AI-2 Visual Verifier (MobileNetV2 CNN)**:
   * Trained on Universitat Politècnica de Catalunya's Wildfire Dataset.
   * Activated only when `AI-1 >= 0.6` to verify presence of actual smoke/flame and reject spurious chemical disturbances.

| AI-1 Score | Environmental State | Camera & AI-2 Action | Risk Level | Map Indicator |
| :--- | :--- | :--- | :--- | :--- |
| **< 0.3** | Clean / Baseline Atmosphere | Standby (Power & Data saving) | **Level 1 (Safe)** | Green |
| **0.3 – 0.6** | Minor baseline variation | Standby; normal polling | **Level 1 (Safe)** | Green |
| **0.6 – 0.9** | Gaseous anomaly detected | Trigger photo; run AI-2 | **Level 2 (Warning)** | Yellow |
| **>= 0.9** OR **(>= 0.6 & AI-2 >= 0.8)** | Pre-Ignition / Active Fire | High-frequency telemetry & alert | **Level 3 (Alert)** | Red |

***

## 4. Key Strengths & Engineering Roadmap

* **GPS Signal Resilience**: Automatic fallback retrieves the node's last-known valid coordinates when canopy density interrupts satellite lock.
* **Bandwidth Optimization**: Binary chunked transport avoids the 33% payload bloat of Base64 encoding across cellular IoT links.
* **Future Roadmap**: Implement sequential temporal prediction (LSTM/GRU for $dC/dt$ gas surge rates) and edge deployment using TensorFlow Lite / ONNX on Jetson/Raspberry Pi boards.


<!-- lang:zh-CN -->
## 技术架构与 Monorepo 工程文档
*一款面向野火极早期预警的高性能、资源解耦型物联网（IoT）系统，致力于在明火产生前的**“起火前化学热解阶段”**捕获火灾隐患。*

***

## 👤 项目与开发者信息
* **项目编号：** #3302
* **参展赛事：** 大温哥华区域科学展（**GVRSF 2026**），不列颠哥伦比亚大学（UBC）主办
* **Alex Cheng（项目负责人）：**
  * 温莎中学（Windsor Secondary School）11 年级学生
  * 负责模块：云平台开发、多模态 AI 管道与全栈 Web 架构
  * 个人主页与项目站：[fg.scalexch.net](https://fg.scalexch.net) | [scalexch.net](https://scalexch.net)
  * GitHub: [@Snowy-Collie](https://github.com/Snowy-Collie) | YouTube: [@SnowyCollie](https://www.youtube.com/@SnowyCollie)
  * 联系邮箱：`alex@scalexch.net`
* **John Cheng（硬件与固件负责人）：**
  * 负责模块：边缘传感器固件、4G 通信模组与底层硬件协议
  * 开源社区：[wezhike.org](https://www.wezhike.org) | 个人主页：[cx192.com](https://www.cx192.com)
  * GitHub: [@wezhike](https://github.com/wezhike) | YouTube: [@wezhike](https://www.youtube.com/@wezhike)

***

## 1. 项目背景与核心理念

传统林火监测方案普遍面临关键瓶颈：**响应周期严重滞后**。目前广泛依靠的卫星热成像或高山瞭望塔光学监控，往往要在林火蔓延、产生大量浓烟甚至形成明火后才能捕获信号，此时火势往往已极难受控。

**ForestGuard AI** 开创性地将防御前线推进至**“起火前化学分解阶段”**：
1. **热解阶段气体微变捕捉**：在明火或可见烟雾形成数小时前，林地干燥枯枝落叶层在高温阴燃下开始热解，释放微量（sub-ppm 级）异味及气体波动（总挥发性有机物 TVOC 及等效二氧化碳 eCO2）。
2. **多模态双层校验**：传感器捕获气体突变后自动唤醒摄像头抓拍现场，并交由轻量级计算机视觉模型二次核验，有效排除汽车尾气、化肥挥发等造成的非火灾化学误报。

***

## 2. 解耦式 Monorepo 系统架构

为了在低配置云服务器（如 2GB 内存实例）上平稳运行、避免深度学习与数据接入并发导致的内存溢出（OOM），并穿透蜂窝网络 NAT，项目采用了**高度模块化的解耦 Monorepo** 架构：


```

┌────────────────────────────────────────────────────────────────────────┐
│                             1. 硬件层 (边缘节点)                        │
│  [传感器: TVOC, eCO2, NH3, H2S, 温湿度] ──► [EG800Q 4G 蜂窝模组]        │
│  [OV2640 / SPI 摄像头分块图片传输]                                      │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ 原生 TCP 二进制流 (ZProtocol 协议帧)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     2. 数据接收服务 (端口 20000)                        │
│  ┌──────────────────────┐  ┌────────────────────────────────────────┐  │
│  │ ZProtocol 解码器     │  │ 多线程连接处理器                       │  │
│  │ (0x31 遥测数据,      │  ├────────────────────────────────────────┤  │
│  │  0x33 图像分片组包)  │  │ GPS 容灾回退逻辑 & 图像拼装器          │  │
│  └──────────┬───────────┘  └───────────────────┬────────────────────┘  │
└─────────────┼──────────────────────────────────┼───────────────────────┘
│ 保存遥测数据与图像文件           │ 实时 HTTP 推送 (/process)
▼                                  ▼
┌─────────────────────────┐          ┌───────────────────────────────────┐
│     PostgreSQL 数据库   │          │       3. AI 推理微服务            │
│     (data_upload)       │          │          (端口 8001)              │
│  ┌───────────────────┐  │          │  ┌─────────────────────────────┐  │
│  │ 遥测传感器记录     │  │          │  │ 特征工程对齐管道              │  │
│  │ GPS 地理坐标       │  │          │  └──────────────┬──────────────┘  │
│  │ 图像本地路径       │  │          │                 ▼                 │
│  │ AI-1 & AI-2 评分  │  │          │  ┌─────────────────────────────┐  │
│  │ final_risk_level  │  │          │  │ AI-1 模型 (XGBoost Booster) │  │
│  └─────────▲─────────┘  │          │  └──────────────┬──────────────┘  │
└────────────┼────────────┘          │                 ▼ (当 AI-1 > 0.6) │
             │ 查询与更新风险状态      │  ┌─────────────────────────────┐  │
             │                       │  │ AI-2 视觉模型 (MobileNetV2) │  │
             │                       │  └──────────────┬──────────────┘  │
             │                       └─────────────────┼─────────────────┘
             │                                         │
             │ 异步回调写入结果 (/api/ai_callback)     │
             └─────────────────────────────────────────┘
                                   ▲
                                   │ RESTful API 与 GIS 实时状态流
┌──────────────────────────────────┴─────────────────────────────────────┐
│                 4. Web 后端服务与地图监控大屏 (端口 8000)                │
│  ┌──────────────────────────────────┐  ┌────────────────────────────┐  │
│  │ FastAPI 业务接口 (/api/data)     │  │ Leaflet.js GIS 电子地图      │  │
│  │ 静态前端挂载 (/static)           │  │ 侧边栏设备详情面板            |  │
│  │ 图像分发接口 (/api/images/{img}) │  │ 手动修正与假数据删除          |  │
│  │ 推理队列与状态轮询                │  │ 动态多色风险标记与告警        │  │
│  └──────────────────────────────────┘  └────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘

```

### 核心子系统职能
1. **数据接入服务 (`src/ingestion/`)**：基于原生多线程 TCP 监听（端口 20000），高效解析二进制 ZProtocol 协议帧（`0x31` 遥测数据、`0x33` 图片分片拼接）。内置 **GPS 信号丢失自动回退机制**。
2. **AI 推理微服务 (`src/ai_service/`)**：独立运行于 8001 端口的 FastAPI 微服务。通过特征对齐管道计算 XGBoost 火险评分；若发现异常，条件唤醒 MobileNetV2 验证现场照片，并通过异步回调写回结果。
3. **Web 后端与可视化大屏 (`src/web_backend/` & `web_frontend/`)**：运行于 8000 端口，基于 Leaflet.js 提供交互式 GIS 风险态势感知地图、实时图表、抓拍照片审查以及人工研判重置功能。

***

## 3. 双层 AI 模型体系与多模态决策逻辑

1. **AI-1：气体环境特征推断器（XGBoost）**
   * 基于 Stefan Blattmann 经典烟雾检测数据集（含 60,000+ 组多样化燃烧与背景读数）训练。
   * 采用底层 C++ 原生 `xgb.Booster` 与 `xgb.DMatrix` 驱动，输出 `0.0` 至 `1.0` 的连续火险概率值。
2. **AI-2：机器视觉核验器（MobileNetV2 CNN）**
   * 针对加泰罗尼亚理工大学野火图像库训练，轻量高效。
   * 仅在 `AI-1 >= 0.6` 时唤醒，精准排除非火灾引发的局部化学异常（如机械尾气、肥料挥发）。

| AI-1 风险评分 | 环境化学状态 | 摄像头与 AI-2 行为 | 综合风险评级 | 地图标记色彩 |
| :--- | :--- | :--- | :--- | :--- |
| **< 0.3** | 洁净 / 正常背景大气 | 保持休眠（节省电池与流量） | **一级：安全 (Safe)** | 绿色 |
| **0.3 – 0.6** | 环境基线轻微波动 | 保持休眠；正常心跳轮询 | **一级：安全 (Safe)** | 绿色 |
| **0.6 – 0.9** | 捕获化学微变与异常 | 唤醒镜头抓拍，执行视觉核查 | **二级：预警 (Warning)** | 黄色 |
| **>= 0.9** 或 **(>= 0.6 且 AI-2 >= 0.8)** | 确认起火前热解或已起明火 | 触发高频上报与实时应急告警 | **三级：警报 (Alert)** | 红色 |

***

## 4. 核心工程优势与后续规划

* **密林 GPS 容灾保活**：树冠茂密导致卫星脱锁时，系统自动调取节点最近一次有效定位（`get_last_known_gps`），确保设备在 GIS 地图上永不掉线。
* **原生二进制网络分发**：分片封装传输照片，相比 Base64 编码降低了 33% 的带宽消耗，适配恶劣野外 4G 窄带网络。
* **后续研究方向**：引入时序神经网络（LSTM/GRU）分析气体浓度变化率（$dC/dt$）；将视觉模型量化为 ONNX/TFLite 格式，实现边缘端直接推理。


<!-- lang:zh-TW -->
## 技術架構與 Monorepo 系統文件
*一套針對森林野火極早期預警的高效能、資源解耦型物聯網（IoT）預測系統，專為在明火產生的**「燃燒前化學熱解階段」**即時捕獲潛在威脅而設計。*

***

## 👤 專案與團隊成員簡介
* **專案編號：** #3302
* **參賽目標：** 大溫哥華區域科學展覽會（**GVRSF 2026**），由英屬哥倫比亞大學（UBC）主辦
* **Alex Cheng（專案負責人）：**
  * 溫莎中學（Windsor Secondary School）11 年級學生
  * 執掌範疇：雲端平台開發、多模態 AI 預測管線與全端 Web 系統架構
  * 個人網站與專案入口：[fg.scalexch.net](https://fg.scalexch.net) | [scalexch.net](https://scalexch.net)
  * GitHub: [@Snowy-Collie](https://github.com/Snowy-Collie) | YouTube: [@SnowyCollie](https://www.youtube.com/@SnowyCollie)
  * 電子郵件：`alex@scalexch.net`
* **John Cheng（硬體與韌體研發主導）：**
  * 執掌範疇：邊緣感測器韌體、4G 通訊模組及底層硬體傳輸協定
  * 開源社群：[wezhike.org](https://www.wezhike.org) | 個人網站：[cx192.com](https://www.cx192.com)
  * GitHub: [@wezhike](https://github.com/wezhike) | YouTube: [@wezhike](https://www.youtube.com/@wezhike)

***

## 1. 研發背景與核心願景

傳統的森林野火監測系統長期受限於**警報反應嚴重延遲**。常見的人造衛星熱成像與山頂巡邏瞭望塔光學觀測，往往須等到火勢蔓延、濃煙瀰漫或明火猛烈燃燒時才能發現，此時撲救難度與撲滅成本皆呈指數級激增。

**ForestGuard AI** 將防禦陣線推進至**「燃燒前化學分解階段」**：
1. **熱解氣體異常捕捉**：在肉眼可見煙霧或火光出現前數小時，乾燥森林腐殖質因高溫陰燃而熱解，釋放出極微量（sub-ppm 級）的揮發性有機物（TVOC）與等效二氧化碳（eCO2）。
2. **多模態二次查驗**：氣體感測器一旦捕捉到突波異常，即刻喚醒鏡頭拍攝現場照片，並由機器視覺卷積神經網路進行二次過濾，徹底排除農藥揮發或車輛廢氣引發的誤報。

***

## 2. 模組化解耦 Monorepo 架構

為了在低規格雲端主機（例如僅有 2GB RAM 之虛擬機）上順暢運作、避免深度學習與資料流並行所導致的記憶體耗盡（OOM），並順利穿透蜂窩行動網路 NAT，本系統採行**高度解耦的單一儲存庫（Monorepo）**設計：

* **資料接入服務 (`src/ingestion/`)**：基於原生多執行緒 TCP 監聽器（埠號 20000），高效解碼自定義二進位 ZProtocol 封包（`0x31` 環境感測數據、`0x33` 鏡頭影像分塊組裝），並內建具備容錯能力的 **GPS 遺失回退機制**。
* **AI 推論微服務 (`src/ai_service/`)**：獨立運行於埠號 8001 的 FastAPI 微服務。經由標準化特徵對齊管線執行 XGBoost 火災機率推論；符合條件時啟動 MobileNetV2 影像檢驗，並透過非同步回呼（Async Callback）寫回資料庫。
* **Web 後端與 GIS 儀表板 (`src/web_backend/` & `web_frontend/`)**：運行於埠號 8000，提供 Leaflet.js 動態地圖視覺化、即時感測數據面板、設備照片檢視與手動管理控制介面。

***

## 3. 雙層 AI 模型與多模態決策邏輯

1. **AI-1：環境化學預測器（XGBoost）**
   * 採用原生 C++ 核心之 `xgb.Booster`，依據氣體與溫濕度指標輸出 `0.0` 至 `1.0` 之連續火險機率。
2. **AI-2：電腦視覺查驗器（MobileNetV2 CNN）**
   * 專門針對野火煙火影像資料集訓練，僅在 `AI-1 >= 0.6` 時啟動，能過濾各類非火災化學異常。

| AI-1 評分區間 | 環境大氣狀態 | 鏡頭與 AI-2 動作 | 最終風險等級 | 地圖圖示標籤 |
| :--- | :--- | :--- | :--- | :--- |
| **< 0.3** | 潔淨 / 基準背景狀態 | 保持休眠（節省電力與行動流量） | **第一級：安全 (Safe)** | 綠色 |
| **0.3 – 0.6** | 環境基線輕微起伏 | 保持休眠；一般週期輪詢 | **第一級：安全 (Safe)** | 綠色 |
| **0.6 – 0.9** | 偵測到化學濃度突波異常 | 喚醒鏡頭拍照；執行 AI-2 查驗 | **第二級：預警 (Warning)** | 黃色 |
| **>= 0.9** 或 **(>= 0.6 且 AI-2 >= 0.8)** | 確認進入熱解或已現明火 | 啟動高頻通報與即時警報傳遞 | **第三級：警戒 (Alert)** | 紅色 |

***

## 4. 關鍵技術亮點與後續藍圖

* **抗遮蔽 GPS 回退保護**：密林樹冠導致 GPS 訊號遺失時，自動調取歷史有效定位，保證節點永不在電子地圖上消失。
* **二進位資料分片傳輸**：相較於 Base64 格式降低了約 33% 傳輸酬載，大幅提升遠端物聯網傳輸的穩定度。
* **後續研究計畫**：計畫導入時序神經網路（LSTM/GRU）評估氣體升溫爬升率（$dC/dt$），並將模型轉換為 ONNX/TFLite 部署至邊緣單板電腦（如 Raspberry Pi / Jetson Nano）。


<!-- lang:ja -->
## 技術アーキテクチャ＆モノレポ仕様書
*明火が発生する前の**「発火前化学熱分解段階」**でリスクを検知する、高性能かつリソース分離型のIoT山火事早期警戒システム。*

***

## 👤 プロジェクトおよび開発者概要
* **プロジェクト番号：** #3302
* **対象コンテスト：** グレーター・バンクーバー地域サイエンスフェア（**GVRSF 2026** / ブリティッシュコロンビア大学 UBC 主催）
* **Alex Cheng（プロジェクトリード）：**
  * ウィンザー・セカンダリー・スクール（Windsor Secondary School）11年生
  * 担当領域：クラウドプラットフォーム開発、マルチモーダルAI推論パイプライン、Webシステム設計
  * サイト＆ポートフォリオ：[fg.scalexch.net](https://fg.scalexch.net) | [scalexch.net](https://scalexch.net)
  * GitHub: [@Snowy-Collie](https://github.com/Snowy-Collie) | YouTube: [@SnowyCollie](https://www.youtube.com/@SnowyCollie)
  * 連絡先：`alex@scalexch.net`
* **John Cheng（ハードウェア＆ファームウェアリード）：**
  * 担当領域：エッジセンサーファームウェア、4Gセルラー通信モジュール、低レイヤ通信プロトコル
  * オープンソースコミュニティ：[wezhike.org](https://www.wezhike.org) | 個人サイト：[cx192.com](https://www.cx192.com)
  * GitHub: [@wezhike](https://github.com/wezhike) | YouTube: [@wezhike](https://www.youtube.com/@wezhike)

***

## 1. 開発背景とコアコンセプト

従来の山火事監視システムには**「検知の大幅な遅延」**という深刻な課題が存在します。人工衛星の赤外線検知や監視塔からの光学カメラに依存する手法では、白煙が立ち上り大規模な燃焼が始まった後でなければ発見できず、消火活動は困難を極めます。

**ForestGuard AI** は、観測の焦点を**「発火前の化学熱分解段階」**へとシフトさせました：
1. **熱分解ガスの微小変動検知**：目に見える炎や煙が現れる数時間前に、林床の有機堆積物がくすぶり始めることで微量（sub-ppmレベル）の揮発性有機化合物（TVOC）および等価二酸化炭素（eCO2）が放出されます。
2. **マルチモーダル2段階検証**：ガス濃度の急変を検知すると同時にカメラを起動し、軽量画像認識CNNによって二次検証を実施。排気ガスや肥料の揮発による誤報を確実に除外します。

***

## 2. 疎結合型モノレポ（Monorepo）システム構造

低スペックなクラウド仮想マシン（メモリ2GB構成など）でのOut-Of-Memory（OOM）を防ぎ、4G携帯網のNAT環境下でも安定動作させるため、各機能は**独立した疎結合アーキテクチャ**として構築されています：

* **データ収集サービス (`src/ingestion/`)**：マルチスレッド対応TCPリスナー（ポート 20000）。独自のバイナリZProtocolフレーム（`0x31` テレメトリ、`0x33` 分割画像フレーム）をデコードし、GPS信号途絶時の自動フォールバックを備えます。
* **AI推論マイクロサービス (`src/ai_service/`)**：ポート 8001 で動作するFastAPIサービス。特徴量エンジニアリングを経てXGBoost推論を行い、基準値を超えた場合にMobileNetV2による画像検証を非同期（Async Callback）で実行します。
* **Webバックエンド＆地図ダッシュボード (`src/web_backend/` & `web_frontend/`)**：ポート 8000 で動作。Leaflet.jsによるリアルタイムGISマップ、センサー推移グラフ、現地写真プレビュー、手動オーバーライド機能を提供します。

***

## 3. 2段階AIモデル構成と判断ロジック

1. **AI-1：環境センサー推論器（XGBoost）**
   * Blattmannの煙検知データセット（60,000件以上）で学習したC++ネイティブの `xgb.Booster` を使用し、火災確率（`0.0` 〜 `1.0`）を出力します。
2. **AI-2：画像認識検証器（MobileNetV2 CNN）**
   * カタルーニャ工科大学の山火事画像セットで学習。
   * `AI-1 >= 0.6` の場合にのみ稼働し、非火災の環境ガス異常による誤検知を遮断します。

| AI-1 スコア | 環境大気の状態 | カメラおよびAI-2の動作 | 総合リスク判定 | マップ表示色 |
| :--- | :--- | :--- | :--- | :--- |
| **< 0.3** | 正常・ベースライン大気 | スタンバイ待機（省電力・通信量削減） | **レベル1：安全 (Safe)** | 緑 (Green) |
| **0.3 – 0.6** | 微小な大気変動 | スタンバイ待機・通常ポーリング | **レベル1：安全 (Safe)** | 緑 (Green) |
| **0.6 – 0.9** | 化学的異常濃度の検知 | カメラ起動・撮影・AI-2画像検証実行 | **レベル2：注意 (Warning)** | 黄 (Yellow) |
| **>= 0.9** または **(>= 0.6 かつ AI-2 >= 0.8)** | 熱分解または明火の発生確認 | 高頻度テレメトリ送信・緊急アラート発報 | **レベル3：警報 (Alert)** | 赤 (Red) |

***

## 4. 主な技術的優位性と今後のロードマップ

* **GPS信号欠落の耐障害性**：密林の樹冠によって衛星補強が失われた場合でも、直近の有効座標を自動取得（`get_last_known_gps`）し、マップ上でのロストを防止します。
* **バイナリパケット直接伝送**：Base64エンコードによる33%のデータオーバーヘッドを排除し、山間部の狭帯域4G通信でも高速にパケットを処理します。
* **今後の研究課題**：時系列モデル（LSTM/GRU）の導入による濃度上昇率（$dC/dt$）のリアルタイム追従、およびモデルのONNX/TFLite化によるエッジシングルボードPC（Raspberry Pi / Jetson）への直接デプロイを予定しています。
