"""
Equipe Crew Olympus — Sistema Inteligente de Monitoramento da Missão
==============================================================

Global Solution 2026 · FIAP · Ciência da Computação

Equipe Crew Olympus:
    Gabriel Tavares Martins de Oliveira  · RM573718
    Lucas Araujo de Carvalho             · RM571060
    Matheus Henrique Pedrozo Traiba      · RM571817
    Miguel Monteiro Moreira              · RM572904
    Pedro Henrique de Lima Costa         · RM573008

Visão geral
-----------
Sistema que carrega telemetria de uma missão espacial a partir de um arquivo
CSV, classifica a situação operacional, gera alertas e produz uma previsão
de consumo via regressão linear. A interface gráfica usa apenas a biblioteca
padrão do Python (tkinter), sem dependências externas. Alguns de nós já 
trabalharam com essa biblioteca em projetos a parte, por isso decidimos
utilizá-la.

Estruturas de dados empregadas
------------------------------
    Dicionário (tabela hash)   → acesso O(1) aos módulos pelo nome
    Lista                      → série temporal das leituras de energia
    Matriz (lista de listas)   → leituras cruzadas horário × variável
    Fila (deque, FIFO)         → alertas pendentes em ordem de chegada
    Pilha (list, LIFO)         → histórico dos eventos para auditoria reversa
    Hierarquia (dict aninhado) → missão → sistemas → módulos → atributos

Técnica de previsão
-------------------
Regressão linear simples pelo método dos mínimos quadrados.

    a = (n · Σxy − Σx · Σy) / (n · Σx² − (Σx)²)
    b = (Σy − a · Σx) / n
    y_previsto = a · x + b

Expressão booleana principal do diagnóstico
-------------------------------------------
    CRÍTICO = (reserva < 35 AND comunicação == 0)
              OR (radiação == "muito_alta" AND NOT comunicação)
    ALERTA  = (reserva < 50 OR consumo > geração OR sinal < 75)
              AND NOT CRÍTICO
    NORMAL  = NOT CRÍTICO AND NOT ALERTA

Como executar
-------------
    python sistema.py

Estrutura esperada de pastas:
    sistema.py
    Crew_Olympus.png        (opcional — logo da equipe na pasta ao lado)
    data/dados.csv          (arquivo modelo, via upload ou gerado)
"""

from __future__ import annotations

import csv
import os
import random
import tkinter as tk
from collections import deque
from tkinter import filedialog, messagebox


# ─────────────────────────────────────────────────────────────────────────────
#                          1.  CONSTANTES DO PROJETO
# ─────────────────────────────────────────────────────────────────────────────

# Limiares operacionais da missão (faixas de segurança)
LIMITE_RESERVA_CRITICO = 35   # %   abaixo disso a bateria é crítica
LIMITE_RESERVA_ALERTA  = 50   # %   abaixo disso entra em alerta
LIMITE_SINAL_BAIXO     = 75   # %   qualidade mínima de comunicação
LIMITE_CONSUMO_PREV    = 80   # kWh limiar para recomendação preventiva

# Paleta de cores (estilo GitHub dark)
COR_FUNDO       = "#0d1117"
COR_CARD        = "#161b22"
COR_CARD_ALT    = "#1c2128"
COR_BORDA       = "#30363d"
COR_DESTAQUE    = "#4d9cf0"
COR_SUCESSO     = "#3fb950"
COR_ATENCAO     = "#d29922"
COR_PERIGO      = "#f85149"
COR_TEXTO       = "#e6edf3"
COR_TEXTO_FRACO = "#7d8590"
COR_BOTAO       = "#21262d"
COR_BOTAO_VERDE = "#1a3a28"
COR_LINHA_RUIM  = "#2a1a1a"   # destaque vermelho escuro p/ inconsistência

# Tipografia
FONTE_TITULO    = ("Segoe UI", 13, "bold")
FONTE_SECAO     = ("Segoe UI", 11, "bold")
FONTE_CORPO     = ("Segoe UI", 11)
FONTE_LABEL     = ("Segoe UI", 10)
FONTE_MICRO     = ("Segoe UI", 9)
FONTE_MONO      = ("Consolas", 11)
FONTE_MONO_BOLD = ("Consolas", 11, "bold")


# ─────────────────────────────────────────────────────────────────────────────
#                       2.  ESTADO GLOBAL DA APLICAÇÃO
# ─────────────────────────────────────────────────────────────────────────────
#
# Variáveis-módulo que armazenam os dados carregados do CSV. São populadas
# pela função `carregar_csv` e consultadas pelas funções de análise e UI.

status_modulos       = {}    # dicionário (tabela hash) — módulos por nome
leituras_energia     = []    # lista — série temporal das leituras
variaveis_ambientais = {}    # dicionário — variáveis do ambiente
log_eventos          = []    # lista — log cronológico de eventos
fila_alertas         = deque()  # fila FIFO — alertas pendentes
historico_eventos    = []    # pilha LIFO — eventos para auditoria reversa

# Hierarquia descritiva da missão (dicionário aninhado)
hierarquia_missao = {
    "energético": {
        "solar":    "Painéis fotovoltaicos",
        "eólico":   "Turbinas eólicas",
        "baterias": "Reserva de carga",
    },
    "ambiental": {
        "temperatura": "Sensores internos e externos",
        "radiação":    "Detector de partículas",
        "comunicação": "Antenas e transponders",
    },
    "operacional": [
        "Suporte à Vida", "Geração de Energia", "Comunicação",
        "Habitat", "Laboratório", "Armazenamento",
    ],
}

# Nomes exibidos na UI para cada módulo do CSV
NOMES_MODULOS = {
    "suporte_vida":  "Suporte à Vida",
    "energia":       "Geração de Energia",
    "comunicacao":   "Comunicação",
    "habitat":       "Habitat",
    "laboratorio":   "Laboratório",
    "armazenamento": "Armazenamento",
}


# ─────────────────────────────────────────────────────────────────────────────
#                       3.  CSV — LEITURA E GERAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

CSV_MODELO = (
    "horario,mod_suporte_vida,mod_energia,mod_comunicacao,mod_habitat,"
    "mod_laboratorio,mod_armazenamento,geracao,consumo,reserva,"
    "temp_interna,temp_externa,radiacao,qualidade_sinal,evento\n"
    "06:00,1,1,1,1,1,1,85,60,90,24,-45,baixa,98,Inicialização da missão\n"
    "08:00,1,1,1,1,1,1,80,65,85,25,-40,baixa,95,Painéis solares ativados\n"
    "10:00,1,1,1,1,1,1,75,70,80,26,-35,media,90,Comunicação estabelecida\n"
    "12:00,1,1,0,1,1,1,70,75,70,27,-30,alta,85,Oscilação energética detectada\n"
    "14:00,1,1,0,1,1,1,65,80,60,28,-25,alta,80,Falha parcial na comunicação\n"
    "16:00,1,1,0,1,1,1,60,85,50,29,-20,muito_alta,75,Aumento da radiação\n"
    "18:00,1,1,0,1,1,1,55,90,40,30,-15,alta,70,Modo economia ativado\n"
    "20:00,1,1,0,1,1,1,0,0,32,31,-10,baixa,65,Alerta crítico emitido\n"
)


