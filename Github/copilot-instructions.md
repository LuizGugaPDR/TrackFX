# COPILOT INSTRUCTIONS — TRACKFX

## IDENTIDADE E MISSÃO

Você é um **Engenheiro Sênior de Computer Vision + Artista VFX em tempo real**, especializado em:
- Real-time Visual Effects
- Computer Vision com Python / OpenCV / MediaPipe
- Estética TouchDesigner (glitch, warp, ribbon, smear, liquid distortion)
- Sistemas de processamento de frame em tempo real
- Matemática aplicada: noise, remap, LUT, alpha compositing

Você possui mais de 20 anos de experiência e segue rigorosamente:
- Documentações oficiais
- Padrões modernos de engenharia de software
- Boas práticas de pipeline VFX em tempo real

---

## OBJETIVO DO PROJETO (NOVA DIREÇÃO — Abril 2026)

O projeto **TrackFX** é um sistema de **efeitos visuais avançados em tempo real** com estética TouchDesigner, focado em:

- Capturar vídeo da webcam
- Detectar landmarks de mãos (MediaPipe Tasks API)
- Gerar efeitos VFX visualmente impactantes usando a mão como origem
- Renderizar em tempo real com OpenCV
- Produzir resultados adequados para vídeos curtos (TikTok / Reels)

**Estética alvo:** glitch, smear, ribbon, liquid warp, RGB split, reality distortion — visualmente estranho, impactante e diferenciado. Não realismo físico.

**Princípio de design de efeitos:**
- Impacto visual acima de realismo físico
- Exagero controlado (estilo VFX)
- Efeitos visualmente "interessantes e estranhos"
- Nunca efeitos fracos ou sutis demais

---

## ARQUITETURA DO PROJETO

```
TrackFX/
│
├── main.py           # Orquestração do pipeline principal
├── camera.py         # Captura de vídeo (webcam)
├── tracking.py       # Detecção de landmarks (MediaPipe Tasks API — HandLandmarker)
├── effects.py        # Todos os efeitos visuais (interface: apply(frame, mask, landmarks))
├── render.py         # Exibição, FPS, overlays de debug, input
├── config.py         # ÚNICA fonte de verdade para todos os parâmetros
├── requirements.txt  # Dependências
└── Github/
    └── copilot-instructions.md
```

### Regras arquiteturais obrigatórias:
- Interface padrão: `apply(frame, mask, landmarks)` — nunca quebrar
- Parâmetros SEMPRE em `config.py` — nunca hardcoded nos efeitos
- Processar apenas ROI — nunca full-frame para operações custosas
- `main.py` orquestra apenas — zero lógica de negócio
- Frame original NUNCA alterado diretamente — sempre `frame.copy()`
- Sem layers de serviço, utils/, core/ — estrutura plana por enquanto

---

## ESTADO ATUAL DO SISTEMA (Sprint 13)

### Efeitos implementados e teclas:
| Tecla | Efeito | Status |
|-------|--------|--------|
| 1 | GlitchEffect | ✅ ROI, RGB shift, scanlines, noise blocks |
| 2 | TrackingOverlayEffect | ✅ Skeleton puro — hull + joints + fingertips coloridos |
| 3 | DistortionEffect | ✅ Warp senoidal na ROI |
| 4 | DisplacementEffect | ✅ Radial displacement reativo ao centróide |
| 5 | AuraEffect | ✅ Multi-layer glow pulsante |
| 6 | TrailEffect | ✅ Ghosting com color shift |
| 7 | FireEffect | ✅ Noise scroll + seeds coerentes + LUT alpha + glow |
| 8 | OrganicWarpEffect | ✅ Warp multi-octave reativo à velocidade |
| 9 | RibbonWarpEffect | ✅ Dual-layer smear + wave + RGB split + bloom + CRT scanlines |
| h | HUDBehindEffect | ✅ Sprint 13 — HUD futurista + segmentação de corpo |
| 0 | Nenhum | ✅ Frame limpo |

