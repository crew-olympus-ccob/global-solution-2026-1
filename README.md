# 🚀 Crew Olympus - Sistema Inteligente de Monitoramento da Missão

Sistema desenvolvido para a Global Solution 2026 da FIAP, com o objetivo de monitorar telemetria de uma missão espacial, identificar situações críticas, detectar inconsistências nos dados e prever consumo energético utilizando Regressão Linear.

## 👨‍💻 Equipe Crew Olympus

| Nome | RM |
|--------|--------|
| Gabriel Tavares Martins de Oliveira | RM573718 |
| Lucas Araujo de Carvalho | RM571060 |
| Matheus Henrique Pedrozo Traiba | RM571817 |
| Miguel Monteiro Moreira | RM572904 |
| Pedro Henrique de Lima Costa | RM573008 |

---

# 📋 Sobre o Projeto

O sistema realiza o monitoramento de uma missão espacial através da leitura de arquivos CSV contendo dados de telemetria.

A aplicação é capaz de:

- Carregar dados reais através de arquivos CSV.
- Gerar dados simulados automaticamente.
- Classificar o estado da missão.
- Detectar inconsistências nos sensores.
- Emitir alertas operacionais.
- Gerar recomendações automáticas.
- Realizar previsão de consumo energético.
- Exibir histórico de eventos.
- Apresentar todas as informações em uma interface gráfica construída com Tkinter.

---

# 🛠 Tecnologias Utilizadas

- Python 3
- Tkinter (Interface Gráfica)
- CSV
- Collections (Deque)
- Programação Orientada a Objetos
- Estruturas de Dados
- Regressão Linear (Mínimos Quadrados)

Nenhuma biblioteca externa é necessária.

---

# 📂 Estrutura do Projeto

```text
projeto/
│
├── src/
│   └── sistema.py
│
├── data/
│   └── dados.csv
│
├── assets/
│   └── Crew_Olympus.png
│
└── README.md
```

---

# 📊 Estruturas de Dados Utilizadas

| Estrutura | Aplicação |
|------------|------------|
| Dicionário (Hash Table) | Armazenamento dos módulos |
| Lista | Leituras de energia |
| Matriz (Lista de listas) | Dados cruzados de telemetria |
| Fila (Deque - FIFO) | Alertas pendentes |
| Pilha (LIFO) | Histórico de eventos |
| Dicionário Aninhado | Hierarquia da missão |

---

# 🧠 Lógica de Diagnóstico

O sistema utiliza expressões booleanas para determinar a situação operacional da missão.

## Estado Crítico

```text
(reserva < 35 AND comunicação == 0)
OR
(radiação == muito_alta AND NOT comunicação)
```

## Estado de Alerta

```text
(reserva < 50 OR consumo > geração OR sinal < 75)
AND NOT CRÍTICO
```

## Estado Normal

```text
NOT CRÍTICO AND NOT ALERTA
```

---

# 📈 Previsão de Consumo

A previsão energética é realizada através de uma Regressão Linear Simples utilizando o método dos mínimos quadrados.

## Fórmulas

```text
a = (n·Σxy − Σx·Σy) / (n·Σx² − (Σx)²)

b = (Σy − a·Σx) / n

y = a·x + b
```

Onde:

- `a` = inclinação da reta
- `b` = intercepto
- `y` = consumo previsto

---

# 🔎 Detecção de Inconsistências

O sistema verifica automaticamente situações incoerentes nos dados.

### Regra 1

Módulo de energia online com consumo igual a zero.

```text
Energia ONLINE
AND
Consumo = 0
```

---

### Regra 2

Aumento da bateria sem excedente energético.

```text
Reserva Atual > Reserva Anterior
AND
(Geração - Consumo) <= 0
```

---

### Regra 3

Comunicação offline com qualidade de sinal alta.

```text
Comunicação OFFLINE
AND
Sinal > 80%
```

---

# 📑 Funcionalidades

## Painel Geral

- Status da missão
- Reserva de bateria
- Estado dos módulos
- Temperatura
- Radiação

## Telemetria

- Leituras energéticas
- Variáveis ambientais
- Hierarquia da missão

## Diagnóstico

- Resultado da análise lógica
- Regras avaliadas

## Previsão

- Modelo de regressão
- Tendência de consumo

## Alertas

- Alertas críticos
- Alertas operacionais
- Inconsistências

## Auditoria

- Validação dos dados
- Explicação dos problemas encontrados

## Recomendações

- Ações sugeridas automaticamente

## Histórico

- Eventos registrados em estrutura LIFO

---

# ▶️ Como Executar

## Clone o projeto

```bash
git clone https://github.com/crew-olympus-ccob/global-solution-2026-1
```

## Entre na pasta

```bash
cd global-solution-2026-1
```

## Execute o sistema

```bash
python src/sistema.py
```

---

# 📄 Formato Esperado do CSV

```csv
horario,mod_suporte_vida,mod_energia,mod_comunicacao,mod_habitat,mod_laboratorio,mod_armazenamento,geracao,consumo,reserva,temp_interna,temp_externa,radiacao,qualidade_sinal,evento
```

Exemplo:

```csv
06:00,1,1,1,1,1,1,85,60,90,24,-45,baixa,98,Inicialização da missão
```

---

# 🎯 Objetivo Acadêmico

Este projeto foi desenvolvido para demonstrar a aplicação prática de:

- Estruturas de Dados
- Algoritmos
- Expressões Booleanas
- Manipulação de Arquivos
- Programação Orientada a Objetos
- Análise de Dados
- Regressão Linear
- Desenvolvimento de Interfaces Gráficas

no contexto de monitoramento inteligente de sistemas críticos.

---

# 📜 Licença

Projeto desenvolvido exclusivamente para fins acadêmicos na FIAP - Global Solution 2026.