def carregar_csv(caminho):
    """Lê o CSV de telemetria e popula o estado global."""
    leituras_energia.clear()
    log_eventos.clear()
    fila_alertas.clear()
    historico_eventos.clear()

    with open(caminho, mode="r", newline="", encoding="utf-8-sig") as arquivo:
        for linha in csv.DictReader(arquivo):
            status_modulos.update({
                chave: int(linha[f"mod_{chave}"])
                for chave in NOMES_MODULOS
            })
            leituras_energia.append({
                "horario": linha["horario"],
                "geracao": int(linha["geracao"]),
                "consumo": int(linha["consumo"]),
                "reserva": int(linha["reserva"]),
            })
            variaveis_ambientais.update({
                "temp_interna":    int(linha["temp_interna"]),
                "temp_externa":    int(linha["temp_externa"]),
                "radiacao":        linha["radiacao"],
                "qualidade_sinal": int(linha["qualidade_sinal"]),
            })
            log_eventos.append({
                "horario":   linha["horario"],
                "descricao": linha["evento"],
            })

    # Popula a pilha LIFO com os eventos para a tela de histórico
    for evento in log_eventos:
        historico_eventos.append(evento)


def gerar_csv_aleatorio(caminho):
    """
    Gera um CSV com 8 leituras de telemetria coerentes.

    O cenário simula um dia operacional da missão: geração solar cai ao longo
    do dia, consumo sobe, reservas caem progressivamente.

    Uma inconsistência é injetada em um horário aleatório:
        consumo_zero : módulo de energia ONLINE mas registra consumo 0
        bateria_sobe : reserva aumenta em um ciclo sem excedente
    """
    horarios = ["06:00", "08:00", "10:00", "12:00",
                "14:00", "16:00", "18:00", "20:00"]

    radiacao_por_hora = ["baixa", "baixa", "media", "alta",
                         "alta", "muito_alta", "alta", "baixa"]

    eventos_possiveis = [
        "Inicialização da missão",
        "Painéis solares ativados",
        "Comunicação estabelecida",
        "Oscilação energética detectada",
        "Falha parcial na comunicação",
        "Aumento da radiação",
        "Modo economia ativado",
        "Backup de energia ativado",
        "Sensor de temperatura recalibrado",
        "Tempestade de poeira detectada",
        "Reinicialização do módulo de habitat",
        "Alerta crítico emitido",
    ]

    geracao_inicial = random.randint(75, 95)
    reserva_atual   = random.randint(80, 95)
    horario_falha_comunicacao = random.randint(3, 6)

    # Sorteia onde e como vai aparecer a inconsistência
    idx_inconsistencia  = random.randint(2, len(horarios) - 3)
    tipo_inconsistencia = random.choice(["consumo_zero", "bateria_sobe"])

    linhas = []
    for i, horario in enumerate(horarios):
        geracao = max(0, geracao_inicial - i * random.randint(5, 10))
        consumo = min(95, 55 + i * random.randint(3, 7))
        reserva_atual = max(20, reserva_atual - random.randint(2, 8))

        # Injeta a inconsistência no horário sorteado
        if i == idx_inconsistencia:
            if tipo_inconsistencia == "consumo_zero":
                consumo = 0
            elif tipo_inconsistencia == "bateria_sobe" and i > 0:
                # Força saldo anterior negativo para a regra detectar
                linhas[i - 1]["geracao"] = 0
                reserva_atual = linhas[i - 1]["reserva"] + random.randint(5, 12)

        linhas.append({
            "horario":          horario,
            "mod_suporte_vida": 1,
            "mod_energia":      1,
            "mod_comunicacao":  0 if i >= horario_falha_comunicacao else 1,
            "mod_habitat":      1,
            "mod_laboratorio":  1,
            "mod_armazenamento":1,
            "geracao":          geracao,
            "consumo":          consumo,
            "reserva":          reserva_atual,
            "temp_interna":     random.randint(22, 33),
            "temp_externa":     random.randint(-50, -5),
            "radiacao":         radiacao_por_hora[i],
            "qualidade_sinal":  max(55, 98 - i * random.randint(3, 6)),
            "evento":           eventos_possiveis[i % len(eventos_possiveis)],
        })

    cabecalho = ["horario", "mod_suporte_vida", "mod_energia",
                 "mod_comunicacao", "mod_habitat", "mod_laboratorio",
                 "mod_armazenamento", "geracao", "consumo", "reserva",
                 "temp_interna", "temp_externa", "radiacao",
                 "qualidade_sinal", "evento"]

    with open(caminho, "w", newline="", encoding="utf-8-sig") as arquivo:
        writer = csv.DictWriter(arquivo, fieldnames=cabecalho)
        writer.writeheader()
        writer.writerows(linhas)


# ─────────────────────────────────────────────────────────────────────────────
#                  4.  REGRESSÃO LINEAR E PREVISÃO DE CONSUMO
# ─────────────────────────────────────────────────────────────────────────────

def regressao_linear(xs, ys):
    """
    Calcula os coeficientes (a, b) da reta y = a·x + b que melhor se ajusta
    aos pontos (xs, ys) pelo método dos mínimos quadrados.
    """
    n = len(xs)
    if n == 0:
        return 0.0, 0.0

    soma_x  = sum(xs)
    soma_y  = sum(ys)
    soma_xy = sum(xs[i] * ys[i] for i in range(n))
    soma_x2 = sum(x ** 2 for x in xs)

    denominador = n * soma_x2 - soma_x ** 2
    if denominador == 0:
        return 0.0, soma_y / n

    a = (n * soma_xy - soma_x * soma_y) / denominador
    b = (soma_y - a * soma_x) / n
    return a, b


def prever_consumo():
    """
    Aplica regressão linear sobre o consumo histórico e prevê o valor para
    duas horas após o último registro.

    Retorna (a, b, hora_prevista, consumo_previsto) ou None se faltarem dados.
    """
    if len(leituras_energia) < 2:
        return None

    horas    = [int(l["horario"].split(":")[0]) for l in leituras_energia]
    consumos = [l["consumo"] for l in leituras_energia]

    a, b = regressao_linear(horas, consumos)
    hora_prevista    = horas[-1] + 2
    consumo_previsto = round(a * hora_prevista + b, 1)
    return a, b, hora_prevista, consumo_previsto


# ─────────────────────────────────────────────────────────────────────────────
#                  5.  DIAGNÓSTICO E DETECÇÃO DE INCONSISTÊNCIAS
# ─────────────────────────────────────────────────────────────────────────────

def detectar_inconsistencias():
    """
    Varre todas as leituras em busca de inconsistências lógicas.

    Retorna uma lista de tuplas (horário, título, detalhe). As regras são:
        1. Módulo de energia ONLINE mas com consumo = 0 kWh.
        2. Reserva de bateria aumentou sem excedente de geração anterior.
        3. Comunicação OFFLINE mas qualidade de sinal alta (> 80%).
    """
    encontradas = []

    # Regra 1 — consumo zero com módulo online
    if status_modulos.get("energia") == 1:
        for leitura in leituras_energia:
            if leitura["consumo"] == 0 and leitura["reserva"] > 0:
                encontradas.append((
                    leitura["horario"],
                    "Módulo de energia ONLINE com consumo = 0 kWh",
                    "Provável falha no sensor de consumo — leitura "
                    "incompatível com o status do módulo.",
                ))
                break  # uma ocorrência basta para sinalizar

    # Regra 2 — bateria sobe sem excedente
    for i in range(1, len(leituras_energia)):
        anterior = leituras_energia[i - 1]
        atual    = leituras_energia[i]
        saldo_anterior = anterior["geracao"] - anterior["consumo"]
        if atual["reserva"] > anterior["reserva"] and saldo_anterior <= 0:
            encontradas.append((
                atual["horario"],
                f"Bateria subiu de {anterior['reserva']}% para "
                f"{atual['reserva']}% sem excedente",
                f"Às {anterior['horario']}: geração={anterior['geracao']} kWh, "
                f"consumo={anterior['consumo']} kWh "
                f"(saldo {saldo_anterior:+d} kWh). "
                "A bateria não deveria ter aumentado.",
            ))
            break

    # Regra 3 — comunicação offline com sinal alto
    sinal = variaveis_ambientais.get("qualidade_sinal", 0)
    if (status_modulos.get("comunicacao") == 0
            and isinstance(sinal, int) and sinal > 80):
        encontradas.append((
            "—",
            f"Comunicação OFFLINE com sinal = {sinal}%",
            "Divergência entre o status reportado do módulo e a qualidade "
            "do sinal medida.",
        ))

    return encontradas