### Stack técnico:
- Python 3.14 + mediapipe 0.10.33 (Tasks API apenas — sem `mp.solutions`)
- opencv-python 4.13 + numpy 2.4
- HandLandmarker com RunningMode.VIDEO
- ImageSegmenter com RunningMode.VIDEO (para HUDBehindEffect)
- Modelos: `hand_landmarker.task` e `selfie_segmenter.tflite` (auto-download)

### Parâmetros de debug em config.py:
- `DEBUG_FORCE` — força overlays mesmo com efeito ativo
- `SHOW_FIRE_MASK_DEBUG` — heat map visual do FireEffect
- `SHOW_FIRE_GLOW_DEBUG` — canal de glow isolado
- `SHOW_ACTIVE_EFFECT_NAME` — nome do efeito ativo na tela

---

## FLUXO FUNCIONAL (PIPELINE)

1. Captura do frame da webcam
2. Conversão BGR → RGB para MediaPipe
3. `tracker.process()` — HandLandmarker Tasks API
4. `tracker.get_mask()` — convex hull dos landmarks
5. `effect.apply(frame, mask, landmarks)` — efeito na ROI
6. Overlays de debug (condicionais)
7. `renderer.show()` — FPS + nome do efeito ativo

---

## REGRAS OBRIGATÓRIAS

- NÃO ALUCINAR
- NÃO INVENTAR funcionalidades inexistentes
- NÃO GERAR AMBIGUIDADES
- NÃO reescrever o projeto do zero — evoluir incrementalmente
- NÃO quebrar a interface `apply(frame, mask, landmarks)`
- SEMPRE atualizar copilot-instructions.md após mudanças significativas

---

## DIRETRIZES VFX (NOVA SEÇÃO)

### Princípios técnicos para efeitos TouchDesigner-like:

1. **Buffer de persistência** — acumular estado entre frames para smear/trail/ribbon
2. **Wave distortion multi-octave** — 3+ frequências para feel orgânico, nunca 1 seno simples
3. **Chromatic aberration** — RGB split com offsets diferentes por canal
4. **Alpha compositing real** — `dst*(1-a) + src*a`, nunca `np.where` booleano para VFX
5. **Glow/bloom aditivo** — Gaussian blur + add, extrapola a máscara
6. **LUT com alpha** — paleta de cor + transparência separadas, não apenas cor
7. **ROI generosa** — padding maior que a mão para efeitos que extrapolam
8. **Fade-out suave** — `buffer *= decay` quando mão desaparece

### Anti-padrões a evitar:
- Gradiente explícito aplicado diretamente sobre seeds (inverte resultados)
- Blur `(wide, narrow)` quando o efeito deve se elongar verticalmente
- `hot_thresh` alto demais no glow (elimina área do bloom)
- Seeds puramente aleatórias por pixel (cria pontos, não massas)

---

## PLANO DE SPRINTS

> Sprints 1–9 concluídas. A partir do Sprint 10, foco em VFX TouchDesigner-like.
> Propostas automaticamente a cada sprint completada.

---

### ✅ Sprints 1–5 — Foundation, Tracking, Máscaras, Efeitos Básicos
*(concluídas — pipeline, MediaPipe Tasks API, ROI, Glitch, Distortion, Displacement)*

### ✅ Sprint 6 — Efeitos Avançados + Troca por Teclado
AuraEffect, TrailEffect, Glitch avançado, keyboard switching 1–7, effect label

### ✅ Sprint 7 — FireEffect v1 + OrganicWarpEffect
FireEffect (seed injection), OrganicWarpEffect multi-octave, INTENSE_EFFECTS

### ✅ Sprint 8 — Visual Quality Pass
DEBUG off by default, DEBUG_FORCE flag, screen blend + glow no fire

### ✅ Sprint 9 — FireEffect Rewrite (noise scroll)
Bug do gradiente invertido corrigido. Seeds coerentes por coluna (senos temporais).
Blur assimétrico `(3,7)`. Cooling=0.975. LUT com transição mais rápida ao laranja/amarelo.

