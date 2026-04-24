# main.py
# Orquestra o pipeline principal do TrackFX.
# Não contém lógica de negócio — apenas coordena os módulos.

import logging
import time
import cv2
import numpy as np
import config
from camera import CameraCapture
from screen import ScreenCapture
from tracking import HandTracker, BodySegmenter
from render import Renderer
from effects import GlitchEffect, DistortionEffect, DisplacementEffect, AuraEffect, TrailEffect, FireEffect, OrganicWarpEffect, RibbonWarpEffect, TrackingOverlayEffect, HUDBehindEffect, PalmRingEffect
from gestures import GestureDetector
from coords import remap_landmarks, make_hand_mask, warp_cam_to_screen, warp_mask_to_screen
import motion

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_EFFECTS = {
    "glitch":       GlitchEffect(),
    "tracking":     TrackingOverlayEffect(),
    "distortion":   DistortionEffect(),
    "displacement": DisplacementEffect(),
    "aura":         AuraEffect(),
    "trail":        TrailEffect(),
    "fire":         FireEffect(),
    "organic":      OrganicWarpEffect(),
    "ribbon":       RibbonWarpEffect(),
    "hud":          HUDBehindEffect(),
    "palm_ring":    PalmRingEffect(),
}

logger = logging.getLogger(__name__)


def _next_effect(current, cycle):
    """Retorna o próximo efeito na lista de ciclo, sem dependência de estado global."""
    if not cycle:
        return current
    try:
        idx = cycle.index(current)
    except ValueError:
        idx = -1
    return cycle[(idx + 1) % len(cycle)]


def main():
    camera = CameraCapture()
    tracker = HandTracker()
    renderer = Renderer()
    gesture_detector = GestureDetector()
    active_key = config.ACTIVE_EFFECT
    effect = _EFFECTS.get(active_key)

    if not camera.open():
        return

    logger.info(
        "Efeito ativo: %s  |  1=glitch  2=tracking  3=distortion  4=displacement  5=aura  6=trail  7=fire  8=organic  9=ribbon  h=hud  r=palm_ring  0=off",
        active_key,
    )

    try:
        while True:
            ret, frame = camera.read()
            if not ret or frame is None:
                continue

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            tracker.process(frame_rgb)

            h, w = frame.shape[:2]
            # Atualiza metricas globais de movimento — consumidas pelos efeitos via motion.state
            motion.update(tracker.landmarks, h, w)

            # --- Detecção de gesto (antes do render, sem custo) ---
            gesture_events = gesture_detector.update(tracker.landmarks)
            for evt in gesture_events:
                if evt == 'pinch':
                    active_key = _next_effect(active_key, config.GESTURE_EFFECT_CYCLE)
                    effect = _EFFECTS.get(active_key)
                    logger.info("Gesto pinch: efeito -> %s", active_key)

            mask = tracker.get_mask(h, w)
            boxes = tracker.get_bounding_boxes(h, w)

            if effect is not None:
                frame = effect.apply(frame, mask, tracker.landmarks)

            # Overlays de debug — só visíveis se DEBUG_FORCE ou sem efeito ativo
            show_debug = config.DEBUG_FORCE or active_key is None
            if show_debug:
                renderer.draw_debug_mask(frame, mask)
                renderer.draw_bounding_boxes(frame, boxes)

            if tracker.has_detections():
                show_lm = config.SHOW_LANDMARKS and (show_debug or active_key not in config.INTENSE_EFFECTS)
                if show_lm:
                    renderer.draw_landmarks(frame, tracker.landmarks)

            # --- Indicador visual de pinch (leve, desenhado direto no frame) ---
            if config.SHOW_PINCH_INDICATOR and tracker.has_detections():
                lm       = tracker.landmarks[0]
                progress = gesture_detector.pinch_progress()
                dist     = gesture_detector.pinch_dist(tracker.landmarks)
                thresh   = config.PINCH_THRESHOLD
                # Mostrar quando dentro da zona de aproximação ou em holding/cooldown
                if dist < thresh * 1.8 or progress > 0:
                    tx = int(lm[4].x * w); ty = int(lm[4].y * h)
                    ix = int(lm[8].x * w); iy = int(lm[8].y * h)
                    t_approach = max(0.0, 1.0 - dist / (thresh * 1.8))
                    t_total    = min(1.0, max(t_approach, progress))
                    # Verde → amarelo → vermelho conforme proximidade/confirmação
                    ind_color  = (0, int(255 * (1.0 - t_total * 0.6)), int(200 * t_total))
                    mid_x = (tx + ix) // 2; mid_y = (ty + iy) // 2
                    cv2.line(frame, (tx, ty), (ix, iy), ind_color, 1, cv2.LINE_AA)
                    cv2.circle(frame, (mid_x, mid_y), 4 + int(4 * progress),
                               ind_color, -1, cv2.LINE_AA)
                    if progress >= 1.0:  # flash de confirmação
                        cv2.circle(frame, (mid_x, mid_y), 14, (100, 255, 255), 2, cv2.LINE_AA)

            renderer.show(frame, active_effect=active_key)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key in config.EFFECT_KEYS:
                active_key = config.EFFECT_KEYS[key]
                effect = _EFFECTS.get(active_key)
                logger.info("Efeito alterado para: %s", active_key)

    finally:
        camera.release()
        tracker.release()
        renderer.close()


