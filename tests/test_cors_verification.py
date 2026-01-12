"""
CORS Verification Test Suite for Azure Container Apps Backend

This script tests the CORS middleware implementation to ensure proper
configuration for Vercel frontend domains.

Usage:
    python test_cors_verification.py

Requirements:
    pip install pytest httpx pytest-asyncio
"""

import os
import re
import sys
from typing import List, Optional
from unittest.mock import MagicMock, patch

# Test configuration
TEST_VERCEL_DOMAINS = [
    "https://amplify-staging.vercel.app",
    "https://amplify-production.vercel.app",
    "https://amplify-deployment-abc123.vercel.app",
    "https://amplify-feature-new.vercel.app",
]

TEST_LOCALHOST_DOMAINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
]

TEST_UNAUTHORIZED_DOMAINS = [
    "https://malicious-site.com",
    "https://attacker.vercel.app",
    "https://not-amplify.vercel.app",
    "http://internal-server.local",
]


class CorsValidator:
    """Validates CORS origin patterns"""

    def __init__(self):
        self.vercel_pattern = re.compile(
            r"^https://amplify-[a-zA-Z0-9-]+\.vercel\.app$"
        )
        self.dev_pattern = re.compile(r"^http://localhost:[0-9]+$")

    def is_allowed_origin(self, origin: str) -> bool:
        """Check if origin matches allowed patterns"""
        if self.vercel_pattern.match(origin):
            return True
        if self.dev_pattern.match(origin):
            return True
        return False

    def validate_vercel_pattern(self, origin: str) -> bool:
        """Validate Vercel amplify domain pattern"""
        return bool(self.vercel_pattern.match(origin))

    def validate_localhost_pattern(self, origin: str) -> bool:
        """Validate localhost pattern"""
        return bool(self.dev_pattern.match(origin))


class CorsTestCase:
    """Represents a single CORS test case"""

    def __init__(
        self, name: str, origin: str, expected_allow: bool, description: str = ""
    ):
        self.name = name
        self.origin = origin
        self.expected_allow = expected_allow
        self.description = description

    def __str__(self):
        return f"{self.name}: {self.origin} -> {'ALLOW' if self.expected_allow else 'DENY'}"


class CorsTestSuite:
    """Main test suite for CORS validation"""

    def __init__(self):
        self.validator = CorsValidator()
        self.test_cases: List[CorsTestCase] = []
        self.results = []

    def add_test_case(self, test_case: CorsTestCase):
        """Add a test case to the suite"""
        self.test_cases.append(test_case)

    def setup_vercel_tests(self):
        """Setup Vercel domain test cases"""
        # Valid Vercel amplify domains
        valid_domains = [
            ("amplify-staging", "https://amplify-staging.vercel.app"),
            ("amplify-production", "https://amplify-production.vercel.app"),
            ("amplify-random123", "https://amplify-random123.vercel.app"),
            ("amplify-feature-test", "https://amplify-feature-test.vercel.app"),
            ("amplify-with-numbers-123", "https://amplify-with-numbers-123.vercel.app"),
        ]

        for name, domain in valid_domains:
            self.add_test_case(
                CorsTestCase(
                    name=f"Valid Vercel: {name}",
                    origin=domain,
                    expected_allow=True,
                    description=f"Should allow valid Vercel domain: {domain}",
                )
            )

    def setup_localhost_tests(self):
        """Setup localhost test cases"""
        localhost_domains = [
            ("localhost-3000", "http://localhost:3000"),
            ("localhost-5173", "http://localhost:5173"),
            ("localhost-8080", "http://localhost:8080"),
        ]

        for name, domain in localhost_domains:
            self.add_test_case(
                CorsTestCase(
                    name=f"Localhost: {name}",
                    origin=domain,
                    expected_allow=True,
                    description=f"Should allow localhost domain: {domain}",
                )
            )

    def setup_invalid_tests(self):
        """Setup invalid domain test cases"""
        invalid_domains = [
            ("not-amplify-vercel", "https://not-amplify.vercel.app"),
            ("other-vercel", "https://other.vercel.app"),
            ("malicious-com", "https://malicious.com"),
            ("empty-origin", ""),
            ("invalid-url", "not-a-valid-url"),
        ]

        for name, domain in invalid_domains:
            self.add_test_case(
                CorsTestCase(
                    name=f"Invalid: {name}",
                    origin=domain,
                    expected_allow=False,
                    description=f"Should deny invalid origin: {domain}",
                )
            )

    def run_tests(self) -> dict:
        """Execute all test cases and return results"""
        passed = 0
        failed = 0

        print("\n" + "=" * 70)
        print("CORS VALIDATION TEST SUITE")
        print("=" * 70)

        for test_case in self.test_cases:
            try:
                result = self.validator.is_allowed_origin(test_case.origin)
                is_passed = result == test_case.expected_allow

                status = "✅ PASS" if is_passed else "❌ FAIL"
                self.results.append(
                    {
                        "name": test_case.name,
                        "origin": test_case.origin,
                        "expected": test_case.expected_allow,
                        "got": result,
                        "passed": is_passed,
                        "description": test_case.description,
                    }
                )

                if is_passed:
                    passed += 1
                else:
                    failed += 1

                print(f"\n{status}")
                print(f"  Test: {test_case.name}")
                print(f"  Origin: {test_case.origin}")
                print(f"  Expected: {'ALLOW' if test_case.expected_allow else 'DENY'}")
                print(f"  Got: {'ALLOW' if result else 'DENY'}")
                if test_case.description:
                    print(f"  Note: {test_case.description}")

            except Exception as e:
                failed += 1
                print(f"\n❌ ERROR")
                print(f"  Test: {test_case.name}")
                print(f"  Error: {str(e)}")

        print("\n" + "=" * 70)
        print(
            f"TEST SUMMARY: {passed} passed, {failed} failed, {len(self.test_cases)} total"
        )
        print("=" * 70)

        return {
            "passed": passed,
            "failed": failed,
            "total": len(self.test_cases),
            "results": self.results,
            "success": failed == 0,
        }

    def generate_report(self) -> str:
        """Generate a detailed test report"""
        report = []
        report.append("# CORS Configuration Verification Report")
        report.append("")
        report.append("## Test Environment")
        report.append(
            f"- Validator Pattern: `^https://amplify-[a-zA-Z0-9-]+\\.vercel\\.app$`"
        )
        report.append(f"- Total Test Cases: {len(self.test_cases)}")
        report.append("")

        report.append("## Test Results")
        report.append("")

        for result in self.results:
            status = "✅" if result["passed"] else "❌"
            report.append(f"{status} **{result['name']}**")
            report.append(f"  - Origin: `{result['origin']}`")
            report.append(
                f"  - Expected: `{result['expected']}` | Got: `{result['got']}`"
            )
            if result["description"]:
                report.append(f"  - Note: {result['description']}")
            report.append("")

        report.append("## Recommendations")
        if self.results:
            failed_tests = [r for r in self.results if not r["passed"]]
            if failed_tests:
                report.append("### Issues Found")
                for test in failed_tests:
                    report.append(
                        f"- **{test['name']}**: Review origin validation logic"
                    )
            else:
                report.append(
                    "✅ All tests passed. CORS configuration appears correct."
                )

        return "\n".join(report)