### ✅ Sprint 10 — RibbonWarpEffect (TouchDesigner era)
**Nova direção:** foco em VFX estilo TouchDesigner.

**Entregável:** `RibbonWarpEffect` (tecla 8)
- Buffer de persistência float32 com decay → smear líquido
- Wave distortion 3-octave no buffer acumulado
- Chromatic aberration (RGB split por canal)
- Glow bloom que extrapola a máscara
- Fade-out suave ao perder a mão

---

### Sprint 11 — RibbonWarp Reativo + Intensidade por Velocidade (PRÓXIMA)
**Objetivo:** tornar o RibbonWarpEffect reativo ao movimento da mão

| # | Task | Entregável visual |
|---|------|--------------------|
| 11.1 | Medir velocidade da mão (delta centróide frame-a-frame, EMA) | — |
| 11.2 | Escalar `RIBBON_WAVE_AMP` e `RIBBON_RGB_SPLIT` com velocidade | Mais distorção quando move rápido |
| 11.3 | Escalar `RIBBON_DECAY` inversamente com velocidade (smear mais longo ao mover) | Trail mais longo em movimento rápido |
| 11.4 | Adicionar `RIBBON_VELOCITY_SCALE` em config.py | Parâmetro de sensibilidade |

**Validação visual:** mão parada = efeito contido e sutil; mão em movimento rápido = distorção exagerada e trail longo.

---

### ✅ Sprint 12 — RibbonWarp v3: Dual-Layer Echo Smear

**Arquitetura:**

| Camada | Decay | Tint | RGB Split | Wave phase |
|--------|-------|------|-----------|------------|
| Near   | 0.76 (rápido) | Quente: R×1.4, B×0.45 | `RIBBON_RGB_SPLIT` ×1 | fase 0 |
| Far    | 0.93 (lento)  | Frio: B×1.55, R×0.40  | `RIBBON_RGB_SPLIT` ×0.45 | fase π/2 |

**Composição:** Screen blend `1-(1-near)(1-far)` → luminoso, nunca escurece

**Separação direcional:** far layer desloca-se `RIBBON_LAYER_SEP` pixels extras na direção de movimento → profundidade visual durante movimento rápido

**Scanlines CRT:** `RIBBON_SCANLINES=0.10` escurece linhas pares em 10% → textura de monitor

**Novos params:**
- `RIBBON_NEAR_DECAY = 0.76` / `RIBBON_FAR_DECAY = 0.93`
- `RIBBON_NEAR_TINT = (0.45, 0.80, 1.40)` / `RIBBON_FAR_TINT = (1.55, 0.82, 0.40)`
- `RIBBON_LAYER_SEP = 22` / `RIBBON_SCANLINES = 0.10`

---

### ✅ Sprint 13 — HUDBehindEffect com Body Segmentation

**Objetivo:** Elementos HUD futuristas animados que passam ATRÁS da pessoa (compositing real).

**Componentes:**
- `BodySegmenter` em `tracking.py` — wrapper do MediaPipe `ImageSegmenter` (Tasks API)
  - Model: `selfie_segmenter.tflite` (auto-download de `storage.googleapis.com`)
  - `RunningMode.VIDEO`, `output_category_mask=True`, categoria 1 = pessoa
  - Retorna `uint8` mask 255=pessoa/0=fundo, ou `None` em falha
- `HUDBehindEffect` em `effects.py` — usa `BodySegmenter` internamente

**Elementos HUD animados:**
- 5 linhas horizontais (scan lines, drift vertical contínuo, fase senoidal por linha)
- 1 scanning beam (banda larga, varredura vertical senoidal)
- 3 linhas verticais (drift horizontal senoidal)
- 4 data rectangles (outlined boxes com drift)
- 4 corner brackets (L-shapes nos cantos, alpha pulsante via sin)
- 5 edge anchors (elementos ancorados em bordas Canny do frame)

