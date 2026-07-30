# 安置帮教智能台账系统 — 等保三级安全加固螺旋计划

> 基于四份摸底报告（鉴权现状、隐私泄露、前端依赖、等保安全差距）
> 制定日期：2026-07-30
> 目标标准：等保三级（医疗/政务）

---

## 〇、摸底结论摘要

### 生产阻断级（P0）

| # | 问题 | 现状 |
|---|------|------|
| 1 | 35个业务路由零鉴权 | persons(13)/visits(7)/reminders(1)/files(4)/persons_stats(10) 全部无 Depends(get_current_user)，仅 auth.py 7个路由有鉴权 |
| 2 | 身份证号隐私泄露 | PersonResponse 同时返回 id_card(完整) + id_card_masked(脱敏)，to_response() 注释写"避免完整号落到前端"但实际未移除 |

### 等保三级必过项（P1）

| # | 问题 | 现状 |
|---|------|------|
| 3 | 无独立审计日志系统 | 安全事件无独立审计记录，EditLog 只记业务数据变更 |
| 4 | 无登录失败锁定 | 无失败计数、无账号锁定、无暴力破解防护 |
| 5 | 密码复杂度不达标 | 仅要求6位，无字符类型要求（等保要求三类以上+8位） |
| 6 | 敏感个人信息明文存储 | 身份证号、手机号在 SQLite 中未加密 |
| 7 | 无通信加密(HTTPS) | 全链路 HTTP 明文传输 |

### 等保三级建议项（P2）

| # | 问题 | 现状 |
|---|------|------|
| 8 | 无请求访问日志中间件 | 仅异常日志，无正常请求的访问日志 |
| 9 | 日志文件无完整性保护 | 无数字签名/哈希校验，等保要求审计记录受保护 |
| 10 | 无服务端会话控制 | JWT 无状态，无法主动踢出/撤销已登录用户 |
| 11 | 无空闲超时自动退出 | ACCESS_TOKEN 120分钟，无空闲检测 |
| 12 | CORS 配置过宽 | allow_methods/allow_headers 全部放通 |
| 13 | 无安全 HTTP 响应头 | 缺少 X-Frame-Options、CSP、HSTS 等 |
| 14 | 无请求限流 | 无暴力破解防护的网络层措施 |
| 15 | Editor 字段可伪造 | 来自请求参数 `data.editor` 而非服务端取 JWT 用户 |
| 16 | 无密码定期更换 | 无 password_changed_at 字段，无有效期机制 |
| 17 | 导出 Excel 不带 token | `handleExportExcel` 直接 fetch() 不经 api() 封装 |

### 已有合规项（不需要改）

- bcrypt 密码哈希（算法合规）
- JWT + SECRET_KEY 强度校验（启动时拒绝弱密钥）
- 首次登录强制改密机制（force_change_password）
- 数据变更留痕（EditLog 表）
- 日志按天轮转保留 30 天
- log_call 装饰器全量记录函数调用轨迹

---

## 一、前置约束（贯穿全计划）

### 后端必须完整号的场景（不能脱敏替代）

- 创建/导入：校验位、查重、推算性别生日、软删墓碑释放
- 编辑 id_card 字段本身：同上
- 编辑留痕：id_card 被修改时 EditLog 记录完整新旧值
- 数据库存储

### 前端约束（不能动的）

| 依赖点 | 位置 | 说明 |
|---|---|---|
| 编辑回填 | `editPerson()` 调 `personApi.detail(id)` 取 `full.id_card` | detail 接口必须返回完整号 |
| 创建提交 | `submitPerson()` 发 `personForm.id_card` | 创建/编辑提交必须发完整号 |
| 小眼睛切换 | 前端本地 `revealListAll`/`revealedRows`/`drawerReveal` | 纯前端切换，不调后端 |
| 导出 Excel | `handleExportExcel` 直接 fetch() | 不带 Authorization 头 |

### 鉴权基础设施（已完备，可复用）

