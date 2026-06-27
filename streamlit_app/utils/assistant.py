"""
utils/assistant.py
"""

from __future__ import annotations
import streamlit as st


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


def answer(q: str, reading: dict, iqar: float, label: str) -> str:
    """Ponto de entrada usado pela UI. Tenta o LLM; se falhar, usa as regras."""
    key = st.secrets.get("ANTHROPIC_API_KEY", None) if hasattr(st, "secrets") else None
    if not key:
        return _rule_based(q, reading, iqar, label)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        system = (
            "Você é o assistente do painel Respira SP de qualidade do ar de São Paulo. "
            f"Leitura atual: PM2.5={reading['pm25']:.0f} µg/m³, IQAr={iqar:.0f} ({label}). "
            "Responda em português, curto (até 3 frases), claro e prático."
        )
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=300,
            system=system,
            messages=[{"role": "user", "content": q}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    except Exception:
        # Qualquer falha (rede, cota, pacote ausente) -> cai no modo regra.
        return _rule_based(q, reading, iqar, label)