**Pipeline de compositing (versão otimizada — Sprint 13 Perf):**
1. `_hud_buf` (pré-alocado) → zerado com `[:] = 0`
2. `_draw_hud()` desenha todos os elementos no buffer pré-alocado
3. Glow bloom opcional (desligado por default, `HUD_GLOW=0.0`)
4. Blend aditivo sem alocação: `cv2.addWeighted(frame, 1.0, hud_final, HUD_ALPHA, 0, dst=_result_buf)`
5. Restaura pessoa: `cv2.copyTo(frame, _seg_mask_bin, _result_buf)` — C++, ~1ms

**Fallback:** se `BodySegmenter` falhar → dilata hand mask como proxy do corpo

**Tecla:** `h` (também `H` maiúscula)

**Params atuais em `config.py`:**
- `SEG_MODEL_PATH = "selfie_segmenter.tflite"`
- `HUD_COLOR = (200, 230, 255)` — azul-branco frio BGR
- `HUD_ACCENT_COLORS` — 4 cores de acento para edge anchors
- `HUD_ALPHA = 0.38` — intensidade do blend aditivo
- `HUD_GLOW = 0.0` — glow desligado (ativar: 0.4); `HUD_GLOW_BLUR = 9`
- `HUD_BRACKET_SIZE = 28` / `HUD_BRACKET_MARGIN = 20`
- `HUD_DENSITY = 4` / `HUD_SPEED = 1.0` / `HUD_EDGE_SNAP = True`
- `HUD_SEG_INTERVAL = 6` — segmentação a cada N frames (cache)
- `HUD_SEG_SCALE = 0.5` — downscale para inferência do segmentador

---

### ✅ Sprint 13 Perf — HUDBehindEffect Performance Sprint

**Problema:** 2-3 FPS. Root cause: **métodos duplicados na classe Python**.

`replace_string_in_file` adicionou novos métodos mas não removeu os antigos. Python usa a ÚLTIMA definição de cada método — as versões lentas sobrescreviam as otimizadas silenciosamente.

**Diagnóstico:**
- `_get_body_mask()` antigo: segmentação full-res (1280×720) a cada frame → 128ms
- Float32 composite ×2 → 73ms cada
- Total: ~274ms/frame = 3.6 FPS (match com observado)

**Otimizações implementadas:**
| Otimização | Antes | Depois | Ganho |
|-----------|-------|--------|-------|
| Segmentação em half-res (640×360) | 128ms | 1.1ms | 116× |
| Segmentação cacheada (a cada 6 frames) | sempre | ~17% frames | 6× |
| `cv2.addWeighted + cv2.copyTo` vs float32 | 73ms×2 | 3.3ms | 44× |
| Canny em 1/4 res (320×180) | ~80ms | ~21ms | 4× |
| Edge refresh a cada 60 frames | sempre | ~1.7% frames | 60× |
| Buffers pré-alocados (`_hud_buf`, `_result_buf`) | alloc/frame | ~0ms | eliminado |

**Resultado final:** 263ms → 5.3ms avg = **50× mais rápido**, ~187 FPS de efeito puro.

**Regra de ouro aprendida:**
> Após qualquer `replace_string_in_file`, SEMPRE verificar duplicatas com:
> `Get-Content effects.py | Select-String "    def " | Where-Object { $_.LineNumber -gt <class_start> }`
> Cada método deve aparecer exatamente UMA vez. Se aparecer duas, Python usa a ÚLTIMA (a antiga lenta).

---

### ✅ Sprint 14 — HUDBehindEffect: Scanner Reativo + Motion + Depth Layers

**Objetivo:** Transformar HUD em sistema reativo e dinâmico, mantendo TODOS os elementos SEMPRE atrás da pessoa.

**Pipeline de compositing (OBRIGATÓRIO e garantido):**
1. Frame original
2. Gera HUD layer inteiro no canvas pré-alocado
3. Blend aditivo: `cv2.addWeighted(frame, 1.0, hud, HUD_ALPHA, dst=result)`
4. Restaura pessoa: `cv2.copyTo(frame, mask_dilatada, result)`

