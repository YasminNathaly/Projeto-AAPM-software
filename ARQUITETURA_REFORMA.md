Proposta de Reformulação e Organização do Sistema AAPM – SENAI Brás
=================================================================

Data: Agosto de 2024
Versão: 1.0
Status: IMPLEMENTADO

═════════════════════════════════════════════════════════════════════════════
SUMÁRIO EXECUTIVO
═════════════════════════════════════════════════════════════════════════════

Durante o desenvolvimento inicial, estruturamos todo o fluxo de navegação — incluindo o 
formulário de login e a visualização do painel administrativo — dentro do próprio 
arquivo base da aplicação (index.html). 

No entanto, para garantir que o projeto siga as MELHORES PRÁTICAS de arquitetura web, 
SEGURANÇA e FACILIDADE DE MANUTENÇÃO, foi necessário separar a área pública da área 
administrativa em estrutura dedica propria.

Abaixo estão os pontos que foram ajustados e como a estrutura foi reorganizada:


═════════════════════════════════════════════════════════════════════════════
1. SEPARAÇÃO DA TELA DE LOGIN (login.html)
═════════════════════════════════════════════════════════════════════════════

Localização: app/templates/login.html

ALTERAÇÃO:
  ▸ Em vez de exibir o login em uma janela modal ou dentro da mesma página base, 
    foi criado um arquivo login.html exclusivo.
  
  ▸ Esta página mantém rigorosamente a mesma identidade visual e o mesmo layout 
    base (cores primárias #d63250 e #008cff, fontes Bebas Neue + Poppins, 
    estilização moderna e a animação do canvas de fundo com partículas).
  
  ▸ Garantindo total consistência estética para o usuário final.

CARACTERÍSTICAS DA TÁ:
  ✓ Canvas interativo com animação de partículas (mesmo estilo do base.html)
  ✓ Formulário de login centrado e responsivo
  ✓ Fluxo de erro e sucesso com animações
  ✓ Redirecionamento automático para /admin após autenticação bem-sucedida
  ✓ Link para voltar à página inicial


═════════════════════════════════════════════════════════════════════════════
2. CRIAÇÃO DO PAINEL ADMINISTRATIVO NA PASTA /admin/
═════════════════════════════════════════════════════════════════════════════

Localização: app/templates/admin/admin.html

ESTRUTURA DO PAINEL:
  📍 Caminho HTTP: /admin
  📍 Arquivo: app/templates/admin/admin.html
  
RECURSOS IMPLEMENTADOS:
  ✓ Dashboard Central
    └─ Estatísticas em tempo real (Associados, Produtos, Fornecedores, Vendas)
    └─ Gráficos de tendências (Chart.js)
    └─ KPIs de performance
  
  ✓ Menu Lateral Intuitivo
    └─ Navegação entre módulos sem recarregar página
    └─ Indicadores visuais de seção ativa
    └─ Links para logout rápido
  
  ✓ Módulos de Gerenciamento
    └─ Gerencial de Associados (Usuários)
    └─ Gerencial de Produtos
    └─ Gerencial de Fornecedores
    └─ Gerencial de Categorias
    └─ Gerencial de Vendas
  
  ✓ Garantias de Segurança
    └─ Verificação de autenticação via localStorage (token JWT)
    └─ Redirecionamento automático para /login se não autenticado
    └─ Suporte a Role-Based Access Control (RBAC)

DESIGN E RESPONSIVIDADE:
  ▸ Sidebar fixa com layout em 2 colunas
  ▸ Responsividade completa para tablets e celulares
  ▸ Tema escuro consistente com a identidade visual da AAPM
  ▸ Cards informativos com ícones e cores semânticas


═════════════════════════════════════════════════════════════════════════════
3. AJUSTE DO ROTEAMENTO E FLUXO DE AUTENTICAÇÃO
═════════════════════════════════════════════════════════════════════════════

ROTAS IMPLEMENTADAS:

┌─ ROTAS PÚBLICAS
│
├─ GET  /              → Página inicial (base.html)
├─ GET  /login         → Formulário de login (NEW: login.html)
├─ GET  /visualizacao  → Página de visualização pública
│
├─ ROTAS DE API
│ ├─ POST /api/auth/login    → Autentica usuário e retorna JWT
│ ├─ POST /api/auth/logout   → Invalidação de sessão
│ ├─ POST /api/auth/registrar → Cadastro de novo usuário
│ └─ GET  /api/auth/me       → Retorna dados do usuário autenticado
│
└─ ROTAS ADMINISTRATIVAS (AUTENTICADAS)
  ├─ GET /admin                  → Painel administrativo (NEW: admin/admin.html)
  ├─ GET /api/usuarios           → Lista de associados
  ├─ GET /api/produtos           → Lista de produtos
  ├─ GET /api/fornecedores       → Lista de fornecedores
  ├─ GET /api/categorias         → Lista de categorias
  ├─ GET /api/vendas             → Lista de vendas
  └─ POST, PUT, DELETE (para cada recurso)


FLUXO DE NAVEGAÇÃO:

┌────────────────────────────────────────────────────────────────────┐
│                     USUÁRIO NÃO AUTENTICADO                        │
└────────────────────────────────────────────────────────────────────┘

    1) Usuário acessa http://sistema.com
       └─> Visualiza página Index (base.html) com opção "PAINEL ADMIN"

    2) Clica em "PAINEL ADMIN" no cabeçalho
       └─> Sistema verifica localStorage[access_token]
       └─> Token não encontrado → Redireciona para /login

    3) Preenche credenciais e clica "Acessar Painel"
       └─> Faz POST para /api/auth/login
       └─> Servidor valida email/senha contra banco de dados
       └─> Se ✓ Correto → Retorna JWT
       └─> Se ✗ Incorreto → Exibe mensagem de erro


┌────────────────────────────────────────────────────────────────────┐
│                      USUÁRIO AUTENTICADO                           │
└────────────────────────────────────────────────────────────────────┘

    1) Token armazenado em localStorage[access_token]
       └─> Acesso válido por 24 horas

    2) Nova tentativa de acesso ao /login
       └─> Sistema detecta token válido
       └─> Redireciona automaticamente para /admin

    3) Dentro do Admin
       └─> Todas as requisições incluem header: "Authorization: Bearer {token}"
       └─> Backend valida token antes de retornar dados
       └─> Acesso completo aos módulos de gerenciamento

    4) Clica em "SAIR" ou "LOGOUT"
       └─> Remove token do localStorage
       └─> Faz POST para /api/auth/logout
       └─> Redireciona para /login ou página inicial


═════════════════════════════════════════════════════════════════════════════
4. IMPLEMENTAÇÃO TÉCNICA
═════════════════════════════════════════════════════════════════════════════

ARQUIVOS CRIADOS/MODIFICADOS:

┌─ FRONTEND (HTML/CSS/JS)
│
├─ NEW: app/templates/login.html
│   └─ Formulário de autenticação com design profissional
│   └─ Validação de formulário com feedback visual
│   └─ Integração com /api/auth/login
│
├─ NEW: app/templates/admin/
│   └─ admin.html
│       └─ Interface administrativa completa
│       └─ Dashboard com gráficos interativos
│       └─ CRUD para todos os módulos
│       └─ Verificação de autenticação no carregamento
│
└─ MODIFIED: app/templates/base.html
    └─ Sem alterações no layout principal
    └─ Botão "PAINEL ADMIN" agora redireciona para /login


