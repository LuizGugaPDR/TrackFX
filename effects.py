# effects.py
# AplicaÃ§Ã£o de efeitos visuais nas regiÃµes mascaradas.
# Interface padrÃ£o obrigatÃ³ria: apply(frame, mask, landmarks)
# O frame original nunca Ã© alterado diretamente â€” sempre usar cÃ³pia.
# A mÃ¡scara controla exatamente onde o efeito Ã© aplicado.
# Todos os efeitos processam apenas a ROI (bounding box da mÃ¡scara) para mÃ¡ximo FPS.

import random
import math
import time
import cv2
import numpy as np
import config
from tracking import HAND_CONNECTIONS, BodySegmenter


# ---------------------------------------------------------------------------
# UtilitÃ¡rios internos
# ---------------------------------------------------------------------------

def _get_mask_roi(mask):
    """Retorna (x1, y1, x2, y2) do bounding box da mÃ¡scara. None se vazia."""
    ys, xs = np.where(mask > 0)
    if len(xs) == 0:
        return None
    pad = 16
    h, w = mask.shape[:2]
    return (max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad),
            min(w, int(xs.max()) + pad), min(h, int(ys.max()) + pad))


def _blend_roi(frame, processed_roi, mask, x1, y1, x2, y2):
    """Cola ROI processada de volta no frame usando a mÃ¡scara como alpha."""
    result = frame.copy()
    roi_mask = mask[y1:y2, x1:x2]
    roi_mask_3ch = cv2.merge([roi_mask, roi_mask, roi_mask])
    region = result[y1:y2, x1:x2]
    result[y1:y2, x1:x2] = np.where(roi_mask_3ch > 0, processed_roi, region)
    return result


# ---------------------------------------------------------------------------
# GlitchEffect (avanÃ§ado: scanlines + blocos de ruÃ­do + RGB shift)
# ---------------------------------------------------------------------------

class GlitchEffect:
    """RGB shift + scanlines + blocos de ruÃ­do dentro da ROI mascarada."""

    def apply(self, frame, mask, landmarks):
        if mask is None or not np.any(mask):
            return frame
        roi = _get_mask_roi(mask)
        if roi is None:
            return frame
        x1, y1, x2, y2 = roi

        shift = config.GLITCH_SHIFT
        region = frame[y1:y2, x1:x2].copy()
        b, g, r = cv2.split(region)

        def shift_ch(ch, dx, dy):
            M = np.float32([[1, 0, dx], [0, 1, dy]])
            return cv2.warpAffine(ch, M, (ch.shape[1], ch.shape[0]),
                                  borderMode=cv2.BORDER_REFLECT)

        b = shift_ch(b, random.randint(-shift, shift), random.randint(-shift, shift))
        r = shift_ch(r, random.randint(-shift, shift), random.randint(-shift, shift))
        processed = cv2.merge([b, g, r])

        # Scanlines horizontais
        alpha = config.GLITCH_SCANLINE_ALPHA
        step = config.GLITCH_SCANLINE_STEP
        if alpha > 0:
            processed[::step, :] = (processed[::step, :] * (1.0 - alpha)).astype(np.uint8)

        # Blocos de ruÃ­do aleatÃ³rios
        rh, rw = processed.shape[:2]
        if random.random() < config.GLITCH_BLOCK_CHANCE:
            bs = config.GLITCH_BLOCK_SIZE
            bx = random.randint(0, max(0, rw - bs))
            by = random.randint(0, max(0, rh - bs))
            noise = np.random.randint(0, 256, (bs, bs, 3), dtype=np.uint8)
            processed[by:by + bs, bx:bx + bs] = noise

        return _blend_roi(frame, processed, mask, x1, y1, x2, y2)


# ---------------------------------------------------------------------------
# DistortionEffect
# ---------------------------------------------------------------------------

class DistortionEffect:
    """Warp senoidal aplicado apenas na ROI mascarada."""

    def apply(self, frame, mask, landmarks):
        if mask is None or not np.any(mask):
            return frame
        roi = _get_mask_roi(mask)
        if roi is None:
            return frame
        x1, y1, x2, y2 = roi

        amplitude = config.DISTORTION_AMPLITUDE
        frequency = config.DISTORTION_FREQUENCY
        region = frame[y1:y2, x1:x2].copy()
        rh, rw = region.shape[:2]

        map_x, map_y = np.meshgrid(np.arange(rw, dtype=np.float32),
                                   np.arange(rh, dtype=np.float32))
        map_x += amplitude * np.sin(2 * np.pi * map_y / frequency)
        map_y += amplitude * np.sin(2 * np.pi * map_x / frequency)

        processed = cv2.remap(region, map_x, map_y,
                              interpolation=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT)
        return _blend_roi(frame, processed, mask, x1, y1, x2, y2)


# ---------------------------------------------------------------------------
# DisplacementEffect (reativo Ã  posiÃ§Ã£o da mÃ£o)
# ---------------------------------------------------------------------------

class DisplacementEffect:
    """Deslocamento radial reativo Ã  posiÃ§Ã£o do centrÃ³ide da mÃ£o."""

    def __init__(self):
        self._smooth_cx = None
        self._smooth_cy = None

    def _centroid(self, landmarks, h, w):
        xs = [lm.x * w for hand in landmarks for lm in hand]
        ys = [lm.y * h for hand in landmarks for lm in hand]
        return float(np.mean(xs)), float(np.mean(ys))

    def apply(self, frame, mask, landmarks):
        if mask is None or not np.any(mask) or not landmarks:
            return frame
        roi = _get_mask_roi(mask)
        if roi is None:
            return frame
        x1, y1, x2, y2 = roi

        h, w = frame.shape[:2]
        cx, cy = self._centroid(landmarks, h, w)
        decay = config.DISPLACEMENT_DECAY
        if self._smooth_cx is None:
            self._smooth_cx, self._smooth_cy = cx, cy
        else:
            self._smooth_cx += decay * (cx - self._smooth_cx)
            self._smooth_cy += decay * (cy - self._smooth_cy)

        amplitude = config.DISPLACEMENT_AMPLITUDE
        region = frame[y1:y2, x1:x2].copy()
        rh, rw = region.shape[:2]

        gx, gy = np.meshgrid(np.arange(rw, dtype=np.float32),
                             np.arange(rh, dtype=np.float32))
        rel_x = gx - (self._smooth_cx - x1)
        rel_y = gy - (self._smooth_cy - y1)
        dist = np.sqrt(rel_x ** 2 + rel_y ** 2) + 1e-6
        strength = amplitude / (1.0 + dist * 0.05)
        map_x = (gx - (rel_x / dist) * strength).astype(np.float32)
        map_y = (gy - (rel_y / dist) * strength).astype(np.float32)

        processed = cv2.remap(region, map_x, map_y,
                              interpolation=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT)
        return _blend_roi(frame, processed, mask, x1, y1, x2, y2)


# ---------------------------------------------------------------------------
# AuraEffect â€” glow pulsante ao redor da mÃ£o
# ---------------------------------------------------------------------------

class AuraEffect:
    """
    Cria um campo de energia/aura ao redor da mÃ£o.
    - Dilata a mÃ¡scara progressivamente em camadas
    - Aplica blur gaussiano para suavizar cada camada
    - CompÃµe as camadas com adiÃ§Ã£o ponderada (glow)
    - PulsaÃ§Ã£o temporal via seno
    """

    def __init__(self):
        self._t = 0.0

    def apply(self, frame, mask, landmarks):
        if mask is None or not np.any(mask):
            return frame

        self._t += config.AURA_PULSE_SPEED
        pulse = 0.75 + 0.25 * math.sin(self._t)  # oscila entre 0.75 e 1.0

        color_bgr = config.AURA_COLOR
        layers = config.AURA_LAYERS
        blur_base = config.AURA_BLUR_BASE
        intensity = config.AURA_INTENSITY * pulse

        result = frame.copy()
        h, w = frame.shape[:2]

        # MÃ¡scara colorida base
        color_layer = np.zeros((h, w, 3), dtype=np.uint8)
        color_layer[mask > 0] = color_bgr

        # ComposiÃ§Ã£o em camadas â€” cada camada dilata e blura mais
        glow = np.zeros((h, w, 3), dtype=np.float32)
        for i in range(1, layers + 1):
            # Dilata a mÃ¡scara proporcionalmente Ã  camada
            kernel_size = blur_base + (i - 1) * 20
            kernel_size = kernel_size if kernel_size % 2 == 1 else kernel_size + 1
            blurred = cv2.GaussianBlur(color_layer, (kernel_size, kernel_size), 0)
            weight = intensity * (1.0 / i)
            glow += blurred.astype(np.float32) * weight

        glow = np.clip(glow, 0, 255).astype(np.uint8)

        # Adiciona glow ao frame (screen blend simplificado)
        result = cv2.add(result, glow)

        # ReforÃ§a a cor sobre a regiÃ£o da mÃ£o
        mask_3ch = cv2.merge([mask, mask, mask])
        hand_tint = np.zeros_like(result)
        hand_tint[mask > 0] = color_bgr
        hand_tint = cv2.GaussianBlur(hand_tint, (blur_base, blur_base), 0)
        result = cv2.addWeighted(result, 1.0, hand_tint, 0.4 * pulse, 0)

        return result


