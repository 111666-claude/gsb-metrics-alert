"""指标告警：滑动窗口均值、阈值滞后、告警冷却抑制。

缺陷：只看当次样本（不看窗口均值）、没有滞后判定、没有冷却期、每次判定全扫历史样本。
"""

WINDOW = 5
HIGH = 80.0
LOW = 60.0
COOLDOWN_MS = 10000


class Alerts:
    """告警判定器。"""

    def __init__(self, window=WINDOW, high=HIGH, low=LOW, cooldown_ms=COOLDOWN_MS):
        self.window = window
        self.high = high
        self.low = low
        self.cooldown_ms = cooldown_ms
        self.samples = []
        self.firing = False
        self.last_fired_ms = -cooldown_ms
        self.scanned = 0

    def observe(self, value, now_ms):
        """上报一个样本，返回本次是否新触发告警。

        缺陷：只看当次样本是否超上限（不看窗口均值）、没有滞后解除、没有冷却期。
        """
        self.scanned += len(self.samples)
        self.samples.append(value)
        if value > self.high:
            self.firing = True
            self.last_fired_ms = now_ms
            return True
        self.firing = False
        return False

    def scanned_count(self):
        return self.scanned