┌─ BACKEND (Python/FastAPI)
│
├─ NEW: app/routers/auth_router.py
│   ├─ POST /api/auth/login
│   ├─ POST /api/auth/logout
│   ├─ POST /api/auth/registrar
│   ├─ GET  /api/auth/me
│   ├─ GET  /login (retorna login.html)
│   ├─ GET  /admin (retorna admin/admin.html)
│   └─ Autenticação JWT com python-jose
│
├─ MODIFIED: main.py
│   ├─ Import do auth_router
│   ├─ app.include_router(auth_router)
│   └─ Removida rota antiga de login
│
└─ UNCHANGED: app/models/usuario.py
    └─ Campo 'senha' (não 'password')
    └─ Compatível com hash bcrypt via passlib


┌─ SEGURANÇA IMPLEMENTADA
│
├─ Hash de Senha: bcrypt (passlib)
├─ Token JWT: python-jose com algoritmo HS256
├─ Expiração de Token: 24 horas (configurável)
├─ Validação de Email e Senha: sensível a caso
├─ Proteção de Sessão: localStorage + Backend validation
└─ CORS: Configurado para requests autenticadas


═════════════════════════════════════════════════════════════════════════════
5. INSTRUÇÕES DE INSTALAÇÃO E USO
═════════════════════════════════════════════════════════════════════════════

PRÉ-REQUISITOS:
  ✓ Python 3.8+
  ✓ MySQL 5.7+
  ✓ Dependências instaladas (pip install -r requirements.txt)

DEPENDÊNCIAS NECESSÁRIAS (já devem estar em requirements.txt):
  • fastapi
  • uvicorn
  • sqlalchemy
  • pymysql
  • passlib[bcrypt]
  • python-jose[cryptography]
  • jinja2
  • python-multipart

VARIÁVEIS DE AMBIENTE (.env):
  DATABASE_URL=mysql+pymysql://usuario:senha@localhost/aapm
  SECRET_KEY=sua-chave-secreta-muito-segura-2024
  (Opcional) ACCESS_TOKEN_EXPIRE_MINUTES=1440


INICIAR O SERVIDOR:
  $ python -m uvicorn main:app --reload
  
  Server iniciará em: http://localhost:8000


CRIAR USUÁRIO ADMINISTRATIVO (seed.py):
  $ python seed.py
  
  Isso deve criar usuários de teste com senhas hasheadas


ACESSAR O SISTEMA:
  1. Abra http://localhost:8000 no navegador
  2. Clique em "PAINEL ADMIN" no cabeçalho
  3. Será redirecionado para http://localhost:8000/login
  4. Digite credenciais (ex: admin@aapm.com / senha123)
  5. Será redirecionado para http://localhost:8000/admin
  6. Acesso completo ao painel administrativo


═════════════════════════════════════════════════════════════════════════════
6. ESTRUTURA FINAL DE PASTAS
═════════════════════════════════════════════════════════════════════════════

Projeto-AAPM-software/
├── app/
│   ├── models/
│   │   ├── usuario.py          ✓ Sem alterações
│   │   ├── produto.py          ✓ Sem alterações
│   │   ├── categoria.py        ✓ Sem alterações
│   │   ├── fornecedor.py       ✓ Sem alterações
│   │   ├── venda.py            ✓ Sem alterações
│   │   └── variacao.py         ✓ Sem alterações
│   │
│   ├── routers/
│   │   ├── auth_router.py      ✨ NEW (autenticação completa)
│   │   ├── categoria_router.py ✓ Sem alterações
│   │   ├── produto_router.py   ✓ Sem alterações
│   │   └── ... (outros routers)
│   │
│   ├── templates/
│   │   ├── base.html                 ✓ Sem alterações
│   │   ├── login.html                ✨ NEW (formulário de login)
│   │   ├── admin/
│   │   │   └── admin.html            ✨ NEW (painel administrativo)
│   │   ├── public/
│   │   │   └── 404.html              ✓ Sem alterações
│   │   └── ... (outros templates)
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css             ✓ Sem alterações
│   │   └── js/
│   │       └── script.js             ✓ Sem alterações
│   │
│   └── database.py                   ✓ Sem alterações
│
├── main.py                           ✨ UPDATED (import auth_router)
├── requirements.txt                  ✓ Sem alterações necessárias
├── seed.py                           ✓ Sem alterações necessárias
└── README.md


