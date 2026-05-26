import unittest
from unittest.mock import call, patch


class DailyMacroUpdateTests(unittest.TestCase):
    def test_daily_update_uses_current_interpreter(self):
        import workflows.daily_macro_update as daily_macro_update

        with patch.object(daily_macro_update.subprocess, "run") as run:
            daily_macro_update.run_daily_update()

        expected_python = daily_macro_update.sys.executable
        self.assertEqual(
            run.call_args_list,
            [
                call(
                    [expected_python, "scripts/update_macro_sources_cache.py"],
                    check=True,
                    timeout=300,
                ),
                call(
                    [expected_python, "scripts/generate_macro_calendar_events.py", "--apply"],
                    check=True,
                    timeout=300,
                ),
            ],
        )

    def test_daily_update_logs_failed_step(self):
        import workflows.daily_macro_update as daily_macro_update

        with patch.object(daily_macro_update.subprocess, "run", side_effect=FileNotFoundError("missing")), \
             self.assertLogs("daily_macro_update", level="WARNING") as logs:
            daily_macro_update.run_daily_update()

        self.assertIn("step=update_macro_sources_cache", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
