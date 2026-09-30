"""指标告警：滑动窗口均值、阈值滞后、告警冷却抑制。"""

from collections import deque

WINDOW = 5
HIGH = 80.0
LOW = 60.0
COOLDOWN_MS = 10000


class Alerts:
    """告警判定器：窗口均值 + 滞后解除 + 冷却抑制。

    只保留最近 window 个样本（deque）并维护其和：单次 observe 摊还
    O(1)，内存 O(window)，scanned_count 每次调用只增加常数（新样本 +1，
    淘汰旧样本再 +1），不随样本总数线性增长。
    """

    def __init__(self, window=WINDOW, high=HIGH, low=LOW, cooldown_ms=COOLDOWN_MS):
        self.window = window
        self.high = high
        self.low = low
        self.cooldown_ms = cooldown_ms
        self.samples = deque()
        self._sum = 0.0
        self.firing = False
        self.last_fired_ms = None
        self.scanned = 0

    def observe(self, value, now_ms):
        """上报一个样本，返回本次是否**新触发**告警。

        - 最近 window 个样本未收齐前只积累不判定，单个尖峰不会触发；
        - 收齐后均值超过 high 才触发（两次触发间隔至少 cooldown_ms）；
        - 告警状态下只有均值低于 low 才解除，low 与 high 之间保持原状态。
        """
        self.samples.append(value)
        self._sum += value
        self.scanned += 1
        if len(self.samples) > self.window:
            self._sum -= self.samples.popleft()
            self.scanned += 1

        if len(self.samples) < self.window:
            return False

        average = self._sum / len(self.samples)

        if self.firing:
            if average < self.low:
                self.firing = False
            return False

        if average > self.high:
            if self.last_fired_ms is None or now_ms - self.last_fired_ms >= self.cooldown_ms:
                self.firing = True
                self.last_fired_ms = now_ms
                return True
        return False

    def scanned_count(self):
        return self.scanned
