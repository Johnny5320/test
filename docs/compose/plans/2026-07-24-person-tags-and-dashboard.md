# 人员标签与仪表盘联动 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增人员标签字段（未成年/xj/精神疾病），将"重点"改为"评级"，仪表盘新增标签统计卡片并支持点击跳转筛选。

**Architecture:** 在Person模型新增3个bool字段，后端stats/summary新增统计，list_persons新增筛选参数，前端表格/表单/仪表盘同步更新。

**Tech Stack:** FastAPI + SQLModel + SQLite + Vue3 + Element Plus

---

## File Structure

| 文件 | 职责 |
|------|------|
| `backend/app/models/person.py` | 新增 is_minor, is_xj, is_mental 字段 |
| `backend/app/schemas/__init__.py` | PersonCreate/Update/Response + StatsSummary 新增字段 |
| `backend/app/api/persons.py` | stats/summary 新增统计 + list_persons 新增筛选 |
| `frontend/index_v2.html` | 表格列、表单、仪表盘、筛选器 |

---

### Task 1: 数据模型 — 新增3个字段

**Covers:** 数据模型变更

**Files:**
- Modify: `judicial-system/backend/app/models/person.py:52-56`

- [ ] **Step 1: 在 Person 模型中新增字段**

在 `is_recidivist` 字段之后添加：

```python
is_minor: Optional[bool] = Field(default=False)        # 是否未成年
is_xj: Optional[bool] = Field(default=False)           # 是否xj
is_mental: Optional[bool] = Field(default=False)       # 是否精神疾病
```

- [ ] **Step 2: 运行迁移确认字段生效**

```bash
cd judicial-system/backend
.\.venv\Scripts\python.exe -c "from app.models.person import Person; print([f.name for f in Person.__table__.columns])"
```

预期输出包含 is_minor, is_xj, is_mental

---

### Task 2: Schema — 新增字段到 Create/Update/Response/StatsSummary

**Covers:** Schema变更

**Files:**
- Modify: `judicial-system/backend/app/schemas/__init__.py`

- [ ] **Step 1: PersonCreate 新增字段**

在 `has_subsidy` 之后、`economic_status` 之前添加：

```python
is_minor: Optional[bool] = False
is_xj: Optional[bool] = False
is_mental: Optional[bool] = False
```

- [ ] **Step 2: PersonUpdate 新增字段**

在 `has_subsidy` 之后、`economic_status` 之前添加：

```python
is_minor: Optional[bool] = None
is_xj: Optional[bool] = None
is_mental: Optional[bool] = None
```

- [ ] **Step 3: PersonResponse 新增字段**

在 `has_subsidy` 之后、`economic_status` 之前添加：

```python
is_minor: Optional[bool] = False
is_xj: Optional[bool] = False
is_mental: Optional[bool] = False
```

- [ ] **Step 4: StatsSummary 新增统计字段**

在 `total_key_target` 之后添加：

```python
total_minor: int = 0
total_xj: int = 0
total_mental: int = 0
```

---

### Task 3: 后端API — stats/summary 新增统计 + list_persons 新增筛选

**Covers:** API变更

**Files:**
- Modify: `judicial-system/backend/app/api/persons.py`

- [ ] **Step 1: stats_summary 新增3个统计**

在 `total_key_target` 统计代码之后添加：

```python
# 未成年人数
total_minor = session.exec(
    select(func.count()).select_from(
        base.where(Person.is_minor == True).subquery()
    )
).one()

# xj人数
total_xj = session.exec(
    select(func.count()).select_from(
        base.where(Person.is_xj == True).subquery()
    )
).one()

# 精神疾病人数
total_mental = session.exec(
    select(func.count()).select_from(
        base.where(Person.is_mental == True).subquery()
    )
).one()
```

在 return StatsSummary 中添加：

```python
total_minor=total_minor,
total_xj=total_xj,
total_mental=total_mental,
```

- [ ] **Step 2: list_persons 新增筛选参数**

在函数签名中添加参数：

```python
is_minor: Optional[bool] = None,
is_xj: Optional[bool] = None,
is_mental: Optional[bool] = None,
prison_place: Optional[str] = None,
village: Optional[str] = None,
```

在筛选逻辑中添加：

```python
if is_minor is not None:
    query = query.where(Person.is_minor == is_minor)
if is_xj is not None:
    query = query.where(Person.is_xj == is_xj)
if is_mental is not None:
    query = query.where(Person.is_mental == is_mental)
if prison_place:
    query = query.where(Person.prison_place == prison_place)
if village:
    query = query.where(Person.village == village)
```

- [ ] **Step 3: 运行测试确认不破坏现有功能**

