# coords.py
# Mapeamento de coordenadas de landmarks de espaço webcam → espaço screen.
#
# Problema:
#   - Tracking vem da webcam (landmarks normalizados 0.0–1.0 relativo ao frame da webcam)
#   - Render acontece no frame da tela (screen space)
#   - Webcam e screen podem ter aspect ratios diferentes
#   - Webcam pode estar em modo espelho (flip horizontal)
#
# Solução:
#   remap_landmarks() → retorna nova lista de landmarks com .x/.y/.z
#   ajustados para screen space. Compatível com a interface MediaPipe
#   (todos os consumidores fazem int(lm.x * w) e int(lm.y * h)).
#
#   make_hand_mask() → gera máscara de mão a partir de landmarks remapeados,
#   sem depender do estado interno do HandTracker.
#
# Módulo 100% stateless — apenas funções puras. Zero estado global.

from __future__ import annotations

import time
from typing import List, Sequence

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Landmark leve — compatível com NormalizedLandmark do MediaPipe
# ---------------------------------------------------------------------------

class _Lm:
    """
    Container mínimo de landmark compatível com NormalizedLandmark do MediaPipe.

    Todos os efeitos, render e motion consomem landmarks via:
        lm.x, lm.y, lm.z  (float normalizado 0.0–1.0)

    Este objeto implementa exatamente essa interface.
    __slots__ garante zero overhead de dict por instância.
    """
    __slots__ = ('x', 'y', 'z')

    def __init__(self, x: float, y: float, z: float = 0.0) -> None:
        self.x = x
        self.y = y
        self.z = z


# ---------------------------------------------------------------------------
# Mapeamento principal
# ---------------------------------------------------------------------------

def remap_landmarks(
    landmarks: List,
    src_wh: tuple,
    dst_wh: tuple,
    flip_h: bool = False,
) -> List[List[_Lm]]:
    """
    Remapeia landmarks normalizados de espaço webcam para espaço screen.

    Mantém proporção via fit-and-center (letterbox/pillarbox automático)
    quando os aspect ratios diferem. Quando são iguais, o mapeamento é direto.

    Args:
        landmarks : list[list[NormalizedLandmark]] — tracker.landmarks
        src_wh    : (width, height) da webcam (fonte dos landmarks)
        dst_wh    : (width, height) do screen  (destino do render)
        flip_h    : True → inverte eixo X (webcam em modo espelho)

    Returns:
        list[list[_Lm]] com .x .y .z normalizados para dst_wh.
        Lista vazia se landmarks estiver vazio.
    """
    if not landmarks:
        return []

    src_w, src_h = src_wh
    dst_w, dst_h = dst_wh

    # --- Calcular scale e offset para manter proporção ---
    # Se os ARs forem iguais (ou quase): mapeamento direto, sem offset.
    # Se diferirem: fit-and-center (como um vídeo letterboxado).
    src_ar = src_w / src_h
    dst_ar = dst_w / dst_h
    ar_diff = abs(src_ar - dst_ar)

    if ar_diff < 0.02:
        # Mesmo AR — mapeamento 1:1
        scale_x = scale_y = 1.0
        off_x = off_y = 0.0
    elif src_ar > dst_ar:
        # Webcam mais larga que a tela → barras horizontais (pillarbox)
        # A largura ocupa 100% → x escala direto; y fica centralizado
        scale_x = 1.0
        scale_y = src_ar / dst_ar     # > 1.0: webcam "estica" verticalmente
        off_x   = 0.0
        off_y   = (1.0 - scale_y) * 0.5  # negativo → crop topo/base
    else:
        # Webcam mais alta que a tela → barras verticais (letterbox)
        # A altura ocupa 100% → y escala direto; x fica centralizado
        scale_y = 1.0
        scale_x = dst_ar / src_ar     # < 1.0: webcam comprimida horizontalmente
        off_y   = 0.0
        off_x   = (1.0 - scale_x) * 0.5  # positivo → margem lateral

    result: List[List[_Lm]] = []
    for hand in landmarks:
        remapped: List[_Lm] = []
        for lm in hand:
            x = (1.0 - lm.x) if flip_h else lm.x
            new_x = x * scale_x + off_x
            new_y = lm.y * scale_y + off_y
            remapped.append(_Lm(new_x, new_y, getattr(lm, 'z', 0.0)))
        result.append(remapped)
    return result


# ---------------------------------------------------------------------------
# Geração de máscara a partir de landmarks remapeados
# ---------------------------------------------------------------------------

