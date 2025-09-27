#!/usr/bin/env python3
"""
Test runner script with Docker management for MongoDB testing.
This script handles starting/stopping Docker containers for tests.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd, check=True, capture_output=False):
    """Run a command and return the result."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=capture_output, text=True)
    return result


def check_docker_available():
    """Check if Docker is available and running."""
    try:
        run_command(["docker", "--version"], capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def start_test_services():
    """Start the test MongoDB container."""
    compose_file = Path(__file__).parent / "docker-compose.test.yml"

    print("Starting test MongoDB container...")
    run_command(["docker", "compose", "-f", str(compose_file), "up", "-d", "--build"])

    # Wait for MongoDB to be ready
    print("Waiting for MongoDB to be ready...")
    max_retries = 30
    for _ in range(max_retries):
        try:
            result = run_command(
                [
                    "docker",
                    "exec",
                    "osint-backend-test-mongodb",
                    "mongosh",
                    "--eval",
                    "db.adminCommand('ping')",
                ],
                capture_output=True,
            )
            if "ok" in result.stdout.lower():
                print("MongoDB is ready!")
                return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(1)

    print("MongoDB failed to start or become ready")
    return False


def stop_test_services():
    """Stop and clean up test containers."""
    compose_file = Path(__file__).parent / "docker-compose.test.yml"

    print("Stopping test containers...")
    run_command(
        ["docker", "compose", "-f", str(compose_file), "down", "-v"], check=False
    )


def run_tests(test_args=None):
    """Run the tests with pytest."""
    if test_args is None:
        test_args = []

    cmd = ["python", "-m", "pytest"] + test_args
    return run_command(cmd)


def main():
    parser = argparse.ArgumentParser(description="Run tests with Docker MongoDB")
    parser.add_argument(
        "test_args", nargs="*", help="Additional arguments to pass to pytest"
    )
    parser.add_argument(
        "--no-docker",
        action="store_true",
        help="Skip Docker setup (assume MongoDB is already running)",
    )

    args = parser.parse_args()

    if not args.no_docker:
        if not check_docker_available():
            print("Error: Docker is not available or not running")
            print(
                "Please install Docker and Docker Compose, or use --no-docker if MongoDB is already running"
            )
            sys.exit(1)

        if not start_test_services():
            print("Error: Failed to start test services")
            sys.exit(1)

    try:
        # Run the tests
        result = run_tests(args.test_args)
        exit_code = result.returncode
    finally:
        if not args.no_docker:
            stop_test_services()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
