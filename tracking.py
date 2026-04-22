# tracking.py
# Detecção de landmarks via MediaPipe Tasks API (Hand Landmarker).
# Estruturado para futura expansão para Pose sem refatoração.
# Trata corretamente ausência de detecção (sem travar, sem erro).
# NÃO usa mp.solutions — API completamente migrada para mediapipe.tasks.

import logging
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
except ImportError as e:
    raise SystemExit(
        f"[TrackFX] Erro de dependência: {e}\n"
        "Execute: pip install mediapipe>=0.10.30"
    ) from e

import config

logger = logging.getLogger(__name__)

_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
)

# Conexões entre landmarks para desenho com OpenCV puro
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]


def _ensure_model():
    model_path = Path(config.MODEL_PATH)
    if model_path.exists():
        return
    logger.info("Modelo não encontrado. Baixando de %s ...", _MODEL_URL)
    try:
        urllib.request.urlretrieve(_MODEL_URL, model_path)
        logger.info("Modelo salvo em: %s", model_path)
    except Exception as e:
        raise SystemExit(
            f"[TrackFX] Falha ao baixar o modelo: {e}\n"
            f"Baixe manualmente e salve como '{config.MODEL_PATH}':\n{_MODEL_URL}"
        ) from e


class HandTracker:
    def __init__(self):
        _ensure_model()
        base_options = mp_python.BaseOptions(model_asset_path=config.MODEL_PATH)
        options = mp_vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.7,
            min_hand_presence_confidence=0.7,
            min_tracking_confidence=0.5,
        )
        self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
        self.landmarks = []  # List[List[NormalizedLandmark]]

    def process(self, frame_rgb):
        timestamp_ms = int(time.monotonic() * 1000)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._landmarker.detect_for_video(mp_image, timestamp_ms)
        self.landmarks = result.hand_landmarks if result.hand_landmarks else []

    def has_detections(self):
        return len(self.landmarks) > 0

    def get_bounding_boxes(self, height, width):
        """Retorna lista de (x1, y1, x2, y2) em pixels para cada mão detectada."""
        boxes = []
        for hand_landmarks in self.landmarks:
            xs = [int(lm.x * width) for lm in hand_landmarks]
            ys = [int(lm.y * height) for lm in hand_landmarks]
            x1, y1 = max(0, min(xs)), max(0, min(ys))
            x2, y2 = min(width, max(xs)), min(height, max(ys))
            boxes.append((x1, y1, x2, y2))
        return boxes

    def get_mask(self, height, width):
        """Retorna máscara binária uint8 usando convex hull de cada mão detectada."""
        mask = np.zeros((height, width), dtype=np.uint8)
        for hand_landmarks in self.landmarks:
            points = np.array(
                [[int(lm.x * width), int(lm.y * height)] for lm in hand_landmarks],
                dtype=np.int32,
            )
            hull = cv2.convexHull(points)
            cv2.fillConvexPoly(mask, hull, 255)
        return mask

    def release(self):
        self._landmarker.close()


# ---------------------------------------------------------------------------
# BodySegmenter — segmentação de pessoa via MediaPipe ImageSegmenter
# Usado pelo HUDBehindEffect para compor HUD atrás do corpo
# ---------------------------------------------------------------------------

_SEG_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/"
    "image_segmenter/selfie_segmenter/float16/latest/selfie_segmenter.tflite"
)


def _ensure_seg_model():
    from pathlib import Path as _Path
    import config as _config
    path = _Path(_config.SEG_MODEL_PATH)
    if path.exists():
        return str(path)
    logger.info("Selfie segmenter não encontrado. Baixando de %s ...", _SEG_MODEL_URL)
    urllib.request.urlretrieve(_SEG_MODEL_URL, path)
    logger.info("Modelo salvo: %s", path)
    return str(path)


class BodySegmenter:
    """
    Segmentação de pessoa em tempo real via MediaPipe Tasks ImageSegmenter.
    - RunningMode.VIDEO para consistência temporal
    - Retorna máscara uint8: 255=pessoa, 0=fundo
    - Fallback automático se modelo indisponível (retorna None → efeito usa hand mask)
    """

    def __init__(self):
        self._segmenter = None
        self._ok        = None   # None=não testado, True=pronto, False=falhou

    def _init(self):
        if self._ok is not None:
            return self._ok
        try:
            model_path = _ensure_seg_model()
            base_opts  = mp_python.BaseOptions(model_asset_path=model_path)
            options    = mp_vision.ImageSegmenterOptions(
                base_options=base_opts,
                running_mode=mp_vision.RunningMode.VIDEO,
                output_category_mask=True,
            )
            self._segmenter = mp_vision.ImageSegmenter.create_from_options(options)
            self._ok = True
            logger.info("BodySegmenter pronto.")
        except Exception as e:
            logger.warning(
                "BodySegmenter indisponível: %s  →  HUD usará hand-mask como fallback.", e
            )
            self._ok = False
        return self._ok

    def get_mask(self, frame_rgb, timestamp_ms):
        """
        Retorna (h, w) uint8 mask: 255=pessoa, 0=fundo.
        Retorna None se segmentador indisponível.
        """
        if not self._init():
            return None
        try:
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
            result = self._segmenter.segment_for_video(mp_img, timestamp_ms)
            arr = result.category_mask.numpy_view()
            # selfie_segmenter: categoria 1 = pessoa, 0 = fundo
            return np.where(arr == 1, np.uint8(255), np.uint8(0))
        except Exception as e:
            logger.debug("BodySegmenter.get_mask falhou: %s", e)
            return None

    def release(self):
        if self._segmenter:
            self._segmenter.close()

