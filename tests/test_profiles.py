from __future__ import annotations

import unittest

from qlibx.errors import ConfigError
from qlibx.profiles import get_profile, list_profiles


class ProfileTest(unittest.TestCase):
    def test_research_profile_is_registered(self) -> None:
        profile = get_profile("qlib.research_daily/v1")

        self.assertEqual(profile.frequency, "day")
        self.assertEqual(set(profile.feature_map), {"pbr", "adjusted_daily_return"})
        self.assertIn("order_execution", profile.excluded_capabilities)
        self.assertEqual(
            [item.profile_id for item in list_profiles()], [profile.profile_id]
        )

    def test_unknown_profile_has_stable_error(self) -> None:
        with self.assertRaises(ConfigError) as caught:
            get_profile("missing/v1")

        self.assertEqual(caught.exception.code, "invalid_config")
        self.assertIn(
            "qlib.research_daily/v1", caught.exception.details["available_profiles"]
        )


if __name__ == "__main__":
    unittest.main()