# ---------------------------------------------------------------------------
# TrailEffect â€” ghosting de frames anteriores
# ---------------------------------------------------------------------------

class TrailEffect:
    """
    MantÃ©m um buffer dos Ãºltimos N frames mascarados.
    CompÃµe os fantasmas com decaimento de alpha e blur,
    criando um rastro visual reativo ao movimento da mÃ£o.
    """

    def __init__(self):
        self._buffer = []  # lista de (roi_frame, mask_snapshot, x1, y1, x2, y2)

    def apply(self, frame, mask, landmarks):
        if mask is None or not np.any(mask):
            self._buffer.clear()
            return frame

        roi = _get_mask_roi(mask)
        if roi is None:
            return frame
        x1, y1, x2, y2 = roi

        # Captura snapshot da ROI atual para o buffer
        snapshot = frame[y1:y2, x1:x2].copy()
        mask_snap = mask[y1:y2, x1:x2].copy()
        self._buffer.append((snapshot, mask_snap, x1, y1, x2, y2))

        max_len = config.TRAIL_LENGTH + 1
        if len(self._buffer) > max_len:
            self._buffer.pop(0)

        result = frame.copy()
        decay = config.TRAIL_DECAY
        blur_k = config.TRAIL_BLUR
        color_shift = config.TRAIL_COLOR_SHIFT

        # CompÃµe fantasmas do mais antigo ao mais recente
        num_ghosts = len(self._buffer) - 1
        for idx, (ghost_roi, ghost_mask, gx1, gy1, gx2, gy2) in enumerate(self._buffer[:-1]):
            alpha = decay * ((idx + 1) / (num_ghosts + 1)) ** 1.5

            ghost = ghost_roi.copy()
            if blur_k > 1:
                ghost = cv2.GaussianBlur(ghost, (blur_k, blur_k), 0)

            # Shift de cor progressivo nos fantasmas
            if color_shift:
                b, g, r = cv2.split(ghost)
                channel_shift = idx + 1
                M = np.float32([[1, 0, channel_shift], [0, 1, 0]])
                r = cv2.warpAffine(r, M, (r.shape[1], r.shape[0]))
                M2 = np.float32([[1, 0, -channel_shift], [0, 1, 0]])
                b = cv2.warpAffine(b, M2, (b.shape[1], b.shape[0]))
                ghost = cv2.merge([b, g, r])

            # ComposiÃ§Ã£o dentro dos limites de roi
            gry = min(gy2 - gy1, result.shape[0] - gy1)
            grx = min(gx2 - gx1, result.shape[1] - gx1)
            if gry <= 0 or grx <= 0:
                continue

            dest = result[gy1:gy1 + gry, gx1:gx1 + grx]
            src = ghost[:gry, :grx]
            gmask = ghost_mask[:gry, :grx]
            gmask_3ch = cv2.merge([gmask, gmask, gmask]).astype(np.float32) / 255.0

            blended = (src.astype(np.float32) * alpha * gmask_3ch
                       + dest.astype(np.float32) * (1.0 - alpha * gmask_3ch))
            result[gy1:gy1 + gry, gx1:gx1 + grx] = np.clip(blended, 0, 255).astype(np.uint8)

        return result


# ---------------------------------------------------------------------------
# FireEffect â€” fogo ascendente via scrolling noise + alpha blending real
# ---------------------------------------------------------------------------

class FireEffect:
    """
    SimulaÃ§Ã£o de chamas convincente:
    - Noise buffer scrollado para cima a cada frame â†’ movimento vertical visÃ­vel
    - Seeds esparsas e aleatÃ³rias na base â†’ formas orgÃ¢nicas, nÃ£o bloco sÃ³lido
    - Threshold cria "tendÃµes" de chama com gaps naturais
    - Gradiente vertical: base quente, topo dissipado
    - LUT com canal alpha: transparÃªncia real por nÃ­vel de calor
    - Glow aditivo ao redor das chamas quentes
    """

    def __init__(self):
        self._noise = None          # buffer interno float32 [sh x sw]
        self._shape = (0, 0)
        self._lut_bgr, self._lut_alpha = self._build_lut()
        self._t = 0.0               # fase temporal para seeds coerentes (lÃ­nguas de fogo)

    # ------------------------------------------------------------------
    def _build_lut(self):
        """LUT separada para BGR (cor) e alpha (transparÃªncia)."""
        lut_bgr   = np.zeros((256, 3), dtype=np.uint8)
        lut_alpha = np.zeros(256,      dtype=np.uint8)

        # (valor_intensidade, (B, G, R), alpha)
        stops = [
            (0,   (0,   0,   0  ), 0  ),   # invisÃ­vel
            (20,  (0,   0,   0  ), 0  ),   # invisÃ­vel
            (42,  (0,   0,   110), 70 ),   # brasa escura
            (78,  (0,   8,   200), 160),   # vermelho escuro
            (115, (0,   55,  248), 210),   # vermelho vivo
            (148, (0,   145, 255), 235),   # laranja-vermelho  â† transiÃ§Ã£o cedo
            (182, (25,  218, 255), 248),   # laranja puro
            (212, (130, 248, 255), 253),   # amarelo-laranja
            (238, (225, 255, 255), 255),   # branco-amarelo
            (255, (255, 255, 255), 255),   # nÃºcleo branco
        ]
        for i in range(len(stops) - 1):
            v0, c0, a0 = stops[i]
            v1, c1, a1 = stops[i + 1]
            for j in range(v0, v1 + 1):
                t = (j - v0) / max(1, v1 - v0)
                lut_bgr[j]   = [int(c0[k] + (c1[k] - c0[k]) * t) for k in range(3)]
                lut_alpha[j] = int(a0 + (a1 - a0) * t)
        lut_bgr[255]   = stops[-1][1]
        lut_alpha[255] = stops[-1][2]
        return lut_bgr, lut_alpha

    # ------------------------------------------------------------------
    def _get_fire_roi(self, mask, frame_shape):
        ys, xs = np.where(mask > 0)
        if len(xs) == 0:
            return None
        fh, fw = frame_shape[:2]
        hand_h   = max(1, int(ys.max()) - int(ys.min()))
        pad_top  = int(hand_h * config.FIRE_FLAME_HEIGHT)
        pad_side = 30
        pad_bot  = 10
        return (max(0, int(xs.min()) - pad_side),
                max(0, int(ys.min()) - pad_top),
                min(fw, int(xs.max()) + pad_side),
                min(fh, int(ys.max()) + pad_bot))

    # ------------------------------------------------------------------
    def apply(self, frame, mask, landmarks):
        if mask is None or not np.any(mask):
            # Cool down silencioso quando mÃ£o some
            if self._noise is not None:
                self._noise *= 0.88
            return frame

        roi = self._get_fire_roi(mask, frame.shape)
        if roi is None:
            return frame
        x1, y1, x2, y2 = roi
        rw, rh = x2 - x1, y2 - y1
        if rw < 6 or rh < 6:
            return frame

        scale = config.FIRE_SCALE
        sw = max(8, int(rw * scale))
        sh = max(8, int(rh * scale))

        # Reinicia buffer se tamanho mudou
        if self._shape != (sh, sw):
            self._noise = np.zeros((sh, sw), dtype=np.float32)
            self._shape = (sh, sw)

        # ---- 1. Scroll do noise para CIMA (movimento de chama) ----
        scroll = config.FIRE_SCROLL
        self._noise = np.roll(self._noise, -scroll, axis=0)
        self._noise[-scroll:, :] = 0.0   # limpa linhas que "saÃ­ram pelo topo"

        # ---- 2. Seeds com coerÃªncia temporal â€” cria lÃ­nguas contÃ­nuas, nÃ£o pontos ----
        self._t += 0.07
        cols = np.arange(sw, dtype=np.float32)
        # Energia por coluna varia no tempo â†’ colunas persistentemente quentes = lÃ­ngua de fogo
        col_e = (
            np.sin(cols * 0.30 + self._t * 2.8) * 0.45 +
            np.sin(cols * 0.72 + self._t * 1.6) * 0.30 +
            np.sin(cols * 1.40 + self._t * 3.8) * 0.15
        )
        col_e = np.clip((col_e + 0.90) / 1.80, 0.10, 1.0)  # normaliza â†’ [0.10, 1.0]

        mask_roi = mask[y1:y2, x1:x2]
        mask_s   = cv2.resize(mask_roi.astype(np.float32), (sw, sh),
                              interpolation=cv2.INTER_LINEAR) / 255.0

        seed_rows = max(2, int(sh * config.FIRE_SEED_HEIGHT))
        raw = np.random.rand(seed_rows, sw).astype(np.float32) * 0.28  # micro-textura fina
        seed_mat = col_e[np.newaxis, :] * np.ones((seed_rows, 1), dtype=np.float32)
        seeds = np.clip((seed_mat + raw) * config.FIRE_INTENSITY, 0.0, 1.0)
        self._noise[-seed_rows:, :] = seeds * mask_s[-seed_rows:, :]

        # ---- 3. Blur assimÃ©trico: estreito Ã— alto â†’ elongaÃ§Ã£o vertical da chama ----
        self._noise = cv2.GaussianBlur(self._noise, (3, 7), 0)

        # ---- 4. Resfriamento progressivo â€” cria gradiente natural: base quente, topo frio ----
        self._noise = np.clip(self._noise * config.FIRE_COOLING, 0.0, 1.0)

        # ---- 5. Threshold cria gaps/tendÃµes (cooling jÃ¡ gera o falloff vertical) ----
        thr = config.FIRE_THRESHOLD
        heat_shaped = np.clip((self._noise - thr) / max(0.01, 1.0 - thr), 0.0, 1.0)

        # ---- 6. Upscale + suavizaÃ§Ã£o vertical pÃ³s-upscale â†’ massa contÃ­nua de chama ----
        heat_up = cv2.resize(heat_shaped, (rw, rh), interpolation=cv2.INTER_LINEAR)
        heat_up = cv2.GaussianBlur(heat_up, (5, 9), 0)

        # ---- 7. Color map via LUT (cor + alpha) ----
        heat_u8   = (heat_up * 255).astype(np.uint8)
        fire_bgr  = self._lut_bgr[heat_u8]                          # (rh, rw, 3)
        fire_alph = self._lut_alpha[heat_u8].astype(np.float32) / 255.0  # (rh, rw)

        # ---- 8. Alpha blend real: fire composto sobre o frame original ----
        result   = frame.copy()
        region_f = result[y1:y2, x1:x2].astype(np.float32)
        fire_f   = fire_bgr.astype(np.float32)
        a3       = fire_alph[:, :, np.newaxis]   # broadcast para 3 canais
        blended  = region_f * (1.0 - a3) + fire_f * a3
        result[y1:y2, x1:x2] = np.clip(blended, 0, 255).astype(np.uint8)

        # ---- 9. Glow aditivo nas regiÃµes quentes ----
        if config.FIRE_GLOW_INTENSITY > 0:
            hot_thresh = 0.12  # threshold baixo â†’ mais Ã¡rea com glow
            glow_mask  = (heat_up > hot_thresh).astype(np.float32)[:, :, np.newaxis]
            glow_src   = np.clip(fire_bgr.astype(np.float32) * glow_mask, 0, 255).astype(np.uint8)

            glow_full  = np.zeros_like(frame)
            glow_full[y1:y2, x1:x2] = glow_src

            gk = config.FIRE_GLOW_BLUR
            gk = gk if gk % 2 == 1 else gk + 1
            glow_blur = cv2.GaussianBlur(glow_full, (gk, gk), 0)

            if config.SHOW_FIRE_GLOW_DEBUG:
                # Exibe o canal de glow isolado (sem compor com o frame)
                result = np.clip(glow_blur.astype(np.float32) * 3.0, 0, 255).astype(np.uint8)
            else:
                result = np.clip(
                    result.astype(np.float32) + glow_blur.astype(np.float32) * config.FIRE_GLOW_INTENSITY,
                    0, 255
                ).astype(np.uint8)

        # ---- 10. Debug: heat map em falso colorido ----
        if config.SHOW_FIRE_MASK_DEBUG:
            heat_vis = (heat_up * 255).astype(np.uint8)
            heat_color = cv2.applyColorMap(heat_vis, cv2.COLORMAP_INFERNO)
            # SobrepÃµe sÃ³ onde hÃ¡ calor detectÃ¡vel
            dbg_mask = (heat_up > 0.01).astype(np.float32)[:, :, np.newaxis]
            roi_region = result[y1:y2, x1:x2].astype(np.float32)
            result[y1:y2, x1:x2] = np.clip(
                roi_region * (1.0 - dbg_mask) + heat_color.astype(np.float32) * dbg_mask,
                0, 255
            ).astype(np.uint8)
            # Label mostrando max heat para diagnÃ³stico
            max_h = float(heat_up.max())
            cv2.putText(result, f"heat_max={max_h:.3f}  thr={config.FIRE_THRESHOLD:.2f}",
                        (x1, max(y1 - 6, 14)), cv2.FONT_HERSHEY_SIMPLEX,
                        0.5, (0, 255, 255), 1, cv2.LINE_AA)

        return result


