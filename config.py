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
SHOW_HAND_LANDMARKS = False  # overlay das marcações/conexões da mão — toggle por pinch ou tecla "l"
LANDMARK_GESTURE_CONTROL = True            # True = gesto controla toggle das landmarks
LANDMARK_THUMB_MIDDLE_THRESHOLD        = 0.22  # dist norm. thumb_tip / middle_tip / hand_size
LANDMARK_THUMB_MIDDLE_COOLDOWN_FRAMES  = 20    # frames de bloqueio após toggle
SHOW_MASK = False       # hull overlay desligado por padrão
DEBUG_FORCE = False     # True = força todos os overlays independente do efeito

# --- Efeitos ---
ACTIVE_EFFECT = "orb"  # opções: "orb", "cube", None

# Troca de efeito por teclado
EFFECT_KEYS = {
    ord("o"): "orb",          # FloatingOrb — objeto flutuante no centro
    ord("O"): "orb",          # aceita maiúscula
    ord("c"): "cube",         # FloatingCube — cubo wireframe holográfico
    ord("C"): "cube",         # aceita maiúscula
    ord("t"): "triangle",     # FloatingTriangle — tetraedro holográfico
    ord("T"): "triangle",     # aceita maiúscula
    ord("0"): None,
}

# Efeitos intensos: overlays de debug desligados automaticamente
INTENSE_EFFECTS = {"orb", "cube", "triangle"}

SHOW_ACTIVE_EFFECT_NAME = True  # mostra o nome do efeito ativo na tela (independente de DEBUG)

# GestureDetector — Sprint 16: controle por gesto (pinch)
PINCH_THRESHOLD      = 0.28   # distância normalizada (pinch_dist/hand_size) para ativar
PINCH_HOLD_FRAMES    = 4      # frames consecutivos para confirmar o pinch (~133ms a 30fps)
PINCH_COOLDOWN_FRAMES = 20    # frames de bloqueio após disparar — evita múltiplos toggles
LANDMARK_PINCH_TOGGLE_COOLDOWN_FRAMES = 20  # alias explícito para o cooldown do toggle de landmarks
SHOW_PINCH_INDICATOR = True   # indicador visual entre polegar e indicador
GESTURE_EFFECT_CYCLE = ["orb", "cube"]  # reservado (pinch não cicla mais efeitos)

# MotionTracker — motion.py: metricas globais de movimento da mao
MOTION_VEL_EMA   = 0.72   # EMA de velocidade (0=sem suavizacao, 1=maximo)
MOTION_ACCEL_EMA = 0.80   # EMA de aceleracao (mais alto = mais suave)
MOTION_SPEED_MAX = 25.0   # pixels/frame que corresponde a speed=1.0
MOTION_DEAD_ZONE = 2.0    # pixels/frame abaixo dos quais speed=0 (elimina jitter)

# ---------------------------------------------------------------------------
# Modo de operação ("camera" | "presentation")
# ---------------------------------------------------------------------------
MODE = "camera"  # altera aqui para ativar o Presentation Mode

# --- Screen Capture (presentation mode) ---
SCREEN_MONITOR_INDEX  = 1      # 1 = monitor principal (mss usa índice 1-based)
SCREEN_TARGET_WIDTH   = 1280
SCREEN_TARGET_HEIGHT  = 720

# --- Presentation Mode ---
PRESENTATION_SHOW_WEBCAM         = False          # desativado — usuário composto em full-frame (T3)
PRESENTATION_WEBCAM_SCALE        = 0.35           # reservado (PiP desativado)
PRESENTATION_WEBCAM_POS          = "bottom_right" # reservado (PiP desativado)
PRESENTATION_ENABLE_SEGMENTATION = True           # recorte do usuário via BodySegmenter
PRESENTATION_FLIP_LANDMARKS      = True           # inverte eixo X (webcam espelhada vs. screen)

# ---------------------------------------------------------------------------
# Visual Compositing — camadas de profundidade (T1, T2, T4, T7)
# ---------------------------------------------------------------------------

