#!/usr/bin/env python3
"""
PotatoClaw Deterministic Verifier (Phase 7)
Replaces expensive semantic model verification with 100% deterministic code checks
for files, exit codes, DOM/URL state, JSON schema, and tests.
"""

import os
import re
import json
from typing import Dict, Any, Optional, Union

class VerificationResult:
    def __init__(
        self,
        passed: bool,
        method: str = "deterministic",
        reason: str = "",
        diagnostics: Optional[Dict[str, Any]] = None,
    ):
        self.passed = passed
        self.method = method
        self.reason = reason.strip()
        self.diagnostics = dict(diagnostics or {})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "method": self.method,
            "reason": self.reason,
            "diagnostics": self.diagnostics,
        }


class DeterministicVerifier:
    """
    Validates task success and state transitions deterministically.
    """
    @staticmethod
    def verify_file_exists(path: str, min_bytes: int = 1) -> VerificationResult:
        """Verifies file existence and minimum size."""
        if not os.path.exists(path):
            return VerificationResult(
                passed=False,
                method="deterministic_fs",
                reason=f"File does not exist: '{path}'",
                diagnostics={"path": path, "exists": False},
            )
        try:
            size = os.path.getsize(path)
            if size < min_bytes:
                return VerificationResult(
                    passed=False,
                    method="deterministic_fs",
                    reason=f"File '{path}' size {size}B < required {min_bytes}B",
                    diagnostics={"path": path, "size_bytes": size, "min_bytes": min_bytes},
                )
            return VerificationResult(
                passed=True,
                method="deterministic_fs",
                reason=f"File exists and is valid ({size} bytes)",
                diagnostics={"path": path, "size_bytes": size},
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                method="deterministic_fs",
                reason=f"Error accessing file '{path}': {e}",
            )

    @staticmethod
    def verify_file_content_matches(path: str, pattern: str) -> VerificationResult:
        """Verifies file contains a substring or matches regex pattern."""
        fs_check = DeterministicVerifier.verify_file_exists(path)
        if not fs_check.passed:
            return fs_check
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            if re.search(pattern, content):
                return VerificationResult(
                    passed=True,
                    method="deterministic_fs_pattern",
                    reason=f"File matches pattern: '{pattern}'",
                )
            return VerificationResult(
                passed=False,
                method="deterministic_fs_pattern",
                reason=f"File does not contain expected pattern '{pattern}'",
            )
        except Exception as e:
            return VerificationResult(passed=False, reason=str(e))

    @staticmethod
    def verify_exit_code(exit_code: int, expected: int = 0) -> VerificationResult:
        """Verifies terminal command returncode."""
        passed = (exit_code == expected)
        return VerificationResult(
            passed=passed,
            method="deterministic_exit_code",
            reason=f"Command exit code {exit_code} == {expected}" if passed else f"Command failed with exit code {exit_code} (expected {expected})",
            diagnostics={"exit_code": exit_code, "expected": expected},
        )

    @staticmethod
    def verify_terminal_output_contains(stdout: str, required_text: str) -> VerificationResult:
        """Verifies stdout contains expected string or phrase."""
        passed = required_text.lower() in stdout.lower()
        return VerificationResult(
            passed=passed,
            method="deterministic_stdout_match",
            reason=f"Output contains '{required_text}'" if passed else f"Output missing '{required_text}'",
        )

    @staticmethod
    def verify_browser_url(actual_url: str, expected_substr: str) -> VerificationResult:
        """Verifies browser URL matches target domain/path."""
        passed = expected_substr.lower() in actual_url.lower()
        return VerificationResult(
            passed=passed,
            method="deterministic_browser_url",
            reason=f"URL matches expected target: '{expected_substr}'" if passed else f"URL '{actual_url}' does not match '{expected_substr}'",
            diagnostics={"actual_url": actual_url, "expected": expected_substr},
        )

    @staticmethod
    def verify_browser_title(actual_title: str, expected_substr: str) -> VerificationResult:
        """Verifies browser title contains expected text."""
        passed = expected_substr.lower() in actual_title.lower()
        return VerificationResult(
            passed=passed,
            method="deterministic_browser_title",
            reason=f"Title matches: '{actual_title}'" if passed else f"Title '{actual_title}' does not contain '{expected_substr}'",
        )

    @staticmethod
    def verify_json_schema(raw_json: Union[str, Dict[str, Any]], required_keys: list) -> VerificationResult:
        """Verifies JSON validity and presence of required keys."""
        try:
            data = json.loads(raw_json) if isinstance(raw_json, str) else raw_json
            missing = [k for k in required_keys if k not in data]
            if missing:
                return VerificationResult(
                    passed=False,
                    method="deterministic_json_schema",
                    reason=f"JSON missing required keys: {missing}",
                    diagnostics={"missing_keys": missing},
                )
            return VerificationResult(
                passed=True,
                method="deterministic_json_schema",
                reason=f"Valid JSON with required keys: {required_keys}",
            )
        except Exception as e:
            return VerificationResult(
                passed=False,
                method="deterministic_json_schema",
                reason=f"Invalid JSON: {e}",
            )
