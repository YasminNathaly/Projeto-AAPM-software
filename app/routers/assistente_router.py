"""
Router do Assistente com IA da AAPM
Recebe a mensagem do usuário (vinda do widget de chat do admin.html/script.js)
e repassa para a API do Gemini (Google), mantendo a chave da API somente no
backend — nunca exposta no front-end.

Este assistente tem acesso a FERRAMENTAS DE CONSULTA (somente leitura) ao
banco de dados: ele pode buscar produtos, ver estoque baixo, vendas recentes,
faturamento total e status de armários. Isso é proposital e importante:
nenhuma das funções abaixo cria, altera ou apaga dados — o modelo só pode
LER informações, nunca escrever. Se um dia quiser dar ao assistente o poder
de, por exemplo, registrar uma venda, crie uma função nova, bem restrita e
validada, e adicione-a à lista FERRAMENTAS — nunca reaproveite as funções de
escrita que já existem no resto do sistema.
"""

import logging
import os
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func as sql_func

from google import genai
from google.genai import types

from app.routers.auth_router import get_usuario_atual
from app.models.usuario import Usuario
from app.database import SessionLocal
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.armario import Armario

logger = logging.getLogger("assistente_ia")

# O SDK do Gemini emite um aviso (não é erro) sempre que usamos tools em
# generate_content em vez de client.chats.send_message. É só uma recomendação
# de estilo do Google — nosso uso funciona normalmente — então silenciamos
# esse aviso específico pra não poluir o terminal a cada mensagem.
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

router = APIRouter()

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

# A chave é lida da variável de ambiente GEMINI_API_KEY (definida no .env).
# Gere a sua em: https://aistudio.google.com/app/apikey
_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=501,
                detail="GEMINI_API_KEY não configurada no servidor. Defina essa variável no arquivo .env.",
            )
        _client = genai.Client(api_key=api_key)
    return _client


# gemini-3.6-flash é o modelo atual recomendado pelo Google (gemini-2.5-flash
# foi descontinuado para contas novas). Dá pra trocar via variável de ambiente
# caso o Google lance uma versão mais nova no futuro.
MODELO_IA = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

MAX_HISTORICO = 12  # limita o tamanho do histórico enviado por requisição


# ─────────────────────────────────────────────────────────────────────────────
# FERRAMENTAS (FUNÇÕES) QUE A IA PODE CHAMAR — SOMENTE LEITURA NO BANCO
# ─────────────────────────────────────────────────────────────────────────────
# O SDK do Gemini lê o nome, os parâmetros e o docstring de cada função pra
# decidir sozinho quando e como chamá-la, executa a chamada e já devolve o
# resultado pro modelo formular a resposta final — tudo dentro de uma única
# chamada a generate_content(), sem código extra da nossa parte.
#
# Cada função abre sua própria sessão de banco (SessionLocal) e a fecha ao
# final, porque elas são chamadas pelo SDK do Gemini, fora do ciclo normal de
# requisição do FastAPI (não dá pra usar o Depends(get_db) aqui).

def buscar_produtos(nome: str = "") -> list[dict]:
    """Busca produtos cadastrados pelo nome (aceita busca parcial, sem diferenciar
    maiúsculas/minúsculas). Se 'nome' vier vazio, retorna os produtos cadastrados
    mais recentemente. Retorna no máximo 10 produtos, cada um com nome, preço,
    estoque e categoria.
    """
    db = SessionLocal()
    try:
        query = db.query(Produto)
        if nome:
            query = query.filter(Produto.nome.ilike(f"%{nome}%"))
        produtos = query.order_by(Produto.id.desc()).limit(10).all()
        return [
            {
                "nome": p.nome,
                "preco": p.preco,
                "estoque": p.estoque if p.estoque is not None else p.quantidade,
                "categoria": p.categoria.nome if p.categoria else None,
            }
            for p in produtos
        ]
    finally:
        db.close()


def consultar_estoque_baixo(limite: int = 5) -> list[dict]:
    """Lista produtos com estoque igual ou menor que 'limite' unidades (padrão 5).
    Use esta função quando o usuário perguntar sobre reposição de estoque ou
    produtos que estão acabando.
    """
    db = SessionLocal()
    try:
        produtos = (
            db.query(Produto)
            .filter(Produto.estoque <= limite)
            .order_by(Produto.estoque.asc())
            .limit(10)
            .all()
        )
        return [{"nome": p.nome, "estoque": p.estoque} for p in produtos]
    finally:
        db.close()