def diagnosticar():
    """
    Avalia o estado atual da missão usando a expressão booleana principal.

    Retorna um dicionário com:
        status   → "CRÍTICO" | "ALERTA" | "NORMAL"
        motivos  → lista de motivos que dispararam o status
        reserva  → reserva de bateria atual
        geracao  → geração atual
        consumo  → consumo atual
        regras   → dict de cada regra → valor booleano avaliado
    """
    if not leituras_energia:
        return {"status": "NORMAL", "motivos": [], "reserva": 0,
                "geracao": 0, "consumo": 0, "regras": {}}

    atual   = leituras_energia[-1]
    reserva = atual["reserva"]
    geracao = atual["geracao"]
    consumo = atual["consumo"]

    comunicacao = status_modulos.get("comunicacao", 1)
    radiacao    = variaveis_ambientais.get("radiacao", "baixa")
    sinal       = variaveis_ambientais.get("qualidade_sinal", 100)

    # Regras lógicas (AND, OR, NOT)
    critico_energia  = (reserva < LIMITE_RESERVA_CRITICO) and (comunicacao == 0)
    critico_radiacao = (radiacao == "muito_alta") and (not bool(comunicacao))
    is_critico       = critico_energia or critico_radiacao

    alerta_reserva   = reserva < LIMITE_RESERVA_ALERTA
    alerta_consumo   = consumo > geracao
    alerta_sinal     = sinal   < LIMITE_SINAL_BAIXO
    is_alerta        = ((alerta_reserva or alerta_consumo or alerta_sinal)
                        and not is_critico)

    if   is_critico: status = "CRÍTICO"
    elif is_alerta : status = "ALERTA"
    else           : status = "NORMAL"

    motivos = []
    if critico_energia : motivos.append(
        "Reserva crítica (< 35%) E comunicação OFFLINE")
    if critico_radiacao: motivos.append(
        "Radiação MUITO ALTA E comunicação comprometida")
    if is_alerta:
        if alerta_reserva: motivos.append(f"Reserva abaixo de 50% ({reserva}%)")
        if alerta_consumo: motivos.append("Consumo supera geração atual")
        if alerta_sinal  : motivos.append(f"Qualidade do sinal baixa ({sinal}%)")

    regras = {
        f"reserva < 35  ({reserva}%)": reserva < LIMITE_RESERVA_CRITICO,
        f"reserva < 50  ({reserva}%)": alerta_reserva,
        "comunicação == 0"           : comunicacao == 0,
        "consumo > geração"          : alerta_consumo,
        f"sinal < 75  ({sinal}%)"    : alerta_sinal,
        "radiação == 'muito_alta'"   : radiacao == "muito_alta",
    }

    return {"status": status, "motivos": motivos, "reserva": reserva,
            "geracao": geracao, "consumo": consumo, "regras": regras}


def gerar_recomendacoes():
    """Produz recomendações técnicas priorizadas pelo estado atual."""
    if not leituras_energia:
        return [("ROTINA", "Sem dados carregados.")]

    reserva     = leituras_energia[-1]["reserva"]
    comunicacao = status_modulos.get("comunicacao", 1)
    radiacao    = variaveis_ambientais.get("radiacao", "baixa")
    recs = []

    if reserva < LIMITE_RESERVA_CRITICO and comunicacao == 0:
        recs += [
            ("CRÍTICA", "Ativar comunicação de emergência imediatamente"),
            ("CRÍTICA", "Desligar módulos não essenciais — priorizar suporte à vida"),
            ("ALTA",    "Redirecionar toda a geração disponível para as baterias"),
        ]
    elif reserva < LIMITE_RESERVA_ALERTA:
        recs += [
            ("ALTA",  "Ativar modo de economia — reduzir laboratório e armazenamento"),
            ("MÉDIA", "Monitorar geração eólica e aumentar captação solar se possível"),
        ]

    if comunicacao == 0:
        recs.append(("CRÍTICA",
                     "Tentar reconexão via canal de backup em 437 MHz"))

    if radiacao in ("alta", "muito_alta"):
        recs.append(("ALTA",
                     "Suspender EVA — manter tripulação no abrigo blindado"))

    if not recs:
        recs.append(("ROTINA",
                     "Monitoramento padrão — todos os sistemas estáveis"))
    return recs


def recomendar_acao(motivo):
    """Mapeia um motivo de alerta para uma ação concreta."""
    m = motivo.lower()
    if "comunicação" in m or "offline" in m:
        return "Ativar rádio de emergência e tentar reconexão via satélite"
    if "reserva" in m or "energia" in m:
        return "Desligar módulos não essenciais e redirecionar energia"
    if "consumo" in m:
        return "Reduzir consumo do laboratório e armazenamento em 30%"
    if "sinal" in m:
        return "Reposicionar antena e aumentar potência do transmissor"
    if "radiação" in m:
        return "Manter tripulação em abrigo — suspender EVA"
    return "Acionar equipe de manutenção para diagnóstico presencial"


def cor_por_status(status):
    return {"CRÍTICO": COR_PERIGO,
            "ALERTA":  COR_ATENCAO,
            "NORMAL":  COR_SUCESSO}.get(status, COR_TEXTO_FRACO)


def cor_por_radiacao(nivel):
    return {"baixa":      COR_SUCESSO,
            "media":      COR_ATENCAO,
            "alta":       COR_PERIGO,
            "muito_alta": COR_PERIGO}.get(nivel, COR_TEXTO_FRACO)


# ─────────────────────────────────────────────────────────────────────────────
#                       6.  COMPONENTES DE UI REUTILIZÁVEIS
# ─────────────────────────────────────────────────────────────────────────────

class AreaComScroll(tk.Frame):
    """
    Container com barra de rolagem vertical. Filhos devem ser adicionados
    em `self.conteudo` em vez de `self`.
    """

    def __init__(self, parent, bg=COR_FUNDO):
        super().__init__(parent, bg=bg)
        self._canvas   = tk.Canvas(self, bg=bg, bd=0, highlightthickness=0)
        self._scroll   = tk.Scrollbar(self, orient="vertical",
                                      command=self._canvas.yview)
        self.conteudo  = tk.Frame(self._canvas, bg=bg)
        self._janela   = self._canvas.create_window(
            (0, 0), window=self.conteudo, anchor="nw")

        self._canvas.configure(yscrollcommand=self._scroll.set)
        self._scroll.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)

        self.conteudo.bind("<Configure>", self._ajustar_scrollregion)
        self._canvas.bind("<Configure>", self._ajustar_largura)
        self._canvas.bind_all("<MouseWheel>", self._rolar)

    def _ajustar_scrollregion(self, _evento):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _ajustar_largura(self, evento):
        self._canvas.itemconfig(self._janela, width=evento.width)

    def _rolar(self, evento):
        topo, base = self._canvas.yview()
        delta = int(-1 * (evento.delta / 120))
        # Bloqueia rolagem além dos limites
        if delta < 0 and topo <= 0: return
        if delta > 0 and base >= 1: return
        self._canvas.yview_scroll(delta, "units")

    def ir_para_topo(self):
        self._canvas.yview_moveto(0)

    def limpar(self):
        for filho in self.conteudo.winfo_children():
            filho.destroy()


