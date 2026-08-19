# effects.py
# Interface padrao obrigatoria: apply(frame, mask, landmarks)

import math
import cv2
import numpy as np
import motion
import config


# ---------------------------------------------------------------------------
# FloatingOrbEffect -- Sprint Orb Finger Control
#
# Posicao : lerp(palma, ponta_indicador, FINGER_CENTER_BIAS)
# Rotacao : delta angular do indicador ao redor do orb
# Escala  : distancia polegar-indicador normalizada pelo tamanho da mao
# Energia : motion.state.speed + accel (glow e brilho)
# Idle    : FLOATING_ORB_IDLE_X / IDLE_Y quando sem mao
#
# Indice MediaPipe usados:
#   0  = pulso (wrist)
#   4  = ponta polegar (thumb tip)
#   5  = base indicador
#   8  = ponta indicador (index tip)
#   9  = base medio
#   12 = ponta medio  (middle tip)
#   [0,5,9,13,17] = centro da palma
#
# Controle por FLOATING_ORB_USE_FINGER_CONTROL:
#   True  -> controle fino pelo indicador (padrao)
#   False -> fallback motion.state da sprint anterior
#
# Extensao futura (NAO implementada):
#   two-hand control  -> distancia entre maos -> scale; centro -> posicao
#   pinch lock        -> pinch ativo fixa posicao do orb no espaco
#   modo orbital      -> orb orbita ao redor da palma
# ---------------------------------------------------------------------------

