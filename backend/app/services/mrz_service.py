from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

from mrz.checker.td1 import TD1CodeChecker
from mrz.checker.td2 import TD2CodeChecker
from mrz.checker.td3 import TD3CodeChecker
import mrz.base.errors as mrz_errors

from app.models.passport import CheckDigitValidation

logger = logging.getLogger(__name__)


@dataclass
class MRZValidationResult:
    """Encapsulates the result of ICAO 9303 MRZ checksum validation."""
    is_valid: bool
    valid_score: int
    check_digits: CheckDigitValidation
    mrz_type: Optional[str] = None
    cleaned_mrz: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    parsed_fields: Optional[Dict[str, Any]] = None


class MRZValidationService:
    """
    Service responsible for normalizing and validating Machine Readable Zone (MRZ) strings
    across TD3 (passports), TD1 (ID cards), and TD2 documents according to ICAO 9303.
    """

    @classmethod
    def validate_mrz(cls, raw_mrz: Optional[str]) -> MRZValidationResult:
        """
        Validates raw MRZ text and computes ICAO 9303 check digits and integrity score.
        """
        if not raw_mrz or not isinstance(raw_mrz, str) or not raw_mrz.strip():
            return MRZValidationResult(
                is_valid=False,
                valid_score=0,
                check_digits=CheckDigitValidation(
                    number=None,
                    date_of_birth=None,
                    expiration_date=None,
                    composite=None,
                    personal_number=None,
                ),
                errors=["No MRZ text provided for validation."],
            )

        lines = cls._preprocess_lines(raw_mrz)
        if not lines:
            return MRZValidationResult(
                is_valid=False,
                valid_score=0,
                check_digits=CheckDigitValidation(
                    number=False,
                    date_of_birth=False,
                    expiration_date=False,
                    composite=False,
                    personal_number=False,
                ),
                errors=["MRZ text contains no readable lines."],
            )

        # Detect document type and select appropriate checker
        mrz_format, checker_cls = cls._detect_format_and_checker(lines)
        if not checker_cls:
            return MRZValidationResult(
                is_valid=False,
                valid_score=0,
                check_digits=CheckDigitValidation(
                    number=False,
                    date_of_birth=False,
                    expiration_date=False,
                    composite=False,
                    personal_number=False,
                ),
                cleaned_mrz="\n".join(lines),
                errors=[
                    f"Unrecognized MRZ format: {len(lines)} lines with lengths {[len(l) for l in lines]}. "
                    "Expected TD3 (2 lines x 44), TD1 (3 lines x 30), or TD2 (2 lines x 36)."
                ],
            )

        cleaned_mrz = "\n".join(lines)

        try:
            checker = checker_cls(cleaned_mrz)
            is_valid = bool(checker)

            # Extract individual check digits
            num_hash = getattr(checker, "document_number_hash", None)
            dob_hash = getattr(checker, "birth_date_hash", None)
            exp_hash = getattr(checker, "expiry_date_hash", None)
            final_hash = getattr(checker, "final_hash", None)
            opt_hash = getattr(checker, "optional_data_hash", None)

            check_digits = CheckDigitValidation(
                number=bool(num_hash) if num_hash is not None else None,
                date_of_birth=bool(dob_hash) if dob_hash is not None else None,
                expiration_date=bool(exp_hash) if exp_hash is not None else None,
                composite=bool(final_hash) if final_hash is not None else None,
                personal_number=bool(opt_hash) if opt_hash is not None else None,
            )

            # Calculate confidence score based on passing check digits
            checks_to_eval = [check_digits.number, check_digits.date_of_birth, check_digits.expiration_date, check_digits.composite]
            if check_digits.personal_number is not None:
                checks_to_eval.append(check_digits.personal_number)

            valid_checks = [c for c in checks_to_eval if c is not None]
            if valid_checks:
                passed_count = sum(1 for c in valid_checks if c is True)
                valid_score = 100 if is_valid else int((passed_count / len(valid_checks)) * 100)
            else:
                valid_score = 100 if is_valid else 0

            # Extract report errors and warnings
            errors = list(getattr(checker.report, "errors", []))
            warnings = list(getattr(checker.report, "warnings", []))

            # Parsed fields namedtuple to dict
            parsed_fields = None
            try:
                raw_fields = checker.fields()
                if hasattr(raw_fields, "_asdict"):
                    parsed_fields = raw_fields._asdict()
            except Exception:
                pass

            return MRZValidationResult(
                is_valid=is_valid,
                valid_score=valid_score,
                check_digits=check_digits,
                mrz_type=mrz_format,
                cleaned_mrz=cleaned_mrz,
                errors=errors,
                warnings=warnings,
                parsed_fields=parsed_fields,
            )

        except (mrz_errors.LengthError, mrz_errors.FieldError, mrz_errors.CountryError,
                mrz_errors.DateError, mrz_errors.SexError) as err:
            logger.warning(f"MRZ validation error: {err}")
            return MRZValidationResult(
                is_valid=False,
                valid_score=0,
                check_digits=CheckDigitValidation(
                    number=False,
                    date_of_birth=False,
                    expiration_date=False,
                    composite=False,
                    personal_number=False,
                ),
                mrz_type=mrz_format,
                cleaned_mrz=cleaned_mrz,
                errors=[str(err)],
            )
        except Exception as exc:
            logger.error(f"Unexpected error validating MRZ: {exc}", exc_info=True)
            return MRZValidationResult(
                is_valid=False,
                valid_score=0,
                check_digits=CheckDigitValidation(
                    number=False,
                    date_of_birth=False,
                    expiration_date=False,
                    composite=False,
                    personal_number=False,
                ),
                mrz_type=mrz_format,
                cleaned_mrz=cleaned_mrz,
                errors=[f"Unexpected validation error: {str(exc)}"],
            )

    @classmethod
    def _preprocess_lines(cls, raw_mrz: str) -> List[str]:
        """
        Cleans and splits the raw MRZ text into lines.
        Handles continuous single strings, removes intra-line whitespace, and upper-cases characters.
        """
        clean_text = raw_mrz.strip()

        # Split on linebreaks
        raw_lines = [line.strip().replace(" ", "").upper() for line in clean_text.splitlines() if line.strip()]

        if len(raw_lines) == 1:
            single = raw_lines[0]
            # Handle continuous strings without newline separators
            if len(single) == 88:
                return [single[:44], single[44:]]
            elif len(single) == 90:
                return [single[:30], single[30:60], single[60:90]]
            elif len(single) == 72:
                return [single[:36], single[36:72]]

        return raw_lines

    @classmethod
    def _detect_format_and_checker(cls, lines: List[str]):
        """
        Identifies whether lines match TD3 (passport), TD1 (ID card), or TD2 (visa/card).
        Returns a tuple of (format_name, checker_class) or (None, None).
        """
        num_lines = len(lines)

        # TD3: Passports (2 lines, 44 chars each)
        if num_lines == 2 and all(len(l) == 44 for l in lines):
            return "TD3", TD3CodeChecker

        # TD1: Identity cards (3 lines, 30 chars each)
        if num_lines == 3 and all(len(l) == 30 for l in lines):
            return "TD1", TD1CodeChecker

        # TD2: Official travel cards / Visas (2 lines, 36 chars each)
        if num_lines == 2 and all(len(l) == 36 for l in lines):
            return "TD2", TD2CodeChecker

        # Slight line length deviation tolerance: if 2 lines of 43-45 chars, pad/trim to 44
        if num_lines == 2 and all(42 <= len(l) <= 46 for l in lines):
            normalized = [cls._adjust_line_length(l, 44) for l in lines]
            lines.clear()
            lines.extend(normalized)
            return "TD3", TD3CodeChecker

        # If 3 lines of 29-31 chars, pad/trim to 30
        if num_lines == 3 and all(28 <= len(l) <= 32 for l in lines):
            normalized = [cls._adjust_line_length(l, 30) for l in lines]
            lines.clear()
            lines.extend(normalized)
            return "TD1", TD1CodeChecker

        return None, None

    @staticmethod
    def _adjust_line_length(line: str, target: int) -> str:
        """Pads with '<' or trims to target length."""
        if len(line) < target:
            return line + ("<" * (target - len(line)))
        return line[:target]
