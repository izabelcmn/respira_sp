# Respira SP — Interface (streamlit_app/)

Front-end em **Streamlit** que **lê os artefatos** do pipeline do grupo e mostra a
previsão de **PM2.5 24h à frente** (modelo **LightGBM**), no estilo do mockup.

> **Princípio de integração:** esta pasta é uma **ilha**. Ela só LÊ três arquivos e
> **não importa nada** de `taxifare/`. Assim não há conflito de merge com o time.

## Contrato (o que a UI lê)

```
respira_sp/                              ← repo do grupo
├── models/lightgbm_pm25.pkl             ← carregado (joblib)
├── models/lightgbm_features.pkl         ← as 46 features, na ordem do treino
├── data/operational/dados_features_*.csv ← lido (índice UTC, coluna MP2.5)
└── streamlit_app/                       ← ESTA pasta (nova, isolada)
```

A UI roda a inferência **ao vivo** (`model.predict` em 24 linhas = milissegundos);
ela **não recalcula feature** — usa a engenharia que já vem no CSV operacional.
A fonte da verdade das features é o `lightgbm_features.pkl` (nunca o `FEATURE_NAMES`).

## Rodar

```bash
cd respira_sp/streamlit_app
pip install -r requirements.txt
streamlit run app.py            # http://localhost:8501
```

Abre **mesmo sem os artefatos**: se faltar `.pkl`/CSV, entra em modo demo (sintético).
Para ativar o LightGBM real, basta os arquivos existirem nos caminhos acima.

## Caminhos configuráveis

Por padrão a UI procura `models/` e `data/operational/` no **pai** desta pasta
(a raiz do repo). Para apontar para outro lugar:

```bash
export RESPIRA_MODELS_DIR=/caminho/para/models
export RESPIRA_OP_DIR=/caminho/para/data/operational
```

## Onde mexer

- **Visual:** `utils/styling.py` (cores em `PALETTE`, faixas IQAr, gauge SVG, CSS).
- **Dados/modelo:** `utils/data.py` (carga do `.pkl`, leitura do CSV, métricas).
- **Gráficos:** `utils/charts.py` (observado×previsto, mapa, barras).
- **Métricas para a banca:** `LGBM_OPERATIONAL` e `BACKTEST_2019` em `utils/data.py`.

## Assistente com LLM (opcional)

Sem chave, o chat responde por regras. Para ligar o LLM:
`pip install anthropic` e crie `.streamlit/secrets.toml` com `ANTHROPIC_API_KEY="sk-ant-..."`.

## Git — zero conflito

```bash
git checkout -b feat/streamlit-ui
# adicione só esta pasta:
git add streamlit_app/
git commit -m "feat: interface Streamlit (lê artefatos LightGBM)"
```

Não edite arquivos do pacote do grupo nem o `.python-version`. Mantenha os `.pkl`
fora do git se forem grandes (use o `.gitignore` desta pasta como base).