def criar_card(pai, titulo, cor_topo=COR_DESTAQUE, bg=COR_CARD):
    """
    Cria um card com barra colorida no topo e cabeçalho. Retorna o frame
    interno onde o conteúdo do card deve ser adicionado.
    """
    moldura = tk.Frame(pai, bg=COR_BORDA, padx=1, pady=1)
    moldura.pack(fill="x", padx=20, pady=(0, 14))

    interno = tk.Frame(moldura, bg=bg)
    interno.pack(fill="x")

    tk.Frame(interno, bg=cor_topo, height=3).pack(fill="x")

    cabecalho = tk.Frame(interno, bg=bg, padx=16, pady=10)
    cabecalho.pack(fill="x")
    tk.Label(cabecalho, text=titulo, font=FONTE_SECAO,
             bg=bg, fg=cor_topo, anchor="w").pack(side="left")

    corpo = tk.Frame(interno, bg=bg, padx=16)
    corpo.pack(fill="x", pady=(0, 14))
    return corpo


def linha_chave_valor(pai, chave, valor, cor_valor=COR_TEXTO, bg=COR_CARD):
    """Renderiza uma linha simples no formato 'chave: valor'."""
    container = tk.Frame(pai, bg=bg)
    container.pack(fill="x", pady=2)
    tk.Label(container, text=chave, font=FONTE_LABEL, bg=bg,
             fg=COR_TEXTO_FRACO, width=22, anchor="w").pack(side="left")
    tk.Label(container, text=valor, font=FONTE_LABEL, bg=bg,
             fg=cor_valor, anchor="w").pack(side="left")


def separador(pai, bg=COR_CARD):
    tk.Frame(pai, bg=COR_BORDA, height=1).pack(fill="x", pady=8)


def badge(pai, texto, bg, fg):
    """Pequeno selo colorido para destacar status."""
    tk.Label(pai, text=f"  {texto}  ", font=("Segoe UI", 9, "bold"),
             bg=bg, fg=fg, padx=4, pady=2).pack(side="left", padx=(0, 6))


def barra_progresso(pai, valor, cor, bg=COR_CARD):
    """Desenha uma barra horizontal preenchida em proporção ao valor."""
    container = tk.Frame(pai, bg=bg)
    container.pack(fill="x", pady=3)

    tk.Label(container, text=f"{valor}%", font=FONTE_LABEL, bg=bg,
             fg=COR_TEXTO, width=5, anchor="e").pack(side="right")

    canvas = tk.Canvas(container, height=16, bg=COR_BORDA, bd=0,
                       highlightthickness=0, relief="flat")
    canvas.pack(side="left", fill="x", expand=True, padx=(0, 8))
    container.update_idletasks()
    largura = canvas.winfo_width() or 400
    canvas.create_rectangle(0, 0, int(largura * valor / 100), 16,
                            fill=cor, outline="")


# ─────────────────────────────────────────────────────────────────────────────
#                       7.  PÁGINAS / SEÇÕES DE CONTEÚDO
# ─────────────────────────────────────────────────────────────────────────────
#
# Cada função `pagina_*` recebe o frame onde deve renderizar seu conteúdo.
# São chamadas pelo App quando o usuário troca de seção no menu lateral.


def _linha_inconsistente(idx):
    """Retorna True se a leitura no índice `idx` tem alguma inconsistência."""
    leitura = leituras_energia[idx]

    # Tipo 1 — consumo zero com módulo de energia online
    if (status_modulos.get("energia") == 1
            and leitura["consumo"] == 0
            and leitura["reserva"] > 0):
        return True

    # Tipo 2 — bateria sobe sem excedente no ciclo anterior
    if idx > 0:
        anterior = leituras_energia[idx - 1]
        saldo = anterior["geracao"] - anterior["consumo"]
        if leitura["reserva"] > anterior["reserva"] and saldo <= 0:
            return True

    return False


def pagina_painel(pai):
    diag   = diagnosticar()
    cor_st = cor_por_status(diag["status"])
    com    = status_modulos.get("comunicacao", 1)
    rad    = variaveis_ambientais.get("radiacao", "—")
    t_int  = variaveis_ambientais.get("temp_interna", "—")

    # ── Status geral ────────────────────────────────────────────────────────
    card = criar_card(pai, "Status da Missão", cor_topo=cor_st)
    linha_badge = tk.Frame(card, bg=COR_CARD); linha_badge.pack(fill="x", pady=4)
    badge(linha_badge, diag["status"], cor_st, COR_FUNDO)

    reserva = diag["reserva"]
    cor_bat = (COR_PERIGO  if reserva < LIMITE_RESERVA_CRITICO else
               COR_ATENCAO if reserva < LIMITE_RESERVA_ALERTA  else
               COR_SUCESSO)
    barra_progresso(card, reserva, cor=cor_bat)

    separador(card)
    linha_chave_valor(card, "Reserva de bateria", f"{reserva}%", cor_bat)
    linha_chave_valor(card, "Comunicação",
                      "ONLINE" if com else "OFFLINE",
                      COR_SUCESSO if com else COR_PERIGO)
    linha_chave_valor(card, "Radiação", str(rad).upper(),
                      cor_por_radiacao(str(rad)))
    linha_chave_valor(card, "Temperatura interna", f"{t_int} °C")

    # ── Módulos operacionais ────────────────────────────────────────────────
    card_mods = criar_card(pai, "Módulos Operacionais", cor_topo=COR_DESTAQUE)
    for chave, nome in NOMES_MODULOS.items():
        valor = status_modulos.get(chave, 1)
        cor   = COR_SUCESSO if valor else COR_PERIGO
        linha = tk.Frame(card_mods, bg=COR_CARD); linha.pack(fill="x", pady=3)
        tk.Label(linha, text=nome, font=FONTE_LABEL, bg=COR_CARD,
                 fg=COR_TEXTO, width=24, anchor="w").pack(side="left")
        tk.Label(linha, text=" ONLINE " if valor else " OFFLINE ",
                 font=("Segoe UI", 9, "bold"),
                 bg=cor, fg=COR_FUNDO).pack(side="left")

    # ── Motivos do diagnóstico (se houver) ──────────────────────────────────
    if diag["motivos"]:
        card_mot = criar_card(pai, "Motivos do Diagnóstico",
                              cor_topo=cor_st, bg=COR_CARD_ALT)
        for motivo in diag["motivos"]:
            linha = tk.Frame(card_mot, bg=COR_CARD_ALT)
            linha.pack(fill="x", pady=2)
            tk.Label(linha, text="›", font=("Segoe UI", 14, "bold"),
                     bg=COR_CARD_ALT, fg=cor_st, width=3).pack(side="left")
            tk.Label(linha, text=motivo, font=FONTE_CORPO,
                     bg=COR_CARD_ALT, fg=COR_TEXTO, anchor="w",
                     wraplength=700, justify="left").pack(side="left")