# T1 — Dashboard como objeto visual (painel flutuante centralizado)
PRES_DASHBOARD_SCALE       = 0.55    # tamanho do painel dentro do frame (0.50–0.80)
PRES_BG_COLOR              = (8, 10, 16)    # cor BGR do canvas de fundo (quase preto azulado)
PRES_PANEL_BORDER          = True           # borda sutil ao redor do painel
PRES_PANEL_BORDER_COLOR    = (55, 95, 155)  # cor da borda — azul-aço suave
PRES_PANEL_GLOW            = 0.22           # intensidade do glow na borda (0=off)

# T4/T7 — Tratamento de camadas para profundidade visual
PRES_DASHBOARD_DIM         = 0.76    # brilho do dashboard relativo ao usuário (fundo menos chamativo)
PRES_USER_BRIGHTNESS       = 1.10    # boost de brilho do usuário (destaque Layer 3)

# T2 — Suavização da borda do recorte do usuário
PRES_MASK_FEATHER          = 7       # raio do blur de feathering da máscara (px, ímpar)

# T5 — Poluição visual
PRES_SHOW_EFFECT_NAME      = False   # esconde label do efeito ativo no presentation mode
PRES_SHOW_FPS              = True    # mantém FPS visível para monitoramento

# Performance + composição visual
PRES_ACTIVE_EFFECT         = "orb"        # efeito ativo no presentation mode (orb ou cube)
PRES_TRACK_SCALE           = 0.5     # reservado — presentation mode usa PRES_CAM como resolução base
PRES_USER_WIDTH_SCALE      = 0.50    # largura do usuário como fração do screen_w
PRES_USER_SIDE             = "right" # posição do usuário: "right" | "left" | "center"
PRES_USER_MARGIN           = 0       # margem da borda em pixels
PRES_CAM_WIDTH             = 640     # resolução da webcam em presentation mode (mais rápido que 1280×720)
PRES_CAM_HEIGHT            = 360     # idem (altura)
PRES_SEG_INTERVAL          = 6       # segmentação a cada N frames (12 era muito lento → mask velha)

# ---------------------------------------------------------------------------
# FloatingOrbEffect — Sprint FloatingOrb: objeto energético flutuante no centro
# ---------------------------------------------------------------------------
FLOATING_ORB_RADIUS         = 120    # raio base do orb em pixels
FLOATING_ORB_ALPHA          = 0.90   # opacidade global dos elementos
FLOATING_ORB_GLOW           = 0.60   # intensidade do bloom (0=off)
FLOATING_ORB_GLOW_BLUR      = 31     # raio do blur do glow (px, ímpar)
FLOATING_ORB_ROTATION_SPEED = 0.8    # graus por frame (anel externo)
FLOATING_ORB_PULSE_SPEED    = 0.055  # velocidade da pulsação (rad/frame)
FLOATING_ORB_REACTIVITY     = 1.0    # multiplicador de reatividade ao movimento
FLOATING_ORB_COLOR          = (220, 160, 255)  # cor BGR base — violeta/lavanda
FLOATING_ORB_ACCENT         = (100, 255, 220)  # cor dos segmentos — ciano

