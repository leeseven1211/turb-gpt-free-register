import unittest
from datetime import date
from unittest.mock import patch

from core.profile_utils import generate_random_birthday


def _age_on_today(birthday: date) -> int:
    today = date.today()
    return today.year - birthday.year - ((today.month, today.day) < (birthday.month, birthday.day))


class ProfileUtilsTests(unittest.TestCase):
    def test_default_oldest_age_is_49(self):
        with patch("core.profile_utils.random.randint", return_value=0):
            birthday = date.fromisoformat(generate_random_birthday())

        self.assertEqual(_age_on_today(birthday), 49)

    def test_default_youngest_age_is_18(self):
        with patch("core.profile_utils.random.randint", side_effect=lambda _start, end: end):
            birthday = date.fromisoformat(generate_random_birthday())

        self.assertEqual(_age_on_today(birthday), 18)

    def test_rejects_invalid_age_range(self):
        with self.assertRaises(ValueError):
            generate_random_birthday(min_age=50, max_age=49)


if __name__ == "__main__":
    unittest.main()
