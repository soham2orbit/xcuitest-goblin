"""
Accessibility Identifier Analyzer for iOS XCUITest projects.

Extracts accessibility identifiers from test files and source code,
analyzes usage patterns, and generates statistics.
"""

import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Optional, Set

from xcuitest_goblin.analyzers.base_analyzer import BaseAnalyzer


class AccessibilityAnalyzer(BaseAnalyzer):
    """
    Analyzes accessibility identifier usage in iOS XCUITest projects.

    Extracts accessibility IDs from test files, searches for definitions
    in source code, and provides comprehensive usage statistics.
    """

    # XCUIElement types to search for
    ELEMENT_TYPES = [
        "buttons",
        "tables",
        "cells",
        "textFields",
        "staticTexts",
        "navigationBars",
        "switches",
        "otherElements",
        "images",
        "collectionViews",
        "webViews",
        "menuItems",
        "links",
        "scrollViews",
        "keyboards",
        "keys",
        "secureTextFields",
        "datePickers",
        "pickers",
        "pickerWheels",
        "sliders",
        "steppers",
        "toolbars",
        "tabBars",
        "alerts",
        "sheets",
        "popovers",
        "textViews",
        "searchFields",
        "progressIndicators",
        "activityIndicators",
    ]

    def __init__(self, project_path: Path):
        """
        Initialize the analyzer.

        Args:
            project_path: Root path of the iOS project
        """
        super().__init__(project_path)
        self.identifiers: Dict[str, Dict] = {}
        self.test_files: Set[str] = set()

    def analyze(
        self, test_path: Optional[Path] = None, source_path: Optional[Path] = None
    ) -> Dict:
        """
        Analyze accessibility identifiers in the project.

        Args:
            test_path: Path to test files directory (optional)
            source_path: Path to source code directory (optional)

        Returns:
            Dictionary containing analysis results
        """
        # Find source files FIRST to register all defined identifiers
        if source_path:
            source_dir = Path(source_path)
        else:
            source_dir = self._find_source_directory()

        if source_dir and source_dir.exists():
            self._scan_source_files(source_dir)

        # Then find test files to track usage
        if test_path:
            test_dir = Path(test_path)
        else:
            test_dir = self._find_test_directory()

        if test_dir and test_dir.exists():
            self._scan_test_files(test_dir)

        # Generate analysis results
        return self._generate_results()

    def _find_test_directory(self) -> Path:
        """
        Find the XCUITest directory in the project.

        Returns:
            Path to the test directory
        """
        # Common test directory patterns
        test_patterns = [
            "**/XCUITests",
            "**/UITests",
            "**/Tests",
            "**/XCUITest",
        ]

        for pattern in test_patterns:
            matches = list(self.project_path.glob(pattern))
            if matches:
                return matches[0]

        return self.project_path

    def _find_source_directory(self) -> Path:
        """
        Find the source code directory in the project.

        Returns:
            Path to the source directory
        """
        # Look for common source directories
        source_patterns = [
            "**/Client",
            "**/Sources",
            "**/Source",
            "**/App",
        ]

        for pattern in source_patterns:
            matches = list(self.project_path.glob(pattern))
            if matches:
                return matches[0]

        return self.project_path

    def _scan_test_files(self, test_dir: Path) -> None:
        """
        Scan test files for accessibility identifier usage.

        Args:
            test_dir: Directory containing test files
        """
        # Find all Swift test files
        test_files = list(test_dir.glob("**/*Tests.swift")) + list(
            test_dir.glob("**/*Test.swift")
        )
        test_files.extend(test_dir.glob("**/register*.swift"))
        test_files.extend(test_dir.glob("**/FxScreenGraph.swift"))

        for test_file in test_files:
            try:
                content = test_file.read_text(encoding="utf-8")
                file_name = test_file.name
                self.test_files.add(file_name)
                self._extract_ids_from_test(content, file_name)
            except Exception as e:
                print(f"Warning: Could not read {test_file}: {e}")

    def _extract_ids_from_test(self, content: str, file_name: str) -> None:
        """
        Extract accessibility IDs from test file content.

        Args:
            content: File content
            file_name: Name of the test file
        """
        # Pattern 1: app.elementType["ID"]
        # Matches: app.buttons["Done"], app.tables.cells["ID"]
        for element_type in self.ELEMENT_TYPES:
            pattern = rf'\.{element_type}\["([^"]+)"\]'
            matches = re.finditer(pattern, content)
            for match in matches:
                id_value = match.group(1)
                # Normalize element type (remove plural 's')
                normalized_type = element_type.rstrip("s")
                self._record_identifier(id_value, file_name, normalized_type)

        # Pattern 2: Generic element access with string literal
        # Matches: .otherElements["ID"], ["ID"]
        generic_pattern = r'\["([^"]+)"\]'
        matches = re.finditer(generic_pattern, content)
        for match in matches:
            id_value = match.group(1)
            # Only record if not already captured
            if id_value not in self.identifiers or file_name not in [
                f for f in self.identifiers[id_value].get("used_in_tests", [])
            ]:
                self._record_identifier(id_value, file_name, "generic")

        # Pattern 3: staticTexts["ID"] without app prefix
        element_pattern = (
            r"(?:^|\s)(" + "|".join(self.ELEMENT_TYPES) + r')\["([^"]+)"\]'
        )
        matches = re.finditer(element_pattern, content)
        for match in matches:
            element_type = match.group(1)
            id_value = match.group(2)
            normalized_type = element_type.rstrip("s")
            self._record_identifier(id_value, file_name, normalized_type)

    def _record_identifier(
        self, id_value: str, file_name: str, element_type: str
    ) -> None:
        """
        Record an accessibility identifier usage.

        Args:
            id_value: The accessibility identifier
            file_name: Test file where it was found
            element_type: Type of UI element
        """
        if id_value not in self.identifiers:
            self.identifiers[id_value] = {
                "id": id_value,
                "usage_count": 0,
                "element_types": set(),
                "used_in_tests": set(),
                "defined_in": set(),
                "is_centralized": False,
            }

        self.identifiers[id_value]["usage_count"] += 1
        self.identifiers[id_value]["element_types"].add(element_type)
        self.identifiers[id_value]["used_in_tests"].add(file_name)

    def _scan_source_files(self, source_dir: Path) -> None:
        """
        Scan source files for accessibility identifier definitions.

        Args:
            source_dir: Directory containing source files
        """
        # Look for AccessibilityIdentifiers.swift file
        centralized_files = list(source_dir.glob("**/AccessibilityIdentifiers.swift"))
        centralized_files.extend(source_dir.glob("**/AccessibilityIdentifier.swift"))

        for file in centralized_files:
            try:
                content = file.read_text(encoding="utf-8")
                self._extract_definitions_from_centralized(content, file.name)
            except Exception as e:
                print(f"Warning: Could not read {file}: {e}")

        # Look for inline definitions in all Swift files
        swift_files = list(source_dir.glob("**/*.swift"))
        for swift_file in swift_files:
            try:
                content = swift_file.read_text(encoding="utf-8")
                self._extract_inline_definitions(content, swift_file.name)
            except Exception as e:
                print(f"Warning: Could not read {swift_file}: {e}")

    def _extract_definitions_from_centralized(
        self, content: str, file_name: str
    ) -> None:
        """
        Extract ID definitions from centralized AccessibilityIdentifiers file.

        Args:
            content: File content
            file_name: Name of the file
        """
        # Pattern: static let identifier = "ID" or case identifier = "ID"
        patterns = [
            r'static\s+let\s+\w+\s*=\s*"([^"]+)"',
            r'case\s+\w+\s*=\s*"([^"]+)"',
            r'let\s+\w+\s*=\s*"([^"]+)"',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                id_value = match.group(1)
                # Create entry if doesn't exist (for tracking unused identifiers)
                if id_value not in self.identifiers:
                    self.identifiers[id_value] = {
                        "id": id_value,
                        "usage_count": 0,
                        "defined_in": set(),
                        "used_in_tests": set(),
                        "element_types": set(),
                        "is_centralized": True,
                    }
                self.identifiers[id_value]["defined_in"].add(file_name)
                self.identifiers[id_value]["is_centralized"] = True

    def _extract_inline_definitions(self, content: str, file_name: str) -> None:
        """
        Extract inline accessibility identifier assignments.

        Args:
            content: File content
            file_name: Name of the file
        """
        # Pattern: .accessibilityIdentifier = "ID"
        pattern = r'\.accessibilityIdentifier\s*=\s*"([^"]+)"'
        matches = re.finditer(pattern, content)

        for match in matches:
            id_value = match.group(1)
            if id_value in self.identifiers:
                self.identifiers[id_value]["defined_in"].add(file_name)

    def _detect_naming_convention(self, id_value: str) -> str:
        """
        Detect the naming convention of an identifier.

        Args:
            id_value: The identifier to check

        Returns:
            Naming convention type
        """
        # Dotted notation (e.g., "Settings.General")
        if "." in id_value:
            return "dotted_notation"

        # PascalCase (starts with uppercase)
        if id_value and id_value[0].isupper():
            return "PascalCase"

        # lowercase (all lowercase)
        if id_value.islower():
            return "lowercase"

        return "other"

    def _generate_results(self) -> Dict:
        """
        Generate the final analysis results.

        Returns:
            Dictionary containing all analysis data
        """
        # Convert sets to lists for JSON serialization
        identifiers_list = []
        naming_conventions: Dict[str, int] = defaultdict(int)

        for id_value, data in self.identifiers.items():
            # Detect naming convention
            convention = self._detect_naming_convention(id_value)
            naming_conventions[convention] += 1

            # Format identifier data
            identifier_data = {
                "id": id_value,
                "usage_count": data["usage_count"],
                "element_types": sorted(list(data["element_types"])),
                "used_in_tests": sorted(list(data["used_in_tests"])),
                "defined_in": (
                    sorted(list(data["defined_in"]))
                    if data["defined_in"]
                    else ["(inline in tests)"]
                ),
                "is_centralized": data["is_centralized"],
            }
            identifiers_list.append(identifier_data)

        # Sort by usage count (descending)
        identifiers_list.sort(key=lambda x: x["usage_count"], reverse=True)

        # Get top 20 most used
        top_20 = [
            {"id": item["id"], "usage_count": item["usage_count"]}
            for item in identifiers_list[:20]
        ]

        # Get unused identifiers (defined but never used in tests)
        unused_ids = [
            item["id"] for item in identifiers_list if item["usage_count"] == 0
        ]

        # Calculate totals
        total_unique_ids = len(self.identifiers)
        total_usage_count = sum(
            data["usage_count"] for data in self.identifiers.values()
        )

        return {
            "total_unique_ids": total_unique_ids,
            "total_usage_count": total_usage_count,
            "identifiers": identifiers_list,
            "naming_conventions": {
                "PascalCase": naming_conventions.get("PascalCase", 0),
                "lowercase": naming_conventions.get("lowercase", 0),
                "dotted_notation": naming_conventions.get("dotted_notation", 0),
            },
            "top_20_most_used": top_20,
            "unused_identifiers": unused_ids,
            "unused_count": len(unused_ids),
        }


def analyze_accessibility_ids(
    project_path: Path,
    test_path: Optional[Path] = None,
    source_path: Optional[Path] = None,
) -> Dict:
    """
    Convenience function to analyze accessibility identifiers.

    Args:
        project_path: Root path of the iOS project
        test_path: Optional custom path to test files
        source_path: Optional custom path to source files

    Returns:
        Dictionary containing analysis results
    """
    analyzer = AccessibilityAnalyzer(project_path)
    return analyzer.analyze(test_path, source_path)
