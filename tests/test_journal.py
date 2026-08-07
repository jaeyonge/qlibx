from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from qlibx.errors import ConfigError
from qlibx.journal import ActionJournal


class JournalTest(unittest.TestCase):
    def test_success_and_failure_are_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = ActionJournal(
                root, actor_id="test-agent", session_id="test-session"
            )
            with journal.operation("data.inspect", read_only=True) as operation:
                operation.succeed(outputs={"result_summary": {"rows": 3}})
            with (
                self.assertRaises(ConfigError),
                journal.operation("data.mapping.validate", read_only=True),
            ):
                raise ConfigError("bad mapping")

            events = [
                json.loads(line)
                for line in journal.path.read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(
                [event["phase"] for event in events],
                ["requested", "started", "succeeded", "requested", "started", "failed"],
            )
            self.assertEqual(events[-1]["error"]["code"], "invalid_config")
            self.assertEqual(events[2]["outputs"]["result_summary"]["rows"], 3)
            succeeded = journal.query(
                action="data.inspect", phase="succeeded", limit=10
            )
            self.assertEqual(len(succeeded), 1)
            self.assertEqual(succeeded[0]["operation_id"], events[0]["operation_id"])


if __name__ == "__main__":
    unittest.main()
