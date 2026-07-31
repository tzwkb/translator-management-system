# 业务口径与 Projectlist 首版字段映射

> 状态：已确认  
> 日期：2026-07-24  
> 数据依据：[日报_琅科2026.xlsx](../../2026-06-30/参考资料/日报_琅科2026.xlsx)

## 一、锁定的最小业务口径

### 译员基础字段

- `gender` 使用 `male/female/undisclosed`；历史未知值保持 `NULL`，不推断。
- `entity_type` 使用 `individual/vendor`；历史未知值保持 `NULL`，不默认归为个人。

### 项目经历

- 当前和过往项目共用 `translator_project_experiences`。
- `project_status` 使用 `current/past`。
- `cooperation_source` 使用 `our_company/external`。
- 外部公司名首版可空；项目名必填。
- 本次只建表，不从旧 `current_project/role` 自动生成数据。

### 一口价与“其他”价格

后续 `special_rates` 的最小字段固定为：

| 字段 | 规则 |
|---|---|
| `translator_id` | 必填 |
| `project_experience_id` | 可空 |
| `project_name` | 必填，保存项目名快照 |
| `source_lang/target_lang` | 可空；填写时必须成对 |
| `rate_type` | `fixed/custom` |
| `task_type` | 标准任务类型；一口价必须填写 |
| `custom_task_name` | `custom` 时必填 |
| `amount` | 非负 |
| `unit` | `project/task/hour/word/other` |
| `currency` | 必填 |
| `remarks` | 可空 |

一口价必须关联译员、项目和任务；“其他”不能只保存一个无名称的通用价格。

### 累计结算

- `settlement_policy` 使用 `monthly/cumulative`。
- PO 的 `settlement_month` 始终表示工作发生月，不因累计付款改写。
- 跨月付款使用 `payment_batches` 关联多个 PO；一个批次只包含一个译员和一个币种。

### 支付方式

- 支付方式码固定为 `wechat/alipay/personal_bank/corporate_cny/corporate_usd`。
- 一名译员可有多个支付账户，并按币种设置默认账户。
- 账户详情使用加密 JSON；账号、证件号等默认脱敏。

## 二、源表识别

| 项目 | 首版规则 |
|---|---|
| 工作表 | 精确匹配 `【项目组】Projectlist (V1.0)` |
| 表头 | 第 3 行；同时校验 `项目名称（稿件/LQA批次）`、`指定译员`、`工作类型`、`译员PO时间（X月）` |
| 数据起始行 | 第 4 行 |
| 项目行 | `指定译员`、`工作类型`、`翻译费率`、`译员PO时间（X月）` 全空时跳过 |
| 不完整 PO 行 | 上述字段部分有值但缺必填项时进入错误预览，不静默跳过 |

## 三、Projectlist 到 PO 的首版映射

| PO 字段 | Projectlist 来源 | 转换与校验 |
|---|---|---|
| `translator_id` | `指定译员` | 姓名去首尾空白后精确匹配未删除译员；零匹配或多匹配均报错，不使用包含匹配 |
| `settlement_month` | `译员PO时间（X月）` | 月份取源单元格；年份由导入时必填的 `settlement_year` 提供，禁止取系统当前年份；与 `DDL` 年份不一致时提示复核 |
| `project` | `归属项目`、`项目名称（稿件/LQA批次）` | 优先取非空的 `归属项目`，否则取项目名称 |
| `source_lang` | `原语言` | 经语言别名表转为规范码；无法映射时报错 |
| `target_lang` | `目标语言` | 经语言别名表转为规范码；无法映射时报错 |
| `role` | `工作类型` | 映射到 `翻译/审校/MTPE/LQA/LQE/其他`；未知值进入错误预览 |
| `word_count` | `译员WWC字数` | 仅用于按字数计价任务；必须为非负数 |
| `rate` | `翻译费率` | 按字报价乘以 1000 后写入系统的“每千字费率”；不得原值直写 |
| `currency` | `币种` | 转为大写币种码；不支持的币种报错 |
| `status` | `结算PO`、`已打款` | 已打款为真时取 `已支付`；否则结算 PO 为真时取 `已开票待付`；其余取 `未开票` |
| `po_number` | 无直接来源 | 首版保持空；重复控制使用后续导入文件哈希，不伪造 PO 号 |
| `remarks` | `关联日报内容` | 追加源工作表名和源行号，便于追溯 |

## 四、金额与特殊任务规则

- 按字任务：`amount = 译员WWC字数 ÷ 1000 × (翻译费率 × 1000)`。
- `稿费金额（CNY）`只用于预览核对，不直接覆盖系统计算金额；源币种不是 CNY 时不能直接比较。
- 小时任务使用 `REPNEW & 小时数`作为数量、`翻译费率`作为每小时价格；当前 PO 模型尚无单位字段，因此只能进入预览并要求人工确认，不能按千字公式自动入账。
- `项目实际总价`、客户报价、毛利和回款字段属于客户侧核算，不写入译员 PO。
- 金额为零的候选行保留在预览中并标记警告，不自动丢弃。

## 五、仍需业务确认

- `审校/MTPE/LQE` 在 Projectlist 中分别采用按字、按小时还是手工金额。
- 跨年时 `settlement_year` 的批次选择规则。
- Projectlist 的勾选字段在导出文件中的实际真值形式。
- 源币种非 CNY 时，是否提供可审计汇率用于核对 `稿费金额（CNY）`。

上述四项在导入功能开发前必须确认；未确认行进入错误预览，不以程序猜测代替。