def make_hand_mask(
    landmarks: List[List[_Lm]],
    height: int,
    width: int,
) -> np.ndarray:
    """
    Gera máscara binária uint8 (convex hull) a partir de landmarks já remapeados.

    Não depende do estado interno do HandTracker — usa apenas os landmarks
    passados como argumento (normalmente a saída de remap_landmarks).

    Args:
        landmarks : list[list[_Lm]] — saída de remap_landmarks()
        height    : altura do frame de destino (screen)
        width     : largura do frame de destino (screen)

    Returns:
        np.ndarray (height, width) uint8 — 255=mão, 0=fundo
    """
    mask = np.zeros((height, width), dtype=np.uint8)
    for hand_lms in landmarks:
        if not hand_lms:
            continue
        points = np.array(
            [[int(lm.x * width), int(lm.y * height)] for lm in hand_lms],
            dtype=np.int32,
        )
        hull = cv2.convexHull(points)
        cv2.fillConvexPoly(mask, hull, 255)
    return mask


# ---------------------------------------------------------------------------
# Warp de frame/máscara webcam → screen space
# ---------------------------------------------------------------------------

def _fit_and_center(
    img: np.ndarray,
    dst_w: int,
    dst_h: int,
    interp: int,
) -> np.ndarray:
    """
    Redimensiona img para (dst_w, dst_h) preservando proporção (fit-and-center).

    - Se AR idêntico: resize direto.
    - Se src mais largo (pillarbox): escala pela largura, crop/pad vertical central.
    - Se src mais alto  (letterbox): escala pela altura,  crop/pad horizontal central.

    O comportamento espelha exatamente remap_landmarks(), garantindo que pixels
    e landmarks fiquem alinhados no frame de destino.
    """
    src_h, src_w = img.shape[:2]
    src_ar = src_w / src_h
    dst_ar = dst_w / dst_h
    is_2d  = img.ndim == 2

    if abs(src_ar - dst_ar) < 0.02:
        return cv2.resize(img, (dst_w, dst_h), interpolation=interp)

    if src_ar > dst_ar:
        # Pillarbox — escala pela largura, crop/pad vertical
        scale    = dst_w / src_w
        scaled_h = int(src_h * scale)
        scaled   = cv2.resize(img, (dst_w, scaled_h), interpolation=interp)
        off      = (scaled_h - dst_h) // 2
        if off >= 0:
            return scaled[off: off + dst_h, :]
        # scaled_h < dst_h — pad
        pad_t = (-off)
        pad_b = dst_h - scaled_h - pad_t
        val   = 0 if is_2d else (0, 0, 0)
        return cv2.copyMakeBorder(scaled, pad_t, pad_b, 0, 0,
                                  cv2.BORDER_CONSTANT, value=val)
    else:
        # Letterbox — escala pela altura, crop/pad horizontal
        scale    = dst_h / src_h
        scaled_w = int(src_w * scale)
        scaled   = cv2.resize(img, (scaled_w, dst_h), interpolation=interp)
        off      = (scaled_w - dst_w) // 2
        if off >= 0:
            return scaled[:, off: off + dst_w]
        # scaled_w < dst_w — pad
        pad_l = (-off)
        pad_r = dst_w - scaled_w - pad_l
        val   = 0 if is_2d else (0, 0, 0)
        return cv2.copyMakeBorder(scaled, 0, 0, pad_l, pad_r,
                                  cv2.BORDER_CONSTANT, value=val)


def warp_cam_to_screen(
    cam_bgr: np.ndarray,
    cam_wh: tuple,
    screen_wh: tuple,
    flip_h: bool = False,
) -> np.ndarray:
    """
    Redimensiona cam_bgr para screen space usando fit-and-center AR-aware.

    Consistente com remap_landmarks(): landmarks e pixels ficam alinhados.

    Args:
        cam_bgr   : frame BGR da webcam
        cam_wh    : (width, height) da webcam — reservado para validação futura
        screen_wh : (width, height) do destino
        flip_h    : True → inverte eixo X antes do warp

    Returns:
        np.ndarray BGR, shape (screen_h, screen_w, 3)
    """
    dst_w, dst_h = screen_wh
    img = cv2.flip(cam_bgr, 1) if flip_h else cam_bgr
    return _fit_and_center(img, dst_w, dst_h, cv2.INTER_LINEAR)


def warp_mask_to_screen(
    cam_mask: np.ndarray,
    cam_wh: tuple,
    screen_wh: tuple,
    flip_h: bool = False,
) -> np.ndarray:
    """
    Redimensiona cam_mask para screen space (INTER_NEAREST preserva binário).

    Args:
        cam_mask  : máscara uint8 (h, w) — 255=pessoa, 0=fundo
        cam_wh    : (width, height) da webcam
        screen_wh : (width, height) do destino
        flip_h    : True → inverte eixo X antes do warp

    Returns:
        np.ndarray uint8, shape (screen_h, screen_w)
    """
    dst_w, dst_h = screen_wh
    msk = cv2.flip(cam_mask, 1) if flip_h else cam_mask
    return _fit_and_center(msk, dst_w, dst_h, cv2.INTER_NEAREST)