def consultar_vendas_recentes(quantidade: int = 5) -> list[dict]:
    """Lista as vendas mais recentes registradas no sistema (padrão 5, no máximo 10).
    Retorna cliente, quantidade, valor total e forma de pagamento de cada venda.
    """
    db = SessionLocal()
    try:
        quantidade = min(max(quantidade, 1), 10)
        vendas = db.query(Venda).order_by(Venda.id.desc()).limit(quantidade).all()
        return [
            {
                "cliente": v.comprador or v.cliente,
                "quantidade": v.quantidade,
                "valor_total": v.preco_total or v.valor_total,
                "forma_pagamento": v.forma_pagamento,
            }
            for v in vendas
        ]
    finally:
        db.close()


def consultar_faturamento_total() -> dict:
    """Retorna o número total de vendas registradas e a soma do valor faturado
    até agora em todo o sistema.
    """
    db = SessionLocal()
    try:
        total_vendas = db.query(sql_func.count(Venda.id)).scalar() or 0
        faturamento = db.query(sql_func.sum(Venda.preco_total)).scalar() or 0
        return {"total_vendas": total_vendas, "faturamento_total": round(float(faturamento), 2)}
    finally:
        db.close()


def consultar_armario(numero: str = "") -> list[dict]:
    """Consulta o status de armários pelo número (ex: '012'). Se 'numero' vier
    vazio, lista os armários cadastrados (no máximo 10), com status
    (Disponível, Ocupado, Manutenção) e localização.
    """
    db = SessionLocal()
    try:
        query = db.query(Armario)
        if numero:
            query = query.filter(Armario.numero == numero)
        armarios = query.limit(10).all()
        return [
            {"numero": a.numero, "status": a.status, "localizacao": a.localizacao}
            for a in armarios
        ]
    finally:
        db.close()


# Lista de ferramentas disponíveis pro modelo. Pra adicionar uma nova consulta,
# basta escrever a função acima (com docstring explicando pra que serve) e
# incluí-la aqui.
FERRAMENTAS = [
    buscar_produtos,
    consultar_estoque_baixo,
    consultar_vendas_recentes,
    consultar_faturamento_total,
    consultar_armario,
]


SYSTEM_INSTRUCTION = """Você é o assistente virtual do Painel Administrativo da AAPM (Associação
de Pais e Mestres) do SENAI Brás. Seu papel é ajudar administradores e operadores a
usar o sistema: Categorias, Fornecedores, Produtos, Associados, Armários, Usuários,
Vendas e Relatório.

Você tem acesso a ferramentas de CONSULTA (somente leitura) ao banco de dados:
buscar produtos, ver estoque baixo, vendas recentes, faturamento total e status
de armários. Use essas ferramentas sempre que a pergunta do usuário depender de
dados reais e atuais do sistema — nunca invente números, nomes ou valores.

Você NÃO tem nenhuma ferramenta de escrita: não pode criar, editar nem apagar
nada no sistema, apenas consultar. Se o usuário pedir uma ação de escrita
(cadastrar, editar, excluir), explique que ele precisa fazer isso pelo próprio
painel (menu correspondente), você não pode executar essa ação.

Regras:
- Responda sempre em português do Brasil, de forma breve, objetiva e cordial.
- Se a pergunta for sobre como fazer algo no painel, explique o caminho (menu/módulo)
  em poucas frases.
- Se não souber a resposta ou for algo fora do escopo do painel, diga isso com
  honestidade e sugira falar com um administrador do sistema.
"""


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

    # O Gemini usa "model" onde o resto do mundo usa "assistant" — convertemos aqui.
    historico_limitado = payload.historico[-MAX_HISTORICO:]
    contents = [
        types.Content(
            role="model" if item.role == "assistant" else "user",
            parts=[types.Part(text=item.content)],
        )
        for item in historico_limitado
    ]
    contents.append(types.Content(role="user", parts=[types.Part(text=payload.mensagem)]))

    try:
        # Passando as funções Python direto em "tools", o SDK do Gemini decide
        # sozinho se/quando chamar alguma delas, executa a chamada e já
        # devolve a resposta final considerando o resultado da consulta.
        resposta = client.models.generate_content(
            model=MODELO_IA,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                max_output_tokens=500,
                temperature=0.4,
                tools=FERRAMENTAS,
            ),
        )
    except Exception as erro:
        # Loga o erro real no terminal do servidor pra facilitar diagnóstico,
        # mas devolve uma mensagem genérica pro usuário final.
        logger.exception("Erro ao chamar a API do Gemini")
        raise HTTPException(
            status_code=502,
            detail="Não foi possível falar com o serviço de IA no momento. Tente novamente em instantes.",
        ) from erro

    texto_resposta = (resposta.text or "").strip()

    if not texto_resposta:
        texto_resposta = "Não consegui gerar uma resposta agora. Pode reformular a pergunta?"

    return AssistenteResponse(resposta=texto_resposta)