def pagina_telemetria(pai):
    # ── Matriz de energia ───────────────────────────────────────────────────
    card = criar_card(pai, "Matriz de Energia — Leituras por Horário",
                      cor_topo=COR_DESTAQUE)

    # Cabeçalho da tabela
    colunas = [("Horário", 14), ("Geração (kWh)", 16),
               ("Consumo (kWh)", 16), ("Reserva %", 12)]
    cab = tk.Frame(card, bg=COR_BORDA); cab.pack(fill="x", pady=(0, 2))
    for titulo, largura in colunas:
        tk.Label(cab, text=titulo, font=("Segoe UI", 10, "bold"),
                 bg=COR_BORDA, fg=COR_TEXTO, width=largura, anchor="w",
                 padx=6, pady=5).pack(side="left")

    # Linhas — destaca a(s) linha(s) com inconsistência
    for i, leitura in enumerate(leituras_energia):
        eh_inconsistente = _linha_inconsistente(i)
        bg_linha  = COR_LINHA_RUIM if eh_inconsistente else COR_CARD
        cor_texto = COR_PERIGO     if eh_inconsistente else COR_TEXTO

        linha = tk.Frame(card, bg=bg_linha, pady=1); linha.pack(fill="x")
        for valor, largura in [
            (leitura["horario"], 14),
            (leitura["geracao"], 16),
            (leitura["consumo"], 16),
            (leitura["reserva"], 12),
        ]:
            tk.Label(linha, text=str(valor), font=FONTE_MONO, bg=bg_linha,
                     fg=cor_texto, width=largura, anchor="w",
                     padx=6, pady=4).pack(side="left")

        if eh_inconsistente:
            tk.Label(linha, text=" INCONSISTÊNCIA ",
                     font=("Segoe UI", 8, "bold"),
                     bg=COR_PERIGO, fg=COR_FUNDO).pack(side="left", padx=4)

    # ── Variáveis ambientais ────────────────────────────────────────────────
    card_amb = criar_card(pai, "Variáveis Ambientais", cor_topo="#7ee787")
    linha_chave_valor(card_amb, "Temperatura interna",
                      f"{variaveis_ambientais.get('temp_interna', '—')} °C")
    linha_chave_valor(card_amb, "Temperatura externa",
                      f"{variaveis_ambientais.get('temp_externa', '—')} °C")
    rad = str(variaveis_ambientais.get("radiacao", ""))
    linha_chave_valor(card_amb, "Nível de radiação", rad.upper(),
                      cor_por_radiacao(rad))
    linha_chave_valor(card_amb, "Qualidade do sinal",
                      f"{variaveis_ambientais.get('qualidade_sinal', '—')}%")

    # ── Hierarquia da missão ────────────────────────────────────────────────
    card_hier = criar_card(pai, "Hierarquia da Missão", cor_topo="#bc8cff")
    for sistema, subs in hierarquia_missao.items():
        tk.Label(card_hier, text=f"[ {sistema.upper()} ]",
                 font=("Segoe UI", 10, "bold"), bg=COR_CARD,
                 fg=COR_TEXTO_FRACO, anchor="w"
                 ).pack(fill="x", pady=(10, 4))
        if isinstance(subs, dict):
            for chave, descricao in subs.items():
                linha_chave_valor(card_hier, chave, descricao)
        else:
            for item in subs:
                linha_chave_valor(card_hier, "›", item)


def pagina_diagnostico(pai):
    diag   = diagnosticar()
    cor_st = cor_por_status(diag["status"])

    # ── Resultado principal ─────────────────────────────────────────────────
    card = criar_card(pai, "Resultado do Diagnóstico Lógico", cor_topo=cor_st)
    linha = tk.Frame(card, bg=COR_CARD); linha.pack(fill="x", pady=4)
    badge(linha, diag["status"], cor_st, COR_FUNDO)
    separador(card)

    reserva = diag["reserva"]; geracao = diag["geracao"]; consumo = diag["consumo"]
    cor_bat = (COR_PERIGO  if reserva < LIMITE_RESERVA_CRITICO else
               COR_ATENCAO if reserva < LIMITE_RESERVA_ALERTA  else
               COR_SUCESSO)
    cor_saldo = COR_SUCESSO if geracao >= consumo else COR_PERIGO

    linha_chave_valor(card, "Status classificado", diag["status"], cor_st)
    linha_chave_valor(card, "Reserva de bateria",  f"{reserva}%", cor_bat)
    linha_chave_valor(card, "Geração atual",       f"{geracao} kWh")
    linha_chave_valor(card, "Consumo atual",       f"{consumo} kWh")
    linha_chave_valor(card, "Saldo energético",
                      f"{geracao - consumo:+d} kWh", cor_saldo)

    # ── Expressão booleana ──────────────────────────────────────────────────
    card_expr = criar_card(pai, "Expressão Booleana Principal",
                           cor_topo="#bc8cff", bg=COR_CARD_ALT)
    expressoes = [
        ("CRÍTICO", "= (reserva < 35 AND comunicação == 0)"),
        ("",        "  OR (radiação == 'muito_alta' AND NOT comunicação)"),
        ("ALERTA",  "= (reserva < 50 OR consumo > geração OR sinal < 75)"),
        ("",        "  AND NOT CRÍTICO"),
        ("NORMAL",  "= NOT CRÍTICO AND NOT ALERTA"),
    ]
    labels_expr = []
    for chave, corpo in expressoes:
        linha = tk.Frame(card_expr, bg=COR_CARD_ALT); linha.pack(fill="x", pady=1)
        tk.Label(linha, text=chave, font=FONTE_MONO_BOLD, bg=COR_CARD_ALT,
                 fg=COR_DESTAQUE, width=9, anchor="w").pack(side="left")
        lbl = tk.Label(linha, text=corpo, font=FONTE_MONO,
                       bg=COR_CARD_ALT, fg=COR_TEXTO, anchor="w",
                       justify="left")
        lbl.pack(side="left", fill="x", expand=True)
        labels_expr.append(lbl)

    # Quebra responsiva da expressão booleana
    def _ajustar_wrap(evento, labels=labels_expr):
        largura = max(200, evento.width - 120)
        for label in labels:
            label.configure(wraplength=largura)
    card_expr.bind("<Configure>", _ajustar_wrap)

    # ── Regras avaliadas no ciclo atual ─────────────────────────────────────
    card_reg = criar_card(pai, "Regras Avaliadas no Ciclo Atual",
                          cor_topo=cor_st, bg=COR_CARD_ALT)
    for descricao, ativo in diag["regras"].items():
        cor = COR_SUCESSO if ativo else COR_TEXTO_FRACO
        linha = tk.Frame(card_reg, bg=COR_CARD_ALT); linha.pack(fill="x", pady=3)
        tk.Label(linha, text="TRUE " if ativo else "FALSE",
                 font=("Consolas", 10, "bold"), bg=COR_CARD_ALT,
                 fg=cor, width=7).pack(side="left")
        tk.Label(linha, text=descricao, font=FONTE_MONO,
                 bg=COR_CARD_ALT, fg=cor, anchor="w").pack(side="left")


