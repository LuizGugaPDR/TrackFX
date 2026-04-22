# config.py
# Única fonte de verdade para todos os parâmetros do sistema.
# Todos os módulos devem importar configurações daqui.

# --- Câmera ---
CAMERA_INDEX = 0
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
TARGET_FPS = 30

# --- Janela ---
WINDOW_NAME = "TrackFX"

# --- Modelo MediaPipe ---
MODEL_PATH = "hand_landmarker.task"  # baixado automaticamente se ausente
SEG_MODEL_PATH = "selfie_segmenter.tflite"  # baixado automaticamente pelo BodySegmenter

# --- Debug ---
DEBUG = False           # desliga bbox e overlays técnicos
SHOW_FPS = True
SHOW_LANDMARKS = False  # landmarks desligados por padrão em modo visual
SHOW_MASK = False       # hull overlay desligado por padrão
DEBUG_FORCE = False     # True = força todos os overlays independente do efeito

# --- Efeitos ---
ACTIVE_EFFECT = "hud"  # opções: "tracking", "glitch", "distortion", "displacement", "aura", "trail", "fire", "organic", "ribbon", "hud", None

# Troca de efeito por teclado
EFFECT_KEYS = {
    ord("1"): "glitch",
    ord("2"): "tracking",    # modo tracking visual puro (skeleton + hull)
    ord("3"): "distortion",
    ord("4"): "displacement",
    ord("5"): "aura",
    ord("6"): "trail",
    ord("7"): "fire",
    ord("8"): "organic",
    ord("9"): "ribbon",
    ord("h"): "hud",          # HUD futurista passando ATRÁS da pessoa
    ord("H"): "hud",          # aceita maiúscula (Caps Lock)
    ord("0"): None,
}

# Efeitos intensos: todos os overlays desligados automaticamente
# "tracking" incluído para evitar desenho duplo se SHOW_LANDMARKS=True
INTENSE_EFFECTS = {"fire", "aura", "displacement", "organic", "trail", "ribbon", "tracking", "hud"}

# Glitch avançado
GLITCH_SHIFT = 14              # deslocamento máximo de canal em pixels
GLITCH_SCANLINE_ALPHA = 0.45   # opacidade das scanlines
GLITCH_SCANLINE_STEP = 3       # espaçamento entre scanlines em pixels
GLITCH_BLOCK_CHANCE = 0.25     # probabilidade de bloco de ruído
GLITCH_BLOCK_SIZE = 16         # tamanho máximo do bloco de ruído

# Distortion
DISTORTION_AMPLITUDE = 10
DISTORTION_FREQUENCY = 60

# Displacement (reativo à posição da mão)
DISPLACEMENT_AMPLITUDE = 20
DISPLACEMENT_DECAY = 0.15

# Aura / Energy Field
AURA_LAYERS = 5                # número de camadas de glow
AURA_BLUR_BASE = 25            # tamanho do kernel do blur base (ímpar)
AURA_INTENSITY = 2.2           # multiplicador de brilho da aura
AURA_COLOR = (180, 60, 255)    # cor BGR da aura
AURA_PULSE_SPEED = 0.12        # velocidade de pulsação

# Trail / Ghosting
TRAIL_LENGTH = 8               # número de frames anteriores no trail
TRAIL_DECAY = 0.65             # alpha de cada frame fantasma
TRAIL_BLUR = 7                 # blur aplicado nos frames fantasmas (ímpar)
TRAIL_COLOR_SHIFT = True       # aplicar shift de cor nos fantasmas

# Fire Effect — noise scrolling
FIRE_INTENSITY    = 1.5    # força da injeção de calor na base (0.5–2.0)
FIRE_COOLING      = 0.975  # resfriamento lento → chamas altas com gradiente natural branco→laranja→vermelho
FIRE_SCROLL       = 3      # pixels scrollados para cima por frame (velocidade da chama)
FIRE_SEED_HEIGHT  = 0.28   # fração da ROI onde as seeds são injetadas (base da chama)
FIRE_DENSITY      = 0.70   # reservado — coerência temporal agora controla a estrutura
FIRE_THRESHOLD    = 0.08   # baixo = mais massa visível, chama com volume
FIRE_SCALE        = 0.40   # resolução interna do buffer (menor = mais FPS)
FIRE_FLAME_HEIGHT = 1.5    # espaço acima da mão (proporção da altura da mão)
FIRE_GLOW_INTENSITY = 2.8  # bloom intenso ao redor das chamas
FIRE_GLOW_BLUR    = 45     # raio do bloom em pixels (ímpar) — extrapola a máscara

