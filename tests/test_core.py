import unittest

from alerts.core import Alerts


class ObserveTest(unittest.TestCase):
    def test_low_value_is_silent(self):
        self.assertFalse(Alerts().observe(50, 0))

    def test_samples_are_kept(self):
        alerts = Alerts(window=5)
        alerts.observe(50, 0)
        self.assertEqual(len(alerts.samples), 1)


class StateTest(unittest.TestCase):
    def test_not_firing_initially(self):
        self.assertFalse(Alerts().firing)

    def test_scanned_starts_at_zero(self):
        self.assertEqual(Alerts().scanned_count(), 0)


if __name__ == "__main__":
    unittest.main()
