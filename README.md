# LPC Sprite Gerador

Aplicativo para Windows (um `.exe`, sem instalar nada) que automatiza o
[Universal LPC Spritesheet Character Generator](https://github.com/LiberatedPixelCup/Universal-LPC-Spritesheet-Character-Generator):
monte personagens **vistos de cima (estilo RPG/Zelda/Stardew)** e salve as sprite sheets na **pasta que você escolher**,
prontas para o Godot.

## Como usar

1. Baixe `LPCSpriteGerador.exe` na página de [Releases](../../releases) e dê dois cliques.
2. Na primeira vez, escolha **onde guardar a arte** (o banco de dados do LPC, ~400 MB, baixado uma vez; vira uma subpasta "LPC Arte") e **onde salvar os sprites** que você exportar, e clique em **Baixar a arte**. Os dois locais podem ser mudados depois em **Configurações** (a arte é movida para o novo lugar).
3. Escolha o corpo, as peças e as cores (a prévia anima andando, correndo, golpeando…).
4. Em **Salvar**, clique em **Escolher pasta…** (por exemplo, dentro do seu projeto Godot) e em **Salvar sprite sheet**.

Também tem **🎲 Sortear** e **Lote de NPCs aleatórios** (ex.: 50 NPCs de uma vez), e **Abrir personagem (.json)** para
continuar um personagem salvo.

## Versão HD "cel shade" (experimental)

Amplia a pixel art (2×, 3× ou 4×) com bordas suaves e redondas, **contorno de tinta**, linhas internas, cores um pouco
mais vivas e, se quiser, menos bandas de sombra. É um efeito automático, sem IA: usa o algoritmo Scale2x/EPX (não inventa
cores), suavização e contorno. Marque **Ver prévia HD** para ver animado e **Salvar também a versão HD** para gerar
`<nome>_hd.png`, as folhas extras `_hd` e o `<nome>_hd.tres` (com os quadros já na escala certa). Os arquivos originais
não mudam. Em quadros muito pequenos o contorno pode "engolir" detalhes finos (olhos); ajuste Suavizar/Contorno.

## Skin a partir de uma imagem (experimental)

Sobe uma imagem de personagem (corpo inteiro, de frente, fundo liso/transparente). O app sugere as cores de **pele, cabelo,
camisa, calça e sapatos**; você ajusta e clica em **Aplicar ao personagem**. As cores livres viram uma paleta de 6 tons
(sombra → luz) sobre as peças do LPC, então funcionam em todas as animações e direções. Camisa e calça aceitam
**estampas** (listras, diagonal, xadrez, bolinhas, camuflagem) que mantêm a sombra do LPC.
Limites: as cores são estimadas por faixas do corpo e erram em personagens estilizados/chibi; a estampa é fixa no
quadro (não "gruda" no tecido durante o movimento). Qualquer peça também aceita **cor livre** pelo seletor ao lado
da cor. Não redesenha a roupa nem o rosto da imagem.

## Analisar quadros (sem tremida)

Função parecida com o *LPC Frames Analyzer*, feita do zero (o `.exe` original não foi usado nem copiado). Ela recorta os
quadros **sem perder a posição**, para a animação não tremer quando o tamanho do quadro muda (como nos golpes de espada):

- **Compacto (recomendado):** cada quadro é recortado no menor retângulo e empacotado; o `.tres` usa a `margin` do
  `AtlasTexture`, então o Godot devolve cada quadro ao tamanho e posição originais, sem ajuste no jogo.
- **Caixa fixa:** todos os quadros (inclusive os oversize) viram a mesma caixa, centrada no centro original.
- Funciona com o personagem atual ou com **qualquer PNG** (folha padrão 832×3456 ou uma animação de 64/128/192 px).
- Salva em `<nome>_frames/`: um PNG por animação, `<nome>_analise.json` (caixas e deslocamentos de cada quadro),
  `<nome>_frames.tres` e, se marcado, os quadros soltos.

## Analisar quadros (sem tremida)

Inspirado no [LPC Frames Analyzer](https://github.com/matheoheo/LPCFramesAnalyzer) (MIT), de matheoheo; o código aqui
é próprio. Ele recorta os quadros **sem perder a posição**, inclusive os de arma grande (oversize), para a animação não
tremer quando o tamanho do quadro muda (como nos golpes de espada):

- **Compacto (recomendado):** cada quadro é recortado no menor retângulo e empacotado; o `.tres` usa a `margin` do
  `AtlasTexture`, então o Godot devolve cada quadro ao tamanho e posição originais, sem ajuste no jogo.
- **Caixa fixa:** todos os quadros viram a mesma caixa, centrada no centro original.
- Para o **personagem atual** o app já conhece cada quadro (não precisa "adivinhar" por varredura). Também analisa
  **um PNG** ou **uma pasta de PNGs** (folha padrão 832×3456, folha com área extra empilhada embaixo, ou uma animação de
  64/128/192 px).
- Salva em `<nome>_frames/`: um PNG por animação, `<nome>_frames.tres` (Godot), `<nome>_analise.json` (completo) e
  `<nome>_lpcanalyzer.json` no formato do LPC Frames Analyzer (`animations[] → name, dir, frames[] → rect, offset`;
  o `offset` é a posição do recorte em relação ao canto da célula padrão 64×64, então o personagem fica ancorado).
- Não gera o formato `.matt`.

## O que é salvo (em `<pasta escolhida>/<nome>/`)

| Arquivo | Para quê |
| --- | --- |
| `<nome>.png` | Folha completa 832×3456 (quadros de 64×64, mesmo layout do gerador original) |
| `animacoes/*.png` | Uma PNG por animação (andar, correr, golpe, parado…) |
| `previas/*.gif` | GIFs com as 4 direções (para conferir) |
| `<nome>_slash_oversize.png` etc. | Folhas extras das armas/ferramentas com golpes grandes (quadros de 128/192 px) |
| `<nome>.tres` | `SpriteFrames` do Godot 4 (`walk_down`, `idle_left`…); se a pasta estiver dentro de um projeto (`project.godot`) o caminho `res://` é calculado sozinho |
| `<nome>.json` | O personagem (abra de novo no app) |
| `CREDITOS.csv` / `CREDITOS.txt` | Autores e licenças das peças usadas |

No lote, tudo vai achatado numa pasta `<prefixo>_lote/`.

## Importante: licenças da arte

O código deste app é GPL-3.0. A **arte** do LPC pertence aos seus autores e cada peça tem licença própria
(CC0, CC-BY, CC-BY-SA, OGA-BY ou GPL). Para **uso privado entre amigos** não há problema; se o jogo for
distribuído/vendido um dia, mantenha os créditos (`CREDITOS.csv`) e confira as licenças (algumas são incompatíveis
com lojas como a Steam/mobile). A arte não vem dentro do `.exe`: ela é baixada do repositório oficial.

## Limitações da versão 0.1

- Armas com golpe grande (espada, maça, cajado…) usam a animação **extra** (ex.: `slash_oversize`, quadros de 192 px),
  salva como `<nome>_slash_oversize.png`; nas animações normais (64 px) o gerador original também não desenha essas armas.
- Só as peças e animações padrão do gerador (não faz o modo de sprites customizados/importados).
- Windows: usa o Edge/Chrome para abrir a janela do app (o Edge já vem no Windows).

## Desinstalar

Em **Configurações → Remover arte e configurações**, ou `LPCSpriteGerador.exe --uninstall`.
Seus sprites gerados nunca são apagados. Depois, apague o `.exe`.

## Rodar pelo código

```
pip install pillow numpy
python lpcgen/launch.py
python -m unittest discover -s tests
```
