"""
OCR-сервис для распознавания текста из сканированных документов.

Использует Tesseract + OpenCV для предобработки изображений.
Гибридный подход: OCR с ручным подтверждением при низкой уверенности.
"""
from pathlib import Path
from typing import Optional
import io

try:
    import cv2
    import numpy as np
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

from app.config import settings


class OCRResult:
    """Результат OCR-распознавания."""
    def __init__(self, text: str, confidence: float, needs_manual_review: bool = False):
        self.text = text
        self.confidence = confidence
        self.needs_manual_review = needs_manual_review


def is_ocr_available() -> bool:
    """Проверяет доступность OCR-движка."""
    return OCR_AVAILABLE


def preprocess_image(image: np.ndarray) -> np.ndarray:
    """
    Предобработка изображения для улучшения качества OCR.
    - Конвертация в grayscale
    - Бинаризация (пороговая обработка)
    - Удаление шума
    - Выравнивание
    """
    if not OCR_AVAILABLE:
        raise RuntimeError("OpenCV не установлен")

    # Convert to grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Denoise
    denoised = cv2.fastNlMeansDenoising(gray, None, 10, 7, 21)

    # Adaptive thresholding for better binarization
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # Deskew
    coords = np.column_stack(np.where(binary > 0))
    if len(coords) > 0:
        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        if abs(angle) > 0.5:  # Only rotate if skew is significant
            (h, w) = binary.shape[:2]
            center = (w // 2, h // 2)
            matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            binary = cv2.warpAffine(
                binary, matrix, (w, h),
                flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
            )

    return binary


def ocr_image(image_path: str, lang: str = "rus") -> OCRResult:
    """
    Распознаёт текст из изображения.

    Args:
        image_path: Путь к изображению
        lang: Язык распознавания (rus, eng, rus+eng)

    Returns:
        OCRResult с текстом, уверенностью и флагом ручной проверки
    """
    if not OCR_AVAILABLE:
        return OCRResult(text="", confidence=0.0, needs_manual_review=True)

    image = cv2.imread(image_path)
    if image is None:
        return OCRResult(text="", confidence=0.0, needs_manual_review=True)

    # Preprocess
    processed = preprocess_image(image)

    # OCR with detailed data
    data = pytesseract.image_to_data(
        processed, lang=lang, output_type=pytesseract.Output.DICT
    )

    # Calculate average confidence
    confidences = [int(c) for c in data["conf"] if int(c) > 0]
    avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0

    # Extract text
    text = pytesseract.image_to_string(processed, lang=lang).strip()

    needs_review = avg_confidence < settings.OCR_CONFIDENCE_THRESHOLD

    return OCRResult(
        text=text,
        confidence=avg_confidence,
        needs_manual_review=needs_review,
    )


def ocr_region(image_path: str, x: int, y: int, w: int, h: int, lang: str = "rus") -> OCRResult:
    """
    Распознаёт текст из указанной области изображения.
    Полезно для извлечения конкретных полей (номер документа, дата подписания).
    """
    if not OCR_AVAILABLE:
        return OCRResult(text="", confidence=0.0, needs_manual_review=True)

    image = cv2.imread(image_path)
    if image is None:
        return OCRResult(text="", confidence=0.0, needs_manual_review=True)

    # Crop region
    region = image[y:y + h, x:x + w]

    # Preprocess
    processed = preprocess_image(region)

    # OCR
    text = pytesseract.image_to_string(processed, lang=lang).strip()

    data = pytesseract.image_to_data(
        processed, lang=lang, output_type=pytesseract.Output.DICT
    )
    confidences = [int(c) for c in data["conf"] if int(c) > 0]
    avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0

    return OCRResult(
        text=text,
        confidence=avg_confidence,
        needs_manual_review=avg_confidence < settings.OCR_CONFIDENCE_THRESHOLD,
    )