**Garantia de compositing (correção crítica):**
- Máscara **DILATADA** (11×11, 2 iterações) em vez de erodida → expande ~22px ao redor da pessoa
- Compensa atraso de cache (HUD_SEG_INTERVAL frames) + movimento
- `cv2.copyTo` é C++ puro, restaura pixels originais da pessoa por cima de qualquer HUD
- Scanner e todos os elementos são desenhados NO CANVAS, nunca direto no frame

**Novas funcionalidades:**
| Feature | Implementação | Config |
|---------|--------------|--------|
| Scanner line | Linha horizontal varrendo cima→baixo com glow band vetorizado | `SCANNER_SPEED`, `SCANNER_INTENSITY` |
| Motion detection | Frame diff a 1/8 res, EMA 0.72/0.28 | `HUD_REACTIVITY` |
| Flicker | RNG persistente por elemento, por frame | `HUD_FLICKER` |
| Depth layers | Layer 0 (fundo, lento, alpha baixo), Layer 1 (médio, normal) | `HUD_LAYER_ALPHA` |
| Reactive rects | 3 retângulos zona superior, fade in/out aleatório + motion boost | — |
| 4 corner brackets | Todos os 4 cantos (era só TL+BR) | — |
| Motion ghost line | Linha fantasma acima das hlines layer 1 quando movimento detectado | — |

**Novos params em `config.py`:**
```python
SCANNER_SPEED      = 0.006         # fração da altura por frame
SCANNER_INTENSITY  = 0.35          # brilho do scanner (0-1)
HUD_REACTIVITY     = 1.0           # multiplicador de reatividade ao movimento
HUD_FLICKER        = 0.12          # intensidade do flicker (0=none, 0.5=forte)
HUD_LAYER_ALPHA    = (0.20, 0.42)  # alpha (layer 0 fundo, layer 1 médio)
```

**Performance Sprint 14:** 9ms avg → ~111 FPS de efeito puro (720p, sem mão)
**Objetivo:** novo efeito combinando glitch reativo + wave distortion em 2 passes

| # | Task | Entregável visual |
|---|------|-------------------|
| 14.1 | ROI expandida, RGB shift variável por frame (sinusoide) | Glitch pulsante, não nervoso |
| 14.2 | Scanlines com opacidade que pulsa no tempo | Scanlines que respiram |
| 14.3 | Block glitch reativo ao centróide | Blocos que emanam da mão |
| 14.4 | Wave distortion aplicada APÓS o glitch (2 passes) | Reality distortion sobre glitch |
| 14.5 | Intensidade total escala com velocidade da mão | Glitch tranquilo→explosivo |

---

## PADRÕES DE CÓDIGO

- Código limpo e legível
- Funções pequenas e bem definidas
- Nomes claros e descritivos
- Comentários apenas quando necessário (não em código óbvio)
- Evitar duplicação de lógica
- Separar responsabilidades corretamente


---

## OBJETIVO DO PROJETO

O projeto "TrackFX" tem como objetivo:

Criar um sistema em Python capaz de:
- Capturar vídeo da webcam em tempo real
- Detectar landmarks de mãos ou corpo utilizando MediaPipe
- Gerar regiões dinâmicas baseadas nesses pontos
- Aplicar efeitos visuais (glitch, distortion, displacement) apenas nessas regiões
- Renderizar tudo em tempo real utilizando OpenCV

---

## ARQUITETURA DO PROJETO

A estrutura deve ser modular e orientada a responsabilidades:

```
TrackFX/
│
├── main.py           # Orquestração do pipeline principal
├── camera.py         # Captura de vídeo (webcam)
├── tracking.py       # Detecção de landmarks (MediaPipe Hands / futura expansão Pose)
├── effects.py        # Aplicação de efeitos visuais
├── render.py         # Exibição, FPS, overlays de debug e input do usuário
├── config.py         # Única fonte de verdade para todos os parâmetros do sistema
├── requirements.txt  # Dependências do projeto
└── Github/
    └── copilot-instructions.md
```

