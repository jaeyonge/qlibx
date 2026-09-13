"""Build and time a position-heavy record shaped like one FF3 portfolio leg."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from vqapr.record import (
    RUN_KIND,
    STRATEGY_KIND,
    RunRecordWriter,
    record_fields,
    write_run_record,
)
from vqapr.public import strategy_report

HERE = Path(__file__).resolve().parent
STORE = HERE / "outputs" / "report-store"
RUN = "ff3-shaped"
REF = "leg@00000001"
SESSIONS = 800
POSITIONS = 300
SEOUL = timezone(timedelta(hours=9))


def _run_record() -> dict[str, object]:
    record: dict[str, object] = dict.fromkeys(record_fields(RUN_KIND))
    record.update(
        {
            "run_id": RUN,
            "writes": "none",
            "declared_digest": "d",
            "instruments": [f"A{i:06d}" for i in range(POSITIONS)],
            "period": {
                "start": datetime(2018, 1, 1, tzinfo=SEOUL).isoformat(),
                "end": datetime(2021, 3, 11, tzinfo=SEOUL).isoformat(),
            },
            "initial_account": {"cash": "1000000000", "positions": {}, "version": 0},
            "datasets": [],
            "strategies": [{"component_id": "leg", "record": REF}],
            "datamodels": [],
        }
    )
    return record


def _strategy_record() -> dict[str, object]:
    record: dict[str, object] = dict.fromkeys(record_fields(STRATEGY_KIND))
    record.update(
        {
            "run_id": RUN,
            "strategy_ref": REF,
            "strategy_id": "leg",
            "fingerprint": "0" * 64,
            "component": {"component_id": "leg"},
            "schedule": {},
            "compliance": [],
            "exchange": None,
            "account": {},
            "tables": {},
            "contract": {},
            "source_digest": {},
            "declared_digest": "d",
            "roster": None,
            "period": _run_record()["period"],
            "timing": {},
        }
    )
    return record


def prepare() -> None:
    if STORE.exists():
        shutil.rmtree(STORE)
    write_run_record(STORE, RUN, _run_record())
    writer = RunRecordWriter(STORE, RUN, REF)
    writer.open()
    names = [f"A{i:06d}" for i in range(POSITIONS)]
    base = datetime(2018, 1, 2, 15, 30, tzinfo=SEOUL)
    quantity = Decimal("1")
    for day in range(SESSIONS):
        at = base + timedelta(days=day)
        price = Decimal(100 + day % 17)
        nav = price * POSITIONS
        rows = [
            {
                "event_time": at,
                "observed_at": at,
                "instrument": "_ACCOUNT",
                "account_version": 1,
                "cash": Decimal(0),
                "nav": nav,
                "quantity": None,
                "price": None,
            }
        ]
        rows.extend(
            {
                "event_time": at,
                "observed_at": at,
                "instrument": name,
                "account_version": 1,
                "cash": None,
                "nav": None,
                "quantity": quantity,
                "price": price,
            }
            for name in names
        )
        writer.append("vqapr.account", rows)
    writer.finish(_strategy_record(), kind=STRATEGY_KIND)
    writer.release()


def measure(mode: str) -> None:
    started = time.perf_counter()
    if mode == "full":
        performance = strategy_report(STORE, RUN).performance
    else:
        from vqapr.public import strategy_performance

        performance = strategy_performance(STORE, RUN)
    elapsed = time.perf_counter() - started
    print(
        json.dumps(
            {
                "mode": mode,
                "seconds": elapsed,
                "periods": performance.periods,
                "digest": hashlib.sha256(
                    json.dumps(performance.as_record(), sort_keys=True).encode()
                ).hexdigest(),
            }
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--mode", choices=("full", "performance"), default="full")
    args = parser.parse_args()
    if args.prepare:
        prepare()
    measure(args.mode)


if __name__ == "__main__":
    main()
