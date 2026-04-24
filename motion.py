# motion.py
# Fonte unica de metricas de movimento da mao para todos os efeitos.
# Calcula centroide, velocidade (EMA), aceleracao e vetor direcional.
#
# Uso em main.py (uma vez por frame, apos tracker.process()):
#   import motion
#   motion.update(tracker.landmarks, h, w)
#
# Uso nos efeitos (leitura apenas — nunca gravar em motion.state):
#   import motion
#   spd      = motion.state.speed      # escalar normalizado [0..1]
#   nx, ny   = motion.state.nx, motion.state.ny   # vetor direcional
#   accel    = motion.state.accel      # aceleracao normalizada [0..1]
#   cx, cy   = motion.state.cx, motion.state.cy   # centroide em pixels

import math
import config


class MotionState:
    """
    Snapshot das metricas de movimento para o frame atual.
    Objeto unico modificado in-place a cada frame — zero alocacao por frame.

    Campos:
        cx, cy   — centroide da(s) mao(s) em pixels
        vx, vy   — velocidade suavizada via EMA (pixels/frame)
        speed    — velocidade escalar normalizada [0..1]
        ax, ay   — aceleracao suavizada via EMA (delta de velocidade)
        accel    — magnitude de aceleracao normalizada [0..1]
        nx, ny   — vetor direcional unitario (persiste quando parado)
        active   — True quando pelo menos uma mao esta detectada
    """
    __slots__ = ('cx', 'cy', 'vx', 'vy', 'speed',
                 'ax', 'ay', 'accel', 'nx', 'ny', 'active')

    def __init__(self):
        self.cx     = 0.0
        self.cy     = 0.0
        self.vx     = 0.0
        self.vy     = 0.0
        self.speed  = 0.0
        self.ax     = 0.0
        self.ay     = 0.0
        self.accel  = 0.0
        self.nx     = 0.0
        self.ny     = 0.0
        self.active = False


# ---------------------------------------------------------------------------
# Estado global (singleton) — acessivel por qualquer modulo com `import motion`
# ---------------------------------------------------------------------------
state = MotionState()

# Estado interno do tracker (privado ao modulo)
_prev_cx = None   # centroide do frame anterior
_prev_cy = None
_prev_vx = 0.0    # velocidade do frame anterior (usada para derivar aceleracao)
_prev_vy = 0.0


# ---------------------------------------------------------------------------
# API publica
# ---------------------------------------------------------------------------
def update(landmarks, h: int, w: int) -> None:
    """
    Atualiza motion.state com as metricas do frame atual.
    Deve ser chamado uma vez por frame em main.py, apos tracker.process().

    Args:
        landmarks : tracker.landmarks — List[List[NormalizedLandmark]]
        h, w      : dimensoes do frame em pixels
    """
    global _prev_cx, _prev_cy, _prev_vx, _prev_vy
    s = state

    # --- Sem mao: decai todos os valores suavemente ate zero ---
    if not landmarks:
        vel_ema = config.MOTION_VEL_EMA
        s.vx   *= vel_ema
        s.vy   *= vel_ema
        s.ax   *= vel_ema
        s.ay   *= vel_ema
        raw_spd = math.sqrt(s.vx * s.vx + s.vy * s.vy)
        eff     = max(0.0, raw_spd - config.MOTION_DEAD_ZONE)
        s.speed = min(1.0, eff / max(0.01, config.MOTION_SPEED_MAX))
        s.accel = 0.0
        s.active = False
        # Reseta historico quando completamente parado (evita jitter no proximo aparecimento)
        if raw_spd < 0.05:
            _prev_cx = None
            _prev_cy = None
        return

    # --- Centroide: media de todos os landmarks de todas as maos ---
    sum_x = 0.0
    sum_y = 0.0
    total = 0
    for hand in landmarks:
        for lm in hand:
            sum_x += lm.x * w
            sum_y += lm.y * h
            total += 1
    cx = sum_x / total
    cy = sum_y / total

    s.cx     = cx
    s.cy     = cy
    s.active = True

    # Primeiro frame com mao — sem historico para derivar velocidade
    if _prev_cx is None:
        _prev_cx = cx
        _prev_cy = cy
        return

    # --- Velocidade bruta (delta do centroide) ---
    raw_vx = cx - _prev_cx
    raw_vy = cy - _prev_cy
    _prev_cx = cx
    _prev_cy = cy

    # --- EMA de velocidade ---
    vel_ema = config.MOTION_VEL_EMA
    new_vx  = s.vx * vel_ema + raw_vx * (1.0 - vel_ema)
    new_vy  = s.vy * vel_ema + raw_vy * (1.0 - vel_ema)

    # --- Aceleracao = delta de velocidade, suavizado ---
    acc_ema = config.MOTION_ACCEL_EMA
    s.ax = s.ax * acc_ema + (new_vx - _prev_vx) * (1.0 - acc_ema)
    s.ay = s.ay * acc_ema + (new_vy - _prev_vy) * (1.0 - acc_ema)
    _prev_vx = new_vx
    _prev_vy = new_vy

    s.vx = new_vx
    s.vy = new_vy

    # --- Speed normalizada (dead zone + clamp a [0..1]) ---
    raw_spd = math.sqrt(new_vx * new_vx + new_vy * new_vy)
    eff     = max(0.0, raw_spd - config.MOTION_DEAD_ZONE)
    s.speed = min(1.0, eff / max(0.01, config.MOTION_SPEED_MAX))

    # --- Aceleracao normalizada ---
    raw_acc = math.sqrt(s.ax * s.ax + s.ay * s.ay)
    s.accel = min(1.0, raw_acc / max(0.01, config.MOTION_SPEED_MAX * 0.3))

    # --- Vetor direcional unitario ---
    # Mantido do frame anterior quando quase parado (evita flip aleatorio)
    if raw_spd > 0.5:
        s.nx = new_vx / raw_spd
        s.ny = new_vy / raw_spd
