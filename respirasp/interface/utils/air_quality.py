"""
utils/air_quality.py
Funções auxiliares para classificação, recomendações, carregamento de previsão
E construção de contexto técnico de qualidade do ar.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

TZ_SP = "America/Sao_Paulo"
FORECAST_COL = "pm25_previsto"


def _to_sp_timestamp(ts):
    """Converte timestamps para horário de São Paulo, quando possível."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        return ts.tz_localize(TZ_SP)
    return ts.tz_convert(TZ_SP)


def carregar_previsao(path: str | Path, col_pm25: str = FORECAST_COL) -> pd.DataFrame:
    """
    Carrega o CSV de previsão usado pelo chatbot.

    Espera um arquivo com:
    - primeira coluna como datetime/index;
    - coluna de previsão, por padrão 'pm25_previsto'.

    Retorna um DataFrame com índice timezone-aware convertido para America/Sao_Paulo.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"Arquivo de previsão não encontrado: {path}")

    df = pd.read_csv(path, index_col=0, parse_dates=True)

    if col_pm25 not in df.columns:
        raise ValueError(
            f"O arquivo de previsão precisa ter a coluna '{col_pm25}'. "
            f"Colunas encontradas: {list(df.columns)}"
        )

    df = df.copy()
    df[col_pm25] = pd.to_numeric(df[col_pm25], errors="coerce")
    df = df.dropna(subset=[col_pm25]).sort_index()

    if df.empty:
        raise ValueError(f"A coluna '{col_pm25}' não possui valores válidos.")

    index = pd.DatetimeIndex(df.index)
    if index.tz is None:
        df.index = index.tz_localize(TZ_SP)
    else:
        df.index = index.tz_convert(TZ_SP)

    return df


def consultar_previsao(df: pd.DataFrame, col_pm25: str = FORECAST_COL) -> dict:
    """
    Consulta a previsão de PM2.5 para as próximas horas.

    Espera um DataFrame com:
    - índice datetime
    - coluna 'pm25_previsto' ou coluna informada em col_pm25
    """
    if col_pm25 not in df.columns:
        raise ValueError(f"O DataFrame precisa ter a coluna '{col_pm25}'.")

    pm25 = pd.to_numeric(df[col_pm25], errors="coerce").dropna()

    if pm25.empty:
        raise ValueError(f"A coluna '{col_pm25}' não possui valores válidos.")

    return {
        "inicio": _to_sp_timestamp(pm25.index.min()),
        "fim": _to_sp_timestamp(pm25.index.max()),
        "pm25_medio": float(pm25.mean()),
        "pm25_max": float(pm25.max()),
        "pm25_min": float(pm25.min()),
        "horario_pico": _to_sp_timestamp(pm25.idxmax()),
        "horario_melhor": _to_sp_timestamp(pm25.idxmin()),
    }


def consultar_classificacao_cetesb(pm25: float) -> str:
    """
    Classifica PM2.5 conforme faixas CETESB para média de 24h.
    Unidade: µg/m³.
    """
    if pm25 <= 25:
        return "Boa"
    if pm25 <= 50:
        return "Moderada"
    if pm25 <= 75:
        return "Ruim"
    if pm25 <= 125:
        return "Muito Ruim"
    return "Péssima"


def consultar_recomendacao_saude(classe: str) -> str:
    recomendacoes = {
        "Boa": (
            "A qualidade do ar está boa. Não há recomendações especiais para a população. "
            "Atividades ao ar livre podem ser realizadas normalmente."
        ),
        "Moderada": (
            "A qualidade do ar está moderada. Pessoas de grupos sensíveis, como crianças, idosos "
            "e pessoas com doenças cardíacas ou pulmonares, devem considerar reduzir esforço físico "
            "pesado ao ar livre, principalmente se apresentarem sintomas."
        ),
        "Ruim": (
            "A qualidade do ar está ruim. Crianças, idosos e pessoas com doenças cardíacas ou "
            "pulmonares devem reduzir esforço físico pesado ao ar livre. A população em geral deve "
            "evitar atividades muito intensas ou prolongadas."
        ),
        "Muito Ruim": (
            "A qualidade do ar está muito ruim. Crianças, idosos e pessoas com doenças cardíacas "
            "ou pulmonares devem evitar esforço físico pesado ao ar livre. A população em geral "
            "deve reduzir atividades físicas intensas e prolongadas."
        ),
        "Péssima": (
            "A qualidade do ar está péssima. Crianças, idosos e pessoas com doenças cardíacas "
            "ou pulmonares devem evitar qualquer esforço físico ao ar livre. A população em geral "
            "também deve evitar atividades físicas ao ar livre, especialmente esforço pesado."
        ),
    }

    return recomendacoes.get(
        classe,
        "Classificação da qualidade do ar não reconhecida. Verifique a classe informada.",
    )


contexto_poluente = """
PM2.5 são partículas muito finas presentes no ar, com diâmetro menor que 2,5 micrômetros.
Por serem pequenas, podem penetrar profundamente nos pulmões e afetar a saúde respiratória e cardiovascular.
""".strip()


contexto_cetesb = """
As recomendações de saúde seguem a classificação de qualidade do ar da CETESB.
Grupos sensíveis incluem crianças, idosos e pessoas com doenças cardíacas ou pulmonares.
Quanto pior a qualidade do ar, maior deve ser a restrição a atividades físicas ao ar livre.
Para classes Moderada, Ruim, Muito Ruim e Péssima, o foco da recomendação é reduzir ou evitar esforço físico pesado ao ar livre, especialmente para grupos sensíveis.
""".strip()


def responder_qualidade_ar(df: pd.DataFrame, col_pm25: str = FORECAST_COL) -> str:
    """Gera uma resposta técnica resumida para uma previsão horária de PM2.5."""
    previsao = consultar_previsao(df, col_pm25=col_pm25)
    classe = consultar_classificacao_cetesb(previsao["pm25_medio"])
    recomendacao = consultar_recomendacao_saude(classe)

    resposta = f"""