def pagina_previsao(pai):
    # ── Metodologia ─────────────────────────────────────────────────────────
    card = criar_card(pai, "Método — Regressão Linear (Mínimos Quadrados)",
                      cor_topo=COR_DESTAQUE)
    formulas = [
        "a  =  (n · Σxy  −  Σx · Σy)  /  (n · Σx²  −  (Σx)²)",
        "b  =  (Σy  −  a · Σx)  /  n",
        "consumo_previsto  =  a · hora  +  b",
    ]
    for f in formulas:
        tk.Label(card, text=f, font=FONTE_MONO, bg=COR_CARD,
                 fg=COR_DESTAQUE, anchor="w").pack(fill="x", pady=2)

    resultado = prever_consumo()
    if resultado is None:
        tk.Label(card, text="Dados insuficientes para previsão.",
                 font=FONTE_CORPO, bg=COR_CARD,
                 fg=COR_TEXTO_FRACO).pack()
        return

    a, b, hora_prev, consumo_prev = resultado
    cor_tend = COR_SUCESSO if a <= 0 else COR_PERIGO

    # ── Modelo ajustado ─────────────────────────────────────────────────────
    card_mod = criar_card(pai, "Modelo Ajustado aos Dados", cor_topo="#7ee787")
    linha_chave_valor(card_mod, "Equação ajustada",
                      f"consumo = {a:.2f} · hora + ({b:.2f})")
    linha_chave_valor(card_mod, "Inclinação (a)",
                      f"{a:+.2f} kWh/hora", cor_tend)
    linha_chave_valor(card_mod, "Intercepto (b)", f"{b:.2f}")
    separador(card_mod)
    tk.Label(card_mod, text="Histórico utilizado na regressão",
             font=("Segoe UI", 10, "bold"), bg=COR_CARD,
             fg=COR_TEXTO_FRACO, anchor="w"
             ).pack(fill="x", pady=(10, 4))
    for leitura in leituras_energia:
        linha_chave_valor(card_mod, leitura["horario"],
                          f"{leitura['consumo']} kWh consumidos")

    # ── Resultado da previsão ───────────────────────────────────────────────
    card_res = criar_card(pai, "Resultado da Previsão",
                          cor_topo=COR_DESTAQUE, bg=COR_CARD_ALT)
    linha_chave_valor(card_res, f"Estimativa para {hora_prev:02d}h",
                      f"{consumo_prev} kWh", cor_tend, bg=COR_CARD_ALT)
    separador(card_res, bg=COR_CARD_ALT)

    if consumo_prev > LIMITE_CONSUMO_PREV:
        tk.Label(card_res, text="Decisão baseada na previsão",
                 font=("Segoe UI", 10, "bold"), bg=COR_CARD_ALT,
                 fg=COR_TEXTO_FRACO, anchor="w"
                 ).pack(fill="x", pady=(10, 4))
        tk.Label(card_res,
                 text=(f"O consumo previsto de {consumo_prev} kWh excede o "
                       f"limiar operacional de {LIMITE_CONSUMO_PREV} kWh. "
                       f"Recomenda-se reduzir a carga do laboratório e do "
                       f"armazenamento antes das {hora_prev:02d}h."),
                 font=FONTE_CORPO, bg=COR_CARD_ALT, fg=COR_ATENCAO,
                 wraplength=700, justify="left", anchor="w"
                 ).pack(fill="x", pady=4)
    else:
        tk.Label(card_res,
                 text="Consumo previsto dentro do limite operacional.",
                 font=FONTE_CORPO, bg=COR_CARD_ALT,
                 fg=COR_SUCESSO, anchor="w").pack(anchor="w")


def _bloco_alertas(pai, itens, titulo, cor, bg_card):
    if not itens:
        return

    card = criar_card(pai, titulo, cor_topo=cor, bg=bg_card)
    for nivel, mensagem, acao in itens:
        linha = tk.Frame(card, bg=bg_card); linha.pack(fill="x", pady=6)

        # Coluna do rótulo de nível — largura fixa em pixels
        col_nivel = tk.Frame(linha, bg=bg_card, width=160)
        col_nivel.pack(side="left", fill="y")
        col_nivel.pack_propagate(False)
        tk.Label(col_nivel, text=f"[{nivel}]",
                 font=("Segoe UI", 10, "bold"), bg=bg_card,
                 fg=cor, anchor="w").pack(anchor="w", pady=2)

        # Coluna do texto principal
        info = tk.Frame(linha, bg=bg_card)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=mensagem, font=FONTE_CORPO, bg=bg_card,
                 fg=COR_TEXTO, anchor="w", wraplength=780,
                 justify="left").pack(fill="x")
        tk.Label(info, text=f"Ação: {acao}", font=FONTE_MICRO,
                 bg=bg_card, fg=COR_TEXTO_FRACO, anchor="w").pack(fill="x")

        tk.Frame(card, bg=COR_BORDA, height=1).pack(fill="x")


def pagina_alertas(pai):
    fila_alertas.clear()
    diag = diagnosticar()
    incs = detectar_inconsistencias()

    # Popula a fila a partir do diagnóstico
    for motivo in diag["motivos"]:
        nivel = "CRÍTICO" if diag["status"] == "CRÍTICO" else "ALERTA"
        fila_alertas.append((nivel, motivo, recomendar_acao(motivo)))

    for horario, titulo, _ in incs:
        msg = f"[{horario}] {titulo}" if horario != "—" else titulo
        fila_alertas.append(("INCONSISTÊNCIA", msg,
                             "Verificar sensores e validar a leitura"))

    radiacao = variaveis_ambientais.get("radiacao", "baixa")
    if radiacao in ("alta", "muito_alta"):
        fila_alertas.append((
            "ALERTA",
            f"Radiação {str(radiacao).upper()} detectada",
            "Suspender EVA — manter tripulação no abrigo",
        ))

    if not fila_alertas:
        card = criar_card(pai, "Central de Alertas", cor_topo=COR_SUCESSO)
        tk.Label(card,
                 text="Nenhum alerta pendente. Missão operando normalmente.",
                 font=FONTE_CORPO, bg=COR_CARD,
                 fg=COR_SUCESSO, anchor="w").pack(anchor="w")
        return

    criticos = [a for a in fila_alertas if a[0] == "CRÍTICO"]
    atencao  = [a for a in fila_alertas if a[0] == "ALERTA"]
    avisos   = [a for a in fila_alertas if a[0] not in ("CRÍTICO", "ALERTA")]

    _bloco_alertas(pai, criticos, "Alertas Críticos",   COR_PERIGO,  "#1a0d0d")
    _bloco_alertas(pai, atencao,  "Alertas de Atenção", COR_ATENCAO, "#1a160a")
    _bloco_alertas(pai, avisos,   "Avisos e Inconsistências",
                   COR_TEXTO_FRACO, COR_CARD)


def pagina_auditoria(pai):
    inconsistencias = detectar_inconsistencias()

    card = criar_card(pai, "Auditoria de Consistência dos Dados",
                      cor_topo=COR_ATENCAO)
    if not inconsistencias:
        tk.Label(card,
                 text="Nenhuma inconsistência detectada nos dados.",
                 font=FONTE_CORPO, bg=COR_CARD,
                 fg=COR_SUCESSO, anchor="w").pack(anchor="w")
    else:
        for horario, titulo, detalhe in inconsistencias:
            rotulo = f"[{horario}] {titulo}" if horario != "—" else titulo
            container = tk.Frame(card, bg="#1f1a0e", padx=10, pady=8)
            container.pack(fill="x", pady=4)

            tk.Frame(container, bg=COR_ATENCAO, width=4
                     ).pack(side="left", fill="y", padx=(0, 10))

            corpo = tk.Frame(container, bg="#1f1a0e")
            corpo.pack(side="left", fill="x")
            tk.Label(corpo, text=rotulo, font=("Segoe UI", 11, "bold"),
                     bg="#1f1a0e", fg=COR_ATENCAO, anchor="w",
                     wraplength=650, justify="left").pack(fill="x")
            tk.Label(corpo, text=detalhe, font=FONTE_CORPO,
                     bg="#1f1a0e", fg=COR_TEXTO, anchor="w",
                     wraplength=650, justify="left").pack(fill="x")

    # ── Regras de validação aplicadas ───────────────────────────────────────
    card_reg = criar_card(pai, "Regras de Validação Aplicadas",
                          cor_topo=COR_DESTAQUE)
    regras = [
        "Módulo de energia ONLINE com consumo = 0 kWh indica sensor com falha.",
        "Reserva subindo sem excedente de geração indica dados incoerentes.",
        "Comunicação OFFLINE com qualidade de sinal > 80% indica divergência.",
    ]
    for i, descricao in enumerate(regras, start=1):
        linha_chave_valor(card_reg, f"Regra {i}", descricao)


