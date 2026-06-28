"""
utils/air_quality.py
Funções auxiliares para classificação, recomendações e contexto de qualidade do ar.
"""

from __future__ import annotations

import pandas as pd

TZ_SP = "America/Sao_Paulo"


def _to_sp_timestamp(ts):
    """Converte timestamps para horário de São Paulo, quando possível."""
    ts = pd.Timestamp(ts)
    if ts.tzinfo is None:
        return ts.tz_localize(TZ_SP)
    return ts.tz_convert(TZ_SP)


def consultar_previsao(df: pd.DataFrame) -> dict:
    """
    Consulta a previsão de PM2.5 para as próximas horas.

    Espera um DataFrame com:
    - índice datetime
    - coluna 'pm25_previsto'
    """
    if "pm25_previsto" not in df.columns:
        raise ValueError("O DataFrame precisa ter a coluna 'pm25_previsto'.")

    pm25 = df["pm25_previsto"].dropna()

    if pm25.empty:
        raise ValueError("A coluna 'pm25_previsto' não possui valores válidos.")

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


def responder_qualidade_ar(df: pd.DataFrame) -> str:
    """Gera uma resposta técnica resumida para uma previsão horária de PM2.5."""
    previsao = consultar_previsao(df)
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