📅 Período analisado:
{previsao['inicio']:%d/%m/%Y %H:%M} até {previsao['fim']:%d/%m/%Y %H:%M}

🌫 PM2.5 médio previsto:
{previsao['pm25_medio']:.1f} µg/m³

📊 Classificação:
{classe}

📈 Maior concentração:
{previsao['pm25_max']:.1f} µg/m³ às {previsao['horario_pico']:%H:%M}

📉 Menor concentração:
{previsao['pm25_min']:.1f} µg/m³ às {previsao['horario_melhor']:%H:%M}

🏃 Recomendação:
{recomendacao}
"""
    return resposta.strip()


def montar_tabela_horaria_previsao(df: pd.DataFrame, col_pm25: str = FORECAST_COL) -> str:
    """Monta uma tabela textual hora a hora para ser usada no contexto do LLM."""
    if col_pm25 not in df.columns:
        raise ValueError(f"O DataFrame precisa ter a coluna '{col_pm25}'.")

    df_local = df.copy()
    index = pd.DatetimeIndex(df_local.index)
    if index.tz is None:
        df_local.index = index.tz_localize(TZ_SP)
    else:
        df_local.index = index.tz_convert(TZ_SP)

    df_local[col_pm25] = pd.to_numeric(df_local[col_pm25], errors="coerce")
    df_local = df_local.dropna(subset=[col_pm25]).sort_index()

    return "\n".join(
        f"  {idx:%d/%m %H:%M} — {row[col_pm25]:.1f} µg/m³ "
        f"({consultar_classificacao_cetesb(row[col_pm25])})"
        for idx, row in df_local.iterrows()
    )


def montar_contexto_previsao(df: pd.DataFrame, col_pm25: str = FORECAST_COL) -> str:
    """Monta o bloco de contexto de previsão para o LLM."""
    resposta_tecnica = responder_qualidade_ar(df, col_pm25=col_pm25)
    tabela_horas = montar_tabela_horaria_previsao(df, col_pm25=col_pm25)

    contexto = f"""
Informações técnicas da previsão:
{resposta_tecnica}

Previsão hora a hora em horário de São Paulo:
{tabela_horas}
"""
    return contexto.strip()