def main_presentation():
    """
    Pipeline do Presentation Mode — Visual Compositing em camadas.

    Camadas (ordem obrigatória):
      Layer 0  canvas escuro (fundo)
      Layer 1  dashboard reduzido, centralizado, com glow
      Layer 2  efeitos visuais da mão (sobre o canvas)
      Layer 3  usuário recortado, escalado e posicionado na frente

    REGRA: efeito deve ser leve (aura/palm_ring/glitch).
    NÃO usar 'hud' — ele tem BodySegmenter interno que duplica o custo.
    """
    screen           = ScreenCapture()
    camera           = CameraCapture()
    tracker          = HandTracker()
    renderer         = Renderer()
    gesture_detector = GestureDetector()

    # Efeito separado do camera mode — usa PRES_ACTIVE_EFFECT
    active_key = config.PRES_ACTIVE_EFFECT
    effect     = _EFFECTS.get(active_key)
    # Ciclo de efeitos sem 'hud' (BodySegmenter interno) e 'tracking' (desenha skeleton)
    _pres_cycle = [k for k in config.GESTURE_EFFECT_CYCLE if k not in ("hud", "tracking")]

    if not screen.open():
        return
    if not camera.open():
        screen.release()
        return

    screen_w, screen_h = screen.frame_size()
    # Reduz resolução da webcam para presentation mode (4× menos pixels → mais FPS).
    # Não afeta modo camera — cada modo usa instância independente de CameraCapture.
    camera._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.PRES_CAM_WIDTH)
    camera._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PRES_CAM_HEIGHT)
    cam_w = int(camera._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cam_h = int(camera._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    logger.info(
        "Presentation Mode  |  screen=%dx%d  webcam=%dx%d  efeito=%s",
        screen_w, screen_h, cam_w, cam_h, active_key,
    )

    # -----------------------------------------------------------------------
    # Segmentador — 1 única instância, throttled, downscaled
    # -----------------------------------------------------------------------
    segmenter  = BodySegmenter() if config.PRESENTATION_ENABLE_SEGMENTATION else None
    _seg_cache = None   # máscara binária em cam space (uint8, shape cam_h x cam_w)
    _seg_n     = 0
    _seg_w     = cam_w  # cam já em resolução reduzida — sem downscale adicional
    _seg_h     = cam_h

    # -----------------------------------------------------------------------
    # Tracking — cam já em PRES_CAM resolução (640×360), sem downscale adicional
    # -----------------------------------------------------------------------
    _trk_w = cam_w
    _trk_h = cam_h

    # -----------------------------------------------------------------------
    # Layer 1 — Geometria do painel (calculada UMA vez)
    # -----------------------------------------------------------------------
    _pw  = int(screen_w * config.PRES_DASHBOARD_SCALE)
    _ph  = int(screen_h * config.PRES_DASHBOARD_SCALE)
    _pox = (screen_w - _pw) // 2
    _poy = (screen_h - _ph) // 2

    # Canvas pré-alocado — resetado a cada frame sem alloc
    _canvas = np.empty((screen_h, screen_w, 3), dtype=np.uint8)

    # Glow do painel — precomputado UMA vez (posição fixa)
    _glow = None
    if config.PRES_PANEL_BORDER and config.PRES_PANEL_GLOW > 0:
        _gb = np.zeros((screen_h, screen_w, 3), dtype=np.uint8)
        cv2.rectangle(_gb,
                      (_pox - 6, _poy - 6),
                      (_pox + _pw + 5, _poy + _ph + 5),
                      config.PRES_PANEL_BORDER_COLOR, 12)
        _glow = np.clip(
            cv2.GaussianBlur(_gb, (21, 21), 0).astype(np.float32) * config.PRES_PANEL_GLOW,
            0, 255,
        ).astype(np.uint8)

    # -----------------------------------------------------------------------
    # Layer 3 — Geometria do usuário (calculada UMA vez)
    # -----------------------------------------------------------------------
    _uw = max(64, int(screen_w * config.PRES_USER_WIDTH_SCALE))
    _uh = max(32, int(_uw * cam_h / cam_w))   # mantém AR da webcam
    if _uh > screen_h:                         # se extrapolar, clipa pela altura
        _uh = screen_h
        _uw = int(_uh * cam_w / cam_h)

    _um  = config.PRES_USER_MARGIN
    side = config.PRES_USER_SIDE
    if side == "right":
        _uox = screen_w - _uw - _um
    elif side == "left":
        _uox = _um
    else:  # center
        _uox = (screen_w - _uw) // 2
    _uox = max(0, min(_uox, screen_w - _uw))
    _uoy = max(0, screen_h - _uh - _um)       # alinhado ao fundo

    # Kernel de feathering (tamanho fixo, sempre ímpar)
    _fk = config.PRES_MASK_FEATHER
    _fk = _fk if _fk % 2 == 1 else _fk + 1
    # Dilation moderada (~11px): cobre bordas e atraso de cache sem destruir a mask
    _dil_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))

    # Buffers pré-alocados para alpha blend — evita alloc de ~3 arrays float32 por frame
    _user_f32     = np.empty((_uh, _uw, 3), dtype=np.float32)
    _bg_f32       = np.empty((_uh, _uw, 3), dtype=np.float32)
    _composite_u8 = np.empty((_uh, _uw, 3), dtype=np.uint8)

    # Profiling por etapa — acumula e imprime a cada 60 frames no log
    _pt = [0.0] * 8
    _pn = 0

    logger.info(
        "Painel=%dx%d  pos=(%d,%d)  usuário=%dx%d  pos=(%d,%d)  tracking=%dx%d",
        _pw, _ph, _pox, _poy, _uw, _uh, _uox, _uoy, _trk_w, _trk_h,
    )

    try:
        while True:
            _ta = time.perf_counter()

            # --- Screen capture ---
            ret_s, screen_raw = screen.read()
            if not ret_s or screen_raw is None:
                continue
            _tb = time.perf_counter()

            # --- Webcam capture ---
            ret_c, cam_frame = camera.read()
            if not ret_c or cam_frame is None:
                continue
            _tc = time.perf_counter()

            # --- Tracking + motion + gestures ---
            tracker.process(cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB))
            motion.update(tracker.landmarks, screen_h, screen_w)
            for evt in gesture_detector.update(tracker.landmarks):
                if evt == 'pinch':
                    active_key = _next_effect(active_key, _pres_cycle)
                    effect     = _EFFECTS.get(active_key)
                    logger.info("Gesto pinch: efeito -> %s", active_key)
            _td = time.perf_counter()

            # ==============================================================
            # Layer 0+1: Canvas escuro + painel flutuante
            # ==============================================================
            _canvas[:] = config.PRES_BG_COLOR
            panel = cv2.resize(screen_raw, (_pw, _ph), interpolation=cv2.INTER_LINEAR)
            panel = cv2.convertScaleAbs(panel, alpha=config.PRES_DASHBOARD_DIM, beta=0)
            _canvas[_poy:_poy + _ph, _pox:_pox + _pw] = panel
            if config.PRES_PANEL_BORDER:
                cv2.rectangle(_canvas,
                              (_pox, _poy),
                              (_pox + _pw - 1, _poy + _ph - 1),
                              config.PRES_PANEL_BORDER_COLOR, 1, cv2.LINE_AA)
            if _glow is not None:
                cv2.add(_canvas, _glow, dst=_canvas)
            frame = _canvas
            _te = time.perf_counter()

            # ==============================================================
            # Layer 2: Efeitos sobre o canvas
            # Landmarks remapeados de espaço de tracking → espaço canvas
            # ==============================================================
            lms  = remap_landmarks(
                tracker.landmarks,
                (_trk_w, _trk_h),
                (screen_w, screen_h),
                flip_h=config.PRESENTATION_FLIP_LANDMARKS,
            )
            mask = make_hand_mask(lms, screen_h, screen_w)
            if effect is not None:
                frame = effect.apply(frame, mask, lms)
            _tf = time.perf_counter()

            # ==============================================================
            # Segmentação (throttled a cada PRES_SEG_INTERVAL frames)
            # ==============================================================
            if segmenter is not None:
                if _seg_n % config.PRES_SEG_INTERVAL == 0:
                    seg_rgb = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2RGB)
                    raw = segmenter.get_mask(seg_rgb, int(time.monotonic() * 1000))
                    # Atualiza cache SOMENTE se há pixels de pessoa
                    if raw is not None and raw.any():
                        _seg_cache = raw  # raw já está em (cam_h, cam_w)
                _seg_n += 1
            _tg = time.perf_counter()

            # ==============================================================
            # Layer 3: Usuário segmentado
            # REGRA: só compor se há máscara válida de pessoa.
            # NUNCA usar fallback retangular (webcam como bloco sólido).
            # ==============================================================
            if _seg_cache is not None:
                user_small = cv2.resize(
                    cv2.flip(cam_frame, 1), (_uw, _uh),
                    interpolation=cv2.INTER_LINEAR,
                )

                seg_flip = cv2.flip(_seg_cache, 1)
                if seg_flip.shape[:2] != (_uh, _uw):
                    seg_flip = cv2.resize(seg_flip, (_uw, _uh),
                                          interpolation=cv2.INTER_NEAREST)

                # Máscara binária + dilation pequena para cobrir bordas
                _, mask_bin  = cv2.threshold(seg_flip, 127, 255, cv2.THRESH_BINARY)
                user_mask_u8 = cv2.dilate(mask_bin, _dil_kernel, iterations=1)

                # Feathering leve nas bordas
                mask_f = cv2.GaussianBlur(
                    user_mask_u8.astype(np.float32) * (1.0 / 255.0), (_fk, _fk), 0
                )

                if config.PRES_USER_BRIGHTNESS != 1.0:
                    user_small = cv2.convertScaleAbs(
                        user_small, alpha=config.PRES_USER_BRIGHTNESS, beta=0
                    )

                # Alpha blend com buffers pré-alocados (sem alloc a cada frame)
                a3 = mask_f[:, :, np.newaxis]                 # view, sem cópia
                _user_f32[:] = user_small                     # uint8 → float32
                _bg_f32[:]   = frame[_uoy:_uoy + _uh, _uox:_uox + _uw]
                np.subtract(_user_f32, _bg_f32, out=_user_f32)
                np.multiply(_user_f32, a3,      out=_user_f32)
                np.add(_user_f32, _bg_f32,      out=_user_f32)
                np.clip(_user_f32, 0, 255,      out=_user_f32)
                _composite_u8[:] = _user_f32                  # float32 → uint8
                frame[_uoy:_uoy + _uh, _uox:_uox + _uw] = _composite_u8
            _th = time.perf_counter()

            # ==============================================================
            # Overlays debug (apenas se DEBUG_FORCE ativo)
            # ==============================================================
            if config.DEBUG_FORCE:
                renderer.draw_debug_mask(frame, mask)
                if tracker.has_detections():
                    renderer.draw_landmarks(frame, lms)

            renderer.show(
                frame,
                active_effect=active_key if config.PRES_SHOW_EFFECT_NAME else None,
            )
            _ti = time.perf_counter()

            # --- Profiling: acumula e imprime a cada 60 frames ---
            _pn += 1
            _pt[0] += (_tb - _ta) * 1000
            _pt[1] += (_tc - _tb) * 1000
            _pt[2] += (_td - _tc) * 1000
            _pt[3] += (_te - _td) * 1000
            _pt[4] += (_tf - _te) * 1000
            _pt[5] += (_tg - _tf) * 1000
            _pt[6] += (_th - _tg) * 1000
            _pt[7] += (_ti - _th) * 1000
            if _pn >= 60:
                _labels = ["screen", "cam.read", "tracking", "compose", "effect", "seg", "user_blend", "render"]
                _total  = sum(_pt)
                logger.info("=== PROFILING (media %d frames) ===", _pn)
                for _lbl, _ms in zip(_labels, _pt):
                    logger.info("  %-14s %6.1f ms  (%4.1f%%)", _lbl, _ms / _pn, _ms / _total * 100)
                logger.info("  %-14s %6.1f ms  → FPS estimado: %.0f",
                            "TOTAL", _total / _pn, 1000.0 / (_total / _pn) if _total > 0 else 0)
                _pt[:] = [0.0] * 8
                _pn    = 0

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key in config.EFFECT_KEYS:
                new_key = config.EFFECT_KEYS[key]
                if new_key not in ("hud", "tracking"):
                    active_key = new_key
                    effect     = _EFFECTS.get(active_key)
                    logger.info("Efeito alterado para: %s", active_key)

    finally:
        screen.release()
        camera.release()
        tracker.release()
        renderer.close()


if __name__ == "__main__":
    if config.MODE == "presentation":
        main_presentation()
    else:
        main()

