"""
Router do Assistente com IA da AAPM
Recebe a mensagem do usuário (vinda do widget de chat do admin.html/script.js)
e repassa para a API da Anthropic (Claude), mantendo a chave da API somente
no backend — nunca exposta no front-end.
"""

import os
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import List, Literal

from anthropic import Anthropic, APIError

from app.routers.auth_router import get_usuario_atual
from app.models.usuario import Usuario

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

# A chave é lida da variável de ambiente ANTHROPIC_API_KEY (definida no .env).
# Gere a sua em: https://console.anthropic.com/settings/keys
_client: Anthropic | None = None


def get_client() -> Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=501,
                detail="ANTHROPIC_API_KEY não configurada no servidor. Defina essa variável no arquivo .env.",
            )
        _client = Anthropic(api_key=api_key)
    return _client


MODELO_IA = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

SYSTEM_PROMPT = """Você é o assistente virtual do Painel Administrativo da AAPM (Associação
de Pais e Mestres) do SENAI Brás. Seu papel é ajudar administradores e operadores a
usar o sistema: Categorias, Fornecedores, Produtos, Associados, Armários, Usuários,
Vendas e Relatório.

Regras:
- Responda sempre em português do Brasil, de forma breve, objetiva e cordial.
- Se a pergunta for sobre como fazer algo no painel, explique o caminho (menu/módulo)
  em poucas frases.
- Se não souber a resposta ou for algo fora do escopo do painel, diga isso com
  honestidade e sugira falar com um administrador do sistema.
- Nunca invente dados de produtos, vendas ou usuários — você não tem acesso ao
  banco de dados, apenas ao contexto da conversa.
"""

MAX_HISTORICO = 12  # limita o tamanho do histórico enviado por requisição


# ─────────────────────────────────────────────────────────────────────────────
# SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class MensagemHistorico(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistenteRequest(BaseModel):
    mensagem: str = Field(..., min_length=1, max_length=2000)
    historico: List[MensagemHistorico] = Field(default_factory=list)


class AssistenteResponse(BaseModel):
    resposta: str


# ─────────────────────────────────────────────────────────────────────────────
# ROTA
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/api/assistente", response_model=AssistenteResponse)
async def conversar_com_assistente(
    payload: AssistenteRequest,
    usuario_atual: Usuario = Depends(get_usuario_atual),  # exige login, igual às outras rotas /api
):
    client = get_client()

    historico_limitado = payload.historico[-MAX_HISTORICO:]
    mensagens = [{"role": m.role, "content": m.content} for m in historico_limitado]
    mensagens.append({"role": "user", "content": payload.mensagem})

    try:
        resposta = client.messages.create(
            model=MODELO_IA,
            max_tokens=500,
            system=SYSTEM_PROMPT,
            messages=mensagens,
        )
    except APIError as erro:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível falar com o serviço de IA no momento. Tente novamente em instantes.",
        ) from erro

    texto_resposta = "".join(
        bloco.text for bloco in resposta.content if getattr(bloco, "type", None) == "text"
    ).strip()

    if not texto_resposta:
        texto_resposta = "Não consegui gerar uma resposta agora. Pode reformular a pergunta?"

    return AssistenteResponse(resposta=texto_resposta)