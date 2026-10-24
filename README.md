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

## Analisar quadros (sem tremida)

Função parecida com o *LPC Frames Analyzer*, feita do zero (o `.exe` original não foi usado nem copiado). Ela recorta os
quadros **sem perder a posição**, para a animação não tremer quando o tamanho do quadro muda (como nos golpes de espada):

- **Compacto (recomendado):** cada quadro é recortado no menor retângulo e empacotado; o `.tres` usa a `margin` do
  `AtlasTexture`, então o Godot devolve cada quadro ao tamanho e posição originais, sem ajuste no jogo.
- **Caixa fixa:** todos os quadros (inclusive os oversize) viram a mesma caixa, centrada no centro original.
- Funciona com o personagem atual ou com **qualquer PNG** (folha padrão 832×3456 ou uma animação de 64/128/192 px).
- Salva em `<nome>_frames/`: um PNG por animação, `<nome>_analise.json` (caixas e deslocamentos de cada quadro),
  `<nome>_frames.tres` e, se marcado, os quadros soltos.

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