# ---------------------------------------------------------------------------
# OrganicWarpEffect â€” warp lÃ­quido multi-octave reativo ao movimento
# ---------------------------------------------------------------------------

class OrganicWarpEffect:
    """
    DeformaÃ§Ã£o orgÃ¢nica baseada em ruÃ­do senoidal multi-octave.
    - Amplitude escala com velocidade da mÃ£o (mais movimento = mais warp)
    - 3 octaves de ruÃ­do para feel lÃ­quido/orgÃ¢nico
    - Processamento apenas na ROI mascarada
    """

    def __init__(self):
        self._t = 0.0
        self._prev_cx = None
        self._prev_cy = None
        self._velocity = 0.0

    def _centroid(self, landmarks, h, w):
        xs = [lm.x * w for hand in landmarks for lm in hand]
        ys = [lm.y * h for hand in landmarks for lm in hand]
        return float(np.mean(xs)), float(np.mean(ys))

    def apply(self, frame, mask, landmarks):
        if mask is None or not np.any(mask):
            self._velocity *= 0.85
            return frame

        roi = _get_mask_roi(mask)
        if roi is None:
            return frame
        x1, y1, x2, y2 = roi

        # Velocidade da mÃ£o â†’ amplitude do warp
        h, w = frame.shape[:2]
        if landmarks:
            cx, cy = self._centroid(landmarks, h, w)
            if self._prev_cx is not None:
                speed = math.sqrt((cx - self._prev_cx) ** 2 + (cy - self._prev_cy) ** 2)
                self._velocity = min(1.0, self._velocity * 0.7 + (speed / 30.0) * 0.3)
            self._prev_cx, self._prev_cy = cx, cy

        self._t += config.ORGANIC_FREQ_TEMPORAL * 0.033

        region = frame[y1:y2, x1:x2].copy()
        rh, rw = region.shape[:2]
        t  = self._t
        fs = config.ORGANIC_FREQ_SPATIAL
        amp = config.ORGANIC_AMPLITUDE * (0.5 + 1.0 * self._velocity)

        gx, gy = np.meshgrid(np.arange(rw, dtype=np.float32),
                             np.arange(rh, dtype=np.float32))

        # 3 octaves senoidal para feel orgÃ¢nico
        dx = (np.sin(gx * fs        + t * 1.0) * np.cos(gy * fs * 0.7  + t * 1.3) +
              np.sin(gx * fs * 2.1  + t * 1.7) * np.cos(gy * fs * 1.8  + t * 0.8) * 0.5 +
              np.sin(gx * fs * 4.3  + t * 2.3) * 0.25) * amp

        dy = (np.cos(gx * fs * 0.8  + t * 0.9) * np.sin(gy * fs        + t * 1.1) +
              np.cos(gx * fs * 1.9  + t * 1.4) * np.sin(gy * fs * 2.2  + t * 0.7) * 0.5 +
              np.cos(gy * fs * 4.1  + t * 1.9) * 0.25) * amp

        map_x = (gx + dx).astype(np.float32)
        map_y = (gy + dy).astype(np.float32)

        processed = cv2.remap(region, map_x, map_y,
                              interpolation=cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REFLECT)
        return _blend_roi(frame, processed, mask, x1, y1, x2, y2)


# ---------------------------------------------------------------------------
# RibbonWarpEffect â€” smear lÃ­quido + wave distortion + chromatic aberration
# EstÃ©tica TouchDesigner: buffer de persistÃªncia + RGB split + bloom
# ---------------------------------------------------------------------------

