# main.py
# Orquestra o pipeline principal do TrackFX.
# Não contém lógica de negócio — apenas coordena os módulos.

import logging
import cv2
import config
from camera import CameraCapture
from tracking import HandTracker
from render import Renderer
from effects import GlitchEffect, DistortionEffect, DisplacementEffect, AuraEffect, TrailEffect, FireEffect, OrganicWarpEffect, RibbonWarpEffect, TrackingOverlayEffect, HUDBehindEffect, PalmRingEffect

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


def main():
    camera = CameraCapture()
    tracker = HandTracker()
    renderer = Renderer()
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


if __name__ == "__main__":
    main()

