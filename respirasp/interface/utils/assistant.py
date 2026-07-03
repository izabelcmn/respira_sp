"""
utils/assistant.py
Assistente inteligente do painel RESPIRA SP.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import streamlit as st
from google import genai

from utils.air_quality import (
    carregar_previsao,
    consultar_classificacao_cetesb,
    consultar_previsao,
    consultar_recomendacao_saude,
    contexto_cetesb,
    contexto_poluente,
    montar_contexto_previsao,
)

from respirasp.params import (
    GOOGLE_CLOUD_PROJECT,
    GOOGLE_CLOUD_LOCATION,
    GOOGLE_GENAI_USE_VERTEXAI,
    GEMINI_MODEL,
)


def _resolve_forecast(
    forecast_df: pd.DataFrame | None = None,
    forecast_path: str | Path | None = None,
) -> pd.DataFrame | None:
    """Obtém a previsão a partir de um DataFrame já carregado ou de um CSV."""
    if forecast_df is not None:
        return forecast_df
    if forecast_path is not None:
        return carregar_previsao(forecast_path)
    return None


def _rule_based(
    q: str,
    reading: dict,
    iqar: float,
    label: str,
    forecast_df: pd.DataFrame | None = None,
) -> str:
    """Fallback simples quando o LLM não estiver disponível."""
    ql = q.lower()
    pm25 = float(reading.get("pm25", 0))
    recomendacao_atual = consultar_recomendacao_saude(label)

    if forecast_df is not None and any(
        k in ql for k in ["amanhã", "amanha", "previsão", "previsao", "próxim", "proxim", "melhor horário", "melhor horario"]
    ):
        previsao = consultar_previsao(forecast_df)
        classe_prevista = consultar_classificacao_cetesb(previsao["pm25_medio"])
        recomendacao_prevista = consultar_recomendacao_saude(classe_prevista)
        return (
            f"A previsão entre **{previsao['inicio']:%d/%m %H:%M}** e "
            f"**{previsao['fim']:%d/%m %H:%M}** indica PM2.5 médio de "
            f"**{previsao['pm25_medio']:.1f} µg/m³**, com qualidade do ar "
            f"**{classe_prevista}**. O menor valor previsto ocorre às "
            f"**{previsao['horario_melhor']:%H:%M}** "
            f"({previsao['pm25_min']:.1f} µg/m³). {recomendacao_prevista}"
        )

    if any(k in ql for k in ["amanhã", "amanha", "previsão", "previsao", "próxim", "proxim"]):
        return (
            "Ainda não encontrei uma tabela de previsão carregada no contexto. "
            f"Com os dados atuais do painel, o PM2.5 está em **{pm25:.0f} µg/m³** "
            f"e a qualidade do ar está **{label}**. {recomendacao_atual}"
        )

    if any(k in ql for k in ["sair", "caminhar", "correr", "exercício", "exercicio", "atividade"]):
        return recomendacao_atual

    if any(k in ql for k in ["pm2.5", "pm25", "poluente", "o que é", "significa"]):
        return (
            "PM2.5 são partículas finas com diâmetro menor que 2,5 micrômetros. "
            "Por serem muito pequenas, podem penetrar profundamente nos pulmões e afetar a saúde respiratória e cardiovascular."
        )

    return (
        f"Agora o IQAr está em **{iqar:.0f}** (**{label}**) e o PM2.5 está em "
        f"**{pm25:.0f} µg/m³**. {recomendacao_atual}"
    )


def _build_context(
    reading: dict,
    iqar: float,
    label: str,
    forecast_df: pd.DataFrame | None = None,
) -> str:
    """Constrói o contexto enviado ao LLM usando leitura atual e previsão, quando disponível."""
    pm25 = float(reading.get("pm25", 0))
    recomendacao = consultar_recomendacao_saude(label)

    bloco_previsao = ""
    if forecast_df is not None:
        bloco_previsao = f"\n\n{montar_contexto_previsao(forecast_df)}"

    contexto = f"""
Você é o assistente inteligente do projeto RESPIRA SP.
Use apenas as informações técnicas abaixo para responder ao usuário.

Informações atuais do painel:
- Poluente monitorado: PM2.5
- Concentração atual de PM2.5: {pm25:.1f} µg/m³
- IQAr atual: {iqar:.0f}
- Classificação atual da qualidade do ar: {label}
- Recomendação de saúde associada à classificação atual: {recomendacao}{bloco_previsao}

Sobre o poluente monitorado:
{contexto_poluente}

Sobre as recomendações de saúde:
{contexto_cetesb}

Regras de resposta:
- Responda em português do Brasil.
- Seja claro, natural e cuidadoso.
- Responda em até 3 frases, salvo se o usuário pedir mais detalhes.
- Use apenas as informações fornecidas neste contexto.
- Use os horários em horário de São Paulo, não em UTC.
- Não invente valores, bairros, horários ou previsões que não estejam no contexto.
- Não altere a classificação da qualidade do ar.
- Não dê diagnóstico médico.
- Se a pergunta for sobre sair, caminhar, correr ou fazer atividade ao ar livre, use a recomendação de saúde.
- Se o usuário perguntar sobre previsão, amanhã, próximas horas, melhor horário ou horário específico, use o bloco de previsão.
- Use a tabela hora a hora apenas quando a pergunta pedir horário específico ou melhor horário.
- Se o usuário relatar sintomas, oriente procurar um profissional de saúde.
"""
    return contexto.strip()


def answer(
    q: str,
    reading: dict,
    iqar: float,
    label: str,
    forecast_df: pd.DataFrame | None = None,
    forecast_path: str | Path | None = None,
) -> str:
    """
    Ponto de entrada usado pela interface.
    Tenta responder usando Gemini.
    Em caso de falha, utiliza a resposta baseada em regras.

    Pode receber a previsão de duas formas:
    - forecast_df: DataFrame já carregado com coluna 'pm25_previsto'; ou
    - forecast_path: caminho para CSV da previsão.
    """
    try:
        forecast = _resolve_forecast(forecast_df=forecast_df, forecast_path=forecast_path)
    except Exception as e:
        st.warning(f"Não foi possível carregar a previsão. Respondendo sem previsão. Erro: {e}")
        forecast = None

    try:
        client = genai.Client(
    vertexai=GOOGLE_GENAI_USE_VERTEXAI,
    project=GOOGLE_CLOUD_PROJECT,
    location=GOOGLE_CLOUD_LOCATION,
    )

        prompt = f"""
{_build_context(reading, iqar, label, forecast_df=forecast)}

Pergunta do usuário:
{q}

Resposta:
"""

        response = client.models.generate_content(
    model=GEMINI_MODEL,
    contents=prompt,
)

        if response.text:
            return response.text.strip()

        return _rule_based(q, reading, iqar, label, forecast_df=forecast)

    except Exception:
        import traceback

        erro = traceback.format_exc()
        print(erro, flush=True)

        st.error("Erro completo da LLM:")
        st.code(erro)

        return _rule_based(q, reading, iqar, label, forecast_df=forecast)