# FloatingOrbEffect — Sprint Orb Interaction Control
FLOATING_ORB_FOLLOW_STRENGTH          = 0.40   # [0..1] fração do offset da mão transferido ao orb
FLOATING_ORB_POSITION_SMOOTHING       = 0.88   # EMA de posição (0=imediato, 1=inércia máxima)
FLOATING_ORB_MAX_OFFSET_X             = 200    # deslocamento horizontal máximo em pixels
FLOATING_ORB_MAX_OFFSET_Y             = 150    # deslocamento vertical máximo em pixels
FLOATING_ORB_MANUAL_ROTATION_STRENGTH = 6.0    # graus/frame adicionados por nx unitário
FLOATING_ORB_ROTATION_DAMPING         = 0.88   # decaimento da velocidade rotacional (0=brusco, 1=nenhum)
FLOATING_ORB_IDLE_ROTATION_SPEED      = 0.4    # velocidade de rotação base sem mão (deg/frame)
FLOATING_ORB_VERTICAL_SCALE_STRENGTH  = 0.25   # influência de ny na escala (cima=expande)
FLOATING_ORB_MIN_SCALE                = 0.65   # escala mínima do orb
FLOATING_ORB_MAX_SCALE                = 1.40   # escala máxima do orb
FLOATING_ORB_ENERGY_FROM_SPEED        = 1.0    # multiplicador de speed→energia
FLOATING_ORB_ACCEL_BURST_STRENGTH     = 0.60   # contribuição extra da aceleração para energia

# FloatingOrbEffect — Sprint Orb Finger Control
FLOATING_ORB_USE_FINGER_CONTROL       = True   # True=controle pelo indicador; False=motion.state legado
FLOATING_ORB_FINGER_ROTATION_STRENGTH = 1.0    # multiplicador do delta angular do indicador
FLOATING_ORB_FINGER_ROTATION_SMOOTHING = 0.75  # EMA do delta angular (0=seco, 1=inércia máxima)
FLOATING_ORB_FINGER_CENTER_BIAS       = 0.60   # 0=palma, 1=ponta do indicador (posição do orb)
FLOATING_ORB_PINCH_SCALE_STRENGTH     = 0.50   # fração da mão que equivale a 100% aberto
FLOATING_ORB_IDLE_X                   = 0.50   # posição X idle normalizada [0..1]
FLOATING_ORB_IDLE_Y                   = 0.50   # posição Y idle normalizada [0..1]
FLOATING_ORB_FLOAT_AMP                = 14     # amplitude da microflutuação orgânica (px)
FLOATING_ORB_FLOAT_SPEED              = 0.018  # velocidade da flutuação orgânica (rad/frame)
FLOATING_ORB_DRIFT_STRENGTH           = 0.18   # fração do offset da mão transferida ao orb (0=centro fixo)

