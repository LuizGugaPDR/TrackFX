# screen.py
# Captura de tela para o Presentation Mode.
# Responsabilidade única: capturar frames da tela via mss e retornar BGR (OpenCV).
#
# Interface idêntica a CameraCapture:
#   sc = ScreenCapture()
#   sc.open()          → bool
#   sc.read()          → (bool, frame_bgr)
#   sc.release()       → None
#   sc.frame_size()    → (width, height)
#
# NÃO contém lógica de efeitos.
# NÃO contém lógica de tracking.

import logging
import cv2
import numpy as np
import config

logger = logging.getLogger(__name__)


class ScreenCapture:
    """
    Captura de tela via mss.

    Suporte a múltiplos monitores via SCREEN_MONITOR_INDEX (config.py).
    mss usa índice 1-based: monitor 1 = principal, 2 = secundário, etc.
    O índice 0 captura todos os monitores combinados.

    O frame retornado por read() é sempre BGR uint8, redimensionado para
    SCREEN_TARGET_WIDTH × SCREEN_TARGET_HEIGHT se a resolução nativa diferir.
    """

    def __init__(self):
        self._sct        = None
        self._monitor    = None
        self._target_w   = config.SCREEN_TARGET_WIDTH
        self._target_h   = config.SCREEN_TARGET_HEIGHT
        self._native_w   = 0
        self._native_h   = 0
        self._needs_resize = False

    # ------------------------------------------------------------------
    def open(self) -> bool:
        try:
            import mss
        except ImportError:
            logger.error(
                "mss não instalado. Execute: pip install mss>=9.0.0"
            )
            return False

        try:
            self._sct = mss.mss()
        except Exception as e:
            logger.error("Falha ao inicializar mss: %s", e)
            return False

        monitors = self._sct.monitors  # índice 0 = all, 1..N = individuais
        idx = config.SCREEN_MONITOR_INDEX

        if idx < 0 or idx >= len(monitors):
            logger.error(
                "SCREEN_MONITOR_INDEX=%d inválido. Monitores disponíveis: 0..%d",
                idx, len(monitors) - 1,
            )
            self._sct.close()
            self._sct = None
            return False

        self._monitor  = monitors[idx]
        self._native_w = self._monitor["width"]
        self._native_h = self._monitor["height"]
        self._needs_resize = (
            self._native_w != self._target_w
            or self._native_h != self._target_h
        )

        logger.info(
            "ScreenCapture iniciada: monitor=%d  nativo=%dx%d  saída=%dx%d",
            idx,
            self._native_w, self._native_h,
            self._target_w, self._target_h,
        )
        return True

    # ------------------------------------------------------------------
    def read(self):
        """
        Captura um frame da tela.

        Retorna:
            (True, frame_bgr)  — sucesso
            (False, None)      — falha ou não inicializado
        """
        if self._sct is None or self._monitor is None:
            return False, None

        try:
            shot = self._sct.grab(self._monitor)  # BGRA uint8
        except Exception as e:
            logger.warning("ScreenCapture.read() falhou: %s", e)
            return False, None

        # mss retorna BGRA — descartar canal alpha
        frame = np.array(shot, dtype=np.uint8)[:, :, :3]  # → BGR

        if self._needs_resize:
            frame = cv2.resize(
                frame,
                (self._target_w, self._target_h),
                interpolation=cv2.INTER_LINEAR,
            )

        return True, frame

    # ------------------------------------------------------------------
    def frame_size(self):
        """Retorna (width, height) do frame de saída."""
        return self._target_w, self._target_h

    # ------------------------------------------------------------------
    def release(self):
        if self._sct is not None:
            self._sct.close()
            self._sct    = None
            self._monitor = None
            logger.info("ScreenCapture liberada.")