- `app/api/deps.py`：`get_current_user` + `require_role(*roles)` 依赖注入函数
- `app/core/security.py`：JWT 签发/验证/刷新（HS256 + bcrypt）
- 前端 `api()` 函数自动带 `Authorization: Bearer` 头
- 前端已有 401 自动刷新 token + 跳转登录逻辑

---

## 二、螺旋第 5.1 圈：P0 生产阻断级修复

### 目标
消除零鉴权路由和身份证号隐私泄露两个生产阻断级问题。

### 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 鉴权遗漏某个路由 | 低 | 高 | 逐文件排查，pytest 验证每个端点 |
| PersonListResponse 改名导致前端报错 | 中 | 中 | 前后端同步改动，grep 确认无遗漏引用 |
| editor 改为服务端取值后旧数据 editor 变化 | 低 | 低 | 仅影响新操作，历史数据不变 |

### 改动 1：逐路由添加鉴权依赖

**方案选择**：逐路由 `Depends(get_current_user)`，不用全局中间件。

理由：
- FastAPI 社区最佳实践推荐显式依赖
- 部分路由需角色检查（require_role），全局中间件无法区分
- 健康检查/登录/刷新/模板下载需保持公开
- 全局中间件白名单维护风险更高

| 文件 | 改动内容 |
|------|----------|
| `app/api/persons.py` | 全部 13 个路由函数签名加 `current_user: User = Depends(get_current_user)` |
| `app/api/visits.py` | 全部 7 个路由加 `Depends(get_current_user)` |
| `app/api/reminders.py` | 1 个路由加 `Depends(get_current_user)` |
| `app/api/files.py` | 4 个路由加 `Depends(get_current_user)` |
| `app/api/persons_stats.py` | 9 个路由加 `Depends(get_current_user)`（`download_import_template` 保持公开） |

保持公开的路由：`/health`、`/`、`/api/auth/login`、`/api/auth/refresh`、`/api/persons/import/template`

### 改动 2：PersonResponse 脱敏改造

引入 `PersonListResponse`（列表用，不含完整 id_card）+ 保留 `PersonResponse`（详情用，含完整 id_card）。

| 文件 | 改动内容 |
|------|----------|
| `app/schemas/person.py` | 新增 `PersonListResponse`（id_card 字段仅含脱敏版，其他字段同 PersonResponse） |
| `app/services/person_service.py` | 新增 `to_list_response(person)` 函数；`list_persons()` 返回 `Page[PersonListResponse]`；保留 `to_response()` 给 detail 用 |
| `app/api/persons.py` | `list_persons` 返回类型改为 `Page[PersonListResponse]`；`get_person` 保持 `PersonResponse` |
| 前端 `index_v2.html` | 列表身份证列绑定从 `row.id_card` 改为 `row.id_card_masked`；小眼睛逻辑适配（列表已无完整号）；`editPerson` 已调 detail 取完整号，无需改 |

### 改动 3：editor 字段从 JWT 取值

| 文件 | 改动内容 |
|------|----------|
| `app/api/persons.py` | create/batch 操作的 editor 从 `current_user.real_name` 取，忽略 `body.editor` |
| `app/api/visits.py` | 同上 |
| `app/services/person_service.py` | `_write_edit_log` 和 `_batch_apply` 的 editor 参数改为必传 |
| `app/services/visit_service.py` | 同上 |

### 改动 4：导出 Excel 带 token

| 文件 | 改动内容 |
|------|----------|
| 前端 `index_v2.html` | `handleExportExcel` 的 fetch 调用加 `Authorization: Bearer ${authToken.value}` 头 |

### 验证门禁

1. 不带 token 访问 `/api/persons`、`/api/visits`、`/api/reminders`、`/api/persons/stats-summary`、`/api/persons/export` → 均返回 401
2. 带有效 token 访问上述接口 → 正常返回数据
3. `/health`、`/api/auth/login`、`/api/auth/refresh`、`/api/persons/import/template` 无需 token
4. 列表接口返回 `id_card_masked`（脱敏格式），不含完整 id_card
5. detail 接口（`GET /api/persons/{id}`）返回完整 `id_card`
6. EditLog 中 editor 为当前登录用户真实姓名
7. 前端列表页显示脱敏号，编辑时回填完整号
8. 导出 Excel 请求带 Authorization 头
9. pytest 全量通过