class FloatingOrbEffect:
    """Sprint Orb Finger Control -- controle pelo indicador, escala por pinch."""

    # Indices MediaPipe relevantes
    _I_WRIST      = 0
    _I_THUMB_TIP  = 4
    _I_PALM       = [0, 5, 9, 13, 17]
    _I_INDEX_TIP  = 8
    _I_MID_BASE   = 9
    _I_MIDDLE_TIP = 12

    def __init__(self):
        self._t              = 0.0
        self._rot            = 0.0
        self._rot_vel        = 0.0    # velocidade rotacional acumulada (deg/frame)
        self._canvas         = None
        self._frame_size     = None
        self._orb_cx         = None   # posicao suavizada X (None = nao inicializado)
        self._orb_cy         = None   # posicao suavizada Y
        self._scale          = 1.0    # escala atual do raio [MIN..MAX]
        self._energy         = 0.0    # energia atual [0..1]
        self._prev_fing_ang  = None   # angulo anterior do indicador em relacao ao orb
        self._prev_idx_tip   = None   # posicao anterior do indicador (para detectar troca de mao)
        self._float_phase    = 0.0    # fase da microflutuacao organica de posicao

    # ------------------------------------------------------------------
    def _finger_data(self, landmarks, h, w, orb_cx, orb_cy):
        """Extrai coordenadas do indicador da mao mais proxima do orb.
        Aceita qualquer numero de maos -- escolhe a melhor para controle.
        Retorna tupla ou None se landmarks vazio."""
        if not landmarks:
            return None

        # Selecionar a mao cujo indicador esta mais proximo do centro do orb.
        # Isso garante controle correto independente de qual mao ou lado da tela.
        best_lm   = landmarks[0]
        best_dist = float('inf')
        for lm_candidate in landmarks:
            ix = lm_candidate[self._I_INDEX_TIP].x * w
            iy = lm_candidate[self._I_INDEX_TIP].y * h
            d  = math.hypot(ix - orb_cx, iy - orb_cy)
            if d < best_dist:
                best_dist = d
                best_lm   = lm_candidate
        lm = best_lm

        # Palm center (media dos 5 pontos-ancora)
        xs = [lm[i].x * w for i in self._I_PALM]
        ys = [lm[i].y * h for i in self._I_PALM]
        palm_cx = sum(xs) / len(xs)
        palm_cy = sum(ys) / len(ys)

        # Pontas dos dedos
        idx_x = lm[self._I_INDEX_TIP].x  * w
        idx_y = lm[self._I_INDEX_TIP].y  * h
        mid_x = lm[self._I_MIDDLE_TIP].x * w
        mid_y = lm[self._I_MIDDLE_TIP].y * h
        thu_x = lm[self._I_THUMB_TIP].x  * w
        thu_y = lm[self._I_THUMB_TIP].y  * h

        # Tamanho da mao (pulso -> base do medio)
        wx = lm[self._I_WRIST].x    * w
        wy = lm[self._I_WRIST].y    * h
        mx = lm[self._I_MID_BASE].x * w
        my = lm[self._I_MID_BASE].y * h
        hand_size = max(1.0, math.hypot(mx - wx, my - wy))

        return (palm_cx, palm_cy, idx_x, idx_y, mid_x, mid_y,
                thu_x, thu_y, hand_size)

    # ------------------------------------------------------------------
    def _draw_orb(self, canvas, cx, cy, radius, nx, energy, t, rot):
        col_main   = config.FLOATING_ORB_COLOR
        col_accent = config.FLOATING_ORB_ACCENT
        a          = config.FLOATING_ORB_ALPHA
        react      = config.FLOATING_ORB_REACTIVITY
        cx_i = int(cx)
        cy_i = int(cy)

        # Pulsacao base
        pulse  = 0.90 + 0.10 * math.sin(t * 3.5)
        r_main = max(8, int(radius * pulse))
        r_in   = max(4, int(r_main * 0.52))
        r_seg  = max(6, int(r_main * 1.18))

        # Inclinacao visual dos arcos externos (nx)
        tilt = abs(nx) * react
        rx   = max(4, int(r_main * (1.0 + tilt * 0.15)))
        ry   = max(4, int(r_main * (1.0 - tilt * 0.08)))

        # 4 arcos externos giratorios
        ring_color = tuple(min(255, int(v * a * 0.85)) for v in col_main)
        for i in range(4):
            start_a = int(rot + i * 90)
            cv2.ellipse(canvas, (cx_i, cy_i), (rx, ry),
                        0, start_a, start_a + 55, ring_color, 2, cv2.LINE_AA)

        # 3 arcos internos (contra-rotacao)
        arc_color = tuple(min(255, int(v * a * 0.60)) for v in col_accent)
        for i in range(3):
            start_a = int(-rot * 1.3 + i * 120)
            cv2.ellipse(canvas, (cx_i, cy_i), (r_in, r_in),
                        0, start_a, start_a + 45, arc_color, 1, cv2.LINE_AA)

        # 8 segmentos radiais (reatividade de energia)
        seg_rot    = rot * 0.35
        seg_bright = 0.65 + energy * react * 0.35
        seg_color  = tuple(min(255, int(v * a * seg_bright)) for v in col_accent)
        for i in range(8):
            ang_rad      = math.radians(seg_rot + i * 45.0)
            cos_a, sin_a = math.cos(ang_rad), math.sin(ang_rad)
            r_in_seg     = int(r_main * 0.78)
            x0 = int(cx + cos_a * r_in_seg)
            y0 = int(cy + sin_a * r_in_seg)
            x1 = int(cx + cos_a * r_seg)
            y1 = int(cy + sin_a * r_seg)
            cv2.line(canvas, (x0, y0), (x1, y1), seg_color, 1, cv2.LINE_AA)

        # Anel pulsante interno
        pulse2       = 0.85 + 0.15 * math.sin(t * 5.2 + 1.0)
        r_pulse      = max(3, int(r_in * 0.65 * pulse2))
        pulse_bright = 0.50 + energy * react * 0.50
        pulse_color  = tuple(min(255, int(v * a * pulse_bright)) for v in col_main)
        cv2.circle(canvas, (cx_i, cy_i), r_pulse, pulse_color, 1, cv2.LINE_AA)

        # Nucleo central + halo
        core_r      = max(3, int(r_main * 0.06 + energy * react * 5))
        core_bright = 0.60 + energy * react * 0.40
        core_color  = tuple(min(255, int(v * core_bright)) for v in col_main)
        cv2.circle(canvas, (cx_i, cy_i), core_r, core_color, -1, cv2.LINE_AA)
        halo_color  = tuple(min(255, int(v * 0.30)) for v in col_main)
        cv2.circle(canvas, (cx_i, cy_i), core_r + 3, halo_color, 1, cv2.LINE_AA)

    # ------------------------------------------------------------------
    def apply(self, frame, mask, landmarks):
        h, w = frame.shape[:2]
        s = motion.state

        # --- Inicializar posicao idle na primeira execucao ---
        if self._orb_cx is None:
            self._orb_cx = w * config.FLOATING_ORB_IDLE_X
            self._orb_cy = h * config.FLOATING_ORB_IDLE_Y

        # --- Energia: EMA de speed + burst de aceleracao ---
        energy_target = min(1.0,
            s.speed * config.FLOATING_ORB_ENERGY_FROM_SPEED +
            s.accel * config.FLOATING_ORB_ACCEL_BURST_STRENGTH)
        self._energy = self._energy * 0.85 + energy_target * 0.15

        pos_smooth = config.FLOATING_ORB_POSITION_SMOOTHING
        damp       = config.FLOATING_ORB_ROTATION_DAMPING

        # --- Posicao: centro + drift suave em direcao a mao + microflutuacao organica ---
        # O orb nunca gruda na palma -- drift e limitado; flutuacao organica nunca para.
        self._float_phase += config.FLOATING_ORB_FLOAT_SPEED
        float_x = math.sin(self._float_phase * 1.00) * config.FLOATING_ORB_FLOAT_AMP
        float_y = math.sin(self._float_phase * 0.73 + 1.3) * config.FLOATING_ORB_FLOAT_AMP * 0.6
        base_cx = w * config.FLOATING_ORB_IDLE_X
        base_cy = h * config.FLOATING_ORB_IDLE_Y
        if s.active:
            drift     = config.FLOATING_ORB_DRIFT_STRENGTH
            target_cx = base_cx + (s.cx - base_cx) * drift + float_x
            target_cy = base_cy + (s.cy - base_cy) * drift + float_y
        else:
            target_cx = base_cx + float_x
            target_cy = base_cy + float_y
        self._orb_cx = self._orb_cx * pos_smooth + target_cx * (1.0 - pos_smooth)
        self._orb_cy = self._orb_cy * pos_smooth + target_cy * (1.0 - pos_smooth)

        # --- Extrair dados dos dedos se finger control ativo ---
        fdata = None
        if config.FLOATING_ORB_USE_FINGER_CONTROL:
            fdata = self._finger_data(landmarks, h, w, self._orb_cx, self._orb_cy)

        # ----------------------------------------------------------------
        # Branch 1: controle pelo indicador
        # ----------------------------------------------------------------
        if fdata is not None:
            (_palm_cx, _palm_cy, idx_x, idx_y, mid_x, mid_y,
             thu_x, thu_y, hand_size) = fdata

            # Posicao: fixa no centro do frame -- orb nao segue a mao
            # palm_cx/cy ignorados intencionalmente

            # Rotacao: delta angular do indicador em torno do orb.
            # Resetar prev_fing_ang se o indicador teleportou (troca de mao entre frames).
            if self._prev_idx_tip is not None:
                jump = math.hypot(idx_x - self._prev_idx_tip[0],
                                  idx_y - self._prev_idx_tip[1])
                if jump > hand_size * 0.60:      # salto maior que 60% da mao = nova mao
                    self._prev_fing_ang = None
            self._prev_idx_tip = (idx_x, idx_y)
            fing_ang = math.degrees(math.atan2(
                idx_y - self._orb_cy, idx_x - self._orb_cx))
            mid_dist = math.hypot(mid_x - idx_x, mid_y - idx_y)
            if mid_dist < hand_size * 0.20:
                mid_ang = math.degrees(math.atan2(
                    mid_y - self._orb_cy, mid_x - self._orb_cx))
                ang_diff = ((mid_ang - fing_ang + 180.0) % 360.0) - 180.0
                fing_ang = fing_ang + ang_diff * 0.5

            if self._prev_fing_ang is not None:
                raw_delta = ((fing_ang - self._prev_fing_ang + 180.0) % 360.0) - 180.0
                raw_delta = max(-25.0, min(25.0, raw_delta))    # clamp anti-salto
                smooth_r  = config.FLOATING_ORB_FINGER_ROTATION_SMOOTHING
                strength  = config.FLOATING_ORB_FINGER_ROTATION_STRENGTH
                self._rot_vel = (self._rot_vel * smooth_r
                                 + raw_delta * strength * (1.0 - smooth_r))
            self._prev_fing_ang = fing_ang

            # Escala: distancia polegar->indicador normalizada
            pinch_dist   = math.hypot(thu_x - idx_x, thu_y - idx_y)
            pinch_norm   = pinch_dist / hand_size
            max_open     = max(0.01, config.FLOATING_ORB_PINCH_SCALE_STRENGTH)
            scale_t      = max(0.0, min(1.0, pinch_norm / max_open))
            mn, mx_s     = config.FLOATING_ORB_MIN_SCALE, config.FLOATING_ORB_MAX_SCALE
            target_scale = mn + (mx_s - mn) * scale_t
            self._scale  = self._scale * 0.90 + target_scale * 0.10

        # ----------------------------------------------------------------
        # Branch 2: fallback motion.state (USE_FINGER_CONTROL=False + mao ativa)
        # ----------------------------------------------------------------
        elif s.active and not config.FLOATING_ORB_USE_FINGER_CONTROL:
            # Posicao: fixa no centro do frame -- orb nao segue a mao
            drive = s.nx * config.FLOATING_ORB_MANUAL_ROTATION_STRENGTH * (1.0 + self._energy * 2.0)
            self._rot_vel = self._rot_vel * damp + drive * (1.0 - damp)
            scale_t = 1.0 - s.ny * config.FLOATING_ORB_VERTICAL_SCALE_STRENGTH
            scale_t = max(config.FLOATING_ORB_MIN_SCALE, min(config.FLOATING_ORB_MAX_SCALE, scale_t))
            self._scale = self._scale * 0.90 + scale_t * 0.10

        # ----------------------------------------------------------------
        # Branch 3: idle -- sem mao ou finger_control sem landmarks
        # ----------------------------------------------------------------
        else:
            self._rot_vel  *= damp
            self._scale     = self._scale * 0.95 + 1.0 * 0.05
            self._prev_fing_ang = None   # reset para proximo ciclo com mao
            self._prev_idx_tip  = None

        # --- Rotacao e tempo ---
        self._rot = (self._rot + config.FLOATING_ORB_IDLE_ROTATION_SPEED + self._rot_vel) % 360.0
        self._t  += config.FLOATING_ORB_PULSE_SPEED

        # --- ROI ao redor da posicao atual do orb ---
        radius = config.FLOATING_ORB_RADIUS * self._scale
        cx     = self._orb_cx
        cy     = self._orb_cy
        pad    = config.FLOATING_ORB_GLOW_BLUR * 2 + 8
        r_pad  = int(radius * 1.35) + pad
        x0     = max(0, int(cx) - r_pad)
        y0     = max(0, int(cy) - r_pad)
        x1     = min(w, int(cx) + r_pad)
        y1     = min(h, int(cy) + r_pad)
        rw, rh = x1 - x0, y1 - y0

        if rw < 8 or rh < 8:
            return frame

        if self._frame_size != (rh, rw):
            self._canvas     = np.zeros((rh, rw, 3), dtype=np.uint8)
            self._frame_size = (rh, rw)
        self._canvas[:] = 0

        self._draw_orb(
            self._canvas,
            cx - x0, cy - y0,
            radius,
            nx=s.nx,
            energy=self._energy,
            t=self._t,
            rot=self._rot,
        )

        if config.FLOATING_ORB_GLOW > 0:
            gk = config.FLOATING_ORB_GLOW_BLUR
            gk = gk if gk % 2 == 1 else gk + 1
            react       = config.FLOATING_ORB_REACTIVITY
            energy_glow = config.FLOATING_ORB_GLOW * (1.0 + self._energy * react * 1.5)
            glow = cv2.GaussianBlur(self._canvas, (gk, gk), 0)
            cv2.addWeighted(self._canvas, 1.0, glow, min(energy_glow, 2.5), 0,
                            dst=self._canvas)

        cv2.add(frame[y0:y1, x0:x1], self._canvas,
                dst=frame[y0:y1, x0:x1])
        return frame

