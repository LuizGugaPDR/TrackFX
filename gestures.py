# gestures.py
# Detecção de gestos baseada em landmarks MediaPipe Tasks API.
#
# Responsabilidade única: converter landmarks em EVENTOS de controle.
# NÃO renderiza nada. NÃO conhece efeitos. NÃO acessa câmera.
#
# Arquitetura de estado:
#   idle → holding → cooldown → idle
#
#   idle:     nenhum gesto ativo
#   holding:  gesto detectado, aguardando confirmação (PINCH_HOLD_FRAMES)
#   cooldown: gesto disparado, bloqueio temporário (PINCH_COOLDOWN_FRAMES)
#
# Normalização de distância:
#   pinch_dist / hand_size   onde hand_size = dist(lm[0], lm[9])
#   → invariante à distância da câmera e tamanho de mão
#
# Índices MediaPipe usados:
#   lm[0]  = pulso (wrist)
#   lm[4]  = ponta do polegar (thumb tip)
#   lm[8]  = ponta do indicador (index tip)
#   lm[9]  = base do médio (referência de tamanho da mão)

import math
import config


class GestureDetector:
    """Máquina de estados leve para detecção de gestos por landmarks.

    Uso:
        detector = GestureDetector()

        # No loop principal (uma vez por frame):
        events = detector.update(tracker.landmarks)
        for evt in events:
            if evt == 'pinch':
                ...

        # Para feedback visual (sem custo adicional):
        progress = detector.pinch_progress()   # 0.0..1.0
        dist     = detector.pinch_dist(tracker.landmarks)  # dist normalizada
    """

    _IDLE     = 0
    _HOLDING  = 1
    _COOLDOWN = 2

    def __init__(self):
        self._state      = self._IDLE
        self._hold_count = 0
        self._cd_count   = 0

    # ------------------------------------------------------------------
    # Interface principal
    # ------------------------------------------------------------------

    def update(self, landmarks):
        """Atualiza estado com os landmarks do frame atual.

        Retorna lista de eventos disparados neste frame.
        Custo: ~microsegundos (apenas aritmética float simples).
        """
        if not landmarks:
            # Sem mão: reset imediato para idle
            self._state      = self._IDLE
            self._hold_count = 0
            return []

        events = []
        pinch  = self._is_pinch(landmarks[0])

        if self._state == self._IDLE:
            if pinch:
                self._state      = self._HOLDING
                self._hold_count = 1

        elif self._state == self._HOLDING:
            if pinch:
                self._hold_count += 1
                if self._hold_count >= config.PINCH_HOLD_FRAMES:
                    events.append('pinch')
                    self._state  = self._COOLDOWN
                    self._cd_count = 0
            else:
                # Pinch quebrado antes de confirmar → volta ao idle
                self._state      = self._IDLE
                self._hold_count = 0

        elif self._state == self._COOLDOWN:
            self._cd_count += 1
            if self._cd_count >= config.PINCH_COOLDOWN_FRAMES:
                self._state    = self._IDLE
                self._cd_count = 0

        return events

    # ------------------------------------------------------------------
    # Métodos de consulta para feedback visual (leitura de estado, sem side-effects)
    # ------------------------------------------------------------------

    def pinch_progress(self):
        """Progresso do pinch atual [0.0..1.0].

        0.0 = idle/sem gesto
        0..1 = holding (confirmação em andamento)
        1.0 = cooldown (gesto acabou de ser disparado)

        Usado para animar o indicador visual — sem parâmetros, custo zero.
        """
        if self._state == self._HOLDING:
            return min(1.0, self._hold_count / max(1, config.PINCH_HOLD_FRAMES))
        if self._state == self._COOLDOWN:
            return 1.0
        return 0.0

    def pinch_dist(self, landmarks):
        """Distância normalizada thumb_tip ↔ index_tip / hand_size [0..~2].

        < PINCH_THRESHOLD  → pinch ativo
        < PINCH_THRESHOLD * 1.8 → zona de aproximação (útil para indicador)
        """
        if not landmarks:
            return 1.0
        return self._normalized_dist(landmarks[0])

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _is_pinch(self, hand_lm):
        return self._normalized_dist(hand_lm) < config.PINCH_THRESHOLD

    def _normalized_dist(self, hand_lm):
        """Distância thumb_tip ↔ index_tip normalizada pelo tamanho da mão."""
        tx, ty = hand_lm[4].x, hand_lm[4].y
        ix, iy = hand_lm[8].x, hand_lm[8].y
        pinch_d = math.hypot(tx - ix, ty - iy)

        wx, wy = hand_lm[0].x, hand_lm[0].y
        mx, my = hand_lm[9].x, hand_lm[9].y
        hand_size = math.hypot(mx - wx, my - wy)

        if hand_size < 1e-5:
            return 1.0
        return pinch_d / hand_size


# ---------------------------------------------------------------------------
# Detecção estacionária do gesto thumb + pinky (sem máquina de estados).
# Retorna True se THUMB_TIP estiver suficientemente perto de PINKY_TIP.
# Normaliza pela largura da mão (wrist → mid_base) para ser invariante à
# distância da câmera.
#
# Índices MediaPipe:
#   lm[0]  = pulso (wrist)
#   lm[4]  = ponta do polegar (thumb tip)
#   lm[9]  = base do médio (referência de tamanho da mão)
#   lm[20] = ponta do mindinho (pinky tip)
# ---------------------------------------------------------------------------

