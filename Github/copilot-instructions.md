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