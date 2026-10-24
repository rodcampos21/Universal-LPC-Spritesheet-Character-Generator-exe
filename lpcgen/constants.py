FRAME = 64
SHEET_W = 832
SHEET_H = 3456
DIRECTIONS = ["up", "left", "down", "right"]            # ordem das linhas na folha LPC
DIR_PT = {"up": "cima", "left": "esquerda", "down": "baixo", "right": "direita"}
BODY_TYPES = ["male", "female", "teen", "child", "muscular", "pregnant"]
BODY_PT = {"male": "Masculino", "female": "Feminino", "teen": "Adolescente", "child": "Criança",
           "muscular": "Musculoso", "pregnant": "Grávida"}

# nome na definição -> (pasta/arquivo, exportável)
ANIM_FOLDER = {"watering": "thrust", "combat": "combat_idle", "1h_slash": "backslash", "1h_backslash": "backslash",
               "1h_halfslash": "halfslash"}
NO_EXPORT = set()
DEFAULT_ANIMS = ["spellcast", "thrust", "walk", "slash", "shoot", "hurt", "watering"]

# pasta -> (y em linhas, linhas, quadros por linha)
ANIMS = {
    "spellcast": (0, 4, 7), "thrust": (4, 4, 8), "walk": (8, 4, 9), "slash": (12, 4, 6),
    "shoot": (16, 4, 13), "hurt": (20, 1, 6), "climb": (21, 1, 6), "idle": (22, 4, 2),
    "jump": (26, 4, 5), "sit": (30, 4, 3), "emote": (34, 4, 3), "run": (38, 4, 8),
    "combat_idle": (42, 4, 2), "backslash": (46, 4, 13), "halfslash": (50, 4, 6),
}
# ciclo de quadros usado na prévia (mesmo do gerador original)
CYCLES = {
    "spellcast": [0, 1, 2, 3, 4, 5, 6], "thrust": [0, 1, 2, 3, 4, 5, 6, 7],
    "walk": [1, 2, 3, 4, 5, 6, 7, 8], "slash": [0, 1, 2, 3, 4, 5],
    "shoot": list(range(13)), "hurt": [0, 1, 2, 3, 4, 5], "climb": [0, 1, 2, 3, 4, 5],
    "idle": [0, 0, 1], "jump": [0, 1, 2, 3, 4, 1], "sit": [0, 1, 2], "emote": [0, 1, 2],
    "run": list(range(8)), "combat_idle": [0, 0, 1], "backslash": [0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12],
    "halfslash": [0, 1, 2, 3, 4, 5],
}
FPS = {"walk": 10, "run": 12, "idle": 3, "combat_idle": 3, "sit": 3, "emote": 3}
ANIM_PT = {"spellcast": "Magia", "thrust": "Estocada", "walk": "Andar", "slash": "Golpe", "shoot": "Arco",
           "hurt": "Dano", "climb": "Escalar", "idle": "Parado", "jump": "Pulo", "sit": "Sentar",
           "emote": "Emoção", "run": "Correr", "combat_idle": "Posição de combate",
           "backslash": "Golpe 1 mão", "halfslash": "Meio golpe"}
UPSTREAM_ZIP = ("https://codeload.github.com/LiberatedPixelCup/"
                "Universal-LPC-Spritesheet-Character-Generator/zip/refs/heads/master")