# ---------------------------------------------------------------------------
# FloatingCubeEffect — Sprint FloatingCube: cubo wireframe holográfico flutuante
# ---------------------------------------------------------------------------
FLOATING_CUBE_SIZE                  = 55     # metade do lado do cubo em pixels (half-extent)
FLOATING_CUBE_MIN_SCALE             = 0.45   # escala mínima (pinch fechado)
FLOATING_CUBE_MAX_SCALE             = 1.20   # escala máxima (mão aberta)
FLOATING_CUBE_ALPHA                 = 0.90   # opacidade global das arestas
FLOATING_CUBE_COLOR                 = (220, 230, 255)  # BGR: branco azulado (arestas frontais)
FLOATING_CUBE_ACCENT_COLOR          = (140, 200, 255)  # BGR: azul médio (arestas traseiras)
FLOATING_CUBE_GLOW                  = 0.55   # legado — substituído em Sprint 3 (mantido para compatibilidade)
# Sprint 1 — Hierarquia de profundidade
FLOATING_CUBE_FRONT_ALPHA           = 1.00   # opacidade das arestas frontais [0..1]
FLOATING_CUBE_BACK_ALPHA            = 0.28   # opacidade das arestas traseiras
FLOATING_CUBE_FRONT_THICKNESS       = 3      # espessura das arestas frontais (px)
FLOATING_CUBE_BACK_THICKNESS        = 1      # espessura das arestas traseiras (px)
# Sprint 2 — Linha dupla (núcleo + halo)
FLOATING_CUBE_CORE_THICKNESS        = 1      # espessura do núcleo interno (px)
FLOATING_CUBE_HALO_THICKNESS        = 4      # espessura do halo externo (px)
FLOATING_CUBE_HALO_ALPHA            = 0.22   # opacidade do halo (fator sobre a aresta)
# Sprint 3 — Glow real (holográfico)
FLOATING_CUBE_GLOW_INTENSITY        = 1.05   # intensidade do glow apertado — pass 1
FLOATING_CUBE_GLOW_BLUR             = 13     # kernel do glow apertado (px, ímpar)
FLOATING_CUBE_GLOW2_INTENSITY       = 0.38   # intensidade do halo suave — pass 2
FLOATING_CUBE_GLOW2_BLUR            = 41     # kernel do halo suave (px, ímpar)
# Sprint 4 — Cor profissional → neon azul holográfico
FLOATING_CUBE_CORE_COLOR            = (255, 255, 255)  # BGR: branco puro — núcleo das arestas
FLOATING_CUBE_GLOW_COLOR            = (220, 140, 20)   # BGR: ciano-azul suave — halo
FLOATING_CUBE_BACK_DESATURATE       = 0.50   # dessaturação das arestas traseiras
# Sprint 5 — Pulsação sutil
FLOATING_CUBE_PULSE_SPEED           = 0.032  # velocidade da respiração (rad/frame)
FLOATING_CUBE_PULSE_INTENSITY       = 0.10   # amplitude da variação de alpha — elegante
# Trail leve ao mover
FLOATING_CUBE_TRAIL_DECAY           = 0.40   # fator de decaimento do rastro por frame
# Sprint 6 — Volumétrico holográfico (faces + partículas)
FLOATING_CUBE_VOLUMETRIC            = True   # habilita faces e partículas internas
FLOATING_CUBE_FACE_COLOR            = (120, 60, 10)   # BGR: azul ciano escuro para faces
FLOATING_CUBE_FACE_ALPHA            = 0.09   # opacidade das faces — volume sem bloquear vídeo
FLOATING_CUBE_PARTICLE_COUNT        = 160    # número de partículas internas
FLOATING_CUBE_PARTICLE_SIZE         = 1      # raio das partículas em px
FLOATING_CUBE_PARTICLE_ALPHA        = 0.55   # opacidade máxima das partículas
FLOATING_CUBE_PARTICLE_COLOR        = (230, 170, 25)  # BGR: ciano suave das partículas
FLOATING_CUBE_PARTICLE_DEPTH        = 0.70   # influência da profundidade no brilho das partículas
FLOATING_CUBE_IDLE_ROTATION_X       = 0.18   # rotação automática no eixo X (deg/frame)
FLOATING_CUBE_IDLE_ROTATION_Y       = 0.28   # rotação automática no eixo Y (deg/frame)
FLOATING_CUBE_IDLE_ROTATION_Z       = 0.06   # rotação automática no eixo Z (deg/frame)
FLOATING_CUBE_FINGER_ROTATION_X     = 1.2    # multiplicador de rotação X por movimento vertical do indicador
FLOATING_CUBE_FINGER_ROTATION_Y     = 1.4    # multiplicador de rotação Y por movimento horizontal do indicador
FLOATING_CUBE_ROTATION_SMOOTHING    = 0.78   # EMA do delta angular (0=seco, 1=inércia máxima)
FLOATING_CUBE_ROTATION_DAMPING      = 0.88   # decaimento da velocidade rotacional
FLOATING_CUBE_POSITION_SMOOTHING    = 0.90   # EMA de posição do cubo
FLOATING_CUBE_IDLE_X                = 0.50   # posição X idle normalizada [0..1]
FLOATING_CUBE_IDLE_Y                = 0.50   # posição Y idle normalizada [0..1]
FLOATING_CUBE_IDLE_DRIFT_AMP        = 10     # amplitude da microflutuação orgânica (px)
FLOATING_CUBE_IDLE_DRIFT_SPEED      = 0.016  # velocidade da flutuação orgânica (rad/frame)
FLOATING_CUBE_DRIFT_STRENGTH        = 0.14   # fração do offset da mão transferida ao cubo
FLOATING_CUBE_OPEN_HAND_THRESHOLD   = 0.38   # distância min indicador-palma / hand_size para "mão aberta"
FLOATING_CUBE_FADE_SPEED            = 0.06   # incremento de alpha por frame ao aparecer/desaparecer
FLOATING_CUBE_PERSPECTIVE_FOV       = 500    # distância focal pseudo-perspectiva (px)
FLOATING_CUBE_ENERGY_FROM_SPEED     = 1.0    # multiplicador de speed→energia (glow)
FLOATING_CUBE_ACCEL_BURST           = 0.50   # burst de energia por aceleração brusca
FLOATING_CUBE_TWO_HAND_SCALE        = 0.50   # legado (nao usado; mantido para compatibilidade)
FLOATING_CUBE_TWO_HAND_PINCH_THRESHOLD      = 0.22   # distancia polegar-indicador / hand_size para contar como pinch
FLOATING_CUBE_TWO_HAND_CENTER_BLEND         = 0.35   # fracao do centro da tela misturada na posicao (0=so entre maos)
FLOATING_CUBE_TWO_HAND_SCALE_RESPONSE       = 1.0    # fator: 1.0 = escala 1:1 com distancia relativa
FLOATING_CUBE_TWO_HAND_SCALE_SMOOTHING      = 0.90   # EMA de escala e distancia com duas maos
FLOATING_CUBE_TWO_HAND_POSITION_SMOOTHING   = 0.92   # EMA de posicao com duas maos
FLOATING_CUBE_TWO_HAND_MIN_SCALE            = 0.25   # escala minima com duas maos
FLOATING_CUBE_TWO_HAND_MAX_SCALE            = 1.40   # escala maxima com duas maos
FLOATING_CUBE_TWO_HAND_MAX_ROTATION_DELTA   = 3.0    # clamp max de rotacao por frame no modo duas maos (deg)

