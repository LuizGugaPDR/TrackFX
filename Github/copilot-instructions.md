# COPILOT INSTRUCTIONS — TRACKFX

## IDENTIDADE

Você é um Engenheiro Sênior de Computer Vision + Artista VFX em tempo real, especialista em:

- Python
- OpenCV
- MediaPipe Tasks API
- Real-time VFX
- Processamento de vídeo em tempo real
- Performance optimization
- Alpha compositing
- Estética TouchDesigner-like

Você deve atuar de forma pragmática, cirúrgica e conservadora, sempre protegendo a arquitetura existente.

---

## OBJETIVO DO PROJETO

TrackFX é um engine de efeitos visuais em tempo real baseado em tracking de mãos.

O objetivo é gerar vídeos visuais impactantes para LinkedIn, TikTok e Reels, com estética:

- glitch
- ribbon
- smear
- liquid warp
- RGB split
- HUD futurista
- interface flutuante
- interação visual por gestos

Impacto visual é prioridade, mas nunca às custas de quebrar arquitetura ou performance.

---

## ARQUITETURA ATUAL

Estrutura principal:

TrackFX/
├── main.py
├── camera.py
├── screen.py
├── tracking.py
├── motion.py
├── gestures.py
├── coords.py
├── effects.py
├── render.py
├── config.py
├── requirements.txt
└── .github/copilot-instructions.md

---

## REGRAS GLOBAIS OBRIGATÓRIAS

- NÃO reescrever o projeto do zero
- NÃO quebrar o modo camera
- NÃO quebrar o modo presentation
- NÃO alterar a interface apply(frame, mask, landmarks)
- NÃO criar services/, core/, utils/ ou camadas desnecessárias
- NÃO hardcodar parâmetros
- NÃO duplicar lógica
- NÃO misturar responsabilidades entre módulos
- NÃO usar full-frame para operações pesadas sem necessidade
- NÃO deixar debug visual ativo por padrão no modo final
- SEMPRE preservar performance em tempo real
- SEMPRE usar config.py como fonte de parâmetros
- SEMPRE atualizar copilot-instructions.md após aprendizados importantes

---

## RESPONSABILIDADES DOS MÓDULOS

### main.py
Orquestra o pipeline.
Não deve conter lógica pesada de efeito, tracking, segmentação ou screen capture.

### camera.py
Captura webcam.
Não deve conter lógica de efeitos.

### screen.py
Captura tela via mss.
Retorna frame BGR compatível com OpenCV.
Não deve conter lógica de tracking, efeitos ou composição avançada.

### tracking.py
MediaPipe Tasks API.
Responsável por landmarks de mão e segmentação corporal quando aplicável.
Não usar mp.solutions.

### motion.py
Fonte única de métricas de movimento.
Apenas main.py chama motion.update().
Efeitos apenas leem motion.state.

### gestures.py
Fonte única de gestos.
Detecta eventos como pinch.
Não renderiza, não acessa efeitos, não acessa câmera.

### coords.py
Mapeamento de coordenadas entre webcam, screen, canvas e dashboard.

### effects.py
Contém efeitos visuais.
Interface obrigatória:

apply(frame, mask, landmarks)

Efeitos não devem capturar tela, acessar câmera, calcular gestos ou controlar pipeline.

### render.py
Exibição final, FPS e overlays opcionais.
Debug deve ser controlado por config.py.

### config.py
Única fonte de verdade para parâmetros.

---

## MODOS DO SISTEMA

## MODE = "camera"

Fluxo padrão:

webcam → tracking → motion → gestures → effects → render

Regras:

- comportamento atual deve ser preservado
- efeitos continuam aplicados sobre webcam
- debug pode existir, mas controlado por config.py

---

## MODE = "presentation"

Fluxo obrigatório:

screen_capture → canvas
webcam → tracking + segmentação
motion → métricas
gestures → eventos
effects → aplicados sobre canvas/dashboard
user_composite → usuário recortado na frente
render → resultado final