# ---------------------------------------------------------------------------
# FloatingCubeEffect -- Sprint FloatingCube: cubo wireframe holografico
#
# Estrutura 3D fake:
#   8 vertices locais em [-SIZE, +SIZE]^3
#   12 arestas (sem objeto interno)
#   Rotacao manual por eixo X/Y (delta do indicador) + idle auto-spin
#   Projecao pseudo-perspectiva manual (sem engine 3D)
#
# Controle:
#   indicador (lm 8)   -> delta X/Y do dedo = rotacao X/Y
#   pinch (lm 4 vs 8)  -> escala do cubo
#   mao aberta         -> fade in; fechada/ausente = fade out
#   motion.state.speed -> energia (glow + brilho)
#
# Posicao:
#   Centro fixo com microflutuacao organica (Lissajous)
#   Drift suave em direcao a mao (FLOATING_CUBE_DRIFT_STRENGTH)
#
# Arestas traseiras (z medio < 0 no espaco projetado) sao desenhadas
# com a cor de acento mais escura, gerando profundidade visual.
#
# Extensao futura (NAO implementada):
#   two-hand control: distancia entre maos -> scale; centro -> posicao
#   pinch lock: congelar rotacao enquanto pinch ativo
#   rotacao Z pelo tilt da mao
# ---------------------------------------------------------------------------