# ---------------------------------------------------------------------------
# FloatingCubeEffect — Bounce Animation (gesto dedão + mindinho)
# ---------------------------------------------------------------------------
CUBE_THUMB_PINKY_GESTURE_ENABLED    = True   # habilita detecção do gesto
CUBE_THUMB_PINKY_THRESHOLD          = 0.22   # distância norm. thumb_tip / pinky_tip / hand_size
CUBE_THUMB_PINKY_COOLDOWN_FRAMES    = 20     # frames de bloqueio após disparar

FLOATING_CUBE_BOUNCE_ENABLED        = True   # habilita a animação de bounce
FLOATING_CUBE_BOUNCE_HEIGHT         = 120    # deslocamento Y máximo em pixels (positivo = sobe)
FLOATING_CUBE_BOUNCE_FAST_UP_FRAMES   = 8    # etapa 1: subida rápida
FLOATING_CUBE_BOUNCE_FAST_DOWN_FRAMES = 10   # etapa 2: descida rápida
FLOATING_CUBE_BOUNCE_SLOW_UP_FRAMES   = 22   # etapa 3: subida lenta
FLOATING_CUBE_BOUNCE_SLOW_DOWN_FRAMES = 24   # etapa 4: descida suave
# ---------------------------------------------------------------------------
# FloatingCubeEffect — Controle de escala por duas mãos (pinch indicador + polegar)
# ---------------------------------------------------------------------------
TWO_HAND_CUBE_SCALE_ENABLED    = True    # habilita controle externo de escala
TWO_HAND_CUBE_PINCH_THRESHOLD  = 0.28    # dist norm. thumb+index / hand_size para pinch
TWO_HAND_CUBE_MIN_SCALE        = 0.25    # escala mínima permitída
TWO_HAND_CUBE_MAX_SCALE        = 2.0     # escala máxima permitída
TWO_HAND_CUBE_SCALE_SMOOTHING  = 0.88    # EMA de suavização da escala (0=seco, 1=inércia)
TWO_HAND_CUBE_DEAD_ZONE        = 0.03    # variação mínima de escala para atualizar alvo