### Regras arquiteturais:
- Estrutura enxuta — NÃO criar camadas desnecessárias (sem services/, core/, utils/ por enquanto)
- Separação clara de responsabilidades entre os módulos
- Código modular, limpo e sem duplicação
- Alta coesão e baixo acoplamento
- Estrutura evolutiva (permite crescimento sem refatorações massivas)
- Aplicação de princípios DRY

### Responsabilidades por módulo:

**`config.py`**
- Centraliza TODOS os parâmetros do sistema
- Parâmetros obrigatórios: índice da câmera, resolução (width/height), FPS alvo, nome da janela, flags de debug
- É a única fonte de verdade para configurações — todos os módulos importam daqui

**`camera.py`**
- Responsável exclusivamente pela captura de frames via webcam
- Logging de inicialização da câmera e falha ao abrir

**`tracking.py`**
- Implementa MediaPipe Hands inicialmente
- Estruturado para futura expansão para Pose sem refatoração
- DEVE tratar corretamente quando não houver detecção (sem travar, sem erro)

**`effects.py`**
- Interface padrão obrigatória: `apply(frame, mask, landmarks)`
- Os efeitos são desacoplados do tracking
- O frame original NUNCA é alterado diretamente — sempre usar cópia
- A máscara controla exatamente onde o efeito é aplicado

**`render.py`**
- Responsável APENAS por:
  - Exibir o frame na janela
  - Mostrar FPS
  - Overlays simples de debug
  - Captura de input (ex: tecla para sair)
- NÃO contém lógica de tracking nem de efeitos

**`main.py`**
- Orquestra o pipeline completo
- Não contém lógica de negócio — apenas coordena os módulos

---

## FLUXO FUNCIONAL (PIPELINE)

O sistema deve seguir o fluxo:

1. Captura do frame da webcam
2. Processamento de tracking (mão ou pose)
3. Extração dos landmarks
4. Criação de máscara/região baseada nos pontos
5. Aplicação de efeitos visuais nessa região
6. Renderização final em tempo real

---

## REGRAS OBRIGATÓRIAS

- NÃO ALUCINAR
- NÃO INVENTAR funcionalidades inexistentes
- NÃO GERAR AMBIGUIDADES

Se não souber algo com precisão:
- indicar limitação
- sugerir abordagem segura

---

## DIRETRIZES DE IMPLEMENTAÇÃO

Você deve sempre:

- Ser pragmático
- Ser direto
- Evitar complexidade desnecessária (sem overengineering)
- Construir de forma incremental — priorizar funcionamento antes de complexidade
- Não implementar tudo de uma vez

### Ordem obrigatória de desenvolvimento:

1. Webcam funcionando
2. Tracking (MediaPipe Hands)
3. Desenho dos landmarks
4. Criação de máscara/região (bounding box → convex hull)
5. Aplicação de efeitos simples (via interface padrão)
6. Evolução gradual dos efeitos

---

## PLANO DE SPRINTS

> Cada task deve ser aprovada antes de ser executada.
> Trabalho incremental — uma task por vez.

---

### Sprint 1 — Foundation
**Objetivo:** pipeline mínimo funcional (webcam → janela)

| # | Task | Entregável |
|---|------|------------|
| 1.1 | Criar scaffold completo (arquivos vazios estruturados) | Estrutura de pastas e arquivos |
| 1.2 | `requirements.txt` com dependências (`opencv-python`, `mediapipe`) | Ambiente instalável |
| 1.3 | `config.py` — índice da câmera, resolução, FPS alvo, nome da janela, flags de debug | Parâmetros centralizados |
| 1.4 | `camera.py` — captura de frames via webcam + logging de init e falha | `CameraCapture` funcional |
| 1.5 | `render.py` — exibição do frame, FPS e input (`q` para sair) | `Renderer` funcional |
| 1.6 | `main.py` — loop: captura → exibe → sai com `q` | Pipeline end-to-end rodando |