class RibbonWarpEffect:
    """
    Sprint 12 â€” Dual-Layer Echo Smear com profundidade visual:
    - Near layer: decay rÃ¡pido, tint quente (laranja/amarelo), RGB split forte
    - Far  layer: decay lento, tint frio (ciano/azul), RGB split suave
    - Wave distortion independente por camada (fases opostas â†’ movem diferente)
    - SeparaÃ§Ã£o direcional: far deslocada mais na direÃ§Ã£o de movimento â†’ profundidade
    - Screen blend das duas camadas â†’ composiÃ§Ã£o luminosa (nunca escurece)
    - Scanline overlay CRT sobre a ROI final
    - Todos os parÃ¢metros reativos Ã  velocidade via EMA + dead zone
    """

    def __init__(self):
        self._near        = None
        self._near_alpha  = None
        self._far         = None
        self._far_alpha   = None
        self._t           = 0.0
        self._prev_cx     = None
        self._prev_cy     = None
        self._vx          = 0.0
        self._vy          = 0.0
        self._speed       = 0.0

    # ------------------------------------------------------------------
    def _get_roi(self, mask, frame_shape):
        ys, xs = np.where(mask > 0)
        if len(xs) == 0:
            return None
        fh, fw = frame_shape[:2]
        pad = config.RIBBON_PAD
        return (max(0, int(xs.min()) - pad),
                max(0, int(ys.min()) - pad),
                min(fw, int(xs.max()) + pad),
                min(fh, int(ys.max()) + pad))

    # ------------------------------------------------------------------
    def _update_velocity(self, landmarks, h, w):
        ema = config.RIBBON_VEL_EMA
        if not landmarks:
            self._vx    *= ema
            self._vy    *= ema
            self._speed *= ema
            return
        xs = [lm.x * w for hand in landmarks for lm in hand]
        ys = [lm.y * h for hand in landmarks for lm in hand]
        cx, cy = float(np.mean(xs)), float(np.mean(ys))
        if self._prev_cx is not None:
            raw_vx = cx - self._prev_cx
            raw_vy = cy - self._prev_cy
            self._vx = self._vx * ema + raw_vx * (1.0 - ema)
            self._vy = self._vy * ema + raw_vy * (1.0 - ema)
            raw_speed = math.sqrt(self._vx ** 2 + self._vy ** 2)
            effective = max(0.0, raw_speed - config.RIBBON_DEAD_ZONE)
            self._speed = min(1.0, effective / max(0.1, config.RIBBON_SPEED_MAX))
        self._prev_cx, self._prev_cy = cx, cy

    # ------------------------------------------------------------------
    def apply(self, frame, mask, landmarks):
        h, w = frame.shape[:2]
        self._update_velocity(landmarks, h, w)

        if mask is None or not np.any(mask):
            if self._near is not None:
                self._near        *= 0.82
                self._near_alpha  *= 0.82
                self._far         *= 0.86
                self._far_alpha   *= 0.86
            return frame

        roi = self._get_roi(mask, frame.shape)
        if roi is None:
            return frame
        x1, y1, x2, y2 = roi
        rw, rh = x2 - x1, y2 - y1
        if rw < 10 or rh < 10:
            return frame

        self._t += 0.055
        spd = self._speed
        vs  = config.RIBBON_VEL_SCALE

        # ---- ParÃ¢metros reativos Ã  velocidade ----
        near_decay = min(0.96,  config.RIBBON_NEAR_DECAY + spd * vs * 0.09)
        far_decay  = min(0.985, config.RIBBON_FAR_DECAY  + spd * vs * 0.04)
        amp        = config.RIBBON_WAVE_AMP  * (1.0 + spd * vs * 2.8)
        near_split = config.RIBBON_RGB_SPLIT * (1.0 + spd * vs * 3.0)
        far_split  = config.RIBBON_RGB_SPLIT * 0.45 * (1.0 + spd * vs * 1.8)
        intens     = config.RIBBON_INTENSITY * (1.0 + spd * vs * 0.5)

        # ---- Vetor direcional ----
        raw_speed = math.sqrt(self._vx ** 2 + self._vy ** 2) + 1e-6
        ndx, ndy  = self._vx / raw_speed, self._vy / raw_speed
        dir_str   = spd * vs

        # ---- Init/reinit buffers ----
        if (self._near is None
                or self._near.shape[0] != rh
                or self._near.shape[1] != rw):
            snap             = frame[y1:y2, x1:x2].astype(np.float32).copy()
            self._near       = snap.copy()
            self._near_alpha = np.zeros((rh, rw), dtype=np.float32)
            self._far        = snap.copy()
            self._far_alpha  = np.zeros((rh, rw), dtype=np.float32)

        # ---- Atualiza smear layers ----
        current  = frame[y1:y2, x1:x2].astype(np.float32)
        mask_roi = cv2.resize(mask[y1:y2, x1:x2].astype(np.float32),
                              (rw, rh), interpolation=cv2.INTER_LINEAR) / 255.0
        mask_3 = mask_roi[:, :, np.newaxis]

        self._near       = self._near       * near_decay + current * mask_3 * (1.0 - near_decay)
        self._near_alpha = np.clip(self._near_alpha * near_decay + mask_roi * (1.0 - near_decay), 0.0, 1.0)
        self._far        = self._far        * far_decay  + current * mask_3 * (1.0 - far_decay)
        self._far_alpha  = np.clip(self._far_alpha  * far_decay  + mask_roi * (1.0 - far_decay),  0.0, 1.0)

        # ---- Wave maps com fases independentes por camada ----
        gx, gy = np.meshgrid(np.arange(rw, dtype=np.float32),
                              np.arange(rh, dtype=np.float32))
        t    = self._t
        freq = config.RIBBON_WAVE_FREQ
        drag = amp * dir_str * 1.5

        # Near: fase 0 â€” drag leve
        dx_n = (amp       * np.sin(gy * freq               + t * 2.3) +
                amp * 0.4 * np.cos(gx * freq * 0.72        + t * 3.1) +
                amp * 0.2 * np.sin((gx + gy) * freq * 0.5  + t * 1.7)) + (-ndx * drag * 0.6)
        dy_n = (amp       * np.cos(gx * freq               + t * 1.8) +
                amp * 0.4 * np.sin(gy * freq * 0.85        + t * 2.5) +
                amp * 0.2 * np.cos((gx - gy) * freq * 0.4  + t * 2.9)) + (-ndy * drag * 0.6)

        # Far: fase Ï€/2 + separaÃ§Ã£o extra â€” drag forte + layer offset
        sep  = config.RIBBON_LAYER_SEP * dir_str
        dx_f = (amp       * np.sin(gy * freq               + t * 2.3 + 1.57) +
                amp * 0.4 * np.cos(gx * freq * 0.72        + t * 3.1 + 1.05) +
                amp * 0.2 * np.sin((gx + gy) * freq * 0.5  + t * 1.7 + 2.09)) + (-ndx * (drag + sep))
        dy_f = (amp       * np.cos(gx * freq               + t * 1.8 + 0.79) +
                amp * 0.4 * np.sin(gy * freq * 0.85        + t * 2.5 + 1.57) +
                amp * 0.2 * np.cos((gx - gy) * freq * 0.4  + t * 2.9 + 0.52)) + (-ndy * (drag + sep))

        # ---- Helper: remap com RGB split direcional ----
        def _remap_split(layer_u8, wdx, wdy, split, nd_x, nd_y, d_str):
            b_ch, g_ch, r_ch = cv2.split(layer_u8)
            base_s = 1.0 - d_str
            rx = split * ( nd_x * d_str + base_s)
            ry = split *   nd_y * d_str
            bx = split * (-nd_x * d_str - base_s)
            by = split * (-nd_y * d_str)

            def _rc(ch, ex, ey):
                mx = np.clip(gx + wdx + ex, 0, rw - 1).astype(np.float32)
                my = np.clip(gy + wdy + ey, 0, rh - 1).astype(np.float32)
                return cv2.remap(ch, mx, my, cv2.INTER_LINEAR,
                                 borderMode=cv2.BORDER_REFLECT)

            return cv2.merge([_rc(b_ch, bx, by), _rc(g_ch, 0, 0), _rc(r_ch, rx, ry)])

        # ---- Near: tint quente ----
        near_u8   = np.clip(self._near, 0, 255).astype(np.uint8)
        near_dist = _remap_split(near_u8, dx_n, dy_n,
                                 near_split, ndx, ndy, dir_str).astype(np.float32)
        nt = config.RIBBON_NEAR_TINT          # (B_scale, G_scale, R_scale)
        near_dist[:, :, 0] *= nt[0]
        near_dist[:, :, 1] *= nt[1]
        near_dist[:, :, 2] *= nt[2]
        near_dist = np.clip(near_dist, 0, 255)

        # ---- Far: tint frio ----
        far_u8   = np.clip(self._far, 0, 255).astype(np.uint8)
        far_dist = _remap_split(far_u8, dx_f, dy_f,
                                far_split, ndx, ndy, dir_str).astype(np.float32)
        ft = config.RIBBON_FAR_TINT           # (B_scale, G_scale, R_scale)
        far_dist[:, :, 0] *= ft[0]
        far_dist[:, :, 1] *= ft[1]
        far_dist[:, :, 2] *= ft[2]
        far_dist = np.clip(far_dist, 0, 255)

        # ---- Screen blend: near + far â†’ composite luminoso ----
        near_n    = near_dist / 255.0
        far_n     = far_dist  / 255.0
        composite = np.clip(1.0 - (1.0 - near_n) * (1.0 - far_n), 0.0, 1.0)

        # Alpha das camadas via screen
        near_a3 = np.clip(self._near_alpha * intens,        0.0, 1.0)[:, :, np.newaxis]
        far_a3  = np.clip(self._far_alpha  * intens * 0.72, 0.0, 1.0)[:, :, np.newaxis]
        alpha_3 = np.clip(1.0 - (1.0 - near_a3) * (1.0 - far_a3), 0.0, 1.0)

        # ---- Alpha blend composite sobre o frame ----
        result   = frame.copy()
        orig_roi = result[y1:y2, x1:x2].astype(np.float32) / 255.0
        blended  = orig_roi * (1.0 - alpha_3) + composite * alpha_3
        result[y1:y2, x1:x2] = np.clip(blended * 255, 0, 255).astype(np.uint8)

        # ---- Glow bloom sobre o composite ----
        if config.RIBBON_GLOW > 0:
            glow_int  = config.RIBBON_GLOW * (1.0 + spd * vs * 1.2)
            luminance = composite.mean(axis=2)
            hot       = (luminance > 0.18).astype(np.float32)
            glow_src  = np.clip(composite * hot[:, :, np.newaxis] * alpha_3 * 255,
                                0, 255).astype(np.uint8)
            glow_full = np.zeros_like(frame, dtype=np.uint8)
            glow_full[y1:y2, x1:x2] = glow_src
            gk = config.RIBBON_GLOW_BLUR
            gk = gk if gk % 2 == 1 else gk + 1
            glow_blur = cv2.GaussianBlur(glow_full, (gk, gk), 0)
            result = np.clip(
                result.astype(np.float32) + glow_blur.astype(np.float32) * glow_int,
                0, 255
            ).astype(np.uint8)

        # ---- Scanline overlay â€” textura CRT sobre a ROI ----
        if config.RIBBON_SCANLINES > 0:
            scan_roi = result[y1:y2, x1:x2].astype(np.float32)
            scan_roi[::2, :] *= (1.0 - config.RIBBON_SCANLINES)
            result[y1:y2, x1:x2] = np.clip(scan_roi, 0, 255).astype(np.uint8)

        return result