---

## 三、螺旋第 5.2 圈：P1 审计日志 + 登录锁定 + 密码复杂度

### 目标
建立独立审计日志系统、实现登录失败锁定、密码复杂度达到等保三级标准。

### 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 审计日志写入影响性能 | 低 | 低 | 异步写入或批量写入，SQLite WAL 模式 |
| 登录锁定误锁合法用户 | 低 | 中 | 锁定时间30分钟，管理员可重置 |
| 密码复杂度导致用户抱怨 | 中 | 低 | 提供密码规则提示，首次强制改密 |

### 改动 1：审计日志表 + 服务

| 文件 | 改动内容 |
|------|----------|
| `app/models/audit_log.py` | **新建** AuditLog 表：id(PK), event_type(str,索引), username(str,索引), real_name(Optional), ip_address(Optional), user_agent(Optional), detail(Optional,max2000), result(str: success/failure), created_at(datetime,索引) |
| `app/services/audit_service.py` | **新建** `log_event(session, event_type, username, real_name, ip, user_agent, detail, result)` + `query_events(session, ...)` 分页查询 |
| `app/api/audit.py` | **新建** `/api/audit/logs` 管理员审计日志查询（仅 director 角色） |
| `app/models/__init__.py` | 导出 AuditLog |

事件类型枚举：`LOGIN_SUCCESS` / `LOGIN_FAILURE` / `LOGIN_LOCKED` / `LOGOUT` / `PASSWORD_CHANGE` / `PASSWORD_RESET` / `USER_CREATE` / `USER_UPDATE` / `USER_DELETE` / `USER_ENABLE_DISABLE` / `DATA_EXPORT` / `DATA_IMPORT` / `DATA_DELETE` / `DATA_BATCH_DELETE` / `ROLE_CHANGE` / `FORCE_LOGOUT`

### 改动 2：登录失败锁定

| 文件 | 改动内容 |
|------|----------|
| `app/models/user.py` | 新增字段：`failed_login_attempts`(int,default=0), `locked_until`(Optional[datetime]), `last_failed_at`(Optional[datetime]) |
| `app/core/config.py` | 新增：`LOGIN_MAX_ATTEMPTS=5`, `LOGIN_LOCKOUT_MINUTES=30` |
| `app/api/auth.py` | login 函数改造：①检查 locked_until 是否在当前时间之后 → 是则返回"账号已锁定"；②密码失败递增 failed_login_attempts + 更新 last_failed_at，达阈值设 locked_until；③密码成功重置 failed_login_attempts=0 + locked_until=None；④每次登录尝试调用 audit_service.log_event |
| `app/api/auth.py` | change_password / admin_reset_password / create_user / update_user / delete_user 成功后记审计日志 |

### 改动 3：密码复杂度校验

| 文件 | 改动内容 |
|------|----------|
| `app/schemas/__init__.py` | ChangePasswordRequest.new_password、CreateUserRequest.password、AdminResetPasswordRequest.new_password 加 `field_validator`：≥8位，含大写/小写/数字/特殊字符中至少三类 |
| `app/core/config.py` | 新增 `PASSWORD_MIN_LENGTH=8`, `PASSWORD_MIN_CLASSES=3` |

密码复杂度规则：
```
至少包含以下四类中的三类：
1. 大写字母 A-Z
2. 小写字母 a-z
3. 数字 0-9
4. 特殊字符 !@#$%^&*()_+-=[]{}|;':",./<>?
```

### 改动 4：登录 IP 记录

| 文件 | 改动内容 |
|------|----------|
| `app/api/auth.py` | login 函数签名加 `request: Request`，从 `request.client.host` 获取 IP 传给审计服务 |

### 验证门禁

