import re
from typing import Optional
from dataclasses import dataclass

# Multiplication table for Dihedral group D5
_D_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]

# Permutation table
_P_TABLE = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]

# Inverse table
_INV_TABLE = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def validate_verhoeff(num_str: str) -> bool:
    """
    Validates a numeric string using the Verhoeff checksum algorithm.
    Returns True if the check digit is valid, False otherwise.
    """
    if not num_str or not num_str.isdigit():
        return False
    c = 0
    for i, item in enumerate(reversed(num_str)):
        c = _D_TABLE[c][_P_TABLE[i % 8][int(item)]]
    return c == 0


def generate_verhoeff(num_str: str) -> str:
    """
    Generates the Verhoeff check digit for a string of digits.
    """
    if not num_str or not num_str.isdigit():
        raise ValueError("Input must be a non-empty string of digits")
    c = 0
    for i, item in enumerate(reversed(num_str)):
        c = _D_TABLE[c][_P_TABLE[(i + 1) % 8][int(item)]]
    return str(_INV_TABLE[c])


def format_aadhaar_number(clean_digits: str) -> str:
    """
    Formats a 12-digit Aadhaar number string as 'XXXX XXXX XXXX'.
    If not 12 digits, returns original string.
    """
    if len(clean_digits) == 12 and clean_digits.isdigit():
        return f"{clean_digits[:4]} {clean_digits[4:8]} {clean_digits[8:]}"
    return clean_digits


@dataclass
class AadhaarNumberValidation:
    raw_number: Optional[str]
    clean_number: Optional[str]
    formatted_number: Optional[str]
    is_12_digits: bool
    checksum_valid: Optional[bool]
    is_valid: bool


class AadhaarValidationService:
    """
    Service to validate and normalize extracted Aadhaar card numbers.
    """

    @classmethod
    def validate_aadhaar_number(cls, raw_number: Optional[str]) -> AadhaarNumberValidation:
        """
        Validates Aadhaar number:
        - Cleans non-digit characters (e.g. whitespace, dashes).
        - Verifies 12-digit requirement.
        - Runs Verhoeff checksum algorithm.
        """
        if not raw_number or not isinstance(raw_number, str):
            return AadhaarNumberValidation(
                raw_number=None,
                clean_number=None,
                formatted_number=None,
                is_12_digits=False,
                checksum_valid=None,
                is_valid=False,
            )

        clean_digits = re.sub(r"\D", "", raw_number.strip())

        if not clean_digits:
            return AadhaarNumberValidation(
                raw_number=raw_number.strip(),
                clean_number=None,
                formatted_number=None,
                is_12_digits=False,
                checksum_valid=None,
                is_valid=False,
            )

        is_12 = len(clean_digits) == 12
        formatted = format_aadhaar_number(clean_digits) if is_12 else clean_digits

        if not is_12:
            return AadhaarNumberValidation(
                raw_number=raw_number.strip(),
                clean_number=clean_digits,
                formatted_number=formatted,
                is_12_digits=False,
                checksum_valid=False,
                is_valid=False,
            )

        checksum_valid = validate_verhoeff(clean_digits)
        # Standard Aadhaar numbers are 12 digits and do not start with 0 or 1
        not_zero_or_one_start = clean_digits[0] not in {"0", "1"}
        is_valid = is_12 and checksum_valid and not_zero_or_one_start

        return AadhaarNumberValidation(
            raw_number=raw_number.strip(),
            clean_number=clean_digits,
            formatted_number=formatted,
            is_12_digits=True,
            checksum_valid=checksum_valid,
            is_valid=is_valid,
        )