# ---------------------------------------------------------------------------
# TrackingOverlayEffect â€” modo de tracking visual puro (sem VFX)
# Exibe skeleton, joints e hull da mÃ£o sobre o frame original.
# ---------------------------------------------------------------------------

class TrackingOverlayEffect:
    """
    Modo de tracking visual puro â€” sem efeitos VFX.
    Exibe skeleton, landmarks e hull da mÃ£o sobre o frame original limpo.
    - Hull outline: contorno fino da mÃ£o (cor ciano)
    - Skeleton: linhas verdes conectando landmarks
    - Joints: pontos cinzas pequenos nos nÃ³s intermediÃ¡rios
    - Fingertips: pontos maiores com cores distintas por dedo
    """

    # Pontas de dedo: cor BGR distinta por dedo
    _TIP_COLORS = {
        4:  (0,   140, 255),   # polegar  â€” laranja
        8:  (0,   230, 255),   # indicador â€” amarelo
        12: (60,  255, 120),   # mÃ©dio     â€” verde-claro
        16: (240, 100,  50),   # anelar    â€” azul
        20: (220,  50, 240),   # mÃ­nimo    â€” magenta
    }
    _TIPS = frozenset(_TIP_COLORS.keys())

    def apply(self, frame, mask, landmarks):
        if not landmarks:
            return frame

        result = frame.copy()
        h, w   = frame.shape[:2]

        # ---- Hull outline (contorno da mÃ£o) ----
        if mask is not None and np.any(mask):
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(result, contours, -1, (80, 255, 200), 1, cv2.LINE_AA)

        for hand_lms in landmarks:
            pts = [(int(lm.x * w), int(lm.y * h)) for lm in hand_lms]

            # ---- Linhas do skeleton ----
            for s, e in HAND_CONNECTIONS:
                cv2.line(result, pts[s], pts[e], (40, 200, 55), 2, cv2.LINE_AA)

            # ---- Joints intermediÃ¡rios ----
            for i, pt in enumerate(pts):
                if i not in self._TIPS:
                    cv2.circle(result, pt, 4, (210, 210, 210), -1, cv2.LINE_AA)
                    cv2.circle(result, pt, 5, (70,  70,  70),   1, cv2.LINE_AA)

            # ---- Fingertips com cor por dedo ----
            for idx, color in self._TIP_COLORS.items():
                cv2.circle(result, pts[idx], 9, color,           -1, cv2.LINE_AA)
                cv2.circle(result, pts[idx], 9, (255, 255, 255),  2, cv2.LINE_AA)

        return result


# ---------------------------------------------------------------------------
# HUDBehindEffect â€” Sprint 14: scanner reativo, motion detection, 2 depth layers
#
# Pipeline de compositing (OBRIGATORIO â€” HUD SEMPRE ATRAS da pessoa):
#   1. frame original
#   2. gerar HUD layer no canvas pre-alocado
#   3. blend aditivo: result = frame + HUD * HUD_ALPHA
#   4. restaurar pessoa: result[mask_dilatada] = frame  (sem vazamento)
#
# Garantia de compositing:
#   - mascara DILATADA (nao erodida): expande cobertura para bordas e atraso de cache
#   - cv2.copyTo restaura pixels originais da pessoa por cima de qualquer HUD
#   - scanner e todos os elementos sao desenhados NO CANVAS, nunca direto no frame
# ---------------------------------------------------------------------------

