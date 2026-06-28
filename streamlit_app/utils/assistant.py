"""
utils/assistant.py
Assistente inteligente do painel RESPIRA SP.
"""

from __future__ import annotations

import os

import streamlit as st
from google import genai

from utils.air_quality import (
    consultar_recomendacao_saude,
    contexto_cetesb,
    contexto_poluente,
)


def _rule_based(q: str, reading: dict, iqar: float, label: str) -> str:
    """Fallback simples quando o LLM não estiver disponível."""
    ql = q.lower()
    pm25 = float(reading.get("pm25", 0))
    recomendacao = consultar_recomendacao_saude(label)

    if any(k in ql for k in ["amanhã", "amanha", "previsão", "previsao", "próxim", "proxim"]):
        return (
            f"A previsão indica PM2.5 em torno de **{pm25:.0f} µg/m³** nas próximas horas, "
            f"com qualidade do ar **{label}**. {recomendacao}"
        )

    if any(k in ql for k in ["sair", "caminhar", "correr", "exercício", "exercicio", "atividade"]):
        return recomendacao

    if any(k in ql for k in ["pm2.5", "pm25", "poluente", "o que é", "significa"]):
        return (
            "PM2.5 são partículas finas com diâmetro menor que 2,5 micrômetros. "
            "Por serem muito pequenas, podem penetrar profundamente nos pulmões e afetar a saúde respiratória e cardiovascular."
        )

    return (
        f"Agora o IQAr está em **{iqar:.0f}** (**{label}**) e o PM2.5 está em "
        f"**{pm25:.0f} µg/m³**. {recomendacao}"
    )


def _build_context(reading: dict, iqar: float, label: str) -> str:
    """Constrói o contexto enviado ao LLM usando a leitura atual do painel."""
    pm25 = float(reading.get("pm25", 0))
    recomendacao = consultar_recomendacao_saude(label)

    contexto = f"""
Você é o assistente inteligente do projeto RESPIRA SP.
Use apenas as informações técnicas abaixo para responder ao usuário.

Informações atuais do painel:
- Poluente monitorado: PM2.5
- Concentração atual de PM2.5: {pm25:.1f} µg/m³
- IQAr atual: {iqar:.0f}
- Classificação atual da qualidade do ar: {label}
- Recomendação de saúde associada à classificação: {recomendacao}

Sobre o poluente monitorado:
{contexto_poluente}

Sobre as recomendações de saúde:
{contexto_cetesb}

Regras de resposta:
- Responda em português do Brasil.
- Seja claro, natural e cuidadoso.
- Responda em até 3 frases, salvo se o usuário pedir mais detalhes.
- Use apenas as informações fornecidas neste contexto.
- Não invente valores, bairros, horários ou previsões que não estejam no contexto.
- Não altere a classificação da qualidade do ar.
- Não dê diagnóstico médico.
- Se a pergunta for sobre sair, caminhar, correr ou fazer atividade ao ar livre, use a recomendação de saúde.
- Se o usuário relatar sintomas, oriente procurar um profissional de saúde.
"""
    return contexto.strip()


def answer(q: str, reading: dict, iqar: float, label: str) -> str:
    """
    Ponto de entrada usado pela interface.
    Tenta responder usando Gemini.
    Em caso de falha, utiliza a resposta baseada em regras.
    """
    try:
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )

        prompt = f"""
{_build_context(reading, iqar, label)}

Pergunta do usuário:
{q}

Resposta:
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        if response.text:
            return response.text.strip()

        return _rule_based(q, reading, iqar, label)

    except Exception as e:
        st.warning(f"LLM indisponível. Usando resposta técnica. Erro: {e}")
        return _rule_based(q, reading, iqar, label)