class FloatingCubeEffect:
    """Sprint FloatingCube -- cubo wireframe holografico com controle pelo indicador."""

    # Indices MediaPipe
    _I_WRIST      = 0
    _I_THUMB_TIP  = 4
    _I_PALM       = [0, 5, 9, 13, 17]
    _I_INDEX_TIP  = 8
    _I_MID_BASE   = 9

    # 8 vertices do cubo em espaco local [-1, +1]^3 (escalados por SIZE)
    _VERTS = [
        (-1, -1, -1), ( 1, -1, -1), ( 1,  1, -1), (-1,  1, -1),  # face traseira
        (-1, -1,  1), ( 1, -1,  1), ( 1,  1,  1), (-1,  1,  1),  # face frontal
    ]
    # 12 arestas: pares de indices de vertices
    _EDGES = [
        (0, 1), (1, 2), (2, 3), (3, 0),  # face traseira
        (4, 5), (5, 6), (6, 7), (7, 4),  # face frontal
        (0, 4), (1, 5), (2, 6), (3, 7),  # arestas laterais
    ]
    # 6 faces: quad de 4 vertices cada (ordem anti-horária vista de fora)
    _FACES = [
        (0, 1, 2, 3),   # traseira   (z = -1)
        (4, 5, 6, 7),   # frontal    (z = +1)
        (0, 1, 5, 4),   # inferior   (y = -1)
        (3, 2, 6, 7),   # superior   (y = +1)
        (0, 3, 7, 4),   # esquerda   (x = -1)
        (1, 2, 6, 5),   # direita    (x = +1)
    ]

    def __init__(self):
        self._rx         = 25.0   # rotacao acumulada em X (deg)
        self._ry         = 45.0   # rotacao acumulada em Y (deg)
        self._rz         = 0.0    # rotacao acumulada em Z (deg)
        self._rvx        = 0.0    # velocidade rotacional X (deg/frame)
        self._rvy        = 0.0    # velocidade rotacional Y (deg/frame)
        self._scale      = 1.0    # escala atual
        self._alpha      = 0.0    # fade atual [0..1]
        self._energy     = 0.0    # energia atual [0..1]
        self._cube_cx    = None   # posicao suavizada X
        self._cube_cy    = None   # posicao suavizada Y
        self._float_phase = 0.0   # fase da microflutuacao
        self._prev_idx   = None   # posicao anterior do indicador (px, py)
        self._prev_idx_tip = None # para deteccao de troca de mao
        self._two_hand_base_dist  = None  # distancia base capturada ao ativar pinch duplo
        self._two_hand_sep_smooth = None  # distancia suavizada entre pinch points
        self._canvas     = None
        self._frame_size = None
        # --- Bounce animation ---
        self._bounce_active       = False
        self._bounce_frame        = 0
        self._bounce_offset_y     = 0.0
        # --- External scale control (two-hand pinch from main.py) ---
        self._ext_scale_active    = False
        self._ext_scale_target    = 1.0
        # Sprint 5 — fase da pulsação
        self._pulse_t             = 0.0
        # Sprint 6 — Partículas 3D pré-geradas (seed fixa = sem tremor entre frames)
        self._particles_local     = FloatingCubeEffect._gen_particles()
        # Trail: buffer de rastro (inicializado lazy junto com _canvas)
        self._trail               = None

    # ------------------------------------------------------------------
    def trigger_bounce_sequence(self):
        """Inicia a animacao de bounce. Ignorado se ja estiver ativa."""
        if not config.FLOATING_CUBE_BOUNCE_ENABLED:
            return
        if self._bounce_active:
            return
        self._bounce_active   = True
        self._bounce_frame    = 0
        self._bounce_offset_y = 0.0

    def _update_bounce(self):
        """Avanca um frame da animacao de bounce. Retorna offset Y atual (neg = sobe).

        Sequencia de etapas (frames acumulados):
          etapa 1 [0, T1)         subida rapida   0 -> -H
          etapa 2 [T1, T2)        descida rapida  -H -> 0
          etapa 3 [T2, T3)        subida lenta    0 -> -H
          etapa 4 [T3, T4)        descida suave   -H -> 0
        Easing: seno em [0, pi/2] para suavizar inicio e fim de cada etapa.
        """
        if not self._bounce_active:
            return 0.0

        T1 = config.FLOATING_CUBE_BOUNCE_FAST_UP_FRAMES
        T2 = T1 + config.FLOATING_CUBE_BOUNCE_FAST_DOWN_FRAMES
        T3 = T2 + config.FLOATING_CUBE_BOUNCE_SLOW_UP_FRAMES
        T4 = T3 + config.FLOATING_CUBE_BOUNCE_SLOW_DOWN_FRAMES
        H  = config.FLOATING_CUBE_BOUNCE_HEIGHT
        f  = self._bounce_frame

        if f < T1:
            # Etapa 1: sobe rapido  (ease-in-out: seno)
            t = f / max(1, T1)
            offset = -H * math.sin(t * math.pi / 2)
        elif f < T2:
            # Etapa 2: desce rapido
            t = (f - T1) / max(1, T2 - T1)
            offset = -H * math.cos(t * math.pi / 2)
        elif f < T3:
            # Etapa 3: sobe lento
            t = (f - T2) / max(1, T3 - T2)
            offset = -H * math.sin(t * math.pi / 2)
        elif f < T4:
            # Etapa 4: desce suave
            t = (f - T3) / max(1, T4 - T3)
            offset = -H * math.cos(t * math.pi / 2)
        else:
            # Animacao concluida
            self._bounce_active   = False
            self._bounce_frame    = 0
            self._bounce_offset_y = 0.0
            return 0.0

        self._bounce_frame   += 1
        self._bounce_offset_y = offset
        return offset

    # ------------------------------------------------------------------
    @staticmethod
    def _rotate(verts, rx_deg, ry_deg, rz_deg):
        """Aplica rotacao ZYX aos vertices 3D. Retorna lista de (x,y,z)."""
        rx = math.radians(rx_deg)
        ry = math.radians(ry_deg)
        rz = math.radians(rz_deg)

        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)

        result = []
        for (vx, vy, vz) in verts:
            # Z
            x1 = vx * cz - vy * sz
            y1 = vx * sz + vy * cz
            z1 = vz
            # Y
            x2 = x1 * cy + z1 * sy
            y2 = y1
            z2 = -x1 * sy + z1 * cy
            # X
            x3 = x2
            y3 = y2 * cx - z2 * sx
            z3 = y2 * sx + z2 * cx
            result.append((x3, y3, z3))
        return result

    @staticmethod
    def _project(verts_3d, cx, cy, fov):
        """Projecao pseudo-perspectiva manual para 2D. Retorna lista de (px, py).
        Vertices ja estao em espaco pixel [-size, +size]; sem multiplicacao extra."""
        pts = []
        for (x, y, z) in verts_3d:
            # dz = distancia focal + deslocamento Z (ja em pixels)
            dz = max(fov * 0.10, fov + z)
            px = cx + x * fov / dz
            py = cy + y * fov / dz
            pts.append((int(px), int(py)))
        return pts

    # ------------------------------------------------------------------
    def _get_hand_data(self, landmarks, h, w, cx, cy):
        """Extrai dados da mao mais proxima do cubo.
        Retorna None se sem landmarks."""
        if not landmarks:
            return None

        best_lm   = landmarks[0]
        best_dist = float('inf')
        for lm_c in landmarks:
            ix = lm_c[self._I_INDEX_TIP].x * w
            iy = lm_c[self._I_INDEX_TIP].y * h
            d  = math.hypot(ix - cx, iy - cy)
            if d < best_dist:
                best_dist = d
                best_lm   = lm_c
        lm = best_lm

        # Palm center
        xs = [lm[i].x * w for i in self._I_PALM]
        ys = [lm[i].y * h for i in self._I_PALM]
        palm_cx = sum(xs) / len(xs)
        palm_cy = sum(ys) / len(ys)

        # Tamanho da mao
        wx = lm[self._I_WRIST].x    * w
        wy = lm[self._I_WRIST].y    * h
        mx = lm[self._I_MID_BASE].x * w
        my = lm[self._I_MID_BASE].y * h
        hand_size = max(1.0, math.hypot(mx - wx, my - wy))

        # Index tip
        idx_x = lm[self._I_INDEX_TIP].x * w
        idx_y = lm[self._I_INDEX_TIP].y * h

        # Thumb tip (para pinch)
        thu_x = lm[self._I_THUMB_TIP].x * w
        thu_y = lm[self._I_THUMB_TIP].y * h

        # Distancia indicador-palma normalizada (detectar mao aberta)
        idx_palm_dist = math.hypot(idx_x - palm_cx, idx_y - palm_cy) / hand_size

        return (palm_cx, palm_cy, idx_x, idx_y, thu_x, thu_y,
                hand_size, idx_palm_dist)

    # ------------------------------------------------------------------
    def set_scale(self, scale):
        """Ativa controle externo de escala (chamado por main.py)."""
        self._ext_scale_active = True
        self._ext_scale_target = float(scale)

    def freeze_scale(self):
        """Desativa controle externo, mantendo a escala atual."""
        self._ext_scale_active = False

    @staticmethod
    def _gen_particles():
        """Gera pontos 3D dentro do volume unitário do cubo com seed fixa.

        Retorna lista de tuplas (x, y, z) em espaço local [-0.82, +0.82]^3.
        A seed fixa garante estabilidade visual (sem tremor entre frames).
        """
        n   = config.FLOATING_CUBE_PARTICLE_COUNT
        rng = np.random.RandomState(42)   # seed fixa: compatível com todas versões NumPy
        pts = rng.uniform(-0.82, 0.82, (n, 3)).astype(np.float32)
        return [tuple(float(v) for v in row) for row in pts]

    # ------------------------------------------------------------------
    def apply(self, frame, mask, landmarks):
        h, w = frame.shape[:2]
        s = motion.state

        # Inicializar posicao no primeiro frame
        if self._cube_cx is None:
            self._cube_cx = w * config.FLOATING_CUBE_IDLE_X
            self._cube_cy = h * config.FLOATING_CUBE_IDLE_Y

        # --- Energia ---
        energy_t   = min(1.0, s.speed * config.FLOATING_CUBE_ENERGY_FROM_SPEED
                              + s.accel * config.FLOATING_CUBE_ACCEL_BURST)
        self._energy = self._energy * 0.85 + energy_t * 0.15

        # --- Posicao: centro + drift suave + microflutuacao ---
        self._float_phase += config.FLOATING_CUBE_IDLE_DRIFT_SPEED
        float_x = math.sin(self._float_phase * 1.00) * config.FLOATING_CUBE_IDLE_DRIFT_AMP
        float_y = math.sin(self._float_phase * 0.71 + 1.1) * config.FLOATING_CUBE_IDLE_DRIFT_AMP * 0.6
        base_cx = w * config.FLOATING_CUBE_IDLE_X
        base_cy = h * config.FLOATING_CUBE_IDLE_Y
        if s.active:
            dr        = config.FLOATING_CUBE_DRIFT_STRENGTH
            target_cx = base_cx + (s.cx - base_cx) * dr + float_x
            target_cy = base_cy + (s.cy - base_cy) * dr + float_y
        else:
            target_cx = base_cx + float_x
            target_cy = base_cy + float_y
        ps = config.FLOATING_CUBE_POSITION_SMOOTHING
        self._cube_cx = self._cube_cx * ps + target_cx * (1.0 - ps)
        self._cube_cy = self._cube_cy * ps + target_cy * (1.0 - ps)

        # --- Dados da mao ---
        hdata = self._get_hand_data(landmarks, h, w, self._cube_cx, self._cube_cy)

        fade_step = config.FLOATING_CUBE_FADE_SPEED
        damp      = config.FLOATING_CUBE_ROTATION_DAMPING
        smooth_r  = config.FLOATING_CUBE_ROTATION_SMOOTHING

        # ----------------------------------------------------------------
        # Detectar pinch duplo antes dos branches
        # ----------------------------------------------------------------
        two_hand_active = False
        if len(landmarks) >= 2:
            lm0, lm1 = landmarks[0], landmarks[1]
            thr = config.FLOATING_CUBE_TWO_HAND_PINCH_THRESHOLD

            def _hs(lm):
                wx = lm[self._I_WRIST].x    * w;  wy = lm[self._I_WRIST].y    * h
                mx = lm[self._I_MID_BASE].x * w;  my = lm[self._I_MID_BASE].y * h
                return max(1.0, math.hypot(mx - wx, my - wy))

            hs0 = _hs(lm0);  hs1 = _hs(lm1)

            # Pontas de cada mao
            t0x = lm0[self._I_THUMB_TIP].x * w;  t0y = lm0[self._I_THUMB_TIP].y * h
            i0x = lm0[self._I_INDEX_TIP].x * w;  i0y = lm0[self._I_INDEX_TIP].y * h
            t1x = lm1[self._I_THUMB_TIP].x * w;  t1y = lm1[self._I_THUMB_TIP].y * h
            i1x = lm1[self._I_INDEX_TIP].x * w;  i1y = lm1[self._I_INDEX_TIP].y * h

            pd0 = math.hypot(i0x - t0x, i0y - t0y) / hs0
            pd1 = math.hypot(i1x - t1x, i1y - t1y) / hs1

            if pd0 <= thr and pd1 <= thr:
                two_hand_active = True
            else:
                # Uma ou ambas as maos nao estao em pinch: reset estado two-hand
                self._two_hand_base_dist  = None
                self._two_hand_sep_smooth = None

        # ----------------------------------------------------------------
        # Branch duas maos: pinch duplo ativo
        # ----------------------------------------------------------------
        if two_hand_active:
            # Pinch points = media thumb+index de cada mao
            pp0x = (t0x + i0x) * 0.5;  pp0y = (t0y + i0y) * 0.5
            pp1x = (t1x + i1x) * 0.5;  pp1y = (t1y + i1y) * 0.5

            # Separacao suavizada (EMA)
            sep_raw = math.hypot(pp1x - pp0x, pp1y - pp0y)
            tss = config.FLOATING_CUBE_TWO_HAND_SCALE_SMOOTHING
            if self._two_hand_sep_smooth is None:
                self._two_hand_sep_smooth = sep_raw
            else:
                self._two_hand_sep_smooth = self._two_hand_sep_smooth * tss + sep_raw * (1.0 - tss)

            # Base capturada na ativacao
            if self._two_hand_base_dist is None:
                self._two_hand_base_dist = max(10.0, self._two_hand_sep_smooth)

            # Escala relativa: ratio atual / base
            ratio = self._two_hand_sep_smooth / self._two_hand_base_dist
            scale_r = config.FLOATING_CUBE_TWO_HAND_SCALE_RESPONSE
            mn_s    = config.FLOATING_CUBE_TWO_HAND_MIN_SCALE
            mx_s    = config.FLOATING_CUBE_TWO_HAND_MAX_SCALE
            max_safe = (min(w, h) * 0.14) / max(1.0, config.FLOATING_CUBE_SIZE)
            mx_s     = min(mx_s, max_safe)
            tgt_scl  = max(mn_s, min(mx_s, ratio * scale_r))
            if not self._ext_scale_active:
                self._scale = self._scale * tss + tgt_scl * (1.0 - tss)

            # Posicao: centro entre pinch points, mesclado com centro da tela
            mid_cx = (pp0x + pp1x) * 0.5
            mid_cy = (pp0y + pp1y) * 0.5
            blend  = config.FLOATING_CUBE_TWO_HAND_CENTER_BLEND
            tgt_cx = mid_cx * (1.0 - blend) + (w * 0.5) * blend
            tgt_cy = mid_cy * (1.0 - blend) + (h * 0.5) * blend
            tps    = config.FLOATING_CUBE_TWO_HAND_POSITION_SMOOTHING
            self._cube_cx = self._cube_cx * tps + tgt_cx * (1.0 - tps)
            self._cube_cy = self._cube_cy * tps + tgt_cy * (1.0 - tps)

            # Rotacao: apenas damping (sem acumulo por tilt de maos)
            max_rv = config.FLOATING_CUBE_TWO_HAND_MAX_ROTATION_DELTA
            self._rvx = max(-max_rv, min(max_rv, self._rvx * damp))
            self._rvy = max(-max_rv, min(max_rv, self._rvy * damp))

            # Fade in
            self._alpha = min(1.0, self._alpha + fade_step * 2.0)

            # Reset estado de uma mao
            self._prev_idx     = None
            self._prev_idx_tip = None

        # ----------------------------------------------------------------
        # Branch uma mao: controle por indicador + pinch
        # ----------------------------------------------------------------
        elif hdata is not None:
            (palm_cx, palm_cy, idx_x, idx_y, thu_x, thu_y,
             hand_size, idx_palm_dist) = hdata

            # Fade in/out por mao aberta
            if idx_palm_dist >= config.FLOATING_CUBE_OPEN_HAND_THRESHOLD:
                self._alpha = min(1.0, self._alpha + fade_step * 2.0)
            else:
                self._alpha = max(0.0, self._alpha - fade_step)

            # Rotacao por delta do indicador (reset se teleportou)
            if self._prev_idx_tip is not None:
                jump = math.hypot(idx_x - self._prev_idx_tip[0],
                                  idx_y - self._prev_idx_tip[1])
                if jump > hand_size * 0.60:
                    self._prev_idx = None
            self._prev_idx_tip = (idx_x, idx_y)

            if self._prev_idx is not None:
                dx_raw = idx_x - self._prev_idx[0]
                dy_raw = idx_y - self._prev_idx[1]
                dx_c = max(-20.0, min(20.0, dx_raw))
                dy_c = max(-20.0, min(20.0, dy_raw))
                str_x = config.FLOATING_CUBE_FINGER_ROTATION_X
                str_y = config.FLOATING_CUBE_FINGER_ROTATION_Y
                self._rvx = self._rvx * smooth_r + (-dy_c * str_x) * (1.0 - smooth_r)
                self._rvy = self._rvy * smooth_r + ( dx_c * str_y) * (1.0 - smooth_r)
            self._prev_idx = (idx_x, idx_y)

            # Escala por pinch (uma mao)
            pinch_dist  = math.hypot(thu_x - idx_x, thu_y - idx_y)
            pinch_norm  = max(0.0, min(1.0, pinch_dist / max(1.0, hand_size * 0.5)))
            mn_s, mx_s  = config.FLOATING_CUBE_MIN_SCALE, config.FLOATING_CUBE_MAX_SCALE
            scale_t     = mn_s + (mx_s - mn_s) * pinch_norm
            if not self._ext_scale_active:
                self._scale = self._scale * 0.90 + scale_t * 0.10

        else:
            # Sem mao: fade out
            self._alpha = max(0.0, self._alpha - fade_step)
            self._rvx  *= damp
            self._rvy  *= damp
            if not self._ext_scale_active:
                self._scale = self._scale * 0.95 + 1.0 * 0.05
            self._prev_idx      = None
            self._prev_idx_tip  = None

        if self._alpha < 0.005:
            return frame

        # --- Escala externa (controle por duas maos via main.py) ---
        if self._ext_scale_active:
            sm = config.TWO_HAND_CUBE_SCALE_SMOOTHING
            self._scale = self._scale * sm + self._ext_scale_target * (1.0 - sm)

        # --- Rotacao acumulada ---
        self._rx = (self._rx + config.FLOATING_CUBE_IDLE_ROTATION_X + self._rvx) % 360.0
        self._ry = (self._ry + config.FLOATING_CUBE_IDLE_ROTATION_Y + self._rvy) % 360.0
        self._rz = (self._rz + config.FLOATING_CUBE_IDLE_ROTATION_Z) % 360.0
        # Damping gradual da velocidade
        self._rvx *= damp
        self._rvy *= damp

        # --- Projecao 3D -> 2D ---
        size = config.FLOATING_CUBE_SIZE * self._scale
        fov  = config.FLOATING_CUBE_PERSPECTIVE_FOV

        local_verts = [(vx * size, vy * size, vz * size) for (vx, vy, vz) in self._VERTS]
        rot_verts   = self._rotate(local_verts, self._rx, self._ry, self._rz)
        cx          = self._cube_cx
        cy          = self._cube_cy + self._update_bounce()
        pts_2d      = self._project(rot_verts, cx, cy, fov)

        # Calcular z medio por aresta (para separar frente/tras)
        edge_z = []
        for (i0, i1) in self._EDGES:
            zm = (rot_verts[i0][2] + rot_verts[i1][2]) * 0.5
            edge_z.append(zm)
        z_max = max(edge_z) if edge_z else 1.0
        z_min = min(edge_z) if edge_z else -1.0
        z_range = max(1.0, z_max - z_min)

        # --- ROI ao redor do cubo ---
        all_x = [p[0] for p in pts_2d]
        all_y = [p[1] for p in pts_2d]
        pad   = config.FLOATING_CUBE_GLOW_BLUR * 2 + 12
        x0    = max(0, min(all_x) - pad)
        y0    = max(0, min(all_y) - pad)
        x1    = min(w, max(all_x) + pad)
        y1    = min(h, max(all_y) + pad)
        rw, rh = x1 - x0, y1 - y0

        if rw < 4 or rh < 4:
            return frame

        if self._frame_size != (rh, rw):
            self._canvas     = np.zeros((rh, rw, 3), dtype=np.uint8)
            self._trail      = np.zeros((rh, rw, 3), dtype=np.uint8)
            self._frame_size = (rh, rw)
        self._canvas[:] = 0

        # Trail: decaimento do rastro anterior
        trail_decay = config.FLOATING_CUBE_TRAIL_DECAY
        if trail_decay > 0 and self._trail is not None:
            cv2.multiply(self._trail, (trail_decay, trail_decay, trail_decay, 0),
                         dst=self._trail, dtype=cv2.CV_8U)

        # Sprint 5 — Pulsação senoidal no alpha global
        self._pulse_t += config.FLOATING_CUBE_PULSE_SPEED
        pulse = 1.0 + config.FLOATING_CUBE_PULSE_INTENSITY * math.sin(self._pulse_t)

        # --- Parâmetros visuais ---
        a_base     = config.FLOATING_CUBE_ALPHA * self._alpha * pulse
        energy     = self._energy
        # Reatividade: espessura aumenta levemente com velocidade
        energy_thick = int(energy * 2.0)
        f_thick    = config.FLOATING_CUBE_FRONT_THICKNESS + energy_thick
        b_thick    = config.FLOATING_CUBE_BACK_THICKNESS
        f_alpha    = config.FLOATING_CUBE_FRONT_ALPHA
        b_alpha    = config.FLOATING_CUBE_BACK_ALPHA
        core_thick = config.FLOATING_CUBE_CORE_THICKNESS
        halo_thick = config.FLOATING_CUBE_HALO_THICKNESS
        halo_alpha = config.FLOATING_CUBE_HALO_ALPHA
        # Colore neon: núcleo branco puro, halo ciano saturado
        col_core   = config.FLOATING_CUBE_CORE_COLOR   # (255,255,255) branco
        col_glow   = config.FLOATING_CUBE_GLOW_COLOR   # ciano neon
        desat      = config.FLOATING_CUBE_BACK_DESATURATE
        grey_luma  = 255  # núcleo é branco — luma fixo

        # --- Sprint 6: parâmetros volumétricos ---
        face_col    = config.FLOATING_CUBE_FACE_COLOR
        face_a_glb  = config.FLOATING_CUBE_FACE_ALPHA * self._alpha
        # z-center de cada face (usa rot_verts já calculados)
        face_z_vals = [
            sum(rot_verts[vi][2] for vi in face) / 4.0
            for face in self._FACES
        ]
        face_order = sorted(range(len(self._FACES)), key=lambda i: face_z_vals[i])
        back_fi    = [fi for fi in face_order if face_z_vals[fi] <= 0.0]
        front_fi   = [fi for fi in face_order if face_z_vals[fi] >  0.0]

        # ── FASE 1: Faces traseiras (sutil, dá volume ao fundo) ───────────
        for fi in back_fi:
            fz_n  = max(0.0, min(1.0, (face_z_vals[fi] - z_min) / z_range))
            fa    = face_a_glb * (0.45 + fz_n * 0.55)
            col_f = tuple(min(255, int(face_col[k] * fa)) for k in range(3))
            pts   = np.array(
                [(pts_2d[vi][0] - x0, pts_2d[vi][1] - y0) for vi in self._FACES[fi]],
                dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(self._canvas, [pts], col_f)

        # ── FASE 2: Arestas traseiras ─────────────────────────────────────
        for ei, (i0, i1) in enumerate(self._EDGES):
            z_n = (edge_z[ei] - z_min) / z_range
            if z_n > 0.55:
                continue
            ea   = b_alpha + (f_alpha - b_alpha) * z_n
            a    = a_base * ea
            brt  = 0.40 + z_n * 0.60
            cf   = tuple(
                min(255, int((col_core[k]*(1.0 - desat*(1.0-z_n)) + grey_luma*desat*(1.0-z_n)) * a * brt))
                for k in range(3))
            ch   = tuple(min(255, int(col_glow[k] * halo_alpha * ea * brt)) for k in range(3))
            p0   = (pts_2d[i0][0] - x0, pts_2d[i0][1] - y0)
            p1   = (pts_2d[i1][0] - x0, pts_2d[i1][1] - y0)
            cv2.line(self._canvas, p0, p1, ch, b_thick + halo_thick, cv2.LINE_AA)
            cv2.line(self._canvas, p0, p1, cf, max(1, core_thick), cv2.LINE_AA)

        # ── FASE 3: Partículas internas (rodam com o cubo) ────────────────
        if config.FLOATING_CUBE_VOLUMETRIC and self._particles_local:
            p_scaled = [(p[0]*size, p[1]*size, p[2]*size) for p in self._particles_local]
            rot_p    = self._rotate(p_scaled, self._rx, self._ry, self._rz)
            proj_p   = self._project(rot_p, cx, cy, fov)
            p_col    = config.FLOATING_CUBE_PARTICLE_COLOR
            p_alpha  = config.FLOATING_CUBE_PARTICLE_ALPHA * self._alpha
            p_depth  = config.FLOATING_CUBE_PARTICLE_DEPTH
            p_sz     = max(1, config.FLOATING_CUBE_PARTICLE_SIZE)
            pz_vals  = [rot_p[i][2] for i in range(len(rot_p))]
            pz_min   = min(pz_vals);  pz_max = max(pz_vals)
            pz_range = max(1.0, pz_max - pz_min)
            for pi in range(len(proj_p)):
                px = proj_p[pi][0] - x0
                py = proj_p[pi][1] - y0
                if not (0 <= px < rw and 0 <= py < rh):
                    continue
                pz_n  = (pz_vals[pi] - pz_min) / pz_range
                bright = (1.0 - p_depth) + p_depth * pz_n
                pa     = p_alpha * bright
                col_p  = tuple(min(255, int(p_col[k] * pa)) for k in range(3))
                cv2.circle(self._canvas, (px, py), p_sz, col_p, -1, cv2.LINE_AA)

        # ── FASE 4: Faces frontais (leve tint sobre partículas) ───────────
        for fi in front_fi:
            fz_n  = max(0.0, min(1.0, (face_z_vals[fi] - z_min) / z_range))
            fa    = face_a_glb * (0.45 + fz_n * 0.55)
            col_f = tuple(min(255, int(face_col[k] * fa)) for k in range(3))
            pts   = np.array(
                [(pts_2d[vi][0] - x0, pts_2d[vi][1] - y0) for vi in self._FACES[fi]],
                dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(self._canvas, [pts], col_f)

        # ── FASE 5: Arestas frontais neon ─────────────────────────────────
        for ei, (i0, i1) in enumerate(self._EDGES):
            z_n = (edge_z[ei] - z_min) / z_range
            if z_n <= 0.55:
                continue
            ea   = b_alpha + (f_alpha - b_alpha) * z_n
            a    = a_base * ea
            brt  = 0.40 + z_n * 0.60
            cf   = tuple(
                min(255, int((col_core[k]*(1.0 - desat*(1.0-z_n)) + grey_luma*desat*(1.0-z_n)) * a * brt))
                for k in range(3))
            ch   = tuple(min(255, int(col_glow[k] * halo_alpha * ea * brt)) for k in range(3))
            p0   = (pts_2d[i0][0] - x0, pts_2d[i0][1] - y0)
            p1   = (pts_2d[i1][0] - x0, pts_2d[i1][1] - y0)
            cv2.line(self._canvas, p0, p1, ch, f_thick + halo_thick, cv2.LINE_AA)
            cv2.line(self._canvas, p0, p1, cf, max(1, core_thick), cv2.LINE_AA)

        # ── FASE 6: Glow no ROI (dois passes) — reativo à energia ────────
        gi1 = config.FLOATING_CUBE_GLOW_INTENSITY * (1.0 + energy * 2.0)
        if gi1 > 0:
            gk1 = config.FLOATING_CUBE_GLOW_BLUR
            gk1 = gk1 if gk1 % 2 == 1 else gk1 + 1
            glow1 = cv2.GaussianBlur(self._canvas, (gk1, gk1), 0)
            cv2.addWeighted(self._canvas, 1.0, glow1, min(gi1, 3.0), 0, dst=self._canvas)
        gi2 = config.FLOATING_CUBE_GLOW2_INTENSITY * (1.0 + energy * 1.2)
        if gi2 > 0:
            gk2 = config.FLOATING_CUBE_GLOW2_BLUR
            gk2 = gk2 if gk2 % 2 == 1 else gk2 + 1
            glow2 = cv2.GaussianBlur(self._canvas, (gk2, gk2), 0)
            cv2.addWeighted(self._canvas, 1.0, glow2, min(gi2, 1.5), 0, dst=self._canvas)

        # Trail: somar rastro anterior e atualizar buffer
        if trail_decay > 0 and self._trail is not None:
            cv2.add(self._canvas, self._trail, dst=self._canvas)
            np.copyto(self._trail, self._canvas)

        cv2.add(frame[y0:y1, x0:x1], self._canvas, dst=frame[y0:y1, x0:x1])
        return frame


# ---------------------------------------------------------------------------
# FloatingTriangleEffect — Tetraedro holográfico flutuante
#
# Geometria: 4 vértices
#   v0, v1, v2 = base triangular (y = +1, plano XZ)
#   v3         = ápice superior (y = -1.6)
# 6 arestas: 3 da base + 3 laterais
# 4 faces triangulares (1 base + 3 laterais)
#
# Visual idêntico ao FloatingCubeEffect: núcleo branco, halo ciano,
# faces translúcidas, glow duplo no ROI, trail, pulsação.
#
# Interface obrigatória: apply(frame, mask, landmarks)
# ---------------------------------------------------------------------------

class FloatingTriangleEffect:
    """Tetraedro holográfico — mesmo look do FloatingCubeEffect."""

    _I_WRIST      = 0
    _I_THUMB_TIP  = 4
    _I_PALM       = [0, 5, 9, 13, 17]
    _I_INDEX_TIP  = 8
    _I_MID_BASE   = 9

    # 4 vértices em espaço local (escalados por SIZE)
    # Base: triângulo equilátero no plano y=+1
    # Ápice: y=-1.6 (acima)
    _r  = 1.0          # raio do triângulo base
    _h3 = _r * (3 ** 0.5) / 2.0
    _VERTS = [
        ( _r,        1.0,  0.0),           # v0 — base direita
        (-_r,        1.0,  0.0),           # v1 — base esquerda
        ( 0.0,       1.0,  _h3 * 2.0),    # v2 — base frente
        ( 0.0,      -1.6,  _h3 * 0.67),   # v3 — ápice
    ]

    # 6 arestas
    _EDGES = [
        (0, 1), (1, 2), (2, 0),   # base
        (0, 3), (1, 3), (2, 3),   # laterais
    ]

    # 4 faces triangulares (índices de vértices)
    _FACES = [
        (0, 1, 2),   # base
        (0, 1, 3),   # lateral esquerda-direita
        (1, 2, 3),   # lateral frente-esquerda
        (0, 2, 3),   # lateral frente-direita
    ]

    def __init__(self):
        self._rx          = 15.0
        self._ry          = 30.0
        self._rz          = 0.0
        self._rvx         = 0.0
        self._rvy         = 0.0
        self._scale       = 1.0
        self._alpha       = 0.0
        self._energy      = 0.0
        self._cx          = None
        self._cy          = None
        self._float_phase = 0.0
        self._prev_idx    = None
        self._prev_idx_tip= None
        self._canvas      = None
        self._trail       = None
        self._frame_size  = None
        self._pulse_t     = 0.0

    # ------------------------------------------------------------------
    @staticmethod
    def _rotate(verts, rx_deg, ry_deg, rz_deg):
        rx = math.radians(rx_deg); ry = math.radians(ry_deg); rz = math.radians(rz_deg)
        cx, sx = math.cos(rx), math.sin(rx)
        cy, sy = math.cos(ry), math.sin(ry)
        cz, sz = math.cos(rz), math.sin(rz)
        result = []
        for (vx, vy, vz) in verts:
            x1 = vx*cz - vy*sz;  y1 = vx*sz + vy*cz;  z1 = vz
            x2 = x1*cy + z1*sy;  y2 = y1;              z2 = -x1*sy + z1*cy
            x3 = x2;             y3 = y2*cx - z2*sx;   z3 = y2*sx + z2*cx
            result.append((x3, y3, z3))
        return result

    @staticmethod
    def _project(verts_3d, cx, cy, fov):
        pts = []
        for (x, y, z) in verts_3d:
            dz = max(fov * 0.10, fov + z)
            pts.append((int(cx + x * fov / dz), int(cy + y * fov / dz)))
        return pts

    # ------------------------------------------------------------------
    def apply(self, frame, mask, landmarks):
        h, w = frame.shape[:2]
        s    = motion.state

        if self._cx is None:
            self._cx = w * config.FLOATING_TRIANGLE_IDLE_X
            self._cy = h * config.FLOATING_TRIANGLE_IDLE_Y

        # Energia
        energy_t     = min(1.0, s.speed * config.FLOATING_TRIANGLE_ENERGY_FROM_SPEED
                                + s.accel * config.FLOATING_TRIANGLE_ACCEL_BURST)
        self._energy = self._energy * 0.85 + energy_t * 0.15

        # Posição com flutuação
        self._float_phase += config.FLOATING_TRIANGLE_IDLE_DRIFT_SPEED
        float_x = math.sin(self._float_phase)       * config.FLOATING_TRIANGLE_IDLE_DRIFT_AMP
        float_y = math.sin(self._float_phase * 0.71 + 1.1) * config.FLOATING_TRIANGLE_IDLE_DRIFT_AMP * 0.6
        base_cx = w * config.FLOATING_TRIANGLE_IDLE_X
        base_cy = h * config.FLOATING_TRIANGLE_IDLE_Y

        fade_step = config.FLOATING_TRIANGLE_FADE_SPEED
        smooth_p  = config.FLOATING_TRIANGLE_POSITION_SMOOTHING
        smooth_r  = config.FLOATING_TRIANGLE_ROTATION_SMOOTHING
        damp      = config.FLOATING_TRIANGLE_ROTATION_DAMPING

        if landmarks:
            self._alpha = min(1.0, self._alpha + fade_step)
            lm       = landmarks[0]
            palm_cx  = sum(lm[i].x for i in self._I_PALM) / len(self._I_PALM) * w
            palm_cy  = sum(lm[i].y for i in self._I_PALM) / len(self._I_PALM) * h
            wx = lm[0].x * w;  wy = lm[0].y * h
            bx = lm[9].x * w;  by = lm[9].y * h
            hand_size = max(1.0, math.hypot(bx - wx, by - wy))

            drift_str = config.FLOATING_TRIANGLE_DRIFT_STRENGTH
            tgt_cx = (base_cx + (palm_cx - base_cx) * drift_str) + float_x
            tgt_cy = (base_cy + (palm_cy - base_cy) * drift_str) + float_y
            self._cx = self._cx * smooth_p + tgt_cx * (1.0 - smooth_p)
            self._cy = self._cy * smooth_p + tgt_cy * (1.0 - smooth_p)

            idx_x = lm[8].x * w;  idx_y = lm[8].y * h
            thu_x = lm[4].x * w;  thu_y = lm[4].y * h

            if self._prev_idx_tip is not None:
                px_prev, py_prev = self._prev_idx_tip
                if abs(idx_x - px_prev) > hand_size * 0.8 or abs(idx_y - py_prev) > hand_size * 0.8:
                    self._prev_idx = None
            self._prev_idx_tip = (idx_x, idx_y)

            if self._prev_idx is not None:
                dx_c = max(-20.0, min(20.0, idx_x - self._prev_idx[0]))
                dy_c = max(-20.0, min(20.0, idx_y - self._prev_idx[1]))
                self._rvx = self._rvx * smooth_r + (-dy_c * config.FLOATING_TRIANGLE_FINGER_ROTATION_X) * (1.0 - smooth_r)
                self._rvy = self._rvy * smooth_r + ( dx_c * config.FLOATING_TRIANGLE_FINGER_ROTATION_Y) * (1.0 - smooth_r)
            self._prev_idx = (idx_x, idx_y)

            pinch_norm = max(0.0, min(1.0, math.hypot(thu_x - idx_x, thu_y - idx_y) / max(1.0, hand_size * 0.5)))
            mn_s, mx_s = config.FLOATING_TRIANGLE_MIN_SCALE, config.FLOATING_TRIANGLE_MAX_SCALE
            self._scale = self._scale * 0.90 + (mn_s + (mx_s - mn_s) * pinch_norm) * 0.10
        else:
            self._alpha = max(0.0, self._alpha - fade_step)
            self._rvx  *= damp;  self._rvy *= damp
            self._scale = self._scale * 0.95 + 1.0 * 0.05
            self._prev_idx = None;  self._prev_idx_tip = None

        if self._alpha < 0.005:
            return frame

        # Rotação
        self._rx = (self._rx + config.FLOATING_TRIANGLE_IDLE_ROTATION_X + self._rvx) % 360.0
        self._ry = (self._ry + config.FLOATING_TRIANGLE_IDLE_ROTATION_Y + self._rvy) % 360.0
        self._rz = (self._rz + config.FLOATING_TRIANGLE_IDLE_ROTATION_Z) % 360.0
        self._rvx *= damp;  self._rvy *= damp

        # Projeção 3D → 2D
        size = config.FLOATING_TRIANGLE_SIZE * self._scale
        fov  = config.FLOATING_TRIANGLE_PERSPECTIVE_FOV
        local_v = [(vx*size, vy*size, vz*size) for (vx, vy, vz) in self._VERTS]
        rot_v   = self._rotate(local_v, self._rx, self._ry, self._rz)
        cx, cy  = self._cx, self._cy
        pts_2d  = self._project(rot_v, cx, cy, fov)

        # Z médio por aresta e face
        edge_z = [(rot_v[i0][2] + rot_v[i1][2]) * 0.5 for (i0, i1) in self._EDGES]
        z_max  = max(edge_z) if edge_z else 1.0
        z_min  = min(edge_z) if edge_z else -1.0
        z_range = max(1.0, z_max - z_min)

        face_z = [sum(rot_v[vi][2] for vi in face) / 3.0 for face in self._FACES]

        # ROI
        all_x  = [p[0] for p in pts_2d]
        all_y  = [p[1] for p in pts_2d]
        pad    = config.FLOATING_TRIANGLE_GLOW_BLUR * 2 + 12
        x0     = max(0, min(all_x) - pad)
        y0     = max(0, min(all_y) - pad)
        x1     = min(w, max(all_x) + pad)
        y1     = min(h, max(all_y) + pad)
        rw, rh = x1 - x0, y1 - y0
        if rw < 4 or rh < 4:
            return frame

        if self._frame_size != (rh, rw):
            self._canvas     = np.zeros((rh, rw, 3), dtype=np.uint8)
            self._trail      = np.zeros((rh, rw, 3), dtype=np.uint8)
            self._frame_size = (rh, rw)
        self._canvas[:] = 0

        # Trail: decaimento
        trail_decay = config.FLOATING_TRIANGLE_TRAIL_DECAY
        if trail_decay > 0 and self._trail is not None:
            cv2.multiply(self._trail, (trail_decay, trail_decay, trail_decay, 0),
                         dst=self._trail, dtype=cv2.CV_8U)

        # Pulsação
        self._pulse_t += config.FLOATING_TRIANGLE_PULSE_SPEED
        pulse  = 1.0 + config.FLOATING_TRIANGLE_PULSE_INTENSITY * math.sin(self._pulse_t)
        a_base = config.FLOATING_TRIANGLE_ALPHA * self._alpha * pulse
        energy = self._energy

        # Parâmetros visuais
        f_alpha   = config.FLOATING_TRIANGLE_FRONT_ALPHA
        b_alpha   = config.FLOATING_TRIANGLE_BACK_ALPHA
        f_thick   = config.FLOATING_TRIANGLE_FRONT_THICKNESS + int(energy * 2.0)
        b_thick   = config.FLOATING_TRIANGLE_BACK_THICKNESS
        col_core  = config.FLOATING_TRIANGLE_CORE_COLOR
        col_glow  = config.FLOATING_TRIANGLE_GLOW_COLOR
        desat     = config.FLOATING_TRIANGLE_BACK_DESATURATE
        grey_luma = 255   # núcleo branco
        halo_a    = config.FLOATING_TRIANGLE_HALO_ALPHA
        halo_t    = config.FLOATING_TRIANGLE_HALO_THICKNESS
        core_t    = config.FLOATING_TRIANGLE_CORE_THICKNESS
        face_col  = config.FLOATING_TRIANGLE_FACE_COLOR
        face_a    = config.FLOATING_TRIANGLE_FACE_ALPHA * self._alpha

        # Ordena faces por Z (pintor)
        face_order = sorted(range(len(self._FACES)), key=lambda i: face_z[i])
        back_fi    = [fi for fi in face_order if face_z[fi] <= 0.0]
        front_fi   = [fi for fi in face_order if face_z[fi] >  0.0]

        def _draw_edge(ei, front):
            z_n = (edge_z[ei] - z_min) / z_range
            if front and z_n <= 0.55:
                return
            if not front and z_n > 0.55:
                return
            ea  = b_alpha + (f_alpha - b_alpha) * z_n
            a   = a_base * ea
            brt = 0.40 + z_n * 0.60
            cf  = tuple(
                min(255, int((col_core[k]*(1.0 - desat*(1.0-z_n)) + grey_luma*desat*(1.0-z_n)) * a * brt))
                for k in range(3))
            ch  = tuple(min(255, int(col_glow[k] * halo_a * ea * brt)) for k in range(3))
            i0, i1 = self._EDGES[ei]
            p0  = (pts_2d[i0][0] - x0, pts_2d[i0][1] - y0)
            p1  = (pts_2d[i1][0] - x0, pts_2d[i1][1] - y0)
            thick = f_thick if z_n > 0.55 else b_thick
            cv2.line(self._canvas, p0, p1, ch, thick + halo_t, cv2.LINE_AA)
            cv2.line(self._canvas, p0, p1, cf, max(1, core_t), cv2.LINE_AA)

        def _draw_face(fi):
            fz_n = max(0.0, min(1.0, (face_z[fi] - z_min) / z_range))
            fa   = face_a * (0.45 + fz_n * 0.55)
            col  = tuple(min(255, int(face_col[k] * fa)) for k in range(3))
            pts  = np.array(
                [(pts_2d[vi][0] - x0, pts_2d[vi][1] - y0) for vi in self._FACES[fi]],
                dtype=np.int32).reshape((-1, 1, 2))
            cv2.fillPoly(self._canvas, [pts], col)

        # Ordem: faces traseiras → arestas traseiras → faces frontais → arestas frontais
        for fi in back_fi:   _draw_face(fi)
        for ei in range(len(self._EDGES)): _draw_edge(ei, front=False)
        for fi in front_fi:  _draw_face(fi)
        for ei in range(len(self._EDGES)): _draw_edge(ei, front=True)

        # Glow duplo no ROI
        gi1 = config.FLOATING_TRIANGLE_GLOW_INTENSITY * (1.0 + energy * 2.0)
        if gi1 > 0:
            gk1 = config.FLOATING_TRIANGLE_GLOW_BLUR
            gk1 = gk1 if gk1 % 2 == 1 else gk1 + 1
            glow1 = cv2.GaussianBlur(self._canvas, (gk1, gk1), 0)
            cv2.addWeighted(self._canvas, 1.0, glow1, min(gi1, 3.0), 0, dst=self._canvas)
        gi2 = config.FLOATING_TRIANGLE_GLOW2_INTENSITY * (1.0 + energy * 1.2)
        if gi2 > 0:
            gk2 = config.FLOATING_TRIANGLE_GLOW2_BLUR
            gk2 = gk2 if gk2 % 2 == 1 else gk2 + 1
            glow2 = cv2.GaussianBlur(self._canvas, (gk2, gk2), 0)
            cv2.addWeighted(self._canvas, 1.0, glow2, min(gi2, 1.5), 0, dst=self._canvas)

        # Trail
        if trail_decay > 0 and self._trail is not None:
            cv2.add(self._canvas, self._trail, dst=self._canvas)
            np.copyto(self._trail, self._canvas)

        cv2.add(frame[y0:y1, x0:x1], self._canvas, dst=frame[y0:y1, x0:x1])
        return frame
