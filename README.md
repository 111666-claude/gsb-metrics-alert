# metrics-alert

指标告警：滑动窗口均值、阈值滞后、告警冷却抑制，只用 Python 标准库。

```
python3 -m alerts.cli --sample window
python3 -m alerts.cli --sample cooldown
python3 -m alerts.cli --sample hysteresis
python3 -m unittest discover -s tests -v
```

## 口径（README 为准）

- **判定用窗口均值**：最近 `window` 个样本的均值（不足 window 时用已有的）超过 `high` 才告警，
  单个尖峰不算。
- **滞后解除**：告警状态下，只有窗口均值低于 `low` 才解除；均值在 low 与 high 之间时保持原状态。
- **冷却抑制**：两次告警的触发间隔至少 `cooldown_ms`，冷却期内的越界不重复触发。
- **返回值语义**：`observe` 返回 `True` 只表示本次**新触发**告警。
- **内存与代价**：只保留窗口内样本；`scanned_count` 不随样本总数线性增长。
- **规模**：单集群 2000 条指标、每秒 10 万次上报，单次摊还 O(1)，内存 O(window)。

## 输出契约（不改格式）

```
fired=0
first=true second=false
firing=true
scanned<=6000
```

## 目录

```
alerts/core.py   窗口均值、滞后与冷却
alerts/cli.py    命令行入口
tests/           unittest 用例
```
