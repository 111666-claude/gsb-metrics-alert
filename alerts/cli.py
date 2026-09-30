"""命令行入口：跑告警样例。"""

import argparse

from .core import Alerts


def build_parser():
    parser = argparse.ArgumentParser(prog="metrics-alert", description="指标告警")
    parser.add_argument("--sample", default="window", help="window / cooldown / hysteresis / scan")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.sample == "window":
        alerts = Alerts()
        fired = 0
        for value in (90, 90, 50, 50, 50):
            if alerts.observe(value, 0):
                fired += 1
        print("fired=%d" % fired)
    elif args.sample == "cooldown":
        alerts = Alerts()
        first = alerts.observe(85, 0)
        second = alerts.observe(85, 1000)
        print("first=%s second=%s" % (str(first).lower(), str(second).lower()))
    elif args.sample == "hysteresis":
        alerts = Alerts()
        for value in (85, 85, 85, 85, 85):
            alerts.observe(value, 0)
        alerts.observe(70, 100000)
        print("firing=%s" % str(alerts.firing).lower())
    elif args.sample == "scan":
        alerts = Alerts()
        for index in range(3000):
            alerts.observe(50, index)
        print("scanned=%d" % alerts.scanned_count())
    else:
        raise SystemExit("需要 --sample window|cooldown|hysteresis|scan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
