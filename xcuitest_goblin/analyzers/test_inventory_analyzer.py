"""Test inventory analyzer for iOS XCUITest projects.

This analyzer scans XCUITest directories to extract test methods, classes,
and statistics about test organization.
"""

import re
import statistics
from pathlib import Path
from typing import Any, Dict, List, Optional

from xcuitest_goblin.analyzers.base_analyzer import BaseAnalyzer
from xcuitest_goblin.config import get_threshold


class TestInventoryAnalyzer(BaseAnalyzer):
    """Analyzes test inventory in iOS XCUITest projects.

    Extracts:
    - Test files and methods
    - Test classes
    - Tests per file statistics
    - Naming pattern consistency
    """

    # Regex patterns for Swift test extraction
    CLASS_PATTERN = re.compile(
        r"(?:final\s+)?class\s+(\w+)\s*:\s*\w*XCTestCase", re.MULTILINE
    )

    # Matches: func testSomething() or func test_something()
    TEST_METHOD_PATTERN = re.compile(r"^\s*func\s+(test\w+)\s*\(", re.MULTILINE)

    # Matches: @Test func something() or @Test("description") or @Test(.bug("..."))
    # Using a simpler pattern that looks ahead to find 'func'
    AT_TEST_PATTERN = re.compile(
        r"@Test(?:\((?:[^()]*|\([^()]*\))*\))?\s+func\s+(\w+)\s*\(", re.MULTILINE
    )

    def analyze(self) -> Dict[str, Any]:
        """Run test inventory analysis.

        Returns:
            Dictionary with test inventory data matching the schema:
            {
                "total_test_files": int,
                "total_test_methods": int,
                "tests_per_file": {
                    "min": int,
                    "max": int,
                    "avg": float,
                    "median": float
                },
                "test_files": [
                    {
                        "file_name": str,
                        "file_path": str,
                        "test_count": int,
                        "test_classes": [str],
                        "test_methods": [str]
                    }
                ],
                "naming_patterns": {
                    "follows_convention": int,
                    "pattern": str,
                    "consistency": str
                }
            }
        """
        # Find all test files with various naming patterns
        test_files = []

        # Primary patterns: Files with "Test" in the name (most reliable)
        test_patterns = [
            "*Tests.swift",  # Standard: LoginTests.swift
            "*Test.swift",  # Singular: LoginTest.swift
            "*_tests.swift",  # Snake case: login_tests.swift
            "*_test.swift",  # Snake case singular: login_test.swift
            "*Test*.swift",  # Variations: LoginTest1.swift, TestScenarios.swift
            "test*.swift",  # Lowercase prefix: testCase42.swift
        ]

        for pattern in test_patterns:
            test_files.extend(self._find_test_files(pattern))

        # FALLBACK: Scan ALL .swift files in XCUITests/UITests directories
        # to catch files with unconventional names that still contain tests
        # (e.g., NewTabSettings.swift without "Test" in name)
        # Note: We DON'T use broad patterns like *Flow*.swift or *Validation*.swift
        # because those can match source files outside test directories
        test_files.extend(self._find_test_files("*.swift"))

        # Remove duplicates
        test_files = sorted(set(test_files))

        if not test_files:
            return self._empty_result()

        # Extract test data from each file
        file_data_list = []
        test_counts = []

        for test_file_path in test_files:
            file_data = self._analyze_test_file(test_file_path)
            if file_data:  # Only include files with tests
                file_data_list.append(file_data)
                test_counts.append(file_data["test_count"])

        if not file_data_list:
            return self._empty_result()

        # Calculate statistics
        total_test_methods = sum(test_counts)
        stats = self._calculate_statistics(test_counts)
        file_naming_analysis = self._analyze_naming_patterns(file_data_list)
        method_naming_analysis = self._analyze_method_naming(file_data_list)

        return {
            "total_test_files": len(file_data_list),
            "total_test_methods": total_test_methods,
            "tests_per_file": stats,
            "test_files": file_data_list,
            "naming_patterns": file_naming_analysis,
            "method_naming_patterns": method_naming_analysis,
        }

    def _analyze_test_file(self, file_path: Path) -> Dict[str, Any] | None:
        """Analyze a single test file.

        Args:
            file_path: Path to the Swift test file

        Returns:
            Dictionary with file analysis data or None if no tests found
        """
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return None

        # Extract test classes
        test_classes = self.CLASS_PATTERN.findall(content)

        # Extract test methods (both patterns)
        test_methods = []

        # func testXxx() pattern
        test_methods.extend(self.TEST_METHOD_PATTERN.findall(content))

        # @Test annotation pattern
        test_methods.extend(self.AT_TEST_PATTERN.findall(content))

        # Count total tests (including duplicates - same method name can exist
        # in multiple classes within the same file)
        total_test_count = len(test_methods)

        # Get unique method names for reporting (preserving order)
        seen = set()
        unique_test_methods = []
        for method in test_methods:
            if method not in seen:
                seen.add(method)
                unique_test_methods.append(method)

        if total_test_count == 0:
            return None

        # Get relative path from project root
        try:
            relative_path = file_path.relative_to(self.project_path)
        except ValueError:
            relative_path = file_path

        return {
            "file_name": file_path.name,
            "file_path": str(relative_path),
            # Count all tests including duplicates in different classes
            "test_count": total_test_count,
            "test_classes": test_classes if test_classes else [file_path.stem],
            "test_methods": unique_test_methods,  # Unique names for reporting
        }

    def _calculate_statistics(self, test_counts: List[int]) -> Dict[str, float]:
        """Calculate statistical measures for tests per file.

        Args:
            test_counts: List of test counts per file

        Returns:
            Dictionary with min, max, avg, median
        """
        if not test_counts:
            return {"min": 0, "max": 0, "avg": 0.0, "median": 0.0}

        return {
            "min": min(test_counts),
            "max": max(test_counts),
            "avg": round(statistics.mean(test_counts), 2),
            "median": statistics.median(test_counts),
        }

    def _analyze_naming_patterns(
        self, file_data_list: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze test file naming patterns for consistency.

        Args:
            file_data_list: List of file data dictionaries

        Returns:
            Dictionary with naming pattern analysis, or None if not configured
        """
        # Get configured pattern - if None, skip naming analysis
        configured_pattern = get_threshold("test_file_naming", "pattern", None)

        if configured_pattern is None:
            return None

        if not file_data_list:
            return {
                "follows_convention": 0,
                "pattern": configured_pattern,
                "consistency": "0%",
            }

        # Extract the suffix from the pattern (e.g., "Tests.swift" from "[Feature]Tests.swift")
        # Pattern format: [Feature]Suffix.swift or similar
        suffix_match = re.search(r"\](.+)$", configured_pattern)
        if suffix_match:
            expected_suffix = suffix_match.group(1)
        else:
            # Fallback: use the pattern as-is if no [Feature] placeholder
            expected_suffix = configured_pattern

        # Check how many files follow the configured pattern
        follows_convention = 0
        for file_data in file_data_list:
            file_name = file_data["file_name"]
            if file_name.endswith(expected_suffix):
                follows_convention += 1

        total_files = len(file_data_list)
        consistency_percentage = round((follows_convention / total_files) * 100, 1)

        return {
            "follows_convention": follows_convention,
            "pattern": configured_pattern,
            "consistency": f"{consistency_percentage}%",
        }

    def _detect_method_naming_style(self, method_name: str) -> str:
        """Detect the naming style of a test method.

        Args:
            method_name: Name of the test method (without 'test' prefix)

        Returns:
            Style identifier: 'camelCase', 'snake_case', or 'BDD'
        """
        # Remove 'test' or 'test_' prefix for analysis
        name = method_name
        if name.startswith("test_"):
            name = name[5:]
        elif name.startswith("test"):
            name = name[4:]

        if not name:
            return "camelCase"  # Default for edge cases

        # BDD style: contains Given/When/Then or multiple underscores with capitals
        if any(kw in name for kw in ["Given", "When", "Then", "_When", "_Then"]):
            return "BDD"

        # snake_case: contains underscores and mostly lowercase
        if "_" in name:
            # Check if it's snake_case (lowercase with underscores)
            parts = name.split("_")
            if all(p.islower() or p == "" for p in parts):
                return "snake_case"
            # Could be BDD or mixed
            return "BDD"

        # camelCase: starts with lowercase, has uppercase letters
        if name[0].islower():
            return "camelCase"

        return "camelCase"  # Default

    def _analyze_method_naming(
        self, file_data_list: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Analyze test method naming patterns for consistency.

        Args:
            file_data_list: List of file data dictionaries with test_methods

        Returns:
            Dictionary with method naming analysis, or None if not configured
        """
        configured_style = get_threshold("test_method_naming", "pattern", None)

        if configured_style is None:
            return None

        # Collect all test methods
        all_methods = []
        for file_data in file_data_list:
            all_methods.extend(file_data.get("test_methods", []))

        if not all_methods:
            return {
                "expected_style": configured_style,
                "consistency": "0%",
                "follows_convention": 0,
                "total_methods": 0,
                "style_breakdown": {},
                "non_compliant_methods": [],
                "non_compliant_count": 0,
            }

        # Analyze each method
        style_counts: Dict[str, int] = {"camelCase": 0, "snake_case": 0, "BDD": 0}
        non_compliant = []

        for method in all_methods:
            style = self._detect_method_naming_style(method)
            style_counts[style] = style_counts.get(style, 0) + 1

            if style != configured_style:
                non_compliant.append({"method": method, "detected_style": style})

        total = len(all_methods)
        follows = style_counts.get(configured_style, 0)
        consistency = round((follows / total) * 100, 1) if total > 0 else 0

        return {
            "expected_style": configured_style,
            "consistency": f"{consistency}%",
            "follows_convention": follows,
            "total_methods": total,
            "style_breakdown": style_counts,
            "non_compliant_methods": non_compliant,  # Full list with details
            "non_compliant_count": len(non_compliant),
        }

    def _empty_result(self) -> Dict[str, Any]:
        """Return an empty result structure when no tests are found.

        Returns:
            Dictionary with zero values for all fields
        """
        configured_pattern = get_threshold("test_file_naming", "pattern", None)
        naming_patterns = None
        if configured_pattern is not None:
            naming_patterns = {
                "follows_convention": 0,
                "pattern": configured_pattern,
                "consistency": "0%",
            }

        method_naming = None
        method_style = get_threshold("test_method_naming", "pattern", None)
        if method_style is not None:
            method_naming = {
                "expected_style": method_style,
                "consistency": "0%",
                "follows_convention": 0,
                "total_methods": 0,
                "style_breakdown": {},
                "non_compliant_methods": [],
                "non_compliant_count": 0,
            }

        return {
            "total_test_files": 0,
            "total_test_methods": 0,
            "tests_per_file": {"min": 0, "max": 0, "avg": 0.0, "median": 0.0},
            "test_files": [],
            "naming_patterns": naming_patterns,
            "method_naming_patterns": method_naming,
        }