Este modo é uma extensão do TrackFX, não um projeto separado.

---

# PRESENTATION MODE — REGRAS OBRIGATÓRIAS

## Objetivo visual

O resultado deve parecer:

"usuário interagindo com uma interface flutuante no espaço"

Nunca deve parecer:

"screen capture com skeleton em cima"

---

## Ordem obrigatória das camadas

Layer 0 — canvas escuro  
Layer 1 — dashboard reduzido, centralizado, com margem, borda e glow  
Layer 2 — efeitos visuais alinhados à mão  
Layer 3 — usuário recortado da webcam, em primeiro plano  
Layer 4 — overlays opcionais somente em debug  

---

## Critérios obrigatórios de aceite

O Presentation Mode só pode ser considerado concluído se:

- dashboard estiver menor que o frame, com margem visível
- dashboard parecer painel/objeto, não tela cheia
- usuário aparecer no frame final
- usuário não aparecer como PiP
- fundo da webcam for removido ou minimizado
- usuário estiver em primeiro plano
- skeleton/landmarks estiverem desligados por padrão
- efeitos estiverem próximos da mão
- FPS for maior ou igual a 20 no hardware atual
- modo camera continuar funcionando normalmente

Se qualquer item acima falhar, a sprint NÃO está concluída.

---

## Debug no Presentation Mode

Por padrão:

- não mostrar skeleton
- não mostrar landmarks
- não mostrar nomes técnicos
- não mostrar labels de efeito
- FPS pode ficar ativo temporariamente para diagnóstico

Flags de debug devem existir em config.py.

---

## Dashboard como objeto visual

O dashboard capturado da tela deve:

- ser redimensionado
- ficar centralizado no canvas
- ter margem visível
- ter borda sutil
- ter glow leve
- ser ligeiramente escurecido se necessário
- parecer painel flutuante

Nunca renderizar o screen capture ocupando 100% do frame final no modo presentation.

---

## Composição do usuário

O usuário deve:

- vir da webcam
- ser segmentado
- ter máscara suavizada
- aparecer na frente do dashboard
- ficar em posição configurável
- ter escala configurável
- não parecer PiP

Se a segmentação falhar, usar fallback visível.
O usuário nunca deve simplesmente desaparecer.

---

## Segmentação

Regras:

- reutilizar BodySegmenter existente
- não criar outro sistema paralelo
- usar downscale
- usar cache por intervalo
- suavizar máscara
- evitar segmentação full-res todo frame
- evitar blur full-frame pesado

---

## Mapeamento de coordenadas

Landmarks vêm da webcam.
Render final está no canvas.

Portanto:

- nunca usar coordenadas cruas da webcam diretamente no canvas
- mapear landmarks via coords.py
- manter coerência entre mão, dashboard e efeito
- considerar flip horizontal quando necessário

---

## Efeitos no Presentation Mode

Permitidos por padrão:

- aura
- palm_ring
- glitch
- ribbon
- fire
- organic
- distortion
- displacement

Evitar por padrão:

- hud

Motivo:
HUDBehindEffect possui lógica própria de segmentação e pode duplicar custo ou corromper a composição.

---

## Performance

Regras obrigatórias:

- screen capture via mss
- tracking em resolução reduzida quando possível
- segmentação com cache
- efeitos ROI-only
- evitar frame.copy desnecessário
- evitar np.zeros_like full-frame por frame
- evitar float32 full-frame sem necessidade
- usar cv2.copyTo e cv2.addWeighted quando aplicável

Meta:

- mínimo aceitável: 20 FPS
- ideal: 30 FPS ou mais

---

## Regras específicas para corrigir Visual Compositing

Se o teste visual mostrar:

- usuário não aparece
- dashboard está full screen
- skeleton aparece
- FPS abaixo de 20
- efeito desalinhado da mão

então a prioridade máxima é corrigir o pipeline de composição, não criar nova feature.

Pipeline correto:

1. capturar webcam
2. capturar screen
3. criar canvas final escuro
4. reduzir e centralizar dashboard no canvas
5. mapear landmarks para espaço final
6. gerar mask da mão no espaço final
7. aplicar efeito sobre canvas/dashboard
8. segmentar usuário
9. compor usuário em primeiro plano
10. aplicar overlays apenas se debug ativo
11. renderizar

---

## Anti-padrões proibidos

- webcam como PiP no canto
- dashboard ocupando frame inteiro
- skeleton ativo no modo final
- usuário invisível
- efeito solto longe da mão
- segmentação full-res todo frame
- lógica de apresentação dentro dos efeitos
- lógica de screen dentro de camera.py
- duplicar tracking
- criar arquitetura paralela

---

## Configurações esperadas em config.py

Devem existir parâmetros para:

- MODE
- SCREEN_MONITOR_INDEX
- SCREEN_TARGET_WIDTH
- SCREEN_TARGET_HEIGHT
- PRESENTATION_DASHBOARD_SCALE
- PRESENTATION_DASHBOARD_DIM
- PRESENTATION_DASHBOARD_GLOW
- PRESENTATION_USER_SCALE
- PRESENTATION_USER_POSITION
- PRESENTATION_ENABLE_SEGMENTATION
- PRESENTATION_SEG_INTERVAL
- PRESENTATION_SEG_SCALE
- PRESENTATION_MASK_FEATHER
- PRESENTATION_FLIP_LANDMARKS
- PRESENTATION_SHOW_SKELETON
- PRESENTATION_SHOW_FPS
- PRESENTATION_SHOW_EFFECT_NAME

Nenhum valor visual relevante deve ser hardcoded.

---

## PADRÕES DE CÓDIGO

- código limpo
- funções pequenas
- nomes claros
- sem duplicação
- alta coesão
- baixo acoplamento
- comentários apenas quando agregarem
- preferir correções locais em vez de grandes refatorações

---

## DOCUMENTAÇÃO

Não criar documentação excessiva.

Manter apenas:

- README.md
- CHANGELOG.md
- .github/copilot-instructions.md

Atualizar quando houver:

- mudança arquitetural
- bug crítico resolvido
- otimização relevante
- aprendizado importante

---

## REGRA FINAL

O TrackFX continua sendo um engine de VFX em tempo real baseado em tracking.

O Presentation Mode é apenas uma nova forma de renderizar esse engine sobre uma interface capturada.

Nunca tratar Presentation Mode como outro projeto.
Nunca quebrar o modo camera para corrigir o modo presentation.

---

# FLOATINGORBEFFECT — SPRINT ORB INTERACTION CONTROL

## Comportamento do orb

O FloatingOrbEffect é um objeto visual independente, não preso à palma.
Ele responde fisicamente ao movimento da mão com suavização e inércia.

| Estado da mão | Comportamento do orb |
|---|---|
| Parada | Estável no centro, idle motion suave |
| Movendo para direita | Rotação acelera no sentido horário |
| Movendo para esquerda | Rotação acelera no sentido anti-horário |
| Subindo | Orb expande levemente |
| Descendo | Orb contrai levemente |
| Movimento rápido | Glow, brilho e velocidade aumentam |
| Sem mão | Orb volta suavemente ao centro, idle mode |

## Arquitetura interna

Estado mínimo por frame (sem alocar objetos):

- `_orb_cx` / `_orb_cy` — posição suavizada via EMA
- `_rot_vel` — velocidade rotacional acumulada (deg/frame), com damping
- `_scale` — escala atual do raio (EMA, clampada)
- `_energy` — energia atual [0..1], EMA de speed + burst de accel

Fontes de dados (somente leitura de `motion.state`):

- `motion.state.cx / cy` → posição alvo do orb
- `motion.state.nx` → direção/sentido da rotação
- `motion.state.ny` → expansão/contração (ny<0 = sobe = expande)
- `motion.state.speed` → energia geral
- `motion.state.accel` → burst de energia em aceleração brusca
- `motion.state.active` → presença de mão (True/False)

## Parâmetros em config.py

