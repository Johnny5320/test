# 安置帮教系统改进设计文档

## [S1] 问题描述

当前系统存在以下问题：

| 问题类别 | 具体问题 | 影响 |
|----------|----------|------|
| 录入效率 | 身份证信息手动输入 | 录入慢，易出错 |
| 表单体验 | 20+字段一屏显示 | 用户体验差 |
| 数据验证 | 必填字段未强制 | 数据不完整 |
| 可视化 | 无图表统计 | 数据不直观 |
| 批量操作 | 无批量功能 | 效率低 |
| 预警机制 | 无智能预警 | 易遗漏 |

## [S2] 目标用户

| 角色 | 使用场景 | 核心需求 |
|------|----------|----------|
| 司法所科员 | 日常录入、走访 | 快速录入、便捷查询 |
| 司法局科员 | 审核、统计 | 数据完整、报表准确 |
| 系统管理员 | 系统维护 | 稳定运行、易于维护 |

## [S3] 硬件环境

| 配置 | 规格 | 约束 |
|------|------|------|
| CPU | Intel 5代 | 性能有限 |
| 内存 | 4GB | 需轻量级设计 |
| 存储 | HDD | IO性能一般 |
| 网络 | 局域网 | 无公网访问 |

## [S4] 功能设计

### 4.1 身份证自动填充

**功能描述：**
输入身份证号后，自动解析前6位填充省/市/县/镇。

**数据来源：**
- 内置行政区划数据（JSON格式，约3000条）
- 前端本地解析，无需请求后端

**数据结构：**
```json
{
  "320000": { "name": "江苏省", "cities": {
    "320100": { "name": "南京市", "districts": {
      "320102": { "name": "玄武区", "towns": ["孝陵卫街道", "梅园新村街道", ...] }
    }}
  }}
}
```

**交互流程：**
```
用户输入身份证号 → 前端解析前6位 → 匹配行政区划 → 自动填充表单字段 → 用户可手动修改
```

**验证规则：**
- 身份证号必须18位
- 前6位必须是有效行政区划代码
- 第7-14位必须是有效日期

### 4.2 分步表单

**步骤设计：**

| 步骤 | 名称 | 字段数 | 必填字段 |
|------|------|--------|----------|
| 1 | 基本信息 | 6 | 姓名、身份证号 |
| 2 | 帮教信息 | 10 | 状态、风险等级 |
| 3 | 家庭社会信息 | 13 | 无 |

**表单布局：**
```
┌─────────────────────────────────────────────┐
│  步骤1: 基本信息    步骤2: 帮教信息    步骤3: 家庭信息  │
├─────────────────────────────────────────────┤
│                                             │
│  姓名: [________]  *必填                    │
│                                             │
│  身份证号: [________]  *必填                 │
│                                             │
│  性别: [自动推算]                            │
│                                             │
│  出生日期: [自动推算]                         │
│                                             │
│  联系电话: [________]                        │
│                                             │
│  所属村委: [________]                        │
│                                             │
├─────────────────────────────────────────────┤
│  [上一步]  [下一步]  [保存]                   │
└─────────────────────────────────────────────┘
```

**验证规则：**
```javascript
const formRules = {
  // 步骤1：基本信息
  name: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  id_card: [
    { required: true, message: '请输入身份证号', trigger: 'blur' },
    { pattern: /^\d{17}[\dXx]$/, message: '身份证号格式错误', trigger: 'blur' }
  ],
  
  // 步骤2：帮教信息
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
  risk_level: [{ required: true, message: '请选择风险等级', trigger: 'change' }],
  
  // 枚举值验证
  status: [{
    type: 'enum',
    enum: ['在帮', '已解除', '脱管', '重点关注'],
    message: '状态值无效',
    trigger: 'change'
  }]
}
```

### 4.3 数据验证

**必填字段：**

| 字段 | 验证规则 | 错误提示 |
|------|----------|----------|
| 姓名 | 非空，最长20字 | 请输入姓名 |
| 身份证号 | 18位，校验位正确 | 身份证号格式错误 |
| 状态 | 枚举值 | 请选择状态 |
| 风险等级 | 枚举值 | 请选择风险等级 |

**枚举值定义：**

| 字段 | 允许值 |
|------|--------|
| status | 在帮、已解除、脱管、重点关注 |
| risk_level | 高、中、低 |
| visit_method | 上门、电话、视频 |
| marital_status | 未婚、已婚、离异、丧偶 |
| education_level | 小学、初中、高中、大专、本科、研究生 |

### 4.4 ECharts可视化

**图表配置：**

