import datetime as dt
import unittest

from update_profile import age_text, dot_fill


class ProfileUpdaterTests(unittest.TestCase):
    def test_age_on_birthday(self):
        self.assertEqual(
            age_text("2000-05-10", dt.date(2026, 5, 10)),
            "26 years, 0 months, 0 days",
        )

    def test_age_before_month_anniversary(self):
        self.assertEqual(
            age_text("2000-01-31", dt.date(2026, 3, 30)),
            "26 years, 1 month, 30 days",
        )

    def test_missing_birth_date_has_instruction(self):
        self.assertEqual(age_text("", dt.date(2026, 1, 1)), "set BIRTH_DATE variable")

    def test_dot_fill_has_padding(self):
        self.assertEqual(dot_fill("123", 8), " ..... ")


if __name__ == "__main__":
    unittest.main()
