"""
utils/air_quality.py
"""

from __future__ import annotations

import pandas as pd


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
        "inicio": pm25.index.min(),
        "fim": pm25.index.max(),
        "pm25_medio": pm25.mean(),
        "pm25_max": pm25.max(),
        "pm25_min": pm25.min(),
        "horario_pico": pm25.idxmax(),
        "horario_melhor": pm25.idxmin(),
    }


def consultar_classificacao_cetesb(pm25: float) -> str:
    """
    Classifica PM2.5 conforme faixas CETESB para média de 24h.
    Unidade: µg/m³
    """

    if pm25 <= 25:
        return "Boa"
    elif pm25 <= 50:
        return "Moderada"
    elif pm25 <= 75:
        return "Ruim"
    elif pm25 <= 125:
        return "Muito Ruim"
    else:
        return "Péssima"


def consultar_recomendacao_saude(classe: str) -> str:
    recomendacoes = {
        "Boa": (
            "A qualidade do ar está adequada. "
            "Atividades ao ar livre podem ser realizadas normalmente."
        ),
        "Moderada": (
            "Pessoas de grupos sensíveis, como crianças, idosos e pessoas com doenças "
            "cardíacas ou pulmonares, devem considerar reduzir esforço físico pesado ao ar livre."
        ),
        "Ruim": (
            "Pessoas de grupos sensíveis devem evitar esforço físico pesado ao ar livre. "
            "A população em geral deve reduzir atividades intensas ou prolongadas."
        ),
        "Muito Ruim": (
            "Pessoas com doenças cardíacas ou pulmonares, idosos e crianças devem evitar "
            "qualquer esforço físico ao ar livre. A população em geral deve evitar esforço pesado."
        ),
        "Péssima": (
            "A condição é crítica. Recomenda-se evitar atividades físicas ao ar livre, "
            "principalmente para grupos sensíveis."
        ),
    }

    return recomendacoes.get(classe, "Classificação não reconhecida.")


def explicar_poluente(poluente: str) -> str:
    poluente = poluente.upper().replace(" ", "")

    explicacoes = {
        "PM2.5": (
            "PM2.5 são partículas muito finas presentes no ar, com diâmetro menor que 2,5 micrômetros. "
            "Por serem pequenas, podem penetrar profundamente nos pulmões e afetar a saúde respiratória e cardiovascular."
        ),
        "PM25": (
            "PM2.5 são partículas muito finas presentes no ar, com diâmetro menor que 2,5 micrômetros. "
            "Por serem pequenas, podem penetrar profundamente nos pulmões e afetar a saúde respiratória e cardiovascular."
        ),
        "PM10": (
            "PM10 são partículas inaláveis com diâmetro menor que 10 micrômetros. "
            "Podem causar irritação nas vias respiratórias e agravar problemas pulmonares."
        ),
        "O3": (
            "O ozônio troposférico é um poluente formado por reações químicas na atmosfera, "
            "principalmente sob luz solar. Pode irritar os pulmões e piorar sintomas respiratórios."
        ),
        "NO2": (
            "O dióxido de nitrogênio está associado principalmente à queima de combustíveis, "
            "como emissões de veículos. Pode irritar as vias respiratórias."
        ),
        "CO": (
            "O monóxido de carbono é um gás produzido pela combustão incompleta. "
            "Em altas concentrações, reduz a capacidade do sangue de transportar oxigênio."
        ),
    }

    return explicacoes.get(
        poluente,
        "Ainda não tenho explicação cadastrada para esse poluente."
    )


def responder_qualidade_ar(df: pd.DataFrame) -> str:
    previsao = consultar_previsao(df)

    classe = consultar_classificacao_cetesb(
        previsao["pm25_medio"]
    )

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