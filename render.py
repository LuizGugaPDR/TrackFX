# render.py
# Responsável exclusivamente por:
#   - Exibir o frame na janela
#   - Mostrar FPS
#   - Overlays simples de debug
#   - Captura de input do usuário (ex: tecla para sair)
# NÃO contém lógica de tracking nem de efeitos.

import time
import cv2
import config
from tracking import HAND_CONNECTIONS


class Renderer:
    def __init__(self):
        self._prev_time = time.time()
        self._fps = 0.0

    def _compute_fps(self):
        now = time.time()
        elapsed = now - self._prev_time
        self._fps = 1.0 / elapsed if elapsed > 0 else 0.0
        self._prev_time = now

    def draw_landmarks(self, frame, landmarks_list):
        if not config.SHOW_LANDMARKS or not landmarks_list:
            return
        h, w = frame.shape[:2]
        for hand_landmarks in landmarks_list:
            # Conexões
            for start_idx, end_idx in HAND_CONNECTIONS:
                p1 = hand_landmarks[start_idx]
                p2 = hand_landmarks[end_idx]
                cv2.line(
                    frame,
                    (int(p1.x * w), int(p1.y * h)),
                    (int(p2.x * w), int(p2.y * h)),
                    (0, 255, 0),
                    2,
                )
            # Pontos
            for lm in hand_landmarks:
                cv2.circle(frame, (int(lm.x * w), int(lm.y * h)), 4, (255, 0, 0), -1)

    def draw_bounding_boxes(self, frame, boxes):
        if not config.DEBUG or not boxes:
            return
        for x1, y1, x2, y2 in boxes:
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)

    def draw_debug_mask(self, frame, mask):
        if not config.SHOW_MASK or mask is None:
            return
        overlay = frame.copy()
        overlay[mask > 0] = (0, 140, 255)
        cv2.addWeighted(overlay, 0.35, frame, 0.65, 0, frame)

    def show(self, frame, active_effect=None):
        self._compute_fps()
        output = frame.copy()

        if config.SHOW_FPS:
            cv2.putText(
                output,
                f"FPS: {self._fps:.1f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 255, 0),
                2,
                cv2.LINE_AA,
            )

        if active_effect is not None and config.DEBUG:
            label = f"[{active_effect if active_effect else 'off'}]  1-5: trocar  0: off  q: sair"
            cv2.putText(
                output, label, (10, output.shape[0] - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 200), 1, cv2.LINE_AA,
            )

        if config.SHOW_ACTIVE_EFFECT_NAME and active_effect is not None:
            effect_label = active_effect
            cv2.putText(
                output, effect_label,
                (10, output.shape[0] - 15),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 200, 0), 2, cv2.LINE_AA,
            )

        cv2.imshow(config.WINDOW_NAME, output)

    def draw_pip_webcam(self, frame, webcam_frame):
        """
        Incrusta o frame da webcam como PiP (picture-in-picture) no frame destino.

        Posição controlada por config.PRESENTATION_WEBCAM_POS:
            "bottom_right" | "bottom_left" | "top_right" | "top_left"
        Tamanho controlado por config.PRESENTATION_WEBCAM_SCALE (fração da largura).
        """
        if webcam_frame is None:
            return
        fh, fw = frame.shape[:2]
        scale  = config.PRESENTATION_WEBCAM_SCALE
        pip_w  = int(fw * scale)
        pip_h  = int(fh * scale)
        pip    = cv2.resize(webcam_frame, (pip_w, pip_h), interpolation=cv2.INTER_LINEAR)

        margin = 12
        pos    = config.PRESENTATION_WEBCAM_POS
        if pos == "bottom_right":
            x1, y1 = fw - pip_w - margin, fh - pip_h - margin
        elif pos == "bottom_left":
            x1, y1 = margin, fh - pip_h - margin
        elif pos == "top_right":
            x1, y1 = fw - pip_w - margin, margin
        else:  # top_left
            x1, y1 = margin, margin

        # Clamp para não sair do frame
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(fw, x1 + pip_w)
        y2 = min(fh, y1 + pip_h)
        pip = pip[: y2 - y1, : x2 - x1]

        # Borda fina para delimitar o PiP
        cv2.rectangle(pip, (0, 0), (pip.shape[1] - 1, pip.shape[0] - 1), (60, 60, 60), 1)
        frame[y1:y2, x1:x2] = pip

    def should_quit(self, wait_ms=1):
        return cv2.waitKey(wait_ms) & 0xFF == ord("q")

    def close(self):
        cv2.destroyAllWindows()
