"""
M7 — Face Verification Model Manager
====================================
Manages the lifecycle of the InsightFace FaceAnalysis singleton instance.
Guarantees lazy loading, thread-safe caching, and clean testability.

Owner: P4 (Identity & Records)
"""

import logging
import threading
from typing import Any, Optional

from backend.app.modules.m7_face.config import (
    DETECTION_SIZE,
    DETECTION_THRESHOLD,
    EXECUTION_PROVIDERS,
    INSIGHTFACE_MODEL_NAME,
)

logger = logging.getLogger(__name__)


class ModelInitializationError(RuntimeError):
    """Raised when InsightFace model loading or preparation fails."""
    pass


class FaceModelManager:
    """
    Singleton manager for the InsightFace FaceAnalysis instance.

    Ensures:
    - Lazy loading: No model or weights are loaded at module import time.
    - Singleton reuse: A single instance is shared across screening requests.
    - Testability: Allows cache clearing or manual model injection for testing.
    """

    _instance: Optional[Any] = None
    _lock: threading.Lock = threading.Lock()

    @classmethod
    def get_model(cls) -> Any:
        """
        Return the cached FaceAnalysis instance, initializing it on first call.

        Returns:
            Configured and prepared FaceAnalysis instance.

        Raises:
            ModelInitializationError: If InsightFace is missing or initialization fails.
        """
        if cls._instance is not None:
            return cls._instance

        with cls._lock:
            # Double-checked locking
            if cls._instance is not None:
                return cls._instance

            cls._instance = cls._load_model()
            return cls._instance

    @classmethod
    def _load_model(cls) -> Any:
        """
        Instantiate and prepare the InsightFace FaceAnalysis model.
        """
        try:
            from insightface.app import FaceAnalysis
        except ImportError as err:
            raise ModelInitializationError(
                "InsightFace is not installed or dependencies are missing. "
                "Ensure 'insightface' and 'onnxruntime' are installed in the active Python environment."
            ) from err

        try:
            logger.info(
                "Initializing InsightFace model '%s' with providers %s...",
                INSIGHTFACE_MODEL_NAME,
                EXECUTION_PROVIDERS,
            )
            app = FaceAnalysis(
                name=INSIGHTFACE_MODEL_NAME,
                providers=list(EXECUTION_PROVIDERS),
            )

            # Prepare models (SCRFD detector and ArcFace recognizer)
            # ctx_id=0 uses CPU execution provider as configured
            try:
                app.prepare(
                    ctx_id=0,
                    det_size=DETECTION_SIZE,
                    det_thresh=DETECTION_THRESHOLD,
                )
            except TypeError:
                # Some versions of insightface do not take det_thresh in prepare()
                app.prepare(ctx_id=0, det_size=DETECTION_SIZE)
                if hasattr(app, "det_model") and hasattr(app.det_model, "det_thresh"):
                    app.det_model.det_thresh = DETECTION_THRESHOLD

            logger.info("InsightFace model '%s' successfully initialized and prepared.", INSIGHTFACE_MODEL_NAME)
            return app

        except Exception as err:
            raise ModelInitializationError(
                f"Failed to initialize InsightFace model '{INSIGHTFACE_MODEL_NAME}': {err}"
            ) from err

    @classmethod
    def set_model(cls, model: Optional[Any]) -> None:
        """
        Manually inject a model instance (useful for test doubles or mocks).
        """
        with cls._lock:
            cls._instance = model

    @classmethod
    def reset(cls) -> None:
        """
        Clear the cached model instance.
        """
        with cls._lock:
            cls._instance = None

    @classmethod
    def is_loaded(cls) -> bool:
        """
        Check if the model instance is currently loaded in memory.
        """
        return cls._instance is not None


# Convenient module-level aliases
get_face_analyzer = FaceModelManager.get_model
reset_face_analyzer = FaceModelManager.reset