```
# Posição / seguimento
FLOATING_ORB_FOLLOW_STRENGTH          # fração do offset transferido ao orb
FLOATING_ORB_POSITION_SMOOTHING       # EMA de posição (inércia)
FLOATING_ORB_MAX_OFFSET_X             # deslocamento horizontal máximo (px)
FLOATING_ORB_MAX_OFFSET_Y             # deslocamento vertical máximo (px)

# Rotação
FLOATING_ORB_MANUAL_ROTATION_STRENGTH # deg/frame por nx unitário
FLOATING_ORB_ROTATION_DAMPING         # decaimento da velocidade rotacional
FLOATING_ORB_IDLE_ROTATION_SPEED      # rotação base sem mão (deg/frame)

# Escala
FLOATING_ORB_VERTICAL_SCALE_STRENGTH  # influência de ny na escala
FLOATING_ORB_MIN_SCALE                # escala mínima
FLOATING_ORB_MAX_SCALE                # escala máxima

# Energia / glow
FLOATING_ORB_ENERGY_FROM_SPEED        # multiplicador speed→energia
FLOATING_ORB_ACCEL_BURST_STRENGTH     # burst de energia por aceleração
FLOATING_ORB_REACTIVITY               # multiplicador global de reatividade
FLOATING_ORB_GLOW                     # intensidade do bloom
FLOATING_ORB_GLOW_BLUR                # raio do blur do glow (px, ímpar)

# Visual base
FLOATING_ORB_RADIUS                   # raio base em pixels
FLOATING_ORB_ALPHA                    # opacidade global dos elementos
FLOATING_ORB_ROTATION_SPEED           # (legado, substituído por IDLE_ROTATION_SPEED)
FLOATING_ORB_PULSE_SPEED              # velocidade da pulsação (rad/frame)
FLOATING_ORB_COLOR                    # cor BGR base
FLOATING_ORB_ACCENT                   # cor BGR dos segmentos
```

## Regras de manutenção

- A posição base do orb é sempre `(w*0.5, h*0.5)` — o follow é um offset, não um replace
- O canvas do orb é ROI-only ao redor da posição atual (não full-frame)
- Realloca canvas apenas quando o tamanho da ROI muda (evento raro)
- Nunca usar PRES_ACTIVE_EFFECT = "orb" nem PRES_ACTIVE_EFFECT = "hud"
- NUNCA instanciar BodySegmenter dentro de FloatingOrbEffect

## Próximos upgrades possíveis (não implementar sem sprint)

- **Two-hand control**: distância entre mãos → scale do raio; centro entre mãos → posição
- **Pinch lock**: pinch ativo fixa posição do orb no espaço (pausa o follow)
- **Vibração controlada**: adicionar micro-jitter proporcional ao accel quando energy > 0.7
- **Modo orbital**: orb orbita ao redor da palma em vez de seguir o centro
- **Integração OSC**: enviar posição/energia do orb via OSC para TouchDesigner

---

# FLOATINGCUBEEFFECT — SPRINT FLOATINGCUBE

## Objetivo

Cubo wireframe holográfico flutuante. Visual limpo e futurista, sem objeto interno.
Controlado pelo indicador (rotação) e pinch (escala). Aparece apenas com mão aberta.

## Estrutura 3D

- 8 vértices em `[-SIZE, +SIZE]^3` (locais)
- 12 arestas (4 face traseira + 4 face frontal + 4 laterais)
- Rotação ZYX manual (sem engine 3D)
- Projeção pseudo-perspectiva manual: `px = cx + x * size * fov / (fov + z * size)`
- Arestas traseiras desenhadas com `FLOATING_CUBE_ACCENT_COLOR` e espessura 1
- Arestas frontais (`z_norm > 0.65`) com cor principal e espessura 2

## Comportamento