```bash
.\.venv\Scripts\python.exe -m pytest tests/ -x -q
```

预期：全部通过

---

### Task 4: 前端 — 人员台账表格改造

**Covers:** 表格列变更

**Files:**
- Modify: `judicial-system/frontend/index_v2.html`

- [ ] **Step 1: "重点"列改为"评级"**

找到第261-263行的"重点"列，替换为：

```html
<el-table-column label="评级" width="70" align="center">
  <template #default="scope"><span v-if="scope && scope.row" :style="{color: scope.row.is_key_target ? '#ff4d4f' : '#999', fontWeight: scope.row.is_key_target ? 'bold' : 'normal'}">{{ scope.row.is_key_target ? '重点' : '一般' }}</span></template>
</el-table-column>
```

- [ ] **Step 2: 在"评级"列后新增3列**

在评级列之后、状态列之前添加：

```html
<el-table-column label="未成年" width="70" align="center">
  <template #default="scope"><el-tag v-if="scope && scope.row && scope.row.is_minor" type="danger" size="small">是</el-tag><span v-else>-</span></template>
</el-table-column>
<el-table-column label="xj" width="60" align="center">
  <template #default="scope"><el-tag v-if="scope && scope.row && scope.row.is_xj" type="warning" size="small">是</el-tag><span v-else>-</span></template>
</el-table-column>
<el-table-column label="精神疾病" width="80" align="center">
  <template #default="scope"><el-tag v-if="scope && scope.row && scope.row.is_mental" type="info" size="small">是</el-tag><span v-else>-</span></template>
</el-table-column>
```

---

### Task 5: 前端 — 编辑/新增表单改造

**Covers:** 表单字段变更

**Files:**
- Modify: `judicial-system/frontend/index_v2.html`

- [ ] **Step 1: 在"重点对象"开关后新增3个开关**

找到第513行 `<el-form-item label="重点对象">` 之后，添加：

```html
<el-form-item label="是否成年"><el-switch v-model="personForm.is_minor"></el-switch></el-form-item>
<el-form-item label="是否xj"><el-switch v-model="personForm.is_xj"></el-switch></el-form-item>
<el-form-item label="精神疾病"><el-switch v-model="personForm.is_mental"></el-switch></el-form-item>
```

- [ ] **Step 2: personForm reactive 新增字段**

在 `is_key_target:false` 之后添加：

```javascript
is_minor:false,is_xj:false,is_mental:false,
```

- [ ] **Step 3: resetForm 新增字段**

在 `is_key_target:false` 之后添加：

```javascript
is_minor:false,is_xj:false,is_mental:false,
```

---

### Task 6: 前端 — 仪表盘改造

**Covers:** 仪表盘统计卡片 + 点击跳转

**Files:**
- Modify: `judicial-system/frontend/index_v2.html`

- [ ] **Step 1: 在"重点帮教对象"卡片后新增3张统计卡片**

找到第134-137行"重点帮教对象"卡片，在其 `</div>` 之后添加：

```html
<div class="stat-card" style="cursor:pointer" @click="currentView='ledger';filterIsMinor=true;filterIsXj='';filterIsMental='';fetchPersons()">
  <div class="num" style="color:#eb2f96">{{ statsData.total_minor || 0 }}</div>
  <div class="label">未成年</div>
</div>
<div class="stat-card" style="cursor:pointer" @click="currentView='ledger';filterIsMinor='';filterIsXj=true;filterIsMental='';fetchPersons()">
  <div class="num" style="color:#fa8c16">{{ statsData.total_xj || 0 }}</div>
  <div class="label">xj</div>
</div>
<div class="stat-card" style="cursor:pointer" @click="currentView='ledger';filterIsMinor='';filterIsXj='';filterIsMental=true;fetchPersons()">
  <div class="num" style="color:#722ed1">{{ statsData.total_mental || 0 }}</div>
  <div class="label">精神疾病</div>
</div>
```

- [ ] **Step 2: fetchStats 解析新字段**

找到 `fetchStats` 函数中的 `Object.assign(statsData,...)` 行，添加：

```javascript
total_minor:data.total_minor||0,total_xj:data.total_xj||0,total_mental:data.total_mental||0,
```

- [ ] **Step 3: statsData reactive 新增字段**

在 `total_key_target:0` 之后添加：

```javascript
total_minor:0,total_xj:0,total_mental:0,
```

- [ ] **Step 4: 监狱分布 — 点击跳转台账**

找到第146-151行的监狱分布 div，修改 `@click` 为：

```html
@click="currentView='ledger';filterStatus='';filterRisk='';filterPrisonPlace=p.name;fetchPersons()"
```