def detect_thumb_pinky_closed(hand_lm):
    """Retorna True se thumb_tip e pinky_tip estiverem próximos (gesto fechado).

    Usa CUBE_THUMB_PINKY_THRESHOLD de config.py.
    Normaliza pela distância wrist→mid_base para ser invariante à câmera.
    """
    if not config.CUBE_THUMB_PINKY_GESTURE_ENABLED:
        return False

    tx, ty = hand_lm[4].x,  hand_lm[4].y   # thumb tip
    px, py = hand_lm[20].x, hand_lm[20].y   # pinky tip
    dist   = math.hypot(tx - px, ty - py)

    wx, wy = hand_lm[0].x, hand_lm[0].y
    mx, my = hand_lm[9].x, hand_lm[9].y
    hand_size = math.hypot(mx - wx, my - wy)

    if hand_size < 1e-5:
        return False
    return (dist / hand_size) < config.CUBE_THUMB_PINKY_THRESHOLD


# ---------------------------------------------------------------------------
# Deteção de pinch indicador + polegar (cada mão individualmente).
# Usado para controle de escala por duas mãos no FloatingCubeEffect.
#
# Índices MediaPipe:
#   lm[0]  = pulso (wrist)
#   lm[4]  = ponta do polegar (thumb tip)
#   lm[8]  = ponta do indicador (index tip)
#   lm[9]  = base do médio (referência de tamanho da mão)
# ---------------------------------------------------------------------------

def detect_index_thumb_pinch(hand_lm):
    """Retorna True se thumb_tip e index_tip estiverem próximos.

    Usa TWO_HAND_CUBE_PINCH_THRESHOLD de config.py.
    Normaliza pela distância wrist→mid_base.
    """
    tx, ty = hand_lm[4].x, hand_lm[4].y   # thumb tip
    ix, iy = hand_lm[8].x, hand_lm[8].y   # index tip
    dist   = math.hypot(tx - ix, ty - iy)

    wx, wy   = hand_lm[0].x, hand_lm[0].y
    bx, by   = hand_lm[9].x, hand_lm[9].y
    hand_size = math.hypot(bx - wx, by - wy)

    if hand_size < 1e-5:
        return False
    return (dist / hand_size) < config.TWO_HAND_CUBE_PINCH_THRESHOLD


def get_pinch_point(hand_lm, frame_w, frame_h):
    """Retorna (x, y) ponto médio entre thumb_tip e index_tip em pixels."""
    tx = hand_lm[4].x * frame_w
    ty = hand_lm[4].y * frame_h
    ix = hand_lm[8].x * frame_w
    iy = hand_lm[8].y * frame_h
    return ((tx + ix) * 0.5, (ty + iy) * 0.5)


# ---------------------------------------------------------------------------
# Deteção estacionária do gesto thumb + middle (sem máquina de estados).
# Usado para toggle das landmarks da mão.
#
# Índices MediaPipe:
#   lm[0]  = pulso (wrist)
#   lm[4]  = ponta do polegar (thumb tip)
#   lm[9]  = base do médio (referência de tamanho da mão)
#   lm[12] = ponta do dedo médio (middle finger tip)
# ---------------------------------------------------------------------------

def detect_thumb_middle_pinch(hand_lm):
    """Retorna True se thumb_tip e middle_tip estiverem próximos.

    Usa LANDMARK_THUMB_MIDDLE_THRESHOLD de config.py.
    Normaliza pela distância wrist→mid_base para ser invariante à câmera.
    """
    tx, ty = hand_lm[4].x,  hand_lm[4].y   # thumb tip
    mx, my = hand_lm[12].x, hand_lm[12].y  # middle finger tip
    dist   = math.hypot(tx - mx, ty - my)

    wx, wy   = hand_lm[0].x, hand_lm[0].y
    bx, by   = hand_lm[9].x, hand_lm[9].y
    hand_size = math.hypot(bx - wx, by - wy)

    if hand_size < 1e-5:
        return False
    return (dist / hand_size) < config.LANDMARK_THUMB_MIDDLE_THRESHOLD


# ---------------------------------------------------------------------------
# Detecção do gesto thumb + ring finger (polegar + anelar).
# Ativa o FloatingTriangleEffect.
#
# Índices MediaPipe:
#   lm[0]  = pulso (wrist)
#   lm[4]  = ponta do polegar (thumb tip)
#   lm[9]  = base do médio (referência de tamanho da mão)
#   lm[16] = ponta do anelar (ring finger tip)
# ---------------------------------------------------------------------------

def detect_thumb_ring_pinch(hand_lm):
    """Retorna True se thumb_tip e ring_tip estiverem próximos.

    Usa TRIANGLE_THUMB_RING_THRESHOLD de config.py.
    Normaliza pela distância wrist→mid_base para ser invariante à câmera.
    """
    if not config.TRIANGLE_THUMB_RING_GESTURE_ENABLED:
        return False

    tx, ty = hand_lm[4].x,  hand_lm[4].y   # thumb tip
    rx, ry = hand_lm[16].x, hand_lm[16].y  # ring finger tip
    dist   = math.hypot(tx - rx, ty - ry)

    wx, wy   = hand_lm[0].x, hand_lm[0].y
    bx, by   = hand_lm[9].x, hand_lm[9].y
    hand_size = math.hypot(bx - wx, by - wy)

    if hand_size < 1e-5:
        return False
    return (dist / hand_size) < config.TRIANGLE_THUMB_RING_THRESHOLD