# Fire debug (desligar em produção)
SHOW_FIRE_MASK_DEBUG   = False  # sobrepõe heat map em falso colorido para ver se o efeito existe
SHOW_FIRE_GLOW_DEBUG   = False  # exibe o canal de glow isolado antes de compor
SHOW_ACTIVE_EFFECT_NAME = True  # mostra o nome do efeito ativo na tela (independente de DEBUG)

# Organic Warp
ORGANIC_AMPLITUDE = 22         # intensidade máxima do warp em pixels
ORGANIC_FREQ_SPATIAL = 0.025   # frequência espacial do ruído
ORGANIC_FREQ_TEMPORAL = 1.6    # velocidade temporal do ruído

# RibbonWarpEffect — dual-layer echo smear (Sprint 12)
RIBBON_WAVE_AMP   = 22     # amplitude base da wave (aumenta com velocidade)
RIBBON_WAVE_FREQ  = 0.032  # frequência espacial da wave
RIBBON_RGB_SPLIT  = 14     # split base da aberração cromática
RIBBON_INTENSITY  = 1.25   # intensidade base do blend
RIBBON_GLOW       = 1.6    # intensidade base do bloom
RIBBON_GLOW_BLUR  = 33     # raio do bloom em pixels (ímpar)
RIBBON_PAD        = 58     # padding da ROI além dos limites da mão

# Dual-layer (Sprint 12)
RIBBON_NEAR_DECAY  = 0.76               # near layer: decay rápido → smear nítido e curto
RIBBON_FAR_DECAY   = 0.93               # far  layer: decay lento  → eco persistente
RIBBON_NEAR_TINT   = (0.45, 0.80, 1.40) # tint quente — (B_scale, G_scale, R_scale)
RIBBON_FAR_TINT    = (1.55, 0.82, 0.40) # tint frio   — (B_scale, G_scale, R_scale)
RIBBON_LAYER_SEP   = 22                 # px de separação entre camadas no vetor de movimento
RIBBON_SCANLINES   = 0.10               # opacidade das scanlines CRT (0 = desligado)

# Controle de velocidade e reatividade (Sprint 11)
RIBBON_VEL_EMA    = 0.72   # suavização EMA da velocidade
RIBBON_DEAD_ZONE  = 2.5    # px/frame abaixo dos quais reatividade = zero
RIBBON_SPEED_MAX  = 22.0   # px/frame que corresponde a speed=1.0
RIBBON_VEL_SCALE  = 1.0    # escala mestre de toda a reatividade

# HUDBehindEffect — HUD futurista que passa ATRÁS da pessoa (Sprint 13 v2)
HUD_COLOR          = (200, 230, 255)  # cor BGR base — branco azulado suave
HUD_ACCENT_COLORS  = [               # paleta de cores para variação entre elementos
    (180, 255, 220),  # ciano suave
    (255, 240, 200),  # branco quente
    (240, 200, 255),  # lavanda
    (200, 255, 240),  # verde-água
]
HUD_THICKNESS      = 1               # espessura das linhas (1=fino, 2=médio)
HUD_ALPHA          = 0.38            # opacidade global do HUD sobre o frame
HUD_GLOW           = 0.0             # bloom (0=desligado para performance; tente 0.4 para visual)
HUD_GLOW_BLUR      = 9               # raio do blur do glow em pixels (ímpar)
HUD_BRACKET_SIZE   = 28             # tamanho em pixels dos braços dos corner brackets
HUD_BRACKET_MARGIN = 20             # margem dos brackets em relação à borda
HUD_DENSITY        = 4              # número de elementos de scan ativos (4=limpo, 6=denso)
HUD_SPEED          = 1.0            # multiplicador global de velocidade de animação
HUD_EDGE_SNAP      = True           # posicionar elementos próximos a bordas da cena
HUD_SEG_INTERVAL   = 6             # rodar segmentação a cada N frames (performance)
HUD_SEG_SCALE      = 0.5           # downscale para inferência do segmentador (0.5=metade)

# HUDBehindEffect — Sprint 14: scanner reativo + motion + depth layers
SCANNER_SPEED      = 0.006         # velocidade do scanner (fração da altura por frame)
SCANNER_INTENSITY  = 0.35          # brilho da linha do scanner (0=off, 1=máximo)
HUD_REACTIVITY     = 1.0           # multiplicador de reatividade ao movimento da cena
HUD_FLICKER        = 0.12          # intensidade do flicker aleatório (0=none, 0.5=forte)
HUD_LAYER_ALPHA    = (0.20, 0.42)  # alpha por camada: (layer 0 fundo, layer 1 médio)