- [ ] **Step 5: 村/居分布 — 点击跳转台账**

找到第180-183行的村/居分布 div，修改为可点击：

```html
<div v-for="v in (statsData.village_distribution||[])" :key="v.name"
     style="padding:6px 12px;background:#f6ffed;border-radius:4px;font-size:13px;cursor:pointer"
     @click="currentView='ledger';filterStatus='';filterRisk='';filterVillage=v.name;fetchPersons()">
  <span style="font-weight:bold;color:#52c41a">{{ v.name }}</span>
  <span style="color:#999;margin-left:4px">{{ v.count }}人</span>
</div>
```

- [ ] **Step 6: 距季度归档截止 — 点击跳转**

找到第237-240行的"距季度归档截止" div，添加点击事件：

```html
<div style="padding:10px 16px;background:#f0f5ff;border-radius:6px;min-width:160px;cursor:pointer" @click="currentView='ledger';filterStatus='在帮';fetchPersons()">
```

---

### Task 7: 前端 — 筛选器新增

**Covers:** 筛选工具栏

**Files:**
- Modify: `judicial-system/frontend/index_v2.html`

- [ ] **Step 1: 新增筛选变量**

在 `filterRisk` 之后添加：

```javascript
const filterIsMinor=ref('');
const filterIsXj=ref('');
const filterIsMental=ref('');
const filterPrisonPlace=ref('');
const filterVillage=ref('');
```

- [ ] **Step 2: fetchPersons 传递新筛选参数**

在 `fetchPersons` 函数中，`if(filterRisk.value)params.set('risk_level',filterRisk.value);` 之后添加：

```javascript
if(filterIsMinor.value)params.set('is_minor','true');
if(filterIsXj.value)params.set('is_xj','true');
if(filterIsMental.value)params.set('is_mental','true');
if(filterPrisonPlace.value)params.set('prison_place',filterPrisonPlace.value);
if(filterVillage.value)params.set('village',filterVillage.value);
```

- [ ] **Step 3: 筛选工具栏新增筛选项**

在 `filterRisk` 筛选器之后、新增人员按钮之前添加：

```html
<el-select v-model="filterIsMinor" placeholder="未成年" clearable style="width:100px" @change="fetchPersons" size="small">
  <el-option label="是" value="true"></el-option>
  <el-option label="否" value="false"></el-option>
</el-select>
<el-select v-model="filterIsXj" placeholder="xj" clearable style="width:80px" @change="fetchPersons" size="small">
  <el-option label="是" value="true"></el-option>
  <el-option label="否" value="false"></el-option>
</el-select>
<el-select v-model="filterIsMental" placeholder="精神疾病" clearable style="width:110px" @change="fetchPersons" size="small">
  <el-option label="是" value="true"></el-option>
  <el-option label="否" value="false"></el-option>
</el-select>
```

- [ ] **Step 4: return 中暴露新变量**

在 return 对象中添加：

```javascript
filterIsMinor,filterIsXj,filterIsMental,filterPrisonPlace,filterVillage,
```

---

### Task 8: 前端 — 清除筛选逻辑

**Covers:** 筛选清除

**Files:**
- Modify: `judicial-system/frontend/index_v2.html`

- [ ] **Step 1: onMenuChange 切换到台账时清除新筛选**

在 `onMenuChange` 函数中，`if(key==='ledger'){fetchPersons();}` 改为：

```javascript
if(key==='ledger'){filterPrisonPlace.value='';filterVillage.value='';fetchPersons();}
```

- [ ] **Step 2: fetchExpiringList 清除新筛选**

在 `fetchExpiringList` 函数中，确保清除：

```javascript
function fetchExpiringList(){filterStatus.value='在帮';filterRisk.value='';filterIsMinor.value='';filterIsXj.value='';filterIsMental.value='';filterPrisonPlace.value='';filterVillage.value='';currentPage.value=1;fetchPersons();}
```

---

### Task 9: 验证 — 运行测试 + 前端检查

**Covers:** 全部

- [ ] **Step 1: 运行后端测试**

```bash
cd judicial-system/backend
.\.venv\Scripts\python.exe -m pytest tests/ -x -q
```

预期：220+ passed

- [ ] **Step 2: 启动服务验证前端**

```bash
cd judicial-system/backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

打开 http://localhost:8000 验证：
1. 人员台账表格显示"评级"列和3个新标签列
2. 编辑表单有3个新开关
3. 仪表盘有3张新统计卡片
4. 点击卡片/监狱/村居可跳转筛选
5. 筛选器可正常工作

- [ ] **Step 3: 覆盖率检查**

```bash
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing tests/
```

预期：覆盖率 ≥ 97%