1. 数据库出现 `audit_logs` 表
2. 登录成功/失败均在 audit_logs 中产生记录（含 event_type、username、ip_address、result）
3. 连续 5 次错误密码 → 第 6 次返回"账号已锁定，请 30 分钟后重试"
4. 锁定期间正确密码也无法登录
5. 锁定到期后可正常登录
6. 创建/编辑/删除用户均记录审计日志
7. 密码 < 8 位 → 拒绝
8. 密码仅含数字（如 12345678）→ 拒绝（只有一类）
9. 密码含大写+小写+数字（如 Abc12345）→ 通过
10. pytest 全量通过

---

## 四、螺旋第 5.3 圈：P1 敏感数据加密 + HTTPS 指导

### 目标
身份证号、手机号的应用层 AES 加密存储；提供 HTTPS 部署指导。

### 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 加密迁移导致数据丢失 | 低 | 高 | 迁移前强制备份，事务内执行，失败回滚 |
| 密文查重性能差 | 中 | 中 | 用 SHA-256 哈希字段做精确匹配，避免密文比较 |
| 前端解密失败显示乱码 | 低 | 中 | decrypt_field 异常时返回 mask_id_card 兜底 |

### 改动 1：应用层 Fernet 加密

| 文件 | 改动内容 |
|------|----------|
| `app/core/encryption.py` | **新建**：`_derive_key(secret_key)` 从 SECRET_KEY 派生 Fernet 密钥；`encrypt_field(plaintext)` 加密返回 `gAAAAA...` 格式；`decrypt_field(ciphertext)` 解密；`mask_phone(phone)` 手机号脱敏（前3+****+后4） |
| `app/models/person.py` | 新增 `id_card_hash`(str, unique, index) 存 SHA-256 哈希值，用于查重 |
| `app/services/person_service.py` | create_person：入库前 `encrypt_field(id_card)` + `encrypt_field(phone)` + 计算 `sha256(id_card)` 存 id_card_hash；update_person：若 id_card/phone 修改则重新加密+更新 hash；list_persons/to_response/to_list_response：读出后 `decrypt_field()` 解密再序列化；`_raise_if_id_card_exists`：用 id_card_hash 精确匹配 |
| `app/services/import_service.py` | 导入时加密后存储，id_card_hash 写入 |
| `app/services/stats_service.py` | 涉及 id_card 的查询改用 id_card_hash 匹配 |
| `app/core/database.py` | 迁移脚本：新增 id_card_hash 列 + 现有数据加密迁移（读明文→加密→写密文→算hash） |

id_card_hash 查重方案：
- 创建/编辑时：`sha256(id_card)` → id_card_hash，UNIQUE 约束 + 精确匹配
- 搜索时：`sha256(search_term)` → 匹配 id_card_hash（身份证号搜索）
- 手机号搜索：同理可加 phone_hash，或保持明文

### 改动 2：HTTPS 部署指导

不改代码，在 README.md 添加 HTTPS 部署章节：
- 方案一：Nginx 反向代理 + Let's Encrypt
- 方案二：Caddy 自动 HTTPS
- 方案三：内网自签名证书
- 强调：生产环境必须启用 HTTPS

### 验证门禁

1. 新增人员后查 SQLite：id_card 为 Fernet 密文（`gAAAAA...`），phone 为密文
2. id_card_hash 为 64 位十六进制 SHA-256 值
3. 列表返回脱敏号，detail 返回解密明文
4. 同一身份证号无法重复添加（id_card_hash UNIQUE 约束）
5. 编辑身份证号后密文和 hash 均更新
6. 导入 Excel 后数据库中 id_card 为密文
7. README.md 包含 HTTPS 部署指导
8. pytest 全量通过

---

## 五、螺旋第 5.4 圈：P2 安全头 + 限流 + 访问日志 + CORS

### 目标
安全 HTTP 响应头、请求限流、访问日志中间件、CORS 收紧。