| 图表类型 | 用途 | 数据源 | 刷新频率 |
|----------|------|--------|----------|
| 饼图 | 状态分布 | /api/persons/stats/summary | 实时 |
| 柱状图 | 风险分布 | /api/persons/stats/summary | 实时 |
| 折线图 | 月度趋势 | /api/persons/stats/trend | 每日 |
| 地图 | 地域分布 | /api/persons/stats/village | 实时 |
| 仪表盘 | 走访完成率 | /api/visits/stats/quarterly | 实时 |

**性能优化（4GB内存）：**
- 使用Canvas渲染（非SVG）
- 数据量>100时分页加载
- 图表按需渲染（切换时加载）
- 使用防抖避免频繁刷新

### 4.5 批量操作

**操作类型：**

| 操作 | 前置条件 | 确认提示 |
|------|----------|----------|
| 批量删除 | 选择≥1条记录 | "确定删除选中的N条记录？" |
| 批量修改状态 | 选择≥1条记录 | "将N条记录状态改为XX？" |
| 批量修改风险 | 选择≥1条记录 | "将N条记录风险等级改为XX？" |
| 批量导出 | 选择≥1条记录 | "导出选中的N条记录？" |

**交互设计：**
```
┌─────────────────────────────────────────────┐
│ ☑ 姓名  ☑ 身份证号  ☑ 状态  ☑ 操作          │
├─────────────────────────────────────────────┤
│ ☐ 张三    320102...   在帮    [编辑] [删除]  │
│ ☑ 李四    320103...   脱管    [编辑] [删除]  │
│ ☐ 王五    320104...   在帮    [编辑] [删除]  │
├─────────────────────────────────────────────┤
│ 已选择 1 条记录  [批量删除] [批量修改状态] [批量导出] │
└─────────────────────────────────────────────┘
```

### 4.6 智能预警

**预警规则：**

| 预警类型 | 规则 | 优先级 | 提醒方式 |
|----------|------|--------|----------|
| 到期预警 | 帮教截止日期 ≤ 30天 | 高 | 红色标记 |
| 走访超期 | 未走访天数 > 规定间隔 | 高 | 红色标记 |
| 风险预警 | 风险等级为"高"且无近期走访 | 中 | 黄色标记 |
| 数据异常 | 关键字段为空 | 低 | 灰色标记 |

**风险评分算法：**
```python
def calculate_risk_score(person, last_visit):
    """计算风险评分（0-100）"""
    score = 0
    
    # 风险等级权重（40分）
    risk_weights = {"高": 40, "中": 20, "低": 10}
    score += risk_weights.get(person.risk_level, 0)
    
    # 走访超期（30分）
    if last_visit:
        days_since = (date.today() - last_visit.visit_date).days
        if days_since > person.visit_interval_days:
            score += 30
    else:
        score += 40  # 从未走访
    
    # 到期预警（30分）
    if person.edu_end_date:
        days_remaining = (person.edu_end_date - date.today()).days
        if days_remaining <= 30:
            score += 30
        elif days_remaining <= 0:
            score += 50
    
    return min(score, 100)

def get_risk_level(score):
    """根据评分返回风险等级"""
    if score >= 60:
        return "高风险"
    elif score >= 30:
        return "中风险"
    else:
        return "低风险"
```

## [S5] API设计

### 5.1 新增接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/persons/batch/delete` | POST | 批量删除 |
| `/api/persons/batch/status` | POST | 批量修改状态 |
| `/api/persons/batch/risk` | POST | 批量修改风险等级 |
| `/api/persons/stats/trend` | GET | 月度趋势统计 |
| `/api/persons/{id}/risk-score` | GET | 风险评分 |
| `/api/reminders/warnings` | GET | 预警列表 |

### 5.2 请求/响应格式

**批量删除：**
```json
// POST /api/persons/batch/delete
// Request
{
  "ids": [1, 2, 3]
}

// Response
{
  "code": 0,
  "message": "成功删除3条记录",
  "data": {
    "deleted_count": 3
  }
}
```

**风险评分：**
```json
// GET /api/persons/1/risk-score
// Response
{
  "code": 0,
  "message": "ok",
  "data": {
    "person_id": 1,
    "score": 75,
    "level": "高风险",
    "factors": [
      {"type": "risk_level", "score": 40, "detail": "风险等级：高"},
      {"type": "visit_overdue", "score": 30, "detail": "走访超期15天"},
      {"type": "expiring", "score": 5, "detail": "帮教截止日期剩余25天"}
    ]
  }
}
```

## [S6] 数据库变更

### 6.1 新增表

```sql
-- 预警记录表
CREATE TABLE warnings (
    id INTEGER PRIMARY KEY,
    person_id INTEGER NOT NULL,
    warning_type TEXT NOT NULL,  -- 'expiring' / 'visit_overdue' / 'risk' / 'data_error'
    priority TEXT NOT NULL,      -- 'high' / 'medium' / 'low'
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (person_id) REFERENCES persons(id)
);
```

### 6.2 字段变更