═════════════════════════════════════════════════════════════════════════════
7. TRATAMENTO DE ERROS E EXCEÇÕES
═════════════════════════════════════════════════════════════════════════════

LOGIN FALHADO (Credenciais Inválidas):
  Status: 401 Unauthorized
  Resposta:
    {
      "detail": "E-mail ou senha incorretos"
    }

USUÁRIO INATIVO:
  Status: 403 Forbidden
  Resposta:
    {
      "detail": "Usuário inativo. Contacte a administração."
    }

TOKEN EXPIRADO:
  Status: 401 Unauthorized
  Resposta:
    {
      "detail": "Token expirado"
    }

TOKEN INVÁLIDO:
  Status: 401 Unauthorized
  Resposta:
    {
      "detail": "Token inválido"
    }

ACESSO NÃO AUTENTICADO A /admin:
  Ação: Redirecionamento automático para /login (via JavaScript no frontend)


═════════════════════════════════════════════════════════════════════════════
8. CONFORMIDADE COM MELHORES PRÁTICAS
═════════════════════════════════════════════════════════════════════════════

✅ SEGURANÇA
  ├─ Hash de senha com bcrypt
  ├─ JWT tokens com expiração
  ├─ Validação de entrada (Pydantic schemas)
  ├─ Proteção contra SQL Injection (ORM SQLAlchemy)
  ├─ HTTPS ready (configurável em produção)
  └─ Headers de segurança (recomendado: CORS, CSP)

✅ USABILIDADE
  ├─ Navegação intuitiva
  ├─ Design responsivo (Desktop, Tablet, Mobile)
  ├─ Consistência visual entre páginas
  ├─ Feedback visual (carregamento, erro, sucesso)
  └─ Acessibilidade básica (alt text, labels)

✅ MANUTENIBILIDADE
  ├─ Separação de responsabilidades (MVC)
  ├─ Código modular e reutilizável
  ├─ Documentação inline
  ├─ Nomes significativos para variáveis e funções
  └─ Estrutura escalável para novos módulos

✅ PERFORMANCE
  ├─ Cache no navegador (localStorage)
  ├─ Gráficos otimizados (Chart.js)
  ├─ Lazy loading de dados
  └─ Requisições HTTP otimizadas


═════════════════════════════════════════════════════════════════════════════
9. PRÓXIMOS PASSOS RECOMENDADOS
═════════════════════════════════════════════════════════════════════════════

FASE 2 - APRIMORAMENTOS:
  □ Implementar 2FA (Two-Factor Authentication)
  □ Adicionar logs de auditoria (quem fez o quê e quando)
  □ Implementar rate limiting para prevenção de brute force
  □ Integração com OAuth2 (Google, Microsoft)
  □ Dashboard com relatórios em PDF/Excel

FASE 3 - INTEGRAÇÕES:
  □ API de notificações (Email, WhatsApp)
  □ Sistema de backup automático
  □ Sync com sistemas externos (ERP, CRM)
  □ Mobile app nativa

FASE 4 - MONITORAMENTO:
  □ Setup de logs centralizados (ELK Stack)
  □ Monitoramento de performance (New Relic, DataDog)
  □ Alertas de segurança
  □ Testes de carga e stress


═════════════════════════════════════════════════════════════════════════════
10. CONTATO E SUPORTE
═════════════════════════════════════════════════════════════════════════════

Para dúvidas sobre a implementação:
  Dashboard: http://localhost:8000/admin
  Página de Login: http://localhost:8000/login
  Documentação da API: http://localhost:8000/docs

Erros conhecidos ou sugestões: Contactar time de desenvolvimento


═════════════════════════════════════════════════════════════════════════════
FIM DO DOCUMENTO
═════════════════════════════════════════════════════════════════════════════

Versão: 1.0
Última atualização: Agosto, 2024
Responsável: Desenvolvimento AAPM
