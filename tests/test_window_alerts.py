"""窗口均值、滞后解除、冷却抑制与判定代价的测试。"""

import random
import time
import unittest

from alerts.core import Alerts


def reference_observe(state, value, now_ms):
    """参考实现：窗口均值 + 滞后 + 冷却（直白写法，用于差分对照）。

    state 为 dict，返回本次是否新触发。
    """
    state["samples"].append(value)
    if len(state["samples"]) > state["window"]:
        state["samples"].pop(0)
    if len(state["samples"]) < state["window"]:
        return False
    average = sum(state["samples"]) / len(state["samples"])
    if state["firing"]:
        if average < state["low"]:
            state["firing"] = False
        return False
    if average > state["high"]:
        last = state["last_fired_ms"]
        if last is None or now_ms - last >= state["cooldown_ms"]:
            state["firing"] = True
            state["last_fired_ms"] = now_ms
            return True
    return False


def reference_new(window, high, low, cooldown_ms):
    return {
        "window": window,
        "high": high,
        "low": low,
        "cooldown_ms": cooldown_ms,
        "samples": [],
        "firing": False,
        "last_fired_ms": None,
    }


class WindowMeanTest(unittest.TestCase):
    def test_single_spike_does_not_fire(self):
        alerts = Alerts(window=5)
        for value in (90, 50, 50, 50, 50):
            self.assertFalse(alerts.observe(value, 0))
        self.assertFalse(alerts.firing)

    def test_two_spikes_diluted_below_high(self):
        alerts = Alerts(window=5)
        fired = 0
        for value in (90, 90, 50, 50, 50):
            if alerts.observe(value, 0):
                fired += 1
        self.assertEqual(fired, 0)

    def test_sustained_high_mean_fires(self):
        alerts = Alerts(window=5)
        results = [alerts.observe(85, index) for index in range(5)]
        self.assertEqual(results, [False, False, False, False, True])
        self.assertTrue(alerts.firing)

    def test_window_slides(self):
        alerts = Alerts(window=5)
        for value in (85, 85, 85, 85, 85):
            alerts.observe(value, 0)
        self.assertTrue(alerts.firing)
        # 均值 78/74/66 位于 low 与 high 之间：保持告警
        for _ in range(3):
            self.assertFalse(alerts.observe(50, 100000))
            self.assertTrue(alerts.firing)
        # 均值 57 < low：解除
        self.assertFalse(alerts.observe(50, 100000))
        self.assertFalse(alerts.firing)


class HysteresisTest(unittest.TestCase):
    def test_mean_between_low_and_high_keeps_firing(self):
        alerts = Alerts(window=5)
        for value in (85, 85, 85, 85, 85):
            alerts.observe(value, 0)
        self.assertTrue(alerts.firing)
        # 均值 78，位于 low 与 high 之间：保持告警
        self.assertFalse(alerts.observe(70, 100000))
        self.assertTrue(alerts.firing)

    def test_mean_below_low_resolves(self):
        alerts = Alerts(window=5)
        for value in (85, 85, 85, 85, 85):
            alerts.observe(value, 0)
        for value in (50, 50, 50, 50, 50):
            alerts.observe(value, 100000)
        self.assertFalse(alerts.firing)

    def test_observe_returns_false_while_firing(self):
        alerts = Alerts(window=5)
        for value in (85, 85, 85, 85, 85):
            alerts.observe(value, 0)
        self.assertFalse(alerts.observe(85, 20000))
        self.assertFalse(alerts.observe(85, 40000))


class CooldownTest(unittest.TestCase):
    def test_second_fire_within_cooldown_suppressed(self):
        alerts = Alerts(window=2, cooldown_ms=10000)
        self.assertFalse(alerts.observe(85, 0))
        self.assertTrue(alerts.observe(85, 0))  # 窗口收齐，首次触发
        alerts.observe(50, 1)
        alerts.observe(50, 2)  # 均值 50 < low，解除
        self.assertFalse(alerts.firing)
        self.assertFalse(alerts.observe(85, 3))  # 均值 67.5
        self.assertFalse(alerts.observe(85, 4))  # 均值 85，但间隔 4 < 10000
        self.assertFalse(alerts.firing)

    def test_fire_after_cooldown(self):
        alerts = Alerts(window=2, cooldown_ms=10000)
        alerts.observe(85, 0)
        self.assertTrue(alerts.observe(85, 0))
        alerts.observe(50, 1)
        alerts.observe(50, 2)
        self.assertFalse(alerts.observe(85, 20000))  # 均值 67.5
        self.assertTrue(alerts.observe(85, 20000))  # 均值 85，间隔 20000 >= 10000
        self.assertTrue(alerts.firing)

    def test_cooldown_boundary_is_inclusive(self):
        alerts = Alerts(window=2, cooldown_ms=10000)
        alerts.observe(85, 0)
        self.assertTrue(alerts.observe(85, 0))
        alerts.observe(50, 1)
        alerts.observe(50, 2)
        self.assertFalse(alerts.observe(85, 9999))  # 均值 67.5
        self.assertFalse(alerts.observe(85, 9999))  # 均值 85，间隔 9999
        self.assertTrue(alerts.observe(85, 10000))  # 恰好间隔 cooldown_ms


class CostTest(unittest.TestCase):
    def test_scanned_is_constant_per_observe(self):
        alerts = Alerts(window=5)
        for index in range(3000):
            alerts.observe(50, index)
        self.assertLessEqual(alerts.scanned_count(), 6000)

    def test_memory_is_bounded_by_window(self):
        alerts = Alerts(window=5)
        for index in range(10000):
            alerts.observe(50, index)
        self.assertLessEqual(len(alerts.samples), 5)

    def test_observe_is_amortized_constant(self):
        alerts = Alerts(window=5)
        started = time.perf_counter()
        for index in range(100000):
            alerts.observe(50, index)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 5.0)


class DeterminismTest(unittest.TestCase):
    def test_same_sequence_same_result(self):
        sequence = [(random.Random(7).randint(40, 100), index * 1000) for index in range(50)]
        first = [Alerts().observe(v, t) for v, t in sequence]
        second = [Alerts().observe(v, t) for v, t in sequence]
        self.assertEqual(first, second)


class DifferentialTest(unittest.TestCase):
    def test_matches_reference_on_random_sequences(self):
        rng = random.Random(20261001)
        diffs = 0
        for _ in range(200):
            window = rng.randint(1, 8)
            high = rng.uniform(70, 90)
            low = high - rng.uniform(5, 25)
            cooldown_ms = rng.choice([0, 100, 1000, 10000])
            alerts = Alerts(window=window, high=high, low=low, cooldown_ms=cooldown_ms)
            reference = reference_new(window, high, low, cooldown_ms)
            now_ms = rng.randint(0, 5)
            for _ in range(rng.randint(1, 60)):
                value = rng.uniform(30, 110)
                now_ms += rng.randint(0, 2000)
                expected = reference_observe(reference, value, now_ms)
                actual = alerts.observe(value, now_ms)
                if actual != expected or alerts.firing != reference["firing"]:
                    diffs += 1
        self.assertEqual(diffs, 0)


if __name__ == "__main__":
    unittest.main()
