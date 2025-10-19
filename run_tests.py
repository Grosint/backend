#!/usr/bin/env python3
"""Test runner script for user functionality."""

import argparse
import os
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def check_docker_available():
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Docker is not available. Please install Docker and try again.")
            return False

        # Check if Docker daemon is running
        result = subprocess.run(["docker", "info"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Docker daemon is not running. Please start Docker and try again.")
            return False

        print("✅ Docker is available and running")
        return True
    except FileNotFoundError:
        print("❌ Docker is not installed. Please install Docker and try again.")
        return False


def start_test_containers():
    """Start MongoDB test container using docker-compose."""
    print("🐳 Starting MongoDB test container...")

    # Start containers in detached mode
    result = subprocess.run(
        ["docker-compose", "-f", "docker-compose.test.yml", "up", "-d"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"❌ Failed to start test containers: {result.stderr}")
        return False

    print("✅ Test containers started successfully")
    return True


def wait_for_mongodb():
    """Wait for MongoDB to be ready."""
    print("⏳ Waiting for MongoDB to be ready...")

    max_attempts = 30
    attempt = 0

    while attempt < max_attempts:
        try:
            # Check if MongoDB is responding
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    "osint-backend-test-mongodb",
                    "mongosh",
                    "--eval",
                    "db.adminCommand('ping')",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0 and "ok" in result.stdout.lower():
                print("✅ MongoDB is ready!")
                return True
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pass

        attempt += 1
        time.sleep(2)
        print(f"   Attempt {attempt}/{max_attempts}...")

    print("❌ MongoDB failed to become ready within the timeout period")
    return False


def stop_test_containers():
    """Stop and remove test containers."""
    print("🧹 Cleaning up test containers...")

    result = subprocess.run(
        ["docker-compose", "-f", "docker-compose.test.yml", "down", "-v"],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        print("✅ Test containers cleaned up successfully")
    else:
        print(f"⚠️  Warning: Failed to clean up containers: {result.stderr}")


def open_html_report():
    """Open the HTML coverage report in the default browser."""
    report_path = Path("htmlcov/index.html")
    if report_path.exists():
        report_url = f"file://{report_path.absolute()}"
        print(f"🌐 Opening coverage report: {report_url}")
        try:
            webbrowser.open(report_url)
            print("✅ Coverage report opened in browser")
        except Exception as e:
            print(f"⚠️  Could not open browser: {e}")
            print(f"📊 You can manually open: {report_path.absolute()}")
    else:
        print("❌ HTML coverage report not found at htmlcov/index.html")


def run_tests(use_docker=True, test_target=None, open_report=False):
    """Run all tests with coverage."""
    # Change to project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)

    containers_started = False

    try:
        if use_docker:
            # Check if Docker is available
            if not check_docker_available():
                sys.exit(1)

            # Start test containers
            if not start_test_containers():
                sys.exit(1)

            containers_started = True

            # Wait for MongoDB to be ready
            if not wait_for_mongodb():
                print("❌ MongoDB is not ready. Tests may fail.")
                sys.exit(1)

        # Run tests with coverage
        print("🧪 Running tests with coverage...")
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-v",
            "--cov=app",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-fail-under=100",
            "--tb=short",
        ]

        # Add test target if specified
        if test_target:
            # Clean up the test target path
            test_target = test_target.strip()

            # Remove leading slash if present
            if test_target.startswith("/"):
                test_target = test_target[1:]

            # Check if it's just a filename (no path separators and doesn't start with tests/)
            if (
                "/" not in test_target
                and "\\" not in test_target
                and not test_target.startswith("tests/")
            ):
                # It's just a filename, try to find it in tests/ directory

                # Look for the file in tests/ directory
                test_file = None
                for root, _dirs, files in os.walk("tests"):
                    for file in files:
                        if file == test_target or file == f"{test_target}.py":
                            test_file = os.path.join(root, file)
                            break
                    if test_file:
                        break

                if test_file:
                    test_target = test_file
                else:
                    # Fallback: prepend tests/ directory
                    if test_target.endswith(".py"):
                        test_target = f"tests/{test_target}"
                    else:
                        test_target = f"tests/{test_target}.py"
            elif test_target.startswith("tests/"):
                # Already has tests/ prefix, use as-is
                pass
            else:
                # Has path separators but doesn't start with tests/, prepend tests/
                if not test_target.startswith("tests/"):
                    test_target = f"tests/{test_target}"

            cmd.append(test_target)
        else:
            cmd.append("tests/")

        result = subprocess.run(cmd)

        if result.returncode == 0:
            print("\n✅ All tests passed with 100% coverage!")
            print("📊 Coverage report generated in htmlcov/index.html")

            # Open HTML report if requested
            if open_report:
                open_html_report()
        else:
            print("\n❌ Some tests failed!")
            return result.returncode

    finally:
        # Clean up containers if we started them
        if containers_started:
            stop_test_containers()

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run tests with optional Docker support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py                                    # Run all tests with Docker
  python run_tests.py --no-docker                       # Run all tests without Docker
  python run_tests.py --open-report                     # Run tests and open HTML report
  python run_tests.py test_auth_endpoints.py            # Run specific test file (auto-prefixed with tests/)
  python run_tests.py test_user_database.py             # Run specific test file
  python run_tests.py test_user_database::TestUserTimestampBehavior  # Run specific test class
  python run_tests.py test_user_database::TestUserTimestampBehavior::test_user_creation_timestamps_are_same  # Run specific test function
  python run_tests.py tests/user/                       # Run all tests in user directory
  python run_tests.py -k "test_user_creation"           # Run tests matching pattern
  python run_tests.py --open-report test_auth_endpoints.py  # Run specific test and open report
        """,
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Run tests without Docker (requires local MongoDB)",
    )
    parser.add_argument(
        "--open-report",
        action="store_true",
        help="Open HTML coverage report in browser after successful test run",
    )
    parser.add_argument(
        "test_target",
        nargs="?",
        help="Specific test to run. Can be:\n"
        "- File: test_auth_endpoints.py (auto-prefixed with tests/)\n"
        "- Class: test_user_database::TestUserTimestampBehavior\n"
        "- Function: test_user_database::TestUserTimestampBehavior::test_user_creation_timestamps_are_same\n"
        "- Directory: tests/user/\n"
        "- Pattern: -k 'test_user_creation'",
    )
    parser.add_argument(
        "pytest_args",
        nargs="*",
        help="Additional arguments to pass to pytest (e.g., -k 'pattern', --maxfail=1)",
    )

    args = parser.parse_args()

    # Build test target
    test_target = args.test_target

    # Add pytest args if provided
    if args.pytest_args:
        if test_target:
            # If we have both test_target and pytest_args, combine them
            test_target = f"{test_target} {' '.join(args.pytest_args)}"
        else:
            # If only pytest_args, use them as the test target
            test_target = " ".join(args.pytest_args)

    # Run tests with or without Docker
    exit_code = run_tests(
        use_docker=not args.no_docker,
        test_target=test_target,
        open_report=args.open_report,
    )
    sys.exit(exit_code)