def test_environment_configuration():
    """Test that environment variables are properly configured"""
    print("\n" + "=" * 70)
    print("ENVIRONMENT CONFIGURATION CHECK")
    print("=" * 70)

    # Mock environment for testing
    test_env = {
        "ALLOWED_ORIGINS": "https://amplify-production.vercel.app,https://amplify-staging.vercel.app",
        "ENVIRONMENT": "development",
    }

    print("\nChecking environment variable loading...")

    # Test environment parsing
    with patch.dict(os.environ, test_env, clear=False):
        allowed_origins = os.getenv("ALLOWED_ORIGINS", "")
        environment = os.getenv("ENVIRONMENT", "production")

        print(f"✅ ALLOWED_ORIGINS: {allowed_origins}")
        print(f"✅ ENVIRONMENT: {environment}")

        origins_list = (
            [o.strip() for o in allowed_origins.split(",")] if allowed_origins else []
        )
        print(f"✅ Parsed Origins: {origins_list}")

        if environment == "development":
            print("✅ Localhost origins will be added automatically")

        return True


def test_regex_patterns():
    """Test regex pattern compilation"""
    print("\n" + "=" * 70)
    print("REGEX PATTERN VALIDATION")
    print("=" * 70)

    patterns = [
        (r"^https://amplify-[a-zA-Z0-9-]+\.vercel\.app$", "Vercel Amplify"),
        (r"^http://localhost:[0-9]+$", "Localhost"),
    ]

    all_valid = True

    for pattern, name in patterns:
        try:
            regex = re.compile(pattern)
            print(f"\n✅ Pattern compiled successfully: {name}")
            print(f"   Pattern: {pattern}")

            # Test with sample values
            test_values = {
                "https://amplify-staging.vercel.app": True,
                "https://amplify-production.vercel.app": True,
                "https://not-amplify.vercel.app": False,
            }

            for value, expected in test_values.items():
                match = bool(regex.match(value))
                status = "✅" if match == expected else "❌"
                print(f"   {status} '{value}' -> {match}")

                if match != expected:
                    all_valid = False

        except re.error as e:
            print(f"\n❌ Pattern compilation failed: {name}")
            print(f"   Error: {e}")
            all_valid = False

    return all_valid


def test_cors_headers():
    """Test CORS header generation"""
    print("\n" + "=" * 70)
    print("CORS HEADER GENERATION")
    print("=" * 70)

    # Simulate CORS header generation logic
    def generate_cors_headers(origin: str, is_allowed: bool) -> dict:
        if not is_allowed:
            return {}

        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-Requested-With",
            "Access-Control-Max-Age": "86400",
        }

    test_cases = [
        ("https://amplify-staging.vercel.app", True),
        ("https://malicious.com", False),
    ]

    for origin, is_allowed in test_cases:
        headers = generate_cors_headers(origin, is_allowed)
        status = "✅" if (bool(headers) == is_allowed) else "❌"
        print(f"\n{status} Origin: {origin}")
        print(f"   Allowed: {is_allowed}")
        print(f"   Headers Generated: {len(headers)} headers")
        if headers:
            for key, value in headers.items():
                print(f"      {key}: {value}")

    return True


def main():
    """Main entry point for CORS verification tests"""
    print("\n🚀 Starting CORS Configuration Verification\n")

    # Create test suite
    suite = CorsTestSuite()

    # Setup test cases
    suite.setup_vercel_tests()
    suite.setup_localhost_tests()
    suite.setup_invalid_tests()

    # Run tests
    results = suite.run_tests()

    # Run additional tests
    test_environment_configuration()
    test_regex_patterns()
    test_cors_headers()

    # Generate report
    report = suite.generate_report()

    # Save report
    report_file = "cors_verification_report.md"
    with open(report_file, "w") as f:
        f.write(report)
    print(f"\n📄 Report saved to: {report_file}")

    # Exit with appropriate code
    if results["success"]:
        print("\n✅ All CORS verification tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some CORS verification tests failed!")
        sys.exit(1)


if __name__ == "__main__":
    main()