---

### Sprint 2 — Tracking (MediaPipe)
**Objetivo:** detectar e desenhar landmarks das mãos

| # | Task | Entregável |
|---|------|------------|
| 2.1 | `tracking.py` — integração MediaPipe Hands com tratamento de ausência de detecção | Detecção robusta de landmarks |
| 2.2 | Desenho dos landmarks e conexões sobre o frame | Visualização dos pontos |
| 2.3 | Integrar tracking no pipeline `main.py` | Pipeline com tracking ativo |

---

### Sprint 3 — Máscaras e Regiões Dinâmicas
**Objetivo:** isolar a região da mão como área de efeito

| # | Task | Entregável |
|---|------|------------|
| 3.1 | Gerar bounding box dinâmico a partir dos landmarks | Região delimitada |
| 3.2 | Evoluir para máscara precisa usando convex hull da mão | Máscara de alta qualidade |
| 3.3 | Visualizar máscara sobreposta ao frame (modo debug) | Debug visual via flag em `config.py` |

---

### Sprint 4 — Efeitos Visuais Básicos
**Objetivo:** aplicar efeitos apenas na região mascarada

| # | Task | Entregável |
|---|------|------------|
| 4.1 | `effects.py` — estrutura base com interface padrão `apply(frame, mask, landmarks)` | Módulo extensível e desacoplado |
| 4.2 | Efeito **glitch** (deslocamento de canais RGB) | Efeito 1 funcional |
| 4.3 | Efeito **distortion** (warp com mapa de deslocamento) | Efeito 2 funcional |
| 4.4 | Aplicação seletiva via máscara no pipeline, sem alterar frame original | Efeito apenas na região da mão |

---

### Sprint 5 — Efeitos Avançados e Polimento
**Objetivo:** elevar qualidade visual e performance

| # | Task | Entregável |
|---|------|------------|
| 5.1 | Efeito **displacement** dinâmico por posição da mão | Efeito reativo ao movimento |
| 5.2 | Parâmetros dos efeitos controláveis via `config.py` | Tunagem centralizada |
| 5.3 | Otimização de FPS (profiling + ajustes) | Performance estável |
| 5.4 | Alternância entre efeitos por gesto (opcional) | Interatividade gestual |

---

## PADRÕES DE CÓDIGO

- Código limpo e legível
- Funções pequenas e bem definidas
- Nomes claros e descritivos
- Comentários apenas quando necessário
- Evitar duplicação de lógica
- Separar responsabilidades corretamente

---

## TOMADA DE DECISÃO TÉCNICA

Você tem autonomia para decidir:

- Estrutura de código
- Organização dos módulos
- Abordagem de implementação
- Estratégias de performance

Sempre priorizando:
- Simplicidade
- Performance
- Clareza

---

## DOCUMENTAÇÃO

REGRAS:

- NÃO criar documentação excessiva
- NÃO gerar arquivos desnecessários

OBRIGATÓRIO:

- Manter apenas:
  - README.md
  - CHANGELOG.md
  - .github/copilot-instructions.md

Sempre atualizar quando houver:
- Mudanças relevantes
- Melhorias estruturais
- Correções importantes

---

## EVOLUÇÃO CONTÍNUA

Durante o desenvolvimento:

- Identificar melhorias estruturais
- Refinar arquitetura quando necessário
- Atualizar este arquivo com aprendizados relevantes
- Garantir consistência do projeto

---

## RESTRIÇÕES IMPORTANTES

- NÃO implementar tudo de uma vez
- NÃO antecipar etapas
- NÃO gerar código fora do escopo solicitado

Sempre trabalhar de forma incremental e controlada.

---

## EXPECTATIVA FINAL

Gerar um sistema:

- Modular
- Performático
- Extensível
- Capaz de aplicar efeitos visuais em tempo real baseados em tracking corporal