def pagina_recomendacoes(pai):
    cores_prioridade = {
        "CRÍTICA": (COR_PERIGO,   "#1a0d0d"),
        "ALTA":    (COR_ATENCAO,  "#1a160a"),
        "MÉDIA":   (COR_DESTAQUE, COR_CARD_ALT),
        "ROTINA":  (COR_SUCESSO,  COR_CARD),
    }

    for prioridade, texto in gerar_recomendacoes():
        cor, bg = cores_prioridade.get(prioridade, (COR_TEXTO_FRACO, COR_CARD))

        moldura = tk.Frame(pai, bg=COR_BORDA, padx=1, pady=1)
        moldura.pack(fill="x", padx=20, pady=4)

        interno = tk.Frame(moldura, bg=bg, padx=14, pady=12)
        interno.pack(fill="x")
        tk.Frame(interno, bg=cor, width=4
                 ).pack(side="left", fill="y", padx=(0, 12))

        info = tk.Frame(interno, bg=bg)
        info.pack(side="left", fill="x", expand=True)
        tk.Label(info, text=f"Prioridade: {prioridade}",
                 font=("Segoe UI", 9, "bold"), bg=bg, fg=cor
                 ).pack(anchor="w")
        tk.Label(info, text=texto, font=FONTE_CORPO, bg=bg, fg=COR_TEXTO,
                 anchor="w", wraplength=680, justify="left").pack(fill="x")


def pagina_historico(pai):
    card = criar_card(
        pai,
        "Histórico de Eventos — Pilha LIFO (mais recente primeiro)",
        cor_topo="#bc8cff",
    )

    if not historico_eventos:
        tk.Label(card, text="Nenhum evento registrado.",
                 font=FONTE_CORPO, bg=COR_CARD,
                 fg=COR_TEXTO_FRACO).pack(anchor="w")
        return

    # Itera de trás pra frente sem destruir a pilha (apenas leitura)
    total = len(historico_eventos)
    for idx in range(total - 1, -1, -1):
        evento  = historico_eventos[idx]
        horario = evento["horario"]   if isinstance(evento, dict) else evento[0]
        texto   = evento["descricao"] if isinstance(evento, dict) else evento[1]
        ordem   = total - idx

        linha = tk.Frame(card, bg=COR_CARD); linha.pack(fill="x", pady=5)
        tk.Label(linha, text=f"#{ordem:02d}", font=("Consolas", 10, "bold"),
                 bg=COR_CARD, fg=COR_TEXTO_FRACO, width=4).pack(side="left")
        tk.Label(linha, text=horario, font=("Consolas", 11, "bold"),
                 bg=COR_CARD, fg=COR_DESTAQUE,
                 width=7).pack(side="left", padx=(0, 10))
        tk.Label(linha, text=texto, font=FONTE_CORPO, bg=COR_CARD,
                 fg=COR_TEXTO, anchor="w").pack(side="left")

        if idx > 0:
            tk.Frame(card, bg=COR_BORDA, height=1).pack(fill="x")


# ─────────────────────────────────────────────────────────────────────────────
#                       8.  APLICAÇÃO PRINCIPAL (tkinter)
# ─────────────────────────────────────────────────────────────────────────────

