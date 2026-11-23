# 🏫 Sistema AAPM — Escola SENAI "Francisco Matarazzo" (Brás)

Plataforma web completa desenvolvida para a **Associação de Pais e Mestres (AAPM)** da **Escola SENAI "Francisco Matarazzo" – Brás (São Paulo/SP)**. O sistema reúne loja virtual para alunos e colaboradores, checkout com pagamento **PIX automatizado (QR Code + EMV Copia e Cola + Webhook com baixa de estoque)**, gestão de armários, cadastro e filtragem de associados, controle de fornecedores e painel administrativo completo.

---

## ✨ Funcionalidades Principais

### 🛍️ Vitrine Pública & Carrinho Inteligente
- **Catálogo Dinâmico (`produtos` e `variacao`):** Exibição dos itens com imagens vinculadas (`/static/assets/` e `/static/uploads/`), preços, filtros por categoria, tamanhos e chips de estoque por variação.
- **Carrinho Lateral Interativo:** Controle de quantidade (1 unidade por clique, com trava automática no limite máximo de estoque disponível), cálculo automático de subtotal e opção de envio direto pelo WhatsApp ou pagamento via PIX.

### 💸 Checkout PIX Automatizado + Baixa Real de Estoque
- **Geração de PIX Padrão EMV (`checkout_pix_router.py`):** Valida o estoque de cada item antes de fechar o pedido, registra a venda como `"Pendente PIX"` e gera o código **PIX Copia e Cola** junto com o **QR Code dinâmico**.
- **Monitoramento & Webhook em Tempo Real:** O modal acompanha o status do pagamento automaticamente a cada 2,5 segundos (`GET /api/checkout/pix/{venda_id}`) e, assim que confirmado (`POST /api/checkout/pix/webhook`), marca a venda como **Concluída**, desconta os itens do estoque principal e da variação (com proteção contra baixa duplicada) e exibe o comprovante aprovado.

### 📊 Painel Administrativo (`/dashboard`)
- **Gestão Completa:** Controle de produtos, upload de imagens (`POST /api/upload-imagem`), categorias, variações/SKU, fornecedores, vendas com múltiplos itens (`itens_venda`), armários e associados.
- **Busca & Filtros de Associados:** Pesquisa rápida e filtragem por status (*Todos*, *Ativos*, *Inativos*).

### 🌓 Design Adaptativo & ♿ Acessibilidade Inclusiva (WCAG)
- **Modo Claro & Modo Escuro:** Alternância instantânea de tema com fotografia real da fachada da unidade SENAI Brás (`fachada-senai.jpg`) e contraste ajustado automaticamente para nitidez dos textos.
- **Menu Flutuante de Acessibilidade:** Controle para aumentar ou diminuir o tamanho da fonte (`A+` / `A-`), ativar **Alto Contraste** e restaurar o padrão, salvando a preferência do usuário no navegador.
- **Navegação por Teclado & Leitores de Tela:** Atalho *"Pular para o conteúdo principal"*, navegação completa via `Tab` e `Enter`, fechamento de modais com `Esc`, atributos `ARIA labels`, descrições `alt` nas imagens e respeito a `prefers-reduced-motion`.

---

## 🏆 Auditoria de Qualidade (Google Lighthouse)

O sistema foi avaliado pelo **Google Lighthouse** e conquistou nota máxima (faixa verde) em todos os critérios:

| Categoria | Pontuação | Nota Equivalente |
| :--- | :---: | :---: |
| ⚡ **Desempenho (Performance)** | **98 / 100** | **9,8 / 10** |
| ♿ **Acessibilidade (Accessibility)** | **98 / 100** | **9,8 / 10** |
| 🛡️ **Práticas Recomendadas (Best Practices)** | **96 / 100** | **9,6 / 10** |
| 🔍 **SEO** | **90 / 100** | **9,0 / 10** |

---

## 📚 Bibliotecas e Tecnologias Utilizadas (O que cada uma faz)

### Back-end, Banco de Dados & Segurança (Python)
- **`fastapi`**: Framework web principal responsável por toda a arquitetura de rotas, APIs REST e renderização das páginas.
- **`uvicorn`**: Servidor web ASGI de alta performance que executa a aplicação FastAPI localmente ou em produção.
- **`sqlalchemy`**: ORM utilizado para modelar e gerenciar todas as tabelas do banco de dados (`Produto`, `Variacao`, `Categoria`, `Usuario`, `Fornecedor`, `Venda`, `ItemVenda`, `Associado`, `Armario`).
- **SQLite (`aapm.db`)**: Banco de dados relacional leve e integrado ao projeto, sem necessidade de servidor externo.
- **`jinja2`**: Motor de templates usado para renderizar o front-end (`base.html` e `admin/admin.html`) com dados dinâmicos do servidor.
- **`bcrypt` & `passlib[bcrypt]`**: Criptografia de senhas para autenticação segura dos administradores (`app/auth_utils.py`).
- **`pydantic[email]`**: Validação rigorosa de dados de entrada e saída nas rotas da API, incluindo verificação de e-mails.
- **`python-dotenv`**: Leitura de variáveis de ambiente e credenciais administrativas a partir do arquivo `.env`.
- **`python-multipart`**: Suporte para formulários HTML e upload de fotos de produtos (`UploadFile`).

### Front-end & Testes
- **HTML5 Semântico, CSS3 & JavaScript Vanilla**: Interface responsiva com variáveis CSS dinâmicas, tema claro/escuro, carrinho lateral, modal PIX e widget de acessibilidade.
- **Playwright / Pytest (`tests/`)**: Suíte de testes automatizados para validar fluxos da interface.

---

## 📁 Arquitetura e Estrutura do Projeto

```text
Projeto-AAPM-software/
├── app/
│   ├── controllers/            # Regras de negócio (produto, usuario, venda, etc.)
│   ├── models/                 # Modelos SQLAlchemy (produto, variacao, venda, associado, armario...)
│   ├── routers/                # Módulos de rotas (auth, produto, categoria, fornecedor, variacao, venda, associado, armario, assistente, checkout_pix)
│   ├── schemas/                # Esquemas Pydantic de validação (produto_schema.py, etc.)
│   ├── static/
│   │   ├── assets/             # Ícones SVG dos produtos, logo SENAI e foto da fachada (fachada-senai.jpg)
│   │   ├── css/                # Estilos globais e temas
│   │   ├── js/                 # Scripts de carrinho, filtros e interatividade
│   │   └── uploads/            # Imagens enviadas pelo painel administrativo
│   ├── templates/
│   │   ├── admin/admin.html    # Painel administrativo (/dashboard)
│   │   └── base.html           # Vitrine pública, modais (Carrinho, PIX) e widget de acessibilidade
│   ├── auth_utils.py           # Utilitários de hash e verificação de senha com bcrypt
│   └── database.py             # Conexão SQLAlchemy (engine, Base, get_db)
├── tests/                      # Testes automatizados da aplicação
├── aapm.db                     # Banco de dados SQLite
├── main.py                     # Ponto de entrada FastAPI (inicialização, CORS, static e routers)
└── README.md                   # Documentação completa do projeto