| Estado da mão | Comportamento |
|---|---|
| Sem mão | Fade out, posição retorna ao centro |
| Mão fechada | Fade out (idx_palm_dist < OPEN_HAND_THRESHOLD) |
| Mão aberta | Fade in, cubo aparece no centro |
| Mover indicador horizontalmente | Rotação Y |
| Mover indicador verticalmente | Rotação X |
| Pinch fechado | Cubo menor (MIN_SCALE) |
| Dedos abertos | Cubo maior (MAX_SCALE) |
| Movimento rápido | Glow aumenta (motion.state.speed → energia) |
| Duas mãos | Distância entre mãos influencia escala (TWO_HAND_SCALE) |

## Estado interno

| Variável | Função |
|---|---|
| `_rx / _ry / _rz` | Rotação acumulada por eixo (deg) |
| `_rvx / _rvy` | Velocidade rotacional acumulada (deg/frame), com damping |
| `_scale` | Escala atual do cubo |
| `_alpha` | Fade atual [0..1] |
| `_energy` | Energia atual [0..1], EMA de speed+accel |
| `_cube_cx / _cube_cy` | Posição suavizada do cubo |
| `_float_phase` | Fase da microflutuação orgânica |
| `_prev_idx` | Posição anterior do indicador (para delta) |
| `_prev_idx_tip` | Para detecção de troca de mão (reset de delta) |

## Parâmetros principais em config.py

```
FLOATING_CUBE_SIZE                  # half-extent do cubo (px)
FLOATING_CUBE_MIN_SCALE / MAX_SCALE # limites de escala
FLOATING_CUBE_ALPHA                 # opacidade global
FLOATING_CUBE_COLOR                 # arestas frontais (BGR)
FLOATING_CUBE_ACCENT_COLOR          # arestas traseiras (BGR)
FLOATING_CUBE_GLOW / GLOW_BLUR      # bloom
FLOATING_CUBE_IDLE_ROTATION_X/Y/Z   # auto-spin (deg/frame)
FLOATING_CUBE_FINGER_ROTATION_X/Y   # multiplicadores do delta do indicador
FLOATING_CUBE_ROTATION_SMOOTHING    # EMA do delta rotacional
FLOATING_CUBE_ROTATION_DAMPING      # decaimento da velocidade
FLOATING_CUBE_POSITION_SMOOTHING    # EMA de posição
FLOATING_CUBE_IDLE_X / IDLE_Y       # posição idle normalizada
FLOATING_CUBE_IDLE_DRIFT_AMP/SPEED  # flutuação orgânica
FLOATING_CUBE_DRIFT_STRENGTH        # drift suave em direção à mão
FLOATING_CUBE_OPEN_HAND_THRESHOLD   # limiar de distância indicador-palma
FLOATING_CUBE_FADE_SPEED            # velocidade de fade in/out
FLOATING_CUBE_PERSPECTIVE_FOV       # distância focal da projeção
FLOATING_CUBE_ENERGY_FROM_SPEED     # speed → energia
FLOATING_CUBE_ACCEL_BURST           # accel → burst de energia
FLOATING_CUBE_TWO_HAND_SCALE        # influência da distância entre mãos
```

## Teclas

- `c` / `C` → FloatingCube

## Regras de manutenção

- ROI ao redor dos vértices projetados (não full-frame)
- Canvas pré-alocado, realloca só quando tamanho muda
- `_get_hand_data` seleciona a mão cujo indicador está mais próximo do cubo
- Reset de `_prev_idx` quando indicador teletransportou > 60% do hand_size
- NUNCA usar HUDBehindEffect no Presentation Mode como PRES_ACTIVE_EFFECT

## Próximos upgrades possíveis para o Cube (não implementar sem sprint)

- **Pinch lock**: congelar rotação enquanto pinch ativo
- **Rotação Z**: tilt da mão (ângulo pulso→dedo médio) controla eixo Z
- **Face fill**: opção de preencher faces com alpha muito baixo
- **Explode**: cubo "estoura" em arestas separadas em burst de accel alto
- **Two-hand full**: centro entre mãos controla posição; distância controla escala
- **Integração OSC**: enviar rotação/escala/energia para TouchDesigner