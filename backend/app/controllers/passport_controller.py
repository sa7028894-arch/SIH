import os
import tempfile
import logging
from typing import Optional, Tuple
from fastapi import UploadFile, HTTPException, status
import cv2
import numpy as np
from passporteye import read_mrz
import pypdfium2 as pdfium

from app.models.passport import (
    PassportValidationResponse,
    MRZData,
    CheckDigitValidation,
)

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
ALLOWED_PDF_EXTENSIONS = {".pdf"}
ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_PDF_EXTENSIONS


class PassportController:
    """
    Controller responsible for handling passport media uploads, converting
    PDFs/images, running primary PassportEye MRZ OCR, and falling back to
    OpenCV contour localization when necessary.
    """

    @classmethod
    async def validate_passport_media(cls, upload_file: UploadFile) -> PassportValidationResponse:
        filename = upload_file.filename or "unknown_file"
        ext = os.path.splitext(filename)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Supported formats: Images (.jpg, .png, .webp, .tiff) and PDF (.pdf)."
            )

        # Save incoming file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_input:
            temp_input_path = temp_input.name
            content = await upload_file.read()
            temp_input.write(content)

        processed_image_paths = []
        crop_path = None

        try:
            # If PDF, rasterize the first page to a high-resolution image
            if ext in ALLOWED_PDF_EXTENSIONS:
                pdf_image_path = cls._rasterize_pdf_first_page(temp_input_path)
                processed_image_paths.append(pdf_image_path)
                target_image_path = pdf_image_path
            else:
                target_image_path = temp_input_path

            # 1. Primary path: PassportEye MRZ extraction
            mrz_result, extraction_method = cls._extract_mrz_with_fallback(target_image_path)

            if mrz_result is not None:
                mrz_data = cls._build_mrz_data(mrz_result, extraction_method)
                is_valid = mrz_data.mrz_valid
                message = (
                    "Passport MRZ successfully detected and validated."
                    if is_valid
                    else f"Passport MRZ detected with confidence score {mrz_data.valid_score}/100."
                )
                return PassportValidationResponse(
                    success=True,
                    mrz_detected=True,
                    message=message,
                    filename=filename,
                    data=mrz_data,
                )

            # No MRZ detected even after fallback
            return PassportValidationResponse(
                success=True,
                mrz_detected=False,
                message="No machine-readable zone (MRZ) could be detected. Please ensure the passport document is clear, straight, and well-lit.",
                filename=filename,
                data=None,
            )

        except Exception as e:
            logger.error(f"Error processing passport media '{filename}': {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing document: {str(e)}"
            )
        finally:
            # Clean up all created temporary files
            if os.path.exists(temp_input_path):
                try:
                    os.remove(temp_input_path)
                except OSError:
                    pass

            for path in processed_image_paths:
                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass

    @classmethod
    def _rasterize_pdf_first_page(cls, pdf_path: str) -> str:
        """
        Renders the first page of a PDF into a high-DPI JPEG image
        suitable for OCR and computer vision.
        """
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            if len(pdf) == 0:
                raise ValueError("PDF document has no pages")

            page = pdf[0]
            # Render at scale 3.0 (approx 216 DPI) for optimal OCR clarity
            bitmap = page.render(scale=3.0)
            pil_image = bitmap.to_pil()

            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_img:
                temp_img_path = temp_img.name
                pil_image.save(temp_img_path, format="JPEG", quality=95)

            return temp_img_path
        except Exception as err:
            logger.warning(f"pypdfium2 rasterization failed: {err}")
            raise ValueError(f"Failed to process PDF file: {err}")

    @classmethod
    def _extract_mrz_with_fallback(cls, image_path: str) -> Tuple[Optional[object], str]:
        """
        Tries PassportEye first. If no clean MRZ is found or confidence is low,
        attempts OpenCV morphological contour detection to crop the MRZ region
        and retries PassportEye on the cropped image.
        """
        # Fast path
        mrz = read_mrz(image_path)
        if mrz is not None and getattr(mrz, "valid_score", 0) >= 70:
            return mrz, "passporteye_direct"

        # Fallback path: manual OpenCV region localization
        crop_path = cls._locate_mrz_manually(image_path)
        if crop_path:
            try:
                crop_mrz = read_mrz(crop_path)
                if crop_mrz is not None:
                    return crop_mrz, "opencv_crop_fallback"
            finally:
                if os.path.exists(crop_path):
                    try:
                        os.remove(crop_path)
                    except OSError:
                        pass

        # If primary had low score but returned something, return it as a last resort
        if mrz is not None:
            return mrz, "passporteye_direct"

        return None, "none"

    @classmethod
    def _locate_mrz_manually(cls, image_path: str) -> Optional[str]:
        """
        Fallback OpenCV technique: uses blackhat + Sobel horizontal gradient +
        morphological closing to find candidate MRZ horizontal bounding boxes
        near the bottom of the document and crops them.
        """
        img = cv2.imread(image_path)
        if img is None:
            return None

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)

        # Highlight small dark text against lighter background
        rect_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (25, 7))
        blackhat = cv2.morphologyEx(gray, cv2.MORPH_BLACKHAT, rect_kernel)

        # Emphasize horizontal edges
        grad_x = cv2.Sobel(blackhat, ddepth=cv2.CV_32F, dx=1, dy=0, ksize=-1)
        grad_x = np.absolute(grad_x)
        min_val, max_val = np.min(grad_x), np.max(grad_x)
        grad_x = (255 * ((grad_x - min_val) / (max_val - min_val + 1e-6))).astype("uint8")

        grad_x = cv2.morphologyEx(grad_x, cv2.MORPH_CLOSE, rect_kernel)
        thresh = cv2.threshold(grad_x, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)[1]

        sq_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, sq_kernel)
        thresh = cv2.erode(thresh, None, iterations=4)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        h_img, w_img = gray.shape

        mrz_candidates = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            aspect_ratio = w / float(h)
            coverage = w / float(w_img)
            # MRZ lines are wide, short, and located towards the bottom
            if aspect_ratio > 4 and coverage > 0.4 and y > h_img * 0.5:
                mrz_candidates.append((x, y, w, h))

        if not mrz_candidates:
            return None

        # Merge candidate boxes
        x1 = min(c[0] for c in mrz_candidates)
        y1 = min(c[1] for c in mrz_candidates)
        x2 = max(c[0] + c[2] for c in mrz_candidates)
        y2 = max(c[1] + c[3] for c in mrz_candidates)

        pad = 15
        mrz_crop = img[max(0, y1 - pad): min(h_img, y2 + pad), max(0, x1 - pad): min(w_img, x2 + pad)]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_crop:
            crop_path = temp_crop.name
            cv2.imwrite(crop_path, mrz_crop)

        return crop_path

    @staticmethod
    def _clean_field(val: Optional[str], is_name: bool = False) -> Optional[str]:
        """
        Sanitizes MRZ fields by removing trailing and filler '<' characters.
        If is_name is True, replaces internal '<' separators with spaces and collapses whitespace.
        Returns None if the cleaned value is empty or consists solely of '<'.
        """
        if not val or not isinstance(val, str):
            return None

        s = val.strip()
        if is_name:
            # Replace '<' with spaces for name components (e.g. "ANNA<MARIA<<<<" -> "ANNA MARIA")
            s = s.replace("<", " ")
            s = " ".join(s.split())
        else:
            # Strip all leading/trailing '<' and whitespace (e.g. "L898902C3<" -> "L898902C3", "P<" -> "P")
            s = s.strip("< ").rstrip("<").strip()

        return s if s else None

    @classmethod
    def _build_mrz_data(cls, mrz, extraction_method: str) -> MRZData:
        data = mrz.to_dict()
        valid_score = int(data.get("valid_score", 0) or 0)

        names = cls._clean_field(data.get("names"), is_name=True)
        surname = cls._clean_field(data.get("surname"), is_name=True)
        if names and surname:
            full_name = f"{names} {surname}".strip()
        elif names:
            full_name = names
        elif surname:
            full_name = surname
        else:
            full_name = None

        document_number = cls._clean_field(data.get("number"))
        nationality = cls._clean_field(data.get("nationality"))
        date_of_birth = cls._clean_field(data.get("date_of_birth"))
        expiry_date = cls._clean_field(data.get("expiration_date"))
        sex = cls._clean_field(data.get("sex"))
        mrz_type = cls._clean_field(data.get("mrz_type")) or cls._clean_field(data.get("type"))
        country = cls._clean_field(data.get("country"))

        check_digits = CheckDigitValidation(
            number=data.get("valid_number"),
            date_of_birth=data.get("valid_date_of_birth"),
            expiration_date=data.get("valid_expiration_date"),
            composite=data.get("valid_composite"),
            personal_number=data.get("valid_personal_number"),
        )

        return MRZData(
            name=full_name,
            document_number=document_number,
            nationality=nationality,
            date_of_birth=date_of_birth,
            expiry_date=expiry_date,
            sex=sex,
            mrz_valid=valid_score > 80,
            valid_score=valid_score,
            mrz_type=mrz_type,
            country=country,
            raw_text=data.get("raw_text"),
            extraction_method=extraction_method,
            check_digits=check_digits,
        )
