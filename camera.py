# camera.py
# Responsável pela captura de frames via webcam.
# Inclui logging de inicialização e falha ao abrir a câmera.

import logging
import cv2
import config

logger = logging.getLogger(__name__)


class CameraCapture:
    def __init__(self):
        self._cap = None

    def open(self):
        logger.info("Inicializando câmera (index=%d)...", config.CAMERA_INDEX)
        self._cap = cv2.VideoCapture(config.CAMERA_INDEX)

        if not self._cap.isOpened():
            logger.error("Falha ao abrir a câmera (index=%d).", config.CAMERA_INDEX)
            return False

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.FRAME_WIDTH)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)
        self._cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)

        logger.info(
            "Câmera inicializada: %dx%d @ %dfps",
            config.FRAME_WIDTH,
            config.FRAME_HEIGHT,
            config.TARGET_FPS,
        )
        return True

    def read(self):
        if self._cap is None:
            return False, None
        return self._cap.read()

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            logger.info("Câmera liberada.")