# ---------------------------------------------------------------------------
# FloatingTriangleEffect — Tetraedro holográfico flutuante
# ---------------------------------------------------------------------------
# Gesto de ativação: polegar + anelar (thumb tip ↔ ring finger tip)
TRIANGLE_THUMB_RING_GESTURE_ENABLED  = True   # habilita detecção do gesto
TRIANGLE_THUMB_RING_THRESHOLD        = 0.24   # dist norm. thumb_tip / ring_tip / hand_size
TRIANGLE_THUMB_RING_COOLDOWN_FRAMES  = 25     # frames de bloqueio após disparar
# Geometria
FLOATING_TRIANGLE_SIZE               = 60     # metade da aresta base em pixels
FLOATING_TRIANGLE_MIN_SCALE          = 0.45
FLOATING_TRIANGLE_MAX_SCALE          = 1.20
# Rotação idle
FLOATING_TRIANGLE_IDLE_ROTATION_X    = 0.14
FLOATING_TRIANGLE_IDLE_ROTATION_Y    = 0.22
FLOATING_TRIANGLE_IDLE_ROTATION_Z    = 0.05
# Posição e suavização
FLOATING_TRIANGLE_POSITION_SMOOTHING = 0.90
FLOATING_TRIANGLE_IDLE_X             = 0.50
FLOATING_TRIANGLE_IDLE_Y             = 0.50
FLOATING_TRIANGLE_IDLE_DRIFT_AMP     = 10
FLOATING_TRIANGLE_IDLE_DRIFT_SPEED   = 0.016
FLOATING_TRIANGLE_DRIFT_STRENGTH     = 0.14
FLOATING_TRIANGLE_FADE_SPEED         = 0.06
FLOATING_TRIANGLE_PERSPECTIVE_FOV    = 500
FLOATING_TRIANGLE_ROTATION_DAMPING   = 0.88
FLOATING_TRIANGLE_ROTATION_SMOOTHING = 0.78
FLOATING_TRIANGLE_FINGER_ROTATION_X  = 1.2
FLOATING_TRIANGLE_FINGER_ROTATION_Y  = 1.4
FLOATING_TRIANGLE_ENERGY_FROM_SPEED  = 1.0
FLOATING_TRIANGLE_ACCEL_BURST        = 0.50
FLOATING_TRIANGLE_OPEN_HAND_THRESHOLD = 0.38
# Visual — mesma família do cubo
FLOATING_TRIANGLE_ALPHA              = 0.90
FLOATING_TRIANGLE_CORE_COLOR         = (255, 255, 255)  # branco puro — núcleo
FLOATING_TRIANGLE_GLOW_COLOR         = (220, 140, 20)   # ciano-azul suave — halo
FLOATING_TRIANGLE_BACK_DESATURATE    = 0.50
FLOATING_TRIANGLE_FRONT_ALPHA        = 1.00
FLOATING_TRIANGLE_BACK_ALPHA         = 0.28
FLOATING_TRIANGLE_FRONT_THICKNESS    = 3
FLOATING_TRIANGLE_BACK_THICKNESS     = 1
FLOATING_TRIANGLE_CORE_THICKNESS     = 1
FLOATING_TRIANGLE_HALO_THICKNESS     = 4
FLOATING_TRIANGLE_HALO_ALPHA         = 0.22
FLOATING_TRIANGLE_GLOW_INTENSITY     = 1.05
FLOATING_TRIANGLE_GLOW_BLUR          = 13
FLOATING_TRIANGLE_GLOW2_INTENSITY    = 0.38
FLOATING_TRIANGLE_GLOW2_BLUR         = 41
FLOATING_TRIANGLE_FACE_COLOR         = (120, 60, 10)
FLOATING_TRIANGLE_FACE_ALPHA         = 0.09
FLOATING_TRIANGLE_PULSE_SPEED        = 0.032
FLOATING_TRIANGLE_PULSE_INTENSITY    = 0.10
FLOATING_TRIANGLE_TRAIL_DECAY        = 0.40