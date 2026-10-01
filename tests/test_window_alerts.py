"""窗口均值、滞后解除、冷却抑制与判定代价的测试。"""

import random
import unittest

from alerts.core import Alerts


class ReferenceAlerts:
    """直白参考实现：窗口均值 + 滞后解除 + 冷却抑制（差分对照用）。

    保留全量样本、每次重切窗口重算均值：正确性优先，不考虑代价。
    """

    def __init__(self, window, high, low, cooldown_ms):
        self.window = window
        self.high = high
        self.low = low
        self.cooldown_ms = cooldown_ms
        self.samples = []
        self.firing = False
        self.last_fired_ms = None

    def observe(self, value, now_ms):
        self.samples.append(value)
        window_samples = self.samples[-self.window:]
        if len(window_samples) < self.window:
            return False
        average = sum(window_samples) / self.window
        if self.firing:
            if average < self.low:
                self.firing = False
            return False
        if average > self.high:
            if (
                self.last_fired_ms is None
                or now_ms - self.last_fired_ms >= self.cooldown_ms
            ):
                self.firing = True
                self.last_fired_ms = now_ms
                return True
        return False


def feed(alerts, values, now_ms=0):
    return [alerts.observe(value, now_ms) for value in values]


class WindowMeanTest(unittest.TestCase):
    def test_incomplete_window_never_fires(self):
        alerts = Alerts(window=5, high=80)
        self.assertEqual(feed(alerts, [100, 100, 100, 100]), [False] * 4)
        self.assertFalse(alerts.firing)

    def test_single_spike_does_not_fire(self):
        alerts = Alerts(window=5, high=80)
        self.assertEqual(feed(alerts, [90, 50, 50, 50, 50]), [False] * 5)
        self.assertFalse(alerts.firing)

    def test_two_spikes_diluted_below_high(self):
        # CLI --sample window 场景：两个 90 尖峰被回落的 50 稀释
        alerts = Alerts()
        self.assertEqual(sum(feed(alerts, [90, 90, 50, 50, 50])), 0)
        self.assertFalse(alerts.firing)

    def test_sustained_high_fires_when_window_fills(self):
        alerts = Alerts(window=5, high=80)
        results = [alerts.observe(85, index) for index in range(5)]
        self.assertEqual(results, [False, False, False, False, True])
        self.assertTrue(alerts.firing)

    def test_mean_equal_to_high_does_not_fire(self):
        alerts = Alerts(window=4, high=80)
        self.assertEqual(feed(alerts, [80, 80, 80, 80]), [False] * 4)
        self.assertFalse(alerts.firing)

    def test_window_slides_and_forgets_old_samples(self):
        alerts = Alerts(window=3, high=80)
        results = feed(alerts, [50, 50, 50, 90, 90, 90])
        self.assertEqual(results, [False] * 5 + [True])


class HysteresisTest(unittest.TestCase):
    def test_mean_between_low_and_high_keeps_firing(self):
        # CLI --sample hysteresis 场景：回落到 70（均值 82）不解除
        alerts = Alerts()
        feed(alerts, [85, 85, 85, 85, 85])
        self.assertTrue(alerts.firing)
        self.assertFalse(alerts.observe(70, 100000))
        self.assertTrue(alerts.firing)

    def test_mean_below_low_resolves(self):
        alerts = Alerts()
        feed(alerts, [85] * 5)
        self.assertTrue(alerts.firing)
        self.assertEqual(feed(alerts, [50] * 5, now_ms=100000), [False] * 5)
        self.assertFalse(alerts.firing)

    def test_mean_exactly_low_keeps_firing(self):
        alerts = Alerts(window=5, high=80, low=60)
        feed(alerts, [85] * 5)
        feed(alerts, [60] * 5, now_ms=100000)
        self.assertTrue(alerts.firing)  # 均值 60 不低于 low，保持告警

    def test_no_retrigger_while_firing(self):
        alerts = Alerts()
        feed(alerts, [85] * 5)
        self.assertTrue(alerts.firing)
        self.assertFalse(alerts.observe(85, 20000))
        self.assertFalse(alerts.observe(85, 100000))
        self.assertTrue(alerts.firing)


class CooldownTest(unittest.TestCase):
    def _fired_alerts(self, cooldown_ms=10000):
        alerts = Alerts(window=2, high=80, low=60, cooldown_ms=cooldown_ms)
        self.assertFalse(alerts.observe(85, 0))   # 窗口未收齐
        self.assertTrue(alerts.observe(85, 0))    # 收齐，首次触发（不受冷却限制）
        return alerts

    def _resolve(self, alerts):
        alerts.observe(50, 1)
        alerts.observe(50, 2)  # 均值 50 < low，解除
        self.assertFalse(alerts.firing)

    def test_second_trigger_within_cooldown_suppressed(self):
        alerts = self._fired_alerts()
        self._resolve(alerts)
        self.assertFalse(alerts.observe(85, 3))    # 均值 67.5，未越界
        self.assertFalse(alerts.observe(85, 4))    # 均值 85 越界，但间隔 4 < 10000
        self.assertFalse(alerts.firing)

    def test_trigger_after_cooldown(self):
        alerts = self._fired_alerts()
        self._resolve(alerts)
        self.assertFalse(alerts.observe(85, 20000))   # 均值 67.5
        self.assertTrue(alerts.observe(85, 20000))    # 均值 85，间隔 20000 >= 10000
        self.assertTrue(alerts.firing)

    def test_cooldown_boundary_is_inclusive(self):
        alerts = self._fired_alerts()
        self._resolve(alerts)
        self.assertFalse(alerts.observe(85, 9999))    # 均值 67.5
        self.assertFalse(alerts.observe(85, 9999))    # 均值 85，间隔 9999 < 10000
        self.assertTrue(alerts.observe(85, 10000))    # 恰好间隔 cooldown_ms

    def test_cooldown_counts_from_last_trigger(self):
        # 告警期间多次越界不更新 last_fired_ms：冷却从真正触发的 t=0 起算
        alerts = Alerts(window=2, high=80, low=60, cooldown_ms=10000)
        self.assertFalse(alerts.observe(85, 0))
        self.assertTrue(alerts.observe(85, 0))
        self.assertFalse(alerts.observe(85, 5000))    # 告警中，不重复触发
        alerts.observe(50, 6000)
        alerts.observe(50, 7000)                      # 均值 50，解除
        self.assertFalse(alerts.observe(85, 8000))    # 均值 67.5
        self.assertFalse(alerts.observe(85, 9000))    # 间隔仍从 t=0 算：9000 < 10000
        self.assertTrue(alerts.observe(85, 10000))


class CostTest(unittest.TestCase):
    def test_scanned_within_cli_contract(self):
        # CLI --sample scan 场景：3000 次上报后 scanned 不超过 6000
        alerts = Alerts()
        for index in range(3000):
            alerts.observe(50, index)
        self.assertLessEqual(alerts.scanned_count(), 6000)

    def test_scanned_is_constant_per_observe(self):
        alerts = Alerts(window=5)
        previous = 0
        for index in range(1000):
            alerts.observe(index % 100, index)
            self.assertLessEqual(alerts.scanned_count() - previous, 2)
            previous = alerts.scanned_count()

    def test_memory_bounded_by_window(self):
        alerts = Alerts(window=5)
        for index in range(10000):
            alerts.observe(50, index)
        self.assertLessEqual(len(alerts.samples), 5)


class DeterminismTest(unittest.TestCase):
    def test_same_sequence_same_results(self):
        rng = random.Random(229)
        now_ms = 0
        sequence = []
        for _ in range(200):
            now_ms += rng.randint(0, 500)
            sequence.append((rng.randint(30, 110), now_ms))
        first = Alerts()
        second = Alerts()
        results_first = [first.observe(value, now) for value, now in sequence]
        results_second = [second.observe(value, now) for value, now in sequence]
        self.assertEqual(results_first, results_second)
        self.assertEqual(first.firing, second.firing)
        self.assertEqual(first.scanned_count(), second.scanned_count())


class DifferentialTest(unittest.TestCase):
    def test_matches_reference_on_200_random_groups(self):
        rng = random.Random(20261001)
        diffs = 0
        for _ in range(200):
            window = rng.randint(1, 8)
            high = rng.randint(60, 90)
            low = high - rng.randint(5, 20)
            cooldown_ms = rng.choice([0, 100, 1000, 10000])
            alerts = Alerts(window=window, high=high, low=low, cooldown_ms=cooldown_ms)
            reference = ReferenceAlerts(window, high, low, cooldown_ms)
            now_ms = rng.randint(0, 5)
            for _ in range(rng.randint(1, 60)):
                value = rng.randint(30, 110)
                now_ms += rng.randint(0, 2000)
                expected = reference.observe(value, now_ms)
                actual = alerts.observe(value, now_ms)
                if actual != expected or alerts.firing != reference.firing:
                    diffs += 1
        self.assertEqual(diffs, 0)


if __name__ == "__main__":
    unittest.main()
