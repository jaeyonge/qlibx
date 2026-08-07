from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from qlibx.errors import MappingConfirmationRequired
from qlibx.registration import inspect_registration_bundle, register_bundle


class RegistrationTest(unittest.TestCase):
    def test_registration_is_confirmed_validated_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with (root / "source.csv").open(
                "w", encoding="utf-8", newline=""
            ) as stream:
                writer = csv.DictWriter(
                    stream, fieldnames=["일자", "종목약코드", "PBR"]
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {"일자": "20200102", "종목약코드": "A", "PBR": "1.0"},
                        {"일자": "20200103", "종목약코드": "A", "PBR": "1.1"},
                    ]
                )
            config = {
                "schema": "qlibx.dataset_registration_bundle/v1",
                "output_dir": "registry",
                "datasets": [
                    {
                        "dataset_id": "fixture/v1",
                        "kind": "valuation",
                        "source": {"type": "csv", "path": "source.csv"},
                        "required_fields": ["date", "instrument", "pbr"],
                        "mappings": {
                            "date": "일자",
                            "instrument": "종목약코드",
                            "pbr": "PBR",
                        },
                        "mapping_confirmed": True,
                        "key": ["date", "instrument"],
                        "date_field": "date",
                        "date_format": "%Y%m%d",
                    }
                ],
            }
            config_path = root / "registration.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            inspected = inspect_registration_bundle(config_path, project_root=root)
            self.assertEqual(inspected["status"], "passed")
            first = register_bundle(config_path, project_root=root)
            index_before = (root / "registry" / "index.json").read_bytes()
            second = register_bundle(config_path, project_root=root)
            self.assertFalse(first["datasets"][0]["reused"])
            self.assertTrue(second["datasets"][0]["reused"])
            self.assertEqual(
                first["datasets"][0]["registration_id"],
                second["datasets"][0]["registration_id"],
            )
            self.assertEqual(first["datasets"][0]["profile"]["duplicate_key_groups"], 0)
            self.assertEqual(
                index_before, (root / "registry" / "index.json").read_bytes()
            )

    def test_unconfirmed_mapping_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "source.csv").write_text(
                "date,value\n20200101,1\n", encoding="utf-8"
            )
            config = {
                "schema": "qlibx.dataset_registration_bundle/v1",
                "datasets": [
                    {
                        "dataset_id": "fixture/v1",
                        "source": {"type": "csv", "path": "source.csv"},
                        "required_fields": ["date"],
                        "mappings": {"date": "date"},
                        "mapping_confirmed": False,
                        "key": ["date"],
                    }
                ],
            }
            config_path = root / "registration.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaises(MappingConfirmationRequired):
                inspect_registration_bundle(config_path, project_root=root)


if __name__ == "__main__":
    unittest.main()