### 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 限流误拦正常用户 | 低 | 中 | 阈值设宽松（120次/分），仅登录接口严格（10次/分） |
| 安全头影响前端功能 | 低 | 中 | CSP 用 default-src 'self'，不阻断内联脚本（dev 环境可放宽） |
| 访问日志体积过大 | 中 | 低 | 按天轮转，保留 90 天 |

### 改动 1：安全 HTTP 响应头

| 文件 | 改动内容 |
|------|----------|
| `app/core/security_headers.py` | **新建** FastAPI 中间件，添加：`X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY`、`X-XSS-Protection: 1; mode=block`、`Strict-Transport-Security: max-age=31536000; includeSubDomains`（HTTPS 时）、`Content-Security-Policy: default-src 'self'`、`Referrer-Policy: strict-origin-when-cross-origin`、`Cache-Control: no-store` |
| `app/main.py` | 注册安全头中间件 |

### 改动 2：请求限流中间件

| 文件 | 改动内容 |
|------|----------|
| `app/core/rate_limit.py` | **新建** 基于内存的滑动窗口限流：登录接口 10次/分/IP，普通 API 120次/分/用户，导入导出 5次/分/用户。返回 429 |
| `app/core/config.py` | 新增 `RATE_LIMIT_LOGIN_PER_MINUTE=10`, `RATE_LIMIT_API_PER_MINUTE=120`, `RATE_LIMIT_EXPORT_PER_MINUTE=5` |
| `app/main.py` | 注册限流中间件 |

### 改动 3：请求访问日志中间件

| 文件 | 改动内容 |
|------|----------|
| `app/core/access_log.py` | **新建** HTTP 请求日志中间件：时间、方法、路径、状态码、耗时(ms)、客户端 IP、用户标识（JWT 解析，未登录为 `-`）→ `logs/access.log`（按天轮转，90 天） |
| `app/core/logging_config.py` | 新增 `setup_access_logging()` 函数 |
| `app/main.py` | 注册访问日志中间件 |

### 改动 4：CORS 收紧

| 文件 | 改动内容 |
|------|----------|
| `app/main.py` | `allow_methods` 从 `["*"]` 改为 `["GET", "POST", "PATCH", "DELETE", "OPTIONS"]`；`allow_headers` 从 `["*"]` 改为 `["Authorization", "Content-Type"]` |

### 改动 5：日志完整性保护

| 文件 | 改动内容 |
|------|----------|
| `app/core/logging_config.py` | 日志格式末尾附加 `|[sha256:xxx]` 哈希值；提供 `verify_log_integrity(log_file)` 工具函数 |

### 验证门禁

1. 响应头包含 `X-Content-Type-Options: nosniff`、`X-Frame-Options: DENY` 等
2. 短时间大量请求登录接口 → 返回 429
3. `logs/access.log` 存在，记录所有 HTTP 请求
4. CORS 预检只允许 GET/POST/PATCH/DELETE/OPTIONS
5. 日志每行包含哈希校验值
6. pytest 全量通过

---

## 六、螺旋第 5.5 圈：P2 会话控制 + 空闲超时 + 密码更换

### 目标
服务端会话控制（主动踢出）、空闲超时、密码定期更换。

### 风险分析

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| token_version 频繁变更导致大量用户登出 | 低 | 中 | 仅在密码变更/强制登出时递增，常规操作不影响 |
| ACCESS_TOKEN 缩短到30分钟影响体验 | 低 | 低 | 前端已有 refresh token 自动续期，用户无感知 |
| 密码过期导致用户无法登录 | 中 | 中 | 提前7天提醒，首次登录强制改密已有机制 |

### 改动 1：服务端会话控制（主动踢出用户）

| 文件 | 改动内容 |
|------|----------|
| `app/models/user.py` | 新增 `token_version`(int, default=0) |
| `app/core/security.py` | `create_access_token` payload 加 `token_version`；`decode_token` 解析出 `token_version` |
| `app/api/deps.py` | `get_current_user` 比对 JWT token_version 与数据库值，不一致则拒绝 |
| `app/api/auth.py` | change_password / admin_reset_password 成功后递增 token_version；新增 `POST /api/auth/force-logout/{user_id}`（仅 director），递增目标用户 token_version |

