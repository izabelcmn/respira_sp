"""
utils/assistant.py
"""

from __future__ import annotations
import streamlit as st
import os
from google import genai
from utils.air_quality import responder_qualidade_ar


def _rule_based(q: str, reading: dict, iqar: float, label: str) -> str:
    """Respostas simples por palavra-chave — suficientes para a demo."""
    ql = q.lower()
    if any(k in ql for k in ["amanhã", "amanha", "previsão", "previsao", "próxim", "proxim"]):
        return (f"A previsão indica PM2.5 em torno de **{reading['pm25']:.0f} µg/m³** "
                f"nas próximas horas, mantendo qualidade **{label}**.")
    if any(k in ql for k in ["melhor", "boa", "limpo", "região", "regiao", "onde"]):
        return ("As regiões com melhor qualidade do ar tendem a ser **Parelheiros**, "
                "**Santana** e bairros mais arborizados/afastados do tráfego.")
    if any(k in ql for k in ["pior", "ruim", "alta"]):
        return ("Os maiores índices costumam aparecer em **Moema** e corredores de "
                "tráfego intenso, sobretudo nos picos da manhã e do fim de tarde.")
    if any(k in ql for k in ["pm2.5", "pm25", "poluente", "o que é", "significa"]):
        return ("PM2.5 são partículas finas (≤2,5 µm) que penetram fundo nas vias "
                "respiratórias. É o poluente dominante deste painel.")
    # default
    return (f"Agora o IQAr está em **{iqar:.0f}** (**{label}**). "
            f"Posso falar sobre a previsão das próximas horas, melhores regiões "
            f"ou o que é o PM2.5.")


def _build_context(df) -> str:
    """Usa a estrutura contruída na função respoder_qualidade_ar()"""
    resposta_tecnica = responder_qualidade_ar(df)

    return f"""
    Você é o assistente inteligente do projeto RESPIRA SP,
    um sistema de previsão da qualidade do ar em São Paulo.

    Use SOMENTE as informações técnicas abaixo para responder.

    INFORMAÇÕES TÉCNICAS:
    {resposta_tecnica}

    Regras:
    - Responda em português do Brasil.
    - Seja curto, claro e prático.
    - Não invente valores.
    - Não altere a classificação CETESB.
    - Se perguntarem sobre caminhada, corrida ou sair ao ar livre, use a recomendação de saúde.
    - Não dê diagnóstico médico.
    """


def answer(q: str, df) -> str:
    """
    Usando Gemini
    """

    try:
        client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
        )

        prompt = f"""
{_build_context(df)}

Pergunta do usuário:
{q}

Resposta:
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        return response.text

    except Exception as e:
        st.warning(f"LLM indisponível. Usando resposta técnica. Erro: {e}")
        return _rule_based(q, df)