| 表 | 字段 | 变更类型 | 说明 |
|----|------|----------|------|
| persons | risk_score | 新增 | 风险评分(0-100) |
| persons | last_visit_date | 新增 | 最后走访日期（冗余字段，提升查询性能） |
| users | last_login | 新增 | 最后登录时间 |
| users | login_count | 新增 | 登录次数 |

## [S7] 前端组件设计

### 7.1 组件结构

```
frontend/
├── index.html
├── css/
│   └── main.css
├── js/
│   ├── app.js
│   ├── api.js
│   ├── store.js
│   ├── utils.js
│   └── components/
│       ├── Dashboard.js        # 仪表盘
│       ├── Ledger.js           # 人员台账
│       ├── PersonForm.js       # 分步表单
│       ├── BatchToolbar.js     # 批量操作栏
│       ├── StatsChart.js       # ECharts图表
│       ├── WarningList.js      # 预警列表
│       └── IdCardParser.js     # 身份证解析
└── data/
    └── regions.json            # 行政区划数据
```

### 7.2 关键组件

**PersonForm（分步表单）：**
```javascript
const PersonForm = {
  props: ['visible', 'personId'],
  data() {
    return {
      currentStep: 0,
      form: {},
      rules: formRules
    }
  },
  methods: {
    nextStep() {
      // 验证当前步骤
      this.$refs.form.validate((valid) => {
        if (valid) this.currentStep++
      })
    },
    prevStep() {
      this.currentStep--
    },
    onSubmit() {
      // 提交表单
    }
  }
}
```

**BatchToolbar（批量操作栏）：**
```javascript
const BatchToolbar = {
  props: ['selectedIds'],
  methods: {
    batchDelete() {
      if (confirm(`确定删除选中的${this.selectedIds.length}条记录？`)) {
        this.$emit('batch-delete', this.selectedIds)
      }
    },
    batchUpdateStatus(status) {
      this.$emit('batch-status', { ids: this.selectedIds, status })
    }
  }
}
```

## [S8] 实施计划

| 阶段 | 任务 | 工期 | 依赖 | 产出 |
|------|------|------|------|------|
| 1 | 行政区划数据准备 | 0.5天 | - | regions.json |
| 2 | 身份证自动填充 | 0.5天 | 阶段1 | IdCardParser.js |
| 3 | 分步表单+验证 | 1.5天 | - | PersonForm.js |
| 4 | 批量操作 | 1天 | - | BatchToolbar.js + API |
| 5 | ECharts可视化 | 1.5天 | - | StatsChart.js |
| 6 | 查询优化 | 0.5天 | - | 后端代码 |
| 7 | 智能预警 | 1.5天 | - | WarningList.js + API |
| 8 | 测试+修复 | 1.5天 | 阶段1-7 | 测试报告 |
| **总计** | | **8.5天** | | |

## [S9] 验收标准

### 功能验收

| 功能 | 验收标准 |
|------|----------|
| 身份证自动填充 | 输入320102开头的身份证号，自动填充江苏省/南京市/玄武区 |
| 分步表单 | 3步表单可正常切换，必填字段验证生效 |
| 枚举值验证 | 输入无效枚举值时提示错误 |
| 批量操作 | 选择多条记录后可批量删除、修改状态 |
| ECharts图表 | 仪表盘显示状态分布、风险分布饼图 |
| 智能预警 | 到期30天内、走访超期的人员显示预警标记 |

### 性能验收

| 指标 | 目标值 |
|------|--------|
| 人员列表查询（1000条） | < 500ms |
| 统计接口响应 | < 1s |
| 图表渲染 | < 2s |
| 内存占用 | < 500MB |

### 兼容性验收

| 环境 | 要求 |
|------|------|
| Chrome 80+ | 完全兼容 |
| Firefox 70+ | 完全兼容 |
| Edge 80+ | 完全兼容 |
| 屏幕分辨率 | 1280x720 及以上 |

## [S10] 风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 行政区划数据不完整 | 低 | 中 | 使用官方数据源 |
| ECharts内存占用高 | 中 | 高 | 使用Canvas渲染，按需加载 |
| 分步表单状态丢失 | 低 | 中 | 使用localStorage缓存 |
| 批量操作性能问题 | 中 | 中 | 分批处理，每批100条 |
| 智能预警误报 | 中 | 低 | 可手动标记忽略 |

## [S11] 决策记录

| 问题 | 决策 | 理由 |
|------|------|------|
| 行政区划数据来源 | 国家统计局数据 | 官方数据，约3000条，准确权威 |
| 批量操作上限 | 100条 | 适合4GB内存，性能稳定 |
| ECharts版本 | 按需引入 | 减少打包体积 |
| 预警通知方式 | 仅页面显示 | 当前阶段够用，后续可扩展 |