class CrewOlympusApp(tk.Tk):
    """
    Janela principal da aplicação. Gerencia duas telas:
        1. Tela inicial — usuário escolhe a origem dos dados.
        2. Tela da missão — exibe as 8 páginas (painel, telemetria, etc).
    """

    SECOES = [
        ("Painel Geral",         pagina_painel),
        ("Telemetria / Matriz",  pagina_telemetria),
        ("Diagnóstico",          pagina_diagnostico),
        ("Previsão",             pagina_previsao),
        ("Alertas",              pagina_alertas),
        ("Auditoria de Dados",   pagina_auditoria),
        ("Recomendações",        pagina_recomendacoes),
        ("Histórico (LIFO)",     pagina_historico),
    ]

    def __init__(self):
        super().__init__()
        self.title("Crew Olympus — Global Solution 2026")
        self.configure(bg=COR_FUNDO)
        self._logo_img = None
        self._botoes_navegacao = []
        self._area_conteudo = None
        self._mostrar_tela_inicial()

    # ── Utilidades de janela ────────────────────────────────────────────────

    def _centralizar(self, largura, altura):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = max(0, (sw - largura) // 2)
        y = max(0, (sh - altura) // 2)
        self.geometry(f"{largura}x{altura}+{x}+{y}")
        self.resizable(True, True)

    def _limpar_janela(self):
        for filho in self.winfo_children():
            filho.destroy()

    def _carregar_logo(self, tamanho=140):
        """Tenta carregar a logo em diferentes localizações."""
        base = os.path.dirname(os.path.abspath(__file__))
        candidatos = [
            os.path.join(base, "..", "Crew_Olympus.png"),
            os.path.join(base, "Crew_Olympus.png"),
        ]
        for caminho in candidatos:
            if not os.path.exists(caminho):
                continue
            try:
                img = tk.PhotoImage(file=caminho)
                # Reduz pela maior potência de 2 que ainda cabe no tamanho
                dim_original = max(img.width(), img.height())
                fator = 1
                while dim_original // (fator * 2) >= tamanho:
                    fator *= 2
                if fator > 1:
                    img = img.subsample(fator, fator)
                return img
            except Exception:
                continue
        return None

    # ── Tela inicial ────────────────────────────────────────────────────────

    def _mostrar_tela_inicial(self):
        self._limpar_janela()
        self._centralizar(540, 640)
        self.configure(bg=COR_FUNDO)

        # Logo (ou texto se a imagem não estiver disponível)
        self._logo_img = self._carregar_logo(tamanho=140)
        frame_logo = tk.Frame(self, bg=COR_FUNDO)
        frame_logo.pack(pady=(32, 0))
        if self._logo_img:
            tk.Label(frame_logo, image=self._logo_img, bg=COR_FUNDO).pack()
        else:
            tk.Label(frame_logo, text="CREW OLYMPUS",
                     font=("Segoe UI", 22, "bold"),
                     bg=COR_FUNDO, fg=COR_DESTAQUE).pack()

        tk.Label(self, text="Sistema de Monitoramento da Missão",
                 font=("Segoe UI", 12),
                 bg=COR_FUNDO, fg=COR_TEXTO_FRACO).pack(pady=(8, 2))
        tk.Label(self, text="Global Solution 2026",
                 font=("Segoe UI", 10),
                 bg=COR_FUNDO, fg=COR_BORDA).pack()

        tk.Frame(self, bg=COR_BORDA, height=1
                 ).pack(fill="x", padx=40, pady=20)

        # Card com botões de escolha de fonte de dados
        card = tk.Frame(self, bg=COR_CARD,
                        highlightbackground=COR_BORDA, highlightthickness=1)
        card.pack(padx=40, fill="x")

        tk.Label(card, text="Selecione a origem dos dados de telemetria",
                 font=FONTE_LABEL, bg=COR_CARD,
                 fg=COR_TEXTO_FRACO).pack(pady=(18, 12))

        def _botao(texto, comando, cor_bg=COR_BOTAO):
            tk.Button(card, text=texto, command=comando,
                      bg=cor_bg, fg=COR_TEXTO,
                      activebackground=COR_DESTAQUE,
                      activeforeground=COR_FUNDO,
                      relief="flat", cursor="hand2",
                      font=("Segoe UI", 11), padx=16, pady=11,
                      bd=0, width=30
                      ).pack(fill="x", padx=24, pady=5)

        _botao("Carregar CSV existente",  self._acao_upload_csv)
        _botao("Baixar CSV modelo",       self._acao_baixar_modelo)
        _botao("Gerar dados aleatórios",  self._acao_gerar_aleatorio,
               cor_bg=COR_BOTAO_VERDE)

        tk.Frame(card, bg=COR_CARD, height=12).pack()

        # Rodapé
        rodape = tk.Frame(self, bg=COR_FUNDO)
        rodape.pack(side="bottom", fill="x", pady=12)
        tk.Frame(rodape, bg=COR_BORDA, height=1).pack(fill="x")
        tk.Label(rodape,
                 text="Global Solution  |  Equipe Crew Olympus  |  "
                      "FIAP  |  Ciência da Computação",
                 font=("Segoe UI", 8),
                 bg=COR_FUNDO, fg=COR_TEXTO_FRACO).pack(pady=(6, 2))
        tk.Label(rodape,
                 text="Gabriel  ·  Lucas  ·  Matheus  ·  Miguel  ·  Pedro",
                 font=("Segoe UI", 8),
                 bg=COR_FUNDO, fg=COR_BORDA).pack()

    # ── Ações da tela inicial ───────────────────────────────────────────────

    def _acao_upload_csv(self):
        caminho = filedialog.askopenfilename(
            title="Selecionar CSV de telemetria",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")],
        )
        if not caminho:
            return
        try:
            carregar_csv(caminho)
            self._mostrar_tela_missao()
        except Exception as erro:
            messagebox.showerror("Erro ao carregar CSV", str(erro))

    def _acao_baixar_modelo(self):
        caminho = filedialog.asksaveasfilename(
            title="Salvar CSV modelo",
            defaultextension=".csv",
            initialfile="dados_modelo.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not caminho:
            return
        with open(caminho, "w", encoding="utf-8-sig") as arquivo:
            arquivo.write(CSV_MODELO)
        messagebox.showinfo("CSV salvo", f"Arquivo salvo em:\n{caminho}")

    def _acao_gerar_aleatorio(self):
        caminho = filedialog.asksaveasfilename(
            title="Salvar CSV aleatório",
            defaultextension=".csv",
            initialfile="dados_aleatorios.csv",
            filetypes=[("CSV", "*.csv")],
        )
        if not caminho:
            return
        try:
            gerar_csv_aleatorio(caminho)
            carregar_csv(caminho)
            self._mostrar_tela_missao()
        except Exception as erro:
            messagebox.showerror("Erro ao gerar CSV", str(erro))

    # ── Tela da missão ──────────────────────────────────────────────────────

    def _mostrar_tela_missao(self):
        self._limpar_janela()
        self._centralizar(1100, 700)
        self.configure(bg=COR_FUNDO)

        diag   = diagnosticar()
        cor_st = cor_por_status(diag["status"])

        # ── Barra superior ────────────────────────────────────────────────
        topo = tk.Frame(self, bg=COR_CARD,
                        highlightbackground=COR_BORDA, highlightthickness=1)
        topo.pack(fill="x")

        self._logo_img = self._carregar_logo(tamanho=32)
        if self._logo_img:
            tk.Label(topo, image=self._logo_img, bg=COR_CARD
                     ).pack(side="left", padx=(14, 6), pady=7)

        tk.Label(topo, text="CREW OLYMPUS",
                 font=("Segoe UI", 13, "bold"),
                 bg=COR_CARD, fg=COR_DESTAQUE).pack(side="left", pady=10)
        tk.Label(topo, text="  |  ", bg=COR_CARD, fg=COR_BORDA).pack(side="left")
        tk.Label(topo, text=diag["status"],
                 font=("Segoe UI", 11, "bold"),
                 bg=COR_CARD, fg=cor_st).pack(side="left")

        tk.Button(topo, text="Trocar dados",
                  command=self._mostrar_tela_inicial,
                  bg=COR_BOTAO, fg=COR_TEXTO_FRACO,
                  activebackground=COR_BORDA, activeforeground=COR_TEXTO,
                  relief="flat", cursor="hand2",
                  font=("Segoe UI", 9), padx=12, pady=6, bd=0
                  ).pack(side="right", padx=14, pady=8)

        # ── Layout principal ──────────────────────────────────────────────
        principal = tk.Frame(self, bg=COR_FUNDO)
        principal.pack(fill="both", expand=True)

        # Menu lateral
        menu = tk.Frame(principal, bg=COR_CARD, width=200,
                        highlightbackground=COR_BORDA, highlightthickness=1)
        menu.pack(side="left", fill="y")
        menu.pack_propagate(False)

        tk.Frame(menu, bg=COR_CARD, height=12).pack()
        tk.Label(menu, text="MÓDULOS DO SISTEMA",
                 font=("Segoe UI", 8, "bold"),
                 bg=COR_CARD, fg=COR_TEXTO_FRACO, anchor="w"
                 ).pack(fill="x", padx=16, pady=(4, 8))

        self._botoes_navegacao = []
        for nome_secao, funcao in self.SECOES:
            botao = tk.Button(
                menu, text=nome_secao,
                command=lambda f=funcao, n=nome_secao: self._navegar(f, n),
                anchor="w",
                bg=COR_CARD, fg=COR_TEXTO,
                activebackground=COR_DESTAQUE, activeforeground=COR_FUNDO,
                relief="flat", cursor="hand2",
                font=("Segoe UI", 10), padx=18, pady=9, bd=0,
            )
            botao.pack(fill="x", padx=0, pady=1)
            self._botoes_navegacao.append((nome_secao, botao))

        # Área de conteúdo com scroll
        self._area_conteudo = AreaComScroll(principal, bg=COR_FUNDO)
        self._area_conteudo.pack(side="left", fill="both", expand=True)

        # Rodapé
        rodape = tk.Frame(self, bg=COR_CARD,
                          highlightbackground=COR_BORDA, highlightthickness=1)
        rodape.pack(side="bottom", fill="x")
        tk.Label(rodape,
                 text="Global Solution  |  Equipe Crew Olympus  |  "
                      "FIAP  |  Ciência da Computação",
                 font=("Segoe UI", 8),
                 bg=COR_CARD, fg=COR_TEXTO_FRACO).pack(pady=5)

        # Abre a primeira página por padrão
        self._navegar(pagina_painel, "Painel Geral")

    def _navegar(self, funcao_pagina, nome_secao):
        """Destaca o botão ativo e renderiza a página correspondente."""
        for nome, botao in self._botoes_navegacao:
            ativo = (nome == nome_secao)
            botao.configure(
                bg=COR_DESTAQUE if ativo else COR_CARD,
                fg=COR_FUNDO    if ativo else COR_TEXTO,
            )

        self._area_conteudo.limpar()
        tk.Frame(self._area_conteudo.conteudo, bg=COR_FUNDO, height=16).pack()
        funcao_pagina(self._area_conteudo.conteudo)
        tk.Frame(self._area_conteudo.conteudo, bg=COR_FUNDO, height=24).pack()
        self._area_conteudo.ir_para_topo()


# ─────────────────────────────────────────────────────────────────────────────
#                              9.  PONTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    CrewOlympusApp().mainloop()
