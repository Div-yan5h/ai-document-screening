"""
M2 — Document Classification (MobileNetV3-Small + Heuristic Fallback)
======================================================================
Implements lightweight MobileNet-based document classification with
confidence thresholding and rule-based heuristic fallback.

Target Classes:
- passport
- visa
- id_card
- unknown

Owner: P2
"""

import os
from typing import List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import transforms
from torchvision.models import mobilenet_v3_small

TARGET_CLASSES: Tuple[str, ...] = ("passport", "visa", "id_card", "unknown")
DEFAULT_CLASS: str = "unknown"

# Build Spec §3 M2: Confidence threshold (~0.6) for reliable classification
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.6

# Default checkpoint path for trained MobileNetV3-Small classifier
DEFAULT_MODEL_PATH: str = os.path.normpath(
    os.path.join(
        os.path.dirname(__file__),
        "models",
        "m2_classifier",
        "m2_classifier.pth",
    )
)


class DocumentClassifier:
    """
    Hybrid Document Classifier combining lightweight MobileNetV3-Small
    with confidence thresholding and aspect-ratio/MRZ heuristic fallback.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        device: Optional[str] = None,
    ):
        if model_path is not None:
            self.model_path = model_path
        elif os.path.exists(DEFAULT_MODEL_PATH):
            self.model_path = DEFAULT_MODEL_PATH
        else:
            self.model_path = None

        self.confidence_threshold = confidence_threshold
        self.target_classes = TARGET_CLASSES
        self._is_loaded = False

        # Device selection: cpu or cuda
        if device:
            self.device = torch.device(device)
        else:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

        # Standard MobileNetV3 input preprocessing pipeline
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        # Initialize MobileNetV3-Small architecture with custom classification head
        self.model = self._build_model()

        # Load weights if provided
        if self.model_path:
            self.load_model(self.model_path)

    def _build_model(self) -> nn.Module:
        """
        Builds the MobileNetV3-Small model with a classification head
        sized for TARGET_CLASSES (4 classes).
        """
        model = mobilenet_v3_small(weights=None)
        in_features = model.classifier[3].in_features
        model.classifier[3] = nn.Linear(in_features, len(self.target_classes))
        model.to(self.device)
        model.eval()
        return model

    def load_model(self, model_path: Optional[str] = None) -> bool:
        """
        Loads model weights from a specified file path.
        Handles missing or corrupt weights safely without crashing.
        """
        target_path = model_path or self.model_path
        if not target_path or not os.path.exists(target_path):
            self._is_loaded = False
            return False

        try:
            checkpoint = torch.load(target_path, map_location=self.device)
            if isinstance(checkpoint, dict) and "state_dict" in checkpoint:
                self.model.load_state_dict(checkpoint["state_dict"])
            elif isinstance(checkpoint, dict):
                self.model.load_state_dict(checkpoint)
            elif isinstance(checkpoint, nn.Module):
                self.model = checkpoint
            self.model.to(self.device)
            self.model.eval()
            self._is_loaded = True
            return True
        except Exception:
            self._is_loaded = False
            return False

    def preprocess(self, image_path: str) -> Optional[torch.Tensor]:
        """
        Loads and preprocesses an image from disk for MobileNet inference.
        Returns:
            torch.Tensor of shape (1, 3, 224, 224) or None if loading fails.
        """
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            image = Image.open(image_path).convert("RGB")
            tensor = self.transform(image)
            return tensor.unsqueeze(0)
        except Exception:
            return None

    def _detect_mrz_pattern(self, bottom_crop: Image.Image) -> bool:
        """
        Detects high-frequency alternating text patterns and horizontal line
        structure indicative of an MRZ zone in the bottom crop.
        """
        try:
            arr = np.array(bottom_crop, dtype=np.float32)
            h, w = arr.shape
            if h < 8 or w < 20:
                return False

            # Calculate horizontal gradients (transitions along each row)
            diffs = np.abs(np.diff(arr, axis=1))
            row_variations = np.mean(diffs, axis=1)

            # In an MRZ region, text lines produce distinct high-frequency horizontal rows
            mean_variation = float(np.mean(row_variations))
            if mean_variation < 4.0:
                return False

            active_threshold = mean_variation * 0.8
            active_rows = row_variations > active_threshold

            # Count line transitions between non-text and text
            transitions = int(np.sum(np.diff(active_rows.astype(int)) != 0))

            return bool(transitions >= 2 and mean_variation >= 5.0)
        except Exception:
            return False

    def classify_heuristic(self, image_path: str) -> Tuple[str, float]:
        """
        Lightweight heuristic fallback classifier using aspect ratio and
        bottom MRZ text pattern detection.

        Standards used:
        - Passport (TD3 standard: 125mm x 88mm -> ~1.42 aspect ratio + bottom MRZ)
        - ID Card (TD1 standard: 85.6mm x 53.98mm -> ~1.586 aspect ratio)
        - Visa (TD2 standard or visa sticker: ~1.20 - 1.34 aspect ratio)

        Returns:
            Tuple of (doc_type, confidence)
        """
        if not image_path or not os.path.exists(image_path):
            return DEFAULT_CLASS, 0.0

        try:
            with Image.open(image_path) as img:
                w, h = img.size
                if w <= 0 or h <= 0:
                    return DEFAULT_CLASS, 0.0

                # Normalize aspect ratio (landscape: width >= height)
                aspect_ratio = max(w, h) / min(w, h)

                # Crop bottom zone (approx bottom 22% of document) for MRZ analysis
                oriented_img = img if w >= h else img.rotate(90, expand=True)
                ow, oh = oriented_img.size

                bottom_h = int(oh * 0.22)
                if bottom_h < 8 or ow < 20:
                    has_mrz = False
                else:
                    bottom_crop = oriented_img.crop((0, oh - bottom_h, ow, oh)).convert("L")
                    has_mrz = self._detect_mrz_pattern(bottom_crop)

                # 1. Passport: TD3 ratio ~1.42 (1.35 to 1.50) with bottom MRZ band
                if 1.35 <= aspect_ratio <= 1.50 and has_mrz:
                    return "passport", 0.75

                # 2. ID Card: TD1 ratio ~1.586 (1.52 to 1.68)
                if 1.52 <= aspect_ratio <= 1.68:
                    confidence = 0.75 if has_mrz else 0.68
                    return "id_card", confidence

                # 3. Visa: TD2 / sticker ratio (1.20 to 1.34) or (1.35 to 1.48 without MRZ)
                if 1.20 <= aspect_ratio <= 1.34:
                    return "visa", 0.65
                if 1.35 <= aspect_ratio <= 1.48 and not has_mrz:
                    return "visa", 0.62
                return DEFAULT_CLASS, 0.0
        except Exception:
            return DEFAULT_CLASS, 0.0

    def predict(self, image_path: str) -> Tuple[str, float, Optional[List[int]]]:
        """
        Run document classification with confidence thresholding and
        heuristic fallback.

        Flow:
        1. If image is missing/unreadable -> ("unknown", 0.0, None)
        2. If model weights loaded -> run MobileNet inference
        3. If model confidence >= threshold (~0.6) -> return model prediction
        4. If model confidence < threshold or weights unavailable -> run heuristic fallback
        5. If heuristic confidence >= threshold -> return heuristic prediction
        6. If neither is confident -> return ("unknown", low_confidence, None)

        Returns:
            Tuple of (doc_type, confidence, doc_bbox):
            - doc_type: One of TARGET_CLASSES
            - confidence: float between 0.0 and 1.0
            - doc_bbox: None (classification only)
        """
        # Safety check: Verify image exists and is readable
        if not image_path or not os.path.exists(image_path):
            return DEFAULT_CLASS, 0.0, None

        mobilenet_doc_type = DEFAULT_CLASS
        mobilenet_confidence = 0.0

        # Attempt MobileNet inference if model weights are loaded
        if self._is_loaded:
            tensor = self.preprocess(image_path)
            if tensor is not None:
                try:
                    with torch.no_grad():
                        tensor = tensor.to(self.device)
                        logits = self.model(tensor)
                        probabilities = torch.softmax(logits, dim=1)[0]
                        top_prob, top_idx = torch.max(probabilities, dim=0)

                        conf = float(top_prob.item())
                        class_idx = int(top_idx.item())
                        if 0 <= class_idx < len(self.target_classes):
                            mobilenet_doc_type = self.target_classes[class_idx]
                            if mobilenet_doc_type == DEFAULT_CLASS:
                                mobilenet_confidence = 0.0
                            else:
                                mobilenet_confidence = max(0.0, min(1.0, conf))
                except Exception:
                    mobilenet_doc_type = DEFAULT_CLASS
                    mobilenet_confidence = 0.0

        # Case 1: High-confidence MobileNet prediction (>= threshold)
        if (
            mobilenet_confidence >= self.confidence_threshold
            and mobilenet_doc_type != DEFAULT_CLASS
        ):
            return mobilenet_doc_type, mobilenet_confidence, None

        # Case 2: Model unavailable or confidence below threshold -> Heuristic fallback
        heuristic_doc_type, heuristic_confidence = self.classify_heuristic(image_path)
        if (
            heuristic_doc_type != DEFAULT_CLASS
            and heuristic_confidence >= self.confidence_threshold
        ):
            return heuristic_doc_type, heuristic_confidence, None

        # Case 3: Neither can classify reliably -> return unknown with low confidence
        # Never return a low-confidence document type as a confident classification
        return DEFAULT_CLASS, mobilenet_confidence, None