### 改动 2：空闲超时自动退出

| 文件 | 改动内容 |
|------|----------|
| `app/core/config.py` | `ACCESS_TOKEN_EXPIRE_MINUTES` 从 120 改为 30 |

方案说明：缩短 access_token 有效期为 30 分钟，配合前端 refresh_token 自动续期机制，用户无感知但符合等保要求。不改后端代码，只改配置。

### 改动 3：密码定期更换

| 文件 | 改动内容 |
|------|----------|
| `app/models/user.py` | 新增 `password_changed_at`(Optional[datetime]) |
| `app/core/config.py` | 新增 `PASSWORD_EXPIRE_DAYS=90` |
| `app/api/auth.py` | change_password 成功后更新 `password_changed_at=now` |
| `app/api/deps.py` | `get_current_user` 检查 password_changed_at 是否超期，超期在返回对象上标记 |
| `app/schemas/__init__.py` | UserResponse 新增 `is_locked`(bool), `password_expired`(bool) |
| `app/api/auth.py` | get_me 计算 is_locked 和 password_expired 返回 |
| 前端 `index_v2.html` | 登录后检查 password_expired 标记，有则弹修改密码对话框 |

### 验证门禁

1. 管理员调用 `force-logout/{user_id}` → 该用户后续请求 401
2. 用户修改密码后旧 token 立即失效
3. access token 30 分钟后过期，前端 refresh 无感续期
4. 密码超 90 天 → 登录时提示修改
5. UserResponse 包含 is_locked 和 password_expired 标记
6. pytest 全量通过

---

## 七、依赖关系与实施顺序

```
5.1 (P0 鉴权+隐私) ──→ 5.2 (P1 审计/锁定/密码) ──→ 5.3 (P1 加密) ──→ 5.4 (P2 安全头/限流) ──→ 5.5 (P2 会话/超时)
```

- 5.1 必须首先完成（生产阻断级）
- 5.2 和 5.3 无代码冲突可并行，但建议顺序执行便于测试
- 5.4 和 5.5 可并行
- 5.3 加密改动影响面最大（service 层、import、stats），需充分回归

## 八、新增依赖

- `cryptography`（Fernet 加密）：确认 `python-jose[cryptography]` 是否已引入，若不可用需添加到 requirements.txt

## 九、关键文件清单

### 后端

| 文件 | 改动圈数 |
|------|----------|
| `app/api/persons.py` | 5.1 |
| `app/api/visits.py` | 5.1 |
| `app/api/reminders.py` | 5.1 |
| `app/api/files.py` | 5.1 |
| `app/api/persons_stats.py` | 5.1 |
| `app/schemas/person.py` | 5.1 |
| `app/services/person_service.py` | 5.1, 5.3 |
| `app/services/visit_service.py` | 5.1 |
| `app/api/auth.py` | 5.2, 5.5 |
| `app/api/deps.py` | 5.5 |
| `app/models/user.py` | 5.2, 5.5 |
| `app/models/person.py` | 5.3 |
| `app/core/config.py` | 5.2, 5.3, 5.4, 5.5 |
| `app/core/security.py` | 5.5 |
| `app/core/database.py` | 5.3 |
| `app/main.py` | 5.4 |
| `app/models/audit_log.py` | 5.2（新建） |
| `app/services/audit_service.py` | 5.2（新建） |
| `app/api/audit.py` | 5.2（新建） |
| `app/core/encryption.py` | 5.3（新建） |
| `app/core/security_headers.py` | 5.4（新建） |
| `app/core/rate_limit.py` | 5.4（新建） |
| `app/core/access_log.py` | 5.4（新建） |

### 前端

| 文件 | 改动圈数 |
|------|----------|
| `frontend/index_v2.html` | 5.1（列表脱敏绑定+导出带token）, 5.5（密码过期提示） |