class HUDBehindEffect:
    """Sprint 14 â€” HUD reativo: scanner, motion, 2 layers, compositing garantido atras da pessoa."""

    def __init__(self):
        self._seg          = None
        self._t            = 0.0
        self._elements     = None
        self._edge_timer   = 0

        # Caches de performance
        self._seg_counter  = 0
        self._seg_mask_bin = None   # (h,w) uint8 dilatada â€” cobertura total da pessoa
        self._hud_buf      = None   # canvas pre-alocado
        self._result_buf   = None   # buffer de saida pre-alocado
        self._frame_size   = (0, 0)
        self._dil_kernel   = None   # kernel de dilatacao pre-alocado

        # Scanner
        self._scanner_y    = 0.0    # posicao [0..1]

        # Motion detection
        self._prev_gray_s  = None   # frame 1/8 res para diff
        self._motion_level = 0.0    # EMA [0..1]

        # RNG persistente para flicker (semente aleatoria por sessao)
        self._rng = np.random.RandomState(int(time.monotonic() * 1000) % 65535)

    # ------------------------------------------------------------------
    def _sample_edge_positions(self, frame):
        """Canny em 1/4 de resolucao â€” rapido."""
        h, w    = frame.shape[:2]
        sh, sw  = max(60, h // 4), max(80, w // 4)
        small   = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
        gray    = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        edges   = cv2.Canny(gray, 40, 110)

        row_sum = edges.sum(axis=1).astype(np.float32)
        col_sum = edges.sum(axis=0).astype(np.float32)

        mg = max(1, sh // 20)
        row_sum[:mg] = 0; row_sum[-mg:] = 0
        col_sum[:max(1, sw // 20)] = 0; col_sum[-max(1, sw // 20):] = 0

        def top_peaks(arr, n, min_gap):
            peaks, a = [], arr.copy()
            for _ in range(n):
                idx = int(np.argmax(a))
                if a[idx] < 1: break
                peaks.append(idx / len(a))
                a[max(0, idx - min_gap):min(len(a), idx + min_gap)] = 0
            return peaks

        return (top_peaks(row_sum, 8, max(1, sh // 12)),
                top_peaks(col_sum, 6, max(1, sw // 12)))

    # ------------------------------------------------------------------
    def _build_elements(self, h, w, y_pts, x_pts):
        density = config.HUD_DENSITY
        colors  = config.HUD_ACCENT_COLORS
        base_c  = config.HUD_COLOR
        rng     = np.random.RandomState(42)
        la      = config.HUD_LAYER_ALPHA   # (layer0_alpha, layer1_alpha)

        def pick(i): return colors[i % len(colors)] if colors else base_c

        els = []

        # --- Layer 0: fundo (lento, transparente) ---
        n_bg = max(1, density // 2)
        for i in range(n_bg):
            y0 = y_pts[i % len(y_pts)] if y_pts else rng.uniform(0.1, 0.9)
            y0 = float(np.clip(y0 + rng.uniform(-0.10, 0.10), 0.03, 0.96))
            vy = rng.uniform(0.0001, 0.0004) * (-1 if rng.rand() > 0.5 else 1)
            els.append({
                'kind': 'hline', 'layer': 0, 'y': y0,
                'vy': vy, 'phase': rng.uniform(0, math.pi * 2),
                'amp': rng.uniform(0.003, 0.010), 'freq': rng.uniform(0.2, 0.6),
                'alpha': la[0] * rng.uniform(0.7, 1.0),
                'color': pick(i),
                'seg_x0': rng.uniform(0.0, 0.20), 'seg_len': rng.uniform(0.50, 0.85),
                '_flicker': 1.0,
            })

        # --- Layer 1: medio (normal) ---
        n_mid = max(1, density - n_bg)
        for i in range(n_mid):
            y0 = y_pts[(n_bg + i) % max(1, len(y_pts))] if y_pts else rng.uniform(0.1, 0.9)
            y0 = float(np.clip(y0 + rng.uniform(-0.06, 0.06), 0.03, 0.96))
            vy = rng.uniform(0.0003, 0.0007) * (-1 if rng.rand() > 0.5 else 1)
            els.append({
                'kind': 'hline', 'layer': 1, 'y': y0,
                'vy': vy, 'phase': rng.uniform(0, math.pi * 2),
                'amp': rng.uniform(0.005, 0.016), 'freq': rng.uniform(0.35, 0.9),
                'alpha': la[1] * rng.uniform(0.7, 1.0),
                'color': pick(n_bg + i),
                'seg_x0': rng.uniform(0.0, 0.25), 'seg_len': rng.uniform(0.35, 0.70),
                '_flicker': 1.0,
            })

        # Linhas verticais (layer 1)
        n_v = max(1, density // 2 - 1)
        for i in range(n_v):
            x0 = x_pts[i % max(1, len(x_pts))] if x_pts else rng.uniform(0.1, 0.9)
            x0 = float(np.clip(x0 + rng.uniform(-0.05, 0.05), 0.03, 0.96))
            vx = rng.uniform(0.0002, 0.0005) * (-1 if rng.rand() > 0.5 else 1)
            els.append({
                'kind': 'vline', 'layer': 1, 'x': x0,
                'vx': vx, 'phase': rng.uniform(0, math.pi * 2),
                'amp': rng.uniform(0.004, 0.013), 'freq': rng.uniform(0.3, 0.8),
                'alpha': la[1] * 0.65,
                'color': pick(i),
                'seg_y0': rng.uniform(0.0, 0.35), 'seg_len': rng.uniform(0.30, 0.60),
                '_flicker': 1.0,
            })

        # Retangulos (layer 1)
        for i in range(2):
            rx = float(np.clip(
                (x_pts[i % max(1, len(x_pts))] if x_pts else rng.uniform(0.1, 0.75))
                + rng.uniform(-0.07, 0.07), 0.03, 0.80))
            ry = float(np.clip(
                (y_pts[i % max(1, len(y_pts))] if y_pts else rng.uniform(0.1, 0.75))
                + rng.uniform(-0.05, 0.05), 0.03, 0.82))
            vy = rng.uniform(0.0002, 0.0005) * (-1 if rng.rand() > 0.5 else 1)
            els.append({
                'kind': 'rect', 'layer': 1, 'x': rx, 'y': ry,
                'w': rng.uniform(0.07, 0.13), 'h': rng.uniform(0.04, 0.08),
                'vy': vy, 'phase': rng.uniform(0, math.pi * 2),
                'amp': rng.uniform(0.003, 0.010), 'freq': rng.uniform(0.3, 0.7),
                'alpha': la[1] * 0.75,
                'color': pick(i),
                '_flicker': 1.0,
            })

        # Retangulos reativos â€” zona superior (cabeca/ombros), fade in/out
        for i in range(3):
            els.append({
                'kind': 'reactive_rect', 'layer': 1,
                'x': rng.uniform(0.05, 0.70),
                'y': rng.uniform(0.04, 0.40),
                'rw': rng.uniform(0.04, 0.10),
                'rh': rng.uniform(0.02, 0.06),
                'alpha': la[1],
                'color': pick(i),
                'fade': rng.uniform(0.0, 0.5),
                '_flicker': 1.0,
            })

        # Corner brackets â€” 4 cantos, layer 0 (fundo)
        for corner, phase in [('tl', 0.0), ('tr', math.pi / 2),
                               ('br', math.pi), ('bl', math.pi * 1.5)]:
            els.append({
                'kind': 'bracket', 'layer': 0, 'corner': corner,
                'phase': phase, 'alpha': la[0] * 0.9,
                'color': base_c, '_flicker': 1.0,
            })

        # Beam varredor (layer 1)
        els.append({
            'kind': 'beam', 'layer': 1, 'y': rng.uniform(0.1, 0.9),
            'vy': 0.004 * config.HUD_SPEED, 'alpha': 0.06,
            'h_px': 14, 'color': base_c, '_flicker': 1.0,
        })

        return els

    # ------------------------------------------------------------------
    def _update_motion(self, frame):
        """Detecta movimento a 1/8 de resolucao. Atualiza _motion_level via EMA."""
        h, w   = frame.shape[:2]
        sh, sw = max(45, h // 8), max(80, w // 8)
        small  = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_AREA)
        gray   = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        if self._prev_gray_s is not None and self._prev_gray_s.shape == gray.shape:
            diff  = cv2.absdiff(gray, self._prev_gray_s)
            level = float(diff.mean()) / 20.0
            self._motion_level = self._motion_level * 0.72 + min(level, 1.0) * 0.28
        self._prev_gray_s = gray

    # ------------------------------------------------------------------
    def _update_elements(self):
        t   = self._t
        spd = config.HUD_SPEED
        flk = config.HUD_FLICKER
        mot = min(1.0, self._motion_level * config.HUD_REACTIVITY)

        for el in self._elements:
            k = el['kind']
            el['_flicker'] = max(0.5, 1.0 + flk * (float(self._rng.uniform()) - 0.5) * 2.0)

            if k == 'hline':
                el['y'] = (el['y'] + el['vy'] * spd) % 1.0
                jitter   = mot * 0.004 * math.sin(t * 7.3 + el['phase'])
                el['_yd'] = el['y'] + el['amp'] * math.sin(t * el['freq'] + el['phase']) + jitter
            elif k == 'vline':
                el['x'] = (el['x'] + el['vx'] * spd) % 1.0
                jitter   = mot * 0.003 * math.sin(t * 6.1 + el['phase'])
                el['_xd'] = el['x'] + el['amp'] * math.sin(t * el['freq'] + el['phase']) + jitter
            elif k == 'rect':
                el['y'] = (el['y'] + el['vy'] * spd) % 1.0
                el['_yd'] = el['y'] + el['amp'] * math.sin(t * el['freq'] + el['phase'])
            elif k == 'reactive_rect':
                # Flash aleatÃ³rio de desaparecimento
                if float(self._rng.uniform()) < 0.006:
                    el['fade'] = 0.0
                target = 1.0 if (float(self._rng.uniform()) > 0.015 or mot > 0.25) else el['fade']
                el['fade'] = el['fade'] * 0.96 + target * 0.04
                el['_fade_actual'] = min(1.0, el['fade'] * (1.0 + mot * 1.5))
            elif k == 'beam':
                el['y'] = (el['y'] + el['vy'] * spd) % 1.0

        # Avanca scanner
        self._scanner_y = (self._scanner_y + config.SCANNER_SPEED * spd) % 1.0

    # ------------------------------------------------------------------
    def _draw_hud(self, canvas, h, w):
        t   = self._t
        thk = config.HUD_THICKNESS
        bsz = config.HUD_BRACKET_SIZE
        bm  = config.HUD_BRACKET_MARGIN
        mot = min(1.0, self._motion_level * config.HUD_REACTIVITY)

        for el in self._elements:
            k     = el['kind']
            flk   = el.get('_flicker', 1.0)
            layer = el.get('layer', 1)
            base_a = el['alpha'] * flk
            # Motion boost aplica apenas no layer 1 (elementos do meio)
            if layer == 1:
                base_a = min(1.0, base_a * (1.0 + mot * 0.5))
            col = el.get('color', config.HUD_COLOR)
            c   = tuple(min(255, int(v * base_a)) for v in col)

            if k == 'hline':
                y_px = int(np.clip(el.get('_yd', el['y']) * h, 0, h - 1))
                x0   = int(el['seg_x0'] * w)
                x1   = int(min(el['seg_x0'] + el['seg_len'], 1.0) * w)
                cv2.line(canvas, (x0, y_px), (x1, y_px), c, thk, cv2.LINE_AA)
                # Linha fantasma de motion (layer 1 + movimento detectado)
                if mot > 0.20 and layer == 1:
                    ca = tuple(min(255, int(v * base_a * mot * 0.45)) for v in col)
                    yy = max(0, y_px - 2)
                    cv2.line(canvas, (x0, yy), (x1, yy), ca, thk, cv2.LINE_AA)

            elif k == 'vline':
                x_px  = int(np.clip(el.get('_xd', el['x']) * w, 0, w - 1))
                y0_v  = int(el['seg_y0'] * h)
                y1_v  = int(min(el['seg_y0'] + el['seg_len'], 1.0) * h)
                cv2.line(canvas, (x_px, y0_v), (x_px, y1_v), c, thk, cv2.LINE_AA)

            elif k == 'rect':
                rx  = int(np.clip(el['x'] * w, 0, w - 1))
                ry  = int(np.clip(el.get('_yd', el['y']) * h, 0, h - 1))
                x2  = min(w - 1, rx + int(el['w'] * w))
                y2  = min(h - 1, ry + int(el['h'] * h))
                cv2.rectangle(canvas, (rx, ry), (x2, y2), c, thk)

            elif k == 'reactive_rect':
                fa  = el.get('_fade_actual', el.get('fade', 0.0))
                a2  = el['alpha'] * flk * fa
                if a2 > 0.02:
                    c2 = tuple(min(255, int(v * a2)) for v in col)
                    rx = int(np.clip(el['x'] * w, 0, w - 1))
                    ry = int(np.clip(el['y'] * h, 0, h - 1))
                    rw = max(2, min(w - rx - 1, int(el['rw'] * w)))
                    rh = max(2, min(h - ry - 1, int(el['rh'] * h)))
                    cv2.rectangle(canvas, (rx, ry), (rx + rw, ry + rh), c2, thk)

            elif k == 'bracket':
                pulse = 0.5 + 0.5 * math.sin(t * 1.3 + el['phase'])
                bc    = tuple(min(255, int(v * el['alpha'] * flk * pulse)) for v in col)
                s     = bsz
                if el['corner'] == 'tl':
                    cv2.line(canvas, (bm,         bm),         (bm + s, bm),         bc, thk)
                    cv2.line(canvas, (bm,         bm),         (bm,     bm + s),      bc, thk)
                elif el['corner'] == 'tr':
                    cv2.line(canvas, (w - bm - s, bm),         (w - bm, bm),          bc, thk)
                    cv2.line(canvas, (w - bm,     bm),         (w - bm, bm + s),      bc, thk)
                elif el['corner'] == 'br':
                    cv2.line(canvas, (w - bm - s, h - bm),     (w - bm, h - bm),      bc, thk)
                    cv2.line(canvas, (w - bm,     h - bm - s), (w - bm, h - bm),      bc, thk)
                elif el['corner'] == 'bl':
                    cv2.line(canvas, (bm,         h - bm),     (bm + s, h - bm),      bc, thk)
                    cv2.line(canvas, (bm,         h - bm - s), (bm,     h - bm),      bc, thk)

            elif k == 'beam':
                y0  = int(el['y'] * h)
                bh  = el['h_px']
                ys  = max(0, y0)
                ye  = min(h, y0 + bh)
                if ye > ys:
                    n      = ye - ys
                    off    = ys - y0
                    a_eff  = min(1.0, el['alpha'] * flk * (1.0 + mot * 0.7))
                    fades  = np.linspace(a_eff * (1.0 - off / bh), 0.0, n, dtype=np.float32)
                    add    = (np.array(col, dtype=np.float32) * fades[:, np.newaxis]).astype(np.int16)
                    canvas[ys:ye] = np.clip(
                        canvas[ys:ye].astype(np.int16) + add[:, np.newaxis, :], 0, 255
                    ).astype(np.uint8)

        # Scanner por ultimo (acima de todos os outros elementos do HUD canvas)
        self._draw_scanner(canvas, h, w)

    # ------------------------------------------------------------------
    def _draw_scanner(self, canvas, h, w):
        """Linha de scanner horizontal varrendo de cima para baixo.
        Tudo desenhado NO CANVAS â€” nunca direto no frame."""
        y_px   = int(np.clip(self._scanner_y * h, 0, h - 1))
        si     = config.SCANNER_INTENSITY
        mot    = self._motion_level
        col    = config.HUD_COLOR
        a_main = min(1.0, si * (1.0 + mot * config.HUD_REACTIVITY * 0.6))
        c_line = tuple(min(255, int(v * a_main)) for v in col)
        cv2.line(canvas, (0, y_px), (w - 1, y_px), c_line, 2, cv2.LINE_AA)

        # Glow band ao redor da linha (vetorizado)
        band_h = 10
        y0 = max(0, y_px - band_h)
        y1 = min(h, y_px + band_h + 1)
        if y1 > y0:
            n     = y1 - y0
            dist  = np.abs(np.arange(y0, y1) - y_px).astype(np.float32)
            fade  = np.clip(1.0 - dist / band_h, 0.0, 1.0) * si * 0.50
            col_f = np.array(col, dtype=np.float32)
            add   = (col_f * fade[:, np.newaxis]).astype(np.int16)
            canvas[y0:y1] = np.clip(
                canvas[y0:y1].astype(np.int16) + add[:, np.newaxis, :], 0, 255
            ).astype(np.uint8)

    # ------------------------------------------------------------------
    def _reanchor_elements(self, y_pts, x_pts):
        rng = np.random.RandomState(int(self._t * 1000) % 65535)
        hi  = [e for e in self._elements if e['kind'] == 'hline']
        vi  = [e for e in self._elements if e['kind'] == 'vline']
        for i, el in enumerate(hi):
            if y_pts:
                tgt = float(np.clip(
                    y_pts[i % len(y_pts)] + rng.uniform(-0.05, 0.05), 0.03, 0.96))
                el['y'] += (tgt - el['y']) * 0.04
        for i, el in enumerate(vi):
            if x_pts:
                tgt = float(np.clip(
                    x_pts[i % len(x_pts)] + rng.uniform(-0.04, 0.04), 0.03, 0.96))
                el['x'] += (tgt - el['x']) * 0.04

    # ------------------------------------------------------------------
    def _refresh_seg_mask(self, frame, hand_mask, h, w):
        """Segmentacao em half-res. DILATA mascara para cobertura total da pessoa.
        Compensacao de atraso de cache (HUD_SEG_INTERVAL frames) e movimento."""
        if self._seg is None:
            self._seg = BodySegmenter()

        scale  = config.HUD_SEG_SCALE
        sw     = max(160, int(w * scale))
        sh     = max(90,  int(h * scale))
        small  = cv2.resize(frame, (sw, sh), interpolation=cv2.INTER_LINEAR)
        frgb   = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
        ts     = int(time.monotonic() * 1000)
        body_s = self._seg.get_mask(frgb, ts)

        if body_s is not None:
            body = cv2.resize(body_s, (w, h), interpolation=cv2.INTER_LINEAR)
            _, body = cv2.threshold(body, 127, 255, cv2.THRESH_BINARY)
            # DILATAR (nao erosao): expande para cobrir bordas + atraso de cache
            body = cv2.dilate(body, self._dil_kernel, iterations=2)
            self._seg_mask_bin = body
        else:
            # Fallback: dilata hand mask como proxy do corpo
            if hand_mask is not None and np.any(hand_mask):
                k  = max(3, h // 10); k = k if k % 2 == 1 else k + 1
                kn = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
                self._seg_mask_bin = cv2.dilate(hand_mask, kn, iterations=5)

    # ------------------------------------------------------------------
    def apply(self, frame, mask, landmarks):
        h, w = frame.shape[:2]
        self._t           += 0.025
        self._seg_counter += 1

        # Reinicializa buffers se resolucao mudou
        if self._frame_size != (h, w):
            self._hud_buf      = np.zeros((h, w, 3), dtype=np.uint8)
            self._result_buf   = np.empty((h, w, 3), dtype=np.uint8)
            self._dil_kernel   = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
            self._seg_mask_bin = None
            self._elements     = None
            self._edge_timer   = 0
            self._frame_size   = (h, w)

        # Atualiza ancoragem de bordas a cada ~60 frames
        self._edge_timer -= 1
        if self._edge_timer <= 0 or self._elements is None:
            y_pts, x_pts = self._sample_edge_positions(frame)
            if self._elements is None:
                self._elements = self._build_elements(h, w, y_pts, x_pts)
            else:
                self._reanchor_elements(y_pts, x_pts)
            self._edge_timer = 60

        # Segmentacao cacheada: roda a cada HUD_SEG_INTERVAL frames
        if self._seg_counter % config.HUD_SEG_INTERVAL == 0 or self._seg_mask_bin is None:
            self._refresh_seg_mask(frame, mask, h, w)

        # Deteccao de movimento (1/8 res, fast)
        self._update_motion(frame)
        self._update_elements()

        # ---- 1. Gera HUD no canvas pre-alocado ----
        self._hud_buf[:] = 0
        self._draw_hud(self._hud_buf, h, w)

        # ---- 2. Glow opcional (desligado por default) ----
        hud_final = self._hud_buf
        if config.HUD_GLOW > 0:
            gk = config.HUD_GLOW_BLUR
            gk = gk if gk % 2 == 1 else gk + 1
            glow = cv2.GaussianBlur(self._hud_buf, (gk, gk), 0)
            hud_final = np.clip(
                self._hud_buf.astype(np.float32) +
                glow.astype(np.float32) * config.HUD_GLOW,
                0, 255
            ).astype(np.uint8)

        # ---- 3. Blend aditivo: result = frame + HUD * HUD_ALPHA ----
        cv2.addWeighted(frame, 1.0, hud_final, config.HUD_ALPHA, 0,
                        dst=self._result_buf)

        # ---- 4. Restaura pessoa â€” mascara DILATADA = sem vazamento do HUD ----
        if self._seg_mask_bin is not None:
            cv2.copyTo(frame, self._seg_mask_bin, self._result_buf)

        return self._result_buf


# ---------------------------------------------------------------------------
# PalmRingEffect â€” Sprint 15: anel energetico ancorado na palma
#
# Ancoragem:
#   Centro da palma = media de lm[0, 5, 9, 13, 17] (pulso + bases dos dedos)
#   Raio base       = distancia lm[0] -> lm[9] * PALM_OBJECT_SCALE
#   Orientacao      = angulo do vetor lm[0] -> lm[9] (pulso -> base do medio)
#   Suavizacao EMA  = PALM_OBJECT_SMOOTHING (posicao + raio independentes)
#
# Estrutura visual do anel:
#   Layer 1 â€” anel externo:  arcos parciais giratorios (cv2.ellipse)
#   Layer 2 â€” segmentos:     12 tracos radiais curtos, rotacao oposta
#   Layer 3 â€” anel interno:  circulo pulsante (seno)
#   Glow bloom:              canvas separado -> GaussianBlur -> blend aditivo
# ---------------------------------------------------------------------------

class PalmRingEffect:
    """Sprint 15 â€” Anel energetico ancorado na palma, com EMA, rotacao e glow."""

    # Indices MediaPipe relevantes
    _I_WRIST    = 0
    _I_PALM     = [0, 5, 9, 13, 17]   # centro da palma
    _I_MID_BASE = 9                    # base do medio â€” define eixo de orientacao

    def __init__(self):
        self._rot        = 0.0    # rotacao acumulada do anel externo (graus)
        self._t          = 0.0    # tempo interno

        # Estado suavizado (EMA)
        self._cx         = None   # centro x (pixels)
        self._cy         = None   # centro y
        self._radius     = None   # raio base (pixels)

        # Fade out ao perder a mao
        self._fade       = 0.0    # 0.0 = invisivel, 1.0 = totalmente visivel
        self._fade_step  = None   # calculado no primeiro frame

        # Buffers pre-alocados
        self._canvas     = None
        self._frame_size = (0, 0)

    # ------------------------------------------------------------------
    def _get_palm_anchor(self, landmarks, h, w):
        """Retorna (cx, cy, radius, angle_deg) em pixels.
        Retorna None se landmarks vazio."""
        if not landmarks:
            return None
        lm = landmarks[0]  # primeira mao detectada

        # Centro = media dos pontos-ancora da palma
        xs = [lm[i].x * w for i in self._I_PALM]
        ys = [lm[i].y * h for i in self._I_PALM]
        cx = sum(xs) / len(xs)
        cy = sum(ys) / len(ys)

        # Raio = distancia pulso -> base do medio
        wx, wy = lm[self._I_WRIST].x * w, lm[self._I_WRIST].y * h
        mx, my = lm[self._I_MID_BASE].x * w, lm[self._I_MID_BASE].y * h
        dist   = math.hypot(mx - wx, my - wy)
        radius = max(20.0, dist * config.PALM_OBJECT_SCALE)

        # Angulo de orientacao (pulso -> base do medio)
        angle  = math.degrees(math.atan2(my - wy, mx - wx))

        return (cx, cy, radius, angle)

    # ------------------------------------------------------------------
    def _smooth(self, target_cx, target_cy, target_r):
        """Aplica EMA em posicao e raio."""
        alpha = 1.0 - config.PALM_OBJECT_SMOOTHING
        if self._cx is None:
            self._cx, self._cy, self._radius = target_cx, target_cy, target_r
        else:
            self._cx     = self._cx     * config.PALM_OBJECT_SMOOTHING + target_cx * alpha
            self._cy     = self._cy     * config.PALM_OBJECT_SMOOTHING + target_cy * alpha
            self._radius = self._radius * config.PALM_OBJECT_SMOOTHING + target_r  * alpha

    # ------------------------------------------------------------------
    def _draw_ring(self, canvas, cx, cy, radius, fade):
        """Desenha o anel completo no canvas."""
        t    = self._t
        rot  = self._rot
        a    = config.PALM_OBJECT_ALPHA * fade

        cx_i = int(cx); cy_i = int(cy)
        r    = int(radius)
        r_in = max(4, int(radius * 0.55))   # raio interno pulsante
        r_seg = int(radius * 1.18)          # raio externo dos segmentos

        col_main   = config.PALM_RING_COLOR
        col_accent = config.PALM_RING_ACCENT

        # Layer 1: 4 arcos do anel externo (giratÃ³rios, 70 graus cada)
        arc_color = tuple(min(255, int(v * a)) for v in col_main)
        for i in range(4):
            start_a = int(rot + i * 90)
            cv2.ellipse(canvas, (cx_i, cy_i), (r, r),
                        0, start_a, start_a + 70,
                        arc_color, 2, cv2.LINE_AA)

        # Layer 2: 12 segmentos radiais curtos (rotacao oposta)
        seg_rot   = -rot * 0.5
        seg_color = tuple(min(255, int(v * a * 0.80)) for v in col_accent)
        n_segs    = 12
        for i in range(n_segs):
            ang_deg   = seg_rot + i * (360.0 / n_segs)
            ang_rad   = math.radians(ang_deg)
            cos_a, sin_a = math.cos(ang_rad), math.sin(ang_rad)
            r_inner_seg  = int(radius * 0.85)
            x0 = int(cx + cos_a * r_inner_seg)
            y0 = int(cy + sin_a * r_inner_seg)
            x1 = int(cx + cos_a * r_seg)
            y1 = int(cy + sin_a * r_seg)
            cv2.line(canvas, (x0, y0), (x1, y1), seg_color, 1, cv2.LINE_AA)

        # Layer 3: anel interno pulsante (seno)
        pulse       = 0.85 + 0.15 * math.sin(t * 2.7)
        r_p         = max(4, int(r_in * pulse))
        inner_color = tuple(min(255, int(v * a * 0.65)) for v in col_main)
        cv2.ellipse(canvas, (cx_i, cy_i), (r_p, r_p),
                    int(rot * 1.8), 5, 180, inner_color, 1, cv2.LINE_AA)
        cv2.ellipse(canvas, (cx_i, cy_i), (r_p, r_p),
                    int(rot * 1.8), 185, 360, inner_color, 1, cv2.LINE_AA)

        # Ponto central (ancora visual)
        dot_color = tuple(min(255, int(v * a * 0.50)) for v in col_accent)
        cv2.circle(canvas, (cx_i, cy_i), max(2, int(radius * 0.04)),
                   dot_color, -1, cv2.LINE_AA)

    # ------------------------------------------------------------------
    def apply(self, frame, mask, landmarks):
        h, w = frame.shape[:2]
        self._t   += 0.04
        self._rot  = (self._rot + config.PALM_OBJECT_ROTATION_SPEED) % 360.0

        # Inicializa fade_step se necessario
        if self._fade_step is None:
            self._fade_step = 1.0 / max(1, config.PALM_FADE_FRAMES)

        anchor = self._get_palm_anchor(landmarks, h, w)

        if anchor is not None:
            cx, cy, radius, _angle = anchor
            self._smooth(cx, cy, radius)
            self._fade = min(1.0, self._fade + self._fade_step * 2.0)
        else:
            self._fade = max(0.0, self._fade - self._fade_step)

        if self._fade < 0.01 or self._cx is None:
            return frame

        cx_i  = int(self._cx);  cy_i = int(self._cy)
        r_max = int(self._radius * 1.30)   # raio maximo com margem

        # --- ROI ao redor do anel (unica area que precisa ser processada) ---
        pad   = config.PALM_OBJECT_GLOW_BLUR * 2 + 4
        x0    = max(0, cx_i - r_max - pad)
        y0    = max(0, cy_i - r_max - pad)
        x1    = min(w, cx_i + r_max + pad)
        y1    = min(h, cy_i + r_max + pad)
        rw, rh = x1 - x0, y1 - y0

        if rw < 4 or rh < 4:
            return frame

        # Canvas ROI pre-alocado (recria se tamanho mudou)
        if self._frame_size != (rh, rw):
            self._canvas     = np.zeros((rh, rw, 3), dtype=np.uint8)
            self._frame_size = (rh, rw)
        self._canvas[:] = 0

        # Desenha anel com coordenadas relativas ao ROI
        self._draw_ring(self._canvas, self._cx - x0, self._cy - y0,
                        self._radius, self._fade)

        # Glow bloom apenas no ROI
        if config.PALM_OBJECT_GLOW > 0:
            gk = config.PALM_OBJECT_GLOW_BLUR
            gk = gk if gk % 2 == 1 else gk + 1
            glow = cv2.GaussianBlur(self._canvas, (gk, gk), 0)
            cv2.addWeighted(self._canvas, 1.0, glow, config.PALM_OBJECT_GLOW, 0,
                            dst=self._canvas)

        # Blend aditivo: modifica apenas a ROI in-place (sem full-frame copy)
        # main.py faz frame = effect.apply(frame,...) entao in-place e seguro
        cv2.add(frame[y0:y1, x0:x1], self._canvas,
                dst=frame[y0:y1, x0:x1])

        return frame
