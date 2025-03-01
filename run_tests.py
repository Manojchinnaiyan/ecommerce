#!/usr/bin/env python
"""
A script to run tests for all apps in the e-commerce API.
Usage: python run_tests.py [app_name]
If app_name is provided, only tests for that app will be run.
Otherwise, tests for all apps will be run.
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ecommerce_api.settings")
django.setup()


def run_tests(app_names=None):
    """Run the tests for the specified apps"""
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2, interactive=True)

    if app_names:
        if not isinstance(app_names, list):
            app_names = [app_names]
        # Prefix app names with 'apps.' to match our app structure
        app_names = [f"apps.{app}" for app in app_names]
        failures = test_runner.run_tests(app_names)
    else:
        # Run all tests
        failures = test_runner.run_tests(
            [
                "apps.accounts",
                "apps.products",
                "apps.orders",
                "apps.payments",
                "apps.cart",
                "apps.wishlist",
                "apps.search",
            ]
        )

    return failures


if __name__ == "__main__":
    # Check if an app name was provided
    if len(sys.argv) > 1:
        app_name = sys.argv[1]
        failures = run_tests(app_name)
    else:
        failures = run_tests()

    # Exit with number of failures as exit code
    sys.exit(bool(failures))
