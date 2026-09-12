// admin.html
  const token = localStorage.getItem('access_token');
  let sessaoInicialValida = Boolean(token);
  if (!token) {
    window.location.href = '/login';
  }

    // ROTAS DO BACKEND / API
    const API_URLS = {
      categoria: '/api/categorias',
      fornecedor: '/api/fornecedores',
      produto: '/api/produtos',
      associado: '/api/associados',
      armario: '/api/armarios',
      usuario: '/api/usuarios',
      venda: '/api/vendas',
      upload: '/api/upload-imagem'
    };

    async function validarSessaoInicial() {
      if (!sessaoInicialValida) return false;
      try {
        const resposta = await fetch('/api/auth/me', {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        if (!resposta.ok) throw new Error('Sessão inválida');
        return true;
      } catch (erro) {
        localStorage.removeItem('access_token');
        sessionStorage.clear();
        window.location.href = '/login';
        return false;
      }
    }

    // ================================================================== //
    // ===== CAMADA DE SEGURANÇA (auth + XSS) =====                        //
    // ================================================================== //

    async function apiFetch(url, options = {}) {
      const tokenAtual = localStorage.getItem('access_token');
      const headers = {
        ...(options.headers || {}),
        ...(tokenAtual ? { 'Authorization': `Bearer ${tokenAtual}` } : {})
      };

      const resposta = await fetch(url, { ...options, headers });

      if (resposta.status === 401 || resposta.status === 403) {
        localStorage.removeItem('access_token');
        mostrarToast('Sessão expirada. Faça login novamente.', 'error');
        setTimeout(() => { window.location.href = 'login.html'; }, 1200);
        throw new Error('Não autenticado');
      }

      return resposta;
    }

    function escapeHTML(valor) {
      if (valor === null || valor === undefined) return '';
      return String(valor)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    const formatadorMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
    function formatarMoeda(valor) {
      const numero = Number(valor);
      return formatadorMoeda.format(isNaN(numero) ? 0 : numero);
    }

    function confirmarAcao(mensagem, tituloBotaoConfirmar = 'Confirmar') {
      return new Promise((resolve) => {
        const overlay = document.getElementById('confirmModalOverlay');
        const textoEl = document.getElementById('confirmModalTexto');
        const btnOk = document.getElementById('confirmModalOk');
        const btnCancelar = document.getElementById('confirmModalCancelar');

        textoEl.textContent = mensagem;
        btnOk.textContent = tituloBotaoConfirmar;
        overlay.classList.add('open');
        abrirModalComFoco(overlay, btnCancelar);

        function limpar(resultado) {
          fecharModalComFoco(overlay);
          btnOk.removeEventListener('click', onOk);
          btnCancelar.removeEventListener('click', onCancelar);
          resolve(resultado);
        }
        function onOk() { limpar(true); }
        function onCancelar() { limpar(false); }

        btnOk.addEventListener('click', onOk);
        btnCancelar.addEventListener('click', onCancelar);
      });
    }

    // ===== FOCUS TRAP GENÉRICO PARA MODAIS =====
    // Guarda o elemento que tinha foco antes de abrir o modal (pra devolver
    // o foco a ele ao fechar) e prende o Tab dentro do modal enquanto ele
    // estiver aberto, evitando que o teclado "vaze" para o conteúdo de trás.
    let elementoComFocoAnterior = null;

    function getFocaveis(container) {
      return [...container.querySelectorAll(
        'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'
      )].filter((el) => el.offsetParent !== null);
    }

    function trapFocusHandler(e) {
      if (e.key !== 'Tab') return;
      const modalAberto = document.querySelector('.detail-overlay.open, .command-palette-overlay.open');
      if (!modalAberto) return;
      const focaveis = getFocaveis(modalAberto);
      if (!focaveis.length) return;
      const primeiro = focaveis[0];
      const ultimo = focaveis[focaveis.length - 1];

      if (e.shiftKey && document.activeElement === primeiro) {
        e.preventDefault();
        ultimo.focus();
      } else if (!e.shiftKey && document.activeElement === ultimo) {
        e.preventDefault();
        primeiro.focus();
      }
    }
    document.addEventListener('keydown', trapFocusHandler);

    function abrirModalComFoco(overlay, elementoParaFocar) {
      elementoComFocoAnterior = document.activeElement;
      const alvo = elementoParaFocar || getFocaveis(overlay)[0];
      setTimeout(() => alvo?.focus(), 60);
    }

    function fecharModalComFoco(overlay) {
      overlay.classList.remove('open');
      if (elementoComFocoAnterior && document.body.contains(elementoComFocoAnterior)) {
        elementoComFocoAnterior.focus();
      }
      elementoComFocoAnterior = null;
    }

    // BASES DE DADOS (carregadas via API do Banco)
    let categorias = [];
    let fornecedores = [];
    let produtos = [];
    let associados = [];
    let armarios = [];
    let usuarios = [];
    let vendas = [];
    let imagemProdutoPendente = null;

    const ITENS_POR_PAGINA = 10;
    let paginaAtual = {
      categoria: 1,
      fornecedor: 1,
      produto: 1,
      associado: 1,
      armario: 1,
      usuario: 1,
      venda: 1,
      relatorio: 1
    };

    // ===== BUSCA POR MÓDULO (corrige o filtro que só olhava a página atual) =====
    // Cada módulo guarda seu termo de busca aqui. filtrarTabelaAtiva() agora
    // filtra a LISTA COMPLETA do módulo ativo (não só as 10 linhas already
    // renderizadas), reseta a paginação pra página 1 e só então re-renderiza —
    // assim um item que está na página 3 aparece normalmente ao ser buscado.
    let termoBuscaPorModulo = {};

    function textoDoItemParaBusca(viewId, item) {
      switch (viewId) {
        case 'categoria': return [item.codigo, item.nome, item.descricao].join(' ');
        case 'fornecedor': return [item.nome, item.documento, item.email, item.telefone].join(' ');
        case 'produto': return [item.nome, nomeCategoriaPorId(item.categoria_id), item.tamanho].join(' ');
        case 'associado': return [item.nome, item.email, item.telefone, item.endereco].join(' ');
        case 'armario': return [item.numero, item.localizacao, item.status, item.nome_completo].join(' ');
        case 'usuario': return [item.nome, item.email, item.perfil].join(' ');
        case 'venda': return [item.comprador || item.cliente, item.produto_nome, item.forma_pagamento].join(' ');
        case 'relatorio': return [item.tipo, item.titulo, item.sub].join(' ');
        default: return '';
      }
    }

    function listaBaseDoModulo(viewId) {
      switch (viewId) {
        case 'categoria': return categorias;
        case 'fornecedor': return fornecedores;
        case 'produto': return produtos;
        case 'associado': return associados;
        case 'armario': return armarios;
        case 'usuario': return usuarios;
        case 'venda': return vendas;
        case 'relatorio': return carregarRelatorioNotificacoes();
        default: return [];
      }
    }

    function filtrarTabelaAtiva() {
      const termo = document.getElementById('tableSearch').value.trim().toLowerCase();
      const active = document.querySelector('.view-content.active');
      if (!active) return;
      const viewId = active.id;

      termoBuscaPorModulo[viewId] = termo;
      paginaAtual[viewId] = 1;

      if (renderizadoresPorModulo[viewId]) renderizadoresPorModulo[viewId]();
    }

    function aplicarBusca(viewId, lista) {
      const termo = (termoBuscaPorModulo[viewId] || '').trim().toLowerCase();
      if (!termo) return lista;
      return lista.filter((item) => textoDoItemParaBusca(viewId, item).toLowerCase().includes(termo));
    }

    // MEXI AQUI: TOASTS DE FEEDBACK (sucesso / erro) PARA TODOS OS CRUDS
    const modulosConfig = {
      categoria: { nome: 'Categoria', genero: 'f' },
      fornecedor: { nome: 'Fornecedor', genero: 'm' },
      produto: { nome: 'Produto', genero: 'm' },
      associado: { nome: 'Associado', genero: 'm' },
      armario: { nome: 'Armário', genero: 'm' },
      usuario: { nome: 'Usuário', genero: 'm' },
      venda: { nome: 'Venda', genero: 'f' }
    };

    const acoesTexto = {
      criar: { m: 'adicionado', f: 'adicionada' },
      editar: { m: 'atualizado', f: 'atualizada' },
      remover: { m: 'removido', f: 'removida' }
    };

    function mensagemSucesso(endpointKey, acao) {
      const cfg = modulosConfig[endpointKey];
      if (!cfg) return 'Operação realizada com sucesso!';
      if (endpointKey === 'venda' && acao === 'criar') return 'Venda registrada com sucesso!';
      const texto = (acoesTexto[acao] && acoesTexto[acao][cfg.genero]) || 'processado';
      return `${cfg.nome} ${texto} com sucesso!`;
    }

    const toastIcons = {
      success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
      error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><line x1="12" y1="8" x2="12" y2="13"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
      warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    };

    function mostrarToast(mensagem, tipo = 'success', sub = '') {
      const container = document.getElementById('toastContainer');
      if (!container) return;

      const toast = document.createElement('div');
      toast.className = 'toast' + (tipo !== 'success' ? ' ' + tipo : '');
      toast.innerHTML = `
        <div class="toast-icon">${toastIcons[tipo] || toastIcons.success}</div>
        <div class="toast-text">
          <div class="toast-title">${escapeHTML(mensagem)}</div>
          ${sub ? `<div class="toast-sub">${escapeHTML(sub)}</div>` : ''}
        </div>
        <div class="toast-close" title="Fechar">
          <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </div>
      `;

      const fecharToast = () => {
        toast.classList.remove('show');
        toast.classList.add('hide');
        setTimeout(() => toast.remove(), 450);
      };

      toast.querySelector('.toast-close').addEventListener('click', fecharToast);
      container.appendChild(toast);

      requestAnimationFrame(() => requestAnimationFrame(() => toast.classList.add('show')));

      setTimeout(fecharToast, 4200);
    }

    function renderPaginacaoControles(containerId, chave, totalItens) {
      const el = document.getElementById(containerId);
      if (!el) return;

      const totalPaginas = Math.max(1, Math.ceil(totalItens / ITENS_POR_PAGINA));
      if (paginaAtual[chave] > totalPaginas) paginaAtual[chave] = totalPaginas;
      if (paginaAtual[chave] < 1) paginaAtual[chave] = 1;
      const atual = paginaAtual[chave];

      if (!totalItens) { el.innerHTML = ''; return; }

      el.innerHTML = `
        ${atual > 1
          ? `<a href="#" class="btn-paginacao" onclick="mudarPagina('${chave}', ${atual - 1}); return false;">Anterior</a>`
          : `<span class="btn-paginacao desativado">Anterior</span>`}
        <span>Página <strong>${atual}</strong> de <strong>${totalPaginas}</strong> (Total de ${totalItens} itens)</span>
        ${atual < totalPaginas
          ? `<a href="#" class="btn-paginacao" onclick="mudarPagina('${chave}', ${atual + 1}); return false;">Próximo</a>`
          : `<span class="btn-paginacao desativado">Próximo</span>`}
      `;
    }

    const renderizadoresPorModulo = {};
    function mudarPagina(chave, novaPagina) {
      paginaAtual[chave] = novaPagina;
      if (renderizadoresPorModulo[chave]) renderizadoresPorModulo[chave]();
    }

    function paginarLista(lista, chave) {
      const totalPaginas = Math.max(1, Math.ceil(lista.length / ITENS_POR_PAGINA));
      if (paginaAtual[chave] > totalPaginas) paginaAtual[chave] = totalPaginas;
      if (paginaAtual[chave] < 1) paginaAtual[chave] = 1;
      const inicio = (paginaAtual[chave] - 1) * ITENS_POR_PAGINA;
      return lista.slice(inicio, inicio + ITENS_POR_PAGINA);
    }

    function normalizarProduto(p) {
      return {
        ...p,
        variacoes: p.variacoes || p.variantes || p.variations || [],
        quantidade: p.quantidade ?? p.estoque ?? 0
      };
    }

    function normalizarArmario(a) {
      return {
        ...a,
        status: a.status || 'Disponível',
        nome_completo: a.nome_completo || null
      };
    }

    function normalizarVenda(v) {
      return {
        ...v,
        associado_id: v.associado_id ?? null,
        desconto_percentual: v.desconto_percentual ?? 0,
        pagamentos: Array.isArray(v.pagamentos) ? v.pagamentos : []
      };
    }

    // ===== CONTROLADOR DE CARREGAMENTO (GET DE TODAS AS ENTIDADES) =====
    // Usado no boot inicial e como fallback caso uma atualização otimista
    // precise ser reconciliada com o servidor (ex.: erro inesperado).
    async function carregarDadosDoBanco() {
      const loadingText = document.querySelector('#adminLoading p');
      if (loadingText) loadingText.innerText = 'Carregando dados...';
      document.body.classList.add('data-loading');
      try {
        const [resCat, resForn, resProd, resAssoc, resArm, resUsr, resVnd] = await Promise.all([
          apiFetch(API_URLS.categoria),
          apiFetch(API_URLS.fornecedor),
          apiFetch(API_URLS.produto),
          apiFetch(API_URLS.associado),
          apiFetch(API_URLS.armario),
          apiFetch(API_URLS.usuario),
          apiFetch(API_URLS.venda)
        ]);

        categorias = resCat.ok ? await resCat.json() : [];
        fornecedores = resForn.ok ? await resForn.json() : [];
        produtos = resProd.ok ? (await resProd.json()).map(normalizarProduto) : [];
        associados = resAssoc.ok ? await resAssoc.json() : [];
        armarios = resArm.ok ? (await resArm.json()).map(normalizarArmario) : [];
        usuarios = resUsr.ok ? await resUsr.json() : [];
        vendas = resVnd.ok ? (await resVnd.json()).map(normalizarVenda) : [];

        renderTudo();
      } catch (erro) {
        console.error('Erro ao conectar e buscar dados do Banco de Dados:', erro);
        mostrarToast('Não foi possível carregar os dados do painel.', 'error', 'Verifique a conexão com o servidor.');
      } finally {
        document.body.classList.remove('data-loading');
      }
    }

    // Re-renderiza tudo que depende do estado global (usado após o load
    // completo e também depois de uma atualização otimista de um único item).
    function renderTudo() {
      renderCategorias();
      renderFornecedores();
      renderProdutos();
      renderAssociados();
      renderArmarios();
      renderUsuarios();
      renderVendas();
      popularSelectsDinamicos();
      renderNotificacoes();
      renderRelatorio();
      renderRelatorioVendas();
      renderDashboard();

      const active = document.querySelector('.view-content.active');
      const activeId = active ? active.id : 'categoria';
      renderStatsBar(activeId);
      renderRecentList(activeId);
    }

    // MEXI AQUI: agora popula também o filtro de categoria da venda e o
    // datalist de busca de produto (com filtro por categoria aplicado).
    function popularSelectsDinamicos() {
      const selCategoria = document.getElementById('prodCategoria');
      const valorAtualCat = selCategoria.value;
      selCategoria.innerHTML = '<option value="">Selecione...</option>' +
        categorias.map(c => `<option value="${escapeHTML(c.id)}">${escapeHTML(c.nome)}</option>`).join('');
      if (valorAtualCat) selCategoria.value = valorAtualCat;

      const selProduto = document.getElementById('vendaProduto');
      const buscaProduto = document.getElementById('vendaProdutoBusca');
      const listaProduto = document.getElementById('vendaProdutoList');
      const filtroCategoria = document.getElementById('vendaFiltroCategoria');

      if (filtroCategoria) {
        const valorAtualFiltro = filtroCategoria.value;
        filtroCategoria.innerHTML = '<option value="">Todas as categorias</option>' +
          categorias.map(c => `<option value="${escapeHTML(c.id)}">${escapeHTML(c.nome)}</option>`).join('');
        if (valorAtualFiltro) filtroCategoria.value = valorAtualFiltro;
      }

      if (listaProduto && selProduto) {
        const valorAtualProdId = selProduto.value;
        const categoriaFiltro = filtroCategoria ? filtroCategoria.value : '';
        const produtosFiltrados = categoriaFiltro
          ? produtos.filter(p => String(p.categoria_id) === String(categoriaFiltro))
          : produtos;

        listaProduto.innerHTML = produtosFiltrados.map(p =>
          `<option data-id="${escapeHTML(p.id)}" value="${escapeHTML(p.nome)} (${formatarMoeda(p.preco)})"></option>`
        ).join('');

        // Se o produto atualmente selecionado ficou fora do filtro de
        // categoria, limpa a seleção pra não deixar um produto "invisível"
        // escolhido. Se ainda estiver visível, mantém o texto sincronizado
        // (útil ao editar uma venda, por exemplo).
        const aindaVisivel = produtosFiltrados.some(p => String(p.id) === String(valorAtualProdId));
        if (valorAtualProdId && aindaVisivel) {
          const p = produtos.find(pr => String(pr.id) === String(valorAtualProdId));
          if (p && buscaProduto) buscaProduto.value = `${p.nome} (${formatarMoeda(p.preco)})`;
          selProduto.value = valorAtualProdId;
        } else if (valorAtualProdId && !aindaVisivel) {
          selProduto.value = '';
          if (buscaProduto) buscaProduto.value = '';
          atualizarResumoVenda();
        }
      }

      const selAssociado = document.getElementById('vendaAssociado');
      if (selAssociado) {
        const valorAtualAssoc = selAssociado.value;
        selAssociado.innerHTML = '<option value="">Não é associado</option>' +
          associados.map(a => `<option value="${escapeHTML(a.id)}">${escapeHTML(a.nome)}</option>`).join('');
        if (valorAtualAssoc) selAssociado.value = valorAtualAssoc;
      }
    }

    // ===== BUSCA DE PRODUTO POR TEXTO (datalist) → resolve pro ID real =====
    function resolverProdutoBusca() {
      const busca = document.getElementById('vendaProdutoBusca');
      const hiddenId = document.getElementById('vendaProduto');
      const listaProduto = document.getElementById('vendaProdutoList');
      const texto = busca.value.trim();

      const opcoes = listaProduto ? Array.from(listaProduto.options) : [];
      const match = opcoes.find(o => o.value === texto);

      hiddenId.value = match ? match.dataset.id : '';
      atualizarResumoVenda();
    }

    // ===== NOTIFICAÇÕES DINÂMICAS (sempre a partir dos dados reais) =====
    const notificacoesIcones = {
      venda: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="21" r="1"/><circle cx="19" cy="21" r="1"/><path d="M3 4h2l2.4 12.2a2 2 0 0 0 2 1.8h7.2a2 2 0 0 0 2-1.6L21 8H6"/></svg>',
      produto: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 8 12 3 3 8v8l9 5 9-5V8Z"/><path d="M3 8l9 5 9-5"/><path d="M12 13v8"/></svg>',
      associado: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
      armario: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="2" width="16" height="20" rx="2"/><line x1="12" y1="2" x2="12" y2="22"/><line x1="7" y1="6" x2="9" y2="6"/><line x1="15" y1="6" x2="17" y2="6"/><circle cx="8" cy="12" r="1"/><circle cx="16" cy="12" r="1"/></svg>',
      usuario: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21c0-4.4 3.6-8 8-8s8 3.6 8 8"/></svg>',
      categoria: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10V6a2 2 0 0 0-2-2h-4L3 15l6 6 11-11Z"/><circle cx="8.5" cy="8.5" r="1.2"/></svg>',
      fornecedor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21V9l9-6 9 6v12"/><path d="M9 21v-8h6v8"/></svg>'
    };

    // ===== RELATÓRIO DE NOTIFICAÇÕES LIDAS (persistido no localStorage) =====
    const CHAVE_RELATORIO_NOTIF = 'aapm_relatorio_notificacoes';

    function idNotificacao(n) {
      return `${n.tipo}-${n.ordem}`;
    }

    function carregarRelatorioNotificacoes() {
      try {
        return JSON.parse(localStorage.getItem(CHAVE_RELATORIO_NOTIF)) || [];
      } catch {
        return [];
      }
    }

    function salvarRelatorioNotificacoes(lista) {
      localStorage.setItem(CHAVE_RELATORIO_NOTIF, JSON.stringify(lista));
    }

    function marcarNotificacaoComoLida(n) {
      const relatorio = carregarRelatorioNotificacoes();
      const id = idNotificacao(n);
      if (relatorio.some(r => r.id === id)) return;

      relatorio.unshift({
        id,
        tipo: n.tipo,
        titulo: n.titulo,
        sub: n.sub,
        lidoEm: new Date().toISOString()
      });
      salvarRelatorioNotificacoes(relatorio);
      renderNotificacoes();
      if (document.querySelector('.view-content.active')?.id === 'relatorio') renderRelatorio();
    }

    function marcarTodasNotificacoesComoLidas(e) {
      if (e) e.stopPropagation();
      const notificacoes = montarNotificacoes();
      if (!notificacoes.length) return;
      notificacoes.forEach(n => marcarNotificacaoComoLida(n));
      mostrarToast('Todas as notificações foram marcadas como lidas.', 'success');
    }

    async function limparRelatorioNotificacoes() {
      const confirmado = await confirmarAcao('Deseja apagar todo o histórico do relatório de notificações?', 'Limpar');
      if (!confirmado) return;
      salvarRelatorioNotificacoes([]);
      renderRelatorio();
      mostrarToast('Relatório limpo com sucesso!', 'success');
    }

    function removerEntradaRelatorio(id) {
      const relatorio = carregarRelatorioNotificacoes().filter(r => r.id !== id);
      salvarRelatorioNotificacoes(relatorio);
      renderRelatorio();
    }

    function renderRelatorio() {
      const tbody = document.getElementById('tblRelatorio');
      if (!tbody) return;
      const relatorio = aplicarBusca('relatorio', carregarRelatorioNotificacoes());
      const pagina = paginarLista(relatorio, 'relatorio');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td><span class="pill-badge">${escapeHTML(item.tipo)}</span></td>
          <td style="font-weight:700;">${escapeHTML(item.titulo)}</td>
          <td>${escapeHTML(item.sub) || '-'}</td>
          <td>${escapeHTML(new Date(item.lidoEm).toLocaleString('pt-BR'))}</td>
          <td>
            <div class="action-btn-group">
              <button class="action-btn danger" title="Remover do relatório" onclick="removerEntradaRelatorio('${item.id}')">
                <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhuma notificação lida ainda.');
      renderPaginacaoControles('pagRelatorio', 'relatorio', relatorio.length);
    }

    function montarNotificacoes() {
      const lidas = new Set(carregarRelatorioNotificacoes().map(r => r.id));
      const itens = [];
      vendas.slice(0, 3).forEach(v => itens.push({ tipo: 'venda', titulo: 'Nova venda registrada', sub: `${v.produto_nome} · ${v.data_venda || ''}`, ordem: v.id }));
      produtos.slice(-2).reverse().forEach(p => itens.push({ tipo: 'produto', titulo: 'Produto cadastrado', sub: p.nome, ordem: p.id }));
      associados.slice(-2).reverse().forEach(a => itens.push({ tipo: 'associado', titulo: 'Associado cadastrado', sub: a.nome, ordem: a.id }));
      armarios.slice(-2).reverse().forEach(a => itens.push({ tipo: 'armario', titulo: 'Armário cadastrado', sub: `Nº ${a.numero} · ${a.status}`, ordem: a.id }));
      usuarios.slice(-2).reverse().forEach(u => itens.push({ tipo: 'usuario', titulo: 'Novo usuário cadastrado', sub: u.nome, ordem: u.id }));
      categorias.slice(-1).reverse().forEach(c => itens.push({ tipo: 'categoria', titulo: 'Categoria cadastrada', sub: c.nome, ordem: c.id }));
      fornecedores.slice(-1).reverse().forEach(f => itens.push({ tipo: 'fornecedor', titulo: 'Fornecedor cadastrado', sub: f.nome, ordem: f.id }));
      return itens
        .filter(n => !lidas.has(idNotificacao(n)))
        .sort((a, b) => (b.ordem || 0) - (a.ordem || 0))
        .slice(0, 6);
    }

    // MEXI AQUI: notificações não vão mais via onclick com JSON inline
    // (era frágil — qualquer aspas/caractere especial no título/sub podia
    // quebrar o atributo). Agora guardamos os objetos num Map por id e o
    // clique é tratado por delegação de evento lendo apenas data-notif-id.
    const notificacoesPorId = new Map();

    function renderNotificacoes() {
      const list = document.getElementById('notifList');
      const dot = document.querySelector('.notif-dot');
      const notificacoes = montarNotificacoes();
      notificacoesPorId.clear();
      notificacoes.forEach(n => notificacoesPorId.set(idNotificacao(n), n));

      list.innerHTML = notificacoes.length ? notificacoes.map(n => `
        <div class="notif-item" style="cursor:pointer;" title="Clique para marcar como lida" data-notif-id="${escapeHTML(idNotificacao(n))}">
          <div class="ni-icon">${notificacoesIcones[n.tipo] || notificacoesIcones.venda}</div>
          <div>
            <div class="ni-title">${escapeHTML(n.titulo)}</div>
            <div class="ni-time">${escapeHTML(n.sub)}</div>
          </div>
        </div>
      `).join('') : '<div class="recent-empty">Nenhuma notificação nova.</div>';
      if (dot) dot.style.display = notificacoes.length ? 'block' : 'none';
    }

    document.getElementById('notifList')?.addEventListener('click', (e) => {
      const item = e.target.closest('[data-notif-id]');
      if (!item) return;
      const n = notificacoesPorId.get(item.dataset.notifId);
      if (n) marcarNotificacaoComoLida(n);
    });

    function toggleNotifications(e, forceClose) {
      if (e) e.stopPropagation();
      const panel = document.getElementById('notifPanel');
      if (forceClose) { panel.classList.remove('open'); return; }
      panel.classList.toggle('open');
    }

    document.addEventListener('click', (e) => {
      const panel = document.getElementById('notifPanel');
      const wrapper = document.getElementById('notifWrapper');
      if (panel && wrapper && panel.classList.contains('open') && !wrapper.contains(e.target)) {
        panel.classList.remove('open');
      }
    });

    function handleAvatarUpload(e) {
      const file = e.target.files && e.target.files[0];
      if (!file) return;
      const url = URL.createObjectURL(file);
      const avatarEl = document.getElementById('avatarDisplay');
      avatarEl.style.backgroundImage = `url(${url})`;
      avatarEl.textContent = '';
    }

    // ===== MODAL: FOTO DO ADMINISTRADOR AMPLIADA =====
    function abrirAvatarModal() {
      const avatarEl = document.getElementById('avatarDisplay');
      const bgImage = avatarEl.style.backgroundImage;
      const modalImg = document.getElementById('avatarModalImg');
      const modalLetter = document.getElementById('avatarModalLetter');
      const overlay = document.getElementById('avatarModalOverlay');

      if (bgImage && bgImage !== 'none' && bgImage !== '') {
        const url = bgImage.slice(5, -2);
        modalImg.src = url;
        modalImg.style.display = 'block';
        modalLetter.style.display = 'none';
      } else {
        modalImg.style.display = 'none';
        modalLetter.textContent = avatarEl.textContent || 'A';
        modalLetter.style.display = 'flex';
      }

      overlay.classList.add('open');
      abrirModalComFoco(overlay, overlay.querySelector('.detail-close'));
    }

    function fecharAvatarModal(e) {
      if (e && e.target !== e.currentTarget) return;
      fecharModalComFoco(document.getElementById('avatarModalOverlay'));
    }

    // ===== MODAL: DETALHES DO PRODUTO =====
    function abrirProdutoModal(id) {
      const item = produtos.find(p => String(p.id) === String(id));
      if (!item) return;

      const img = document.getElementById('produtoModalImg');
      const imgEmpty = document.getElementById('produtoModalImgEmpty');
      if (item.imagem_url) {
        img.src = item.imagem_url;
        img.alt = item.nome;
        img.style.display = 'block';
        imgEmpty.style.display = 'none';
      } else {
        img.style.display = 'none';
        imgEmpty.style.display = 'flex';
      }

      document.getElementById('produtoModalNome').textContent = item.nome;
      document.getElementById('produtoModalCategoria').textContent = nomeCategoriaPorId(item.categoria_id);
      document.getElementById('produtoModalTamanho').textContent = item.tamanho || (item.variacoes && item.variacoes.length ? item.variacoes.map(v => v.nome_variacao).join(', ') : '-');
      document.getElementById('produtoModalQtd').textContent = item.quantidade ?? item.estoque ?? 0;
      document.getElementById('produtoModalPreco').textContent = formatarMoeda(item.preco);
      const variacaoWrap = document.getElementById('produtoModalVariacoes');
      if (variacaoWrap) {
        const variacoes = Array.isArray(item.variacoes) && item.variacoes.length ? item.variacoes : [];
        variacaoWrap.innerHTML = variacoes.length ? variacoes.map(v => `
          <div style="display:flex; justify-content:space-between; gap:12px; padding: 0.55rem 0.75rem; border:1px solid var(--border-color); border-radius:12px; background: var(--bg-surface-hover);">
            <span>${escapeHTML(v.nome_variacao)}</span>
            <strong style="color: var(--primary);">${escapeHTML(v.estoque ?? 0)} und.</strong>
          </div>
        `).join('') : '<div style="color: var(--text-muted);">Sem variações cadastradas.</div>';
      }
      const overlay = document.getElementById('produtoModalOverlay');
      overlay.classList.add('open');
      abrirModalComFoco(overlay, overlay.querySelector('.detail-close'));
    }

    function fecharProdutoModal(e) {
      if (e && e.target !== e.currentTarget) return;
      fecharModalComFoco(document.getElementById('produtoModalOverlay'));
    }

    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      ['produtoModalOverlay', 'avatarModalOverlay', 'comprovanteModalOverlay', 'cropModalOverlay', 'confirmModalOverlay']
        .forEach((id) => {
          const overlay = document.getElementById(id);
          if (overlay?.classList.contains('open')) fecharModalComFoco(overlay);
        });
    });

    // ===== RECORTE DE IMAGEM DO PRODUTO (Cropper.js) =====
    let cropperInstance = null;
    let cropArquivoOriginal = null;

    function handleProdutoImagem(e) {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      // Fallback: se o Cropper.js não carregou (CDN fora do ar, bloqueio de
      // rede etc.), não trava o cadastro — usa a imagem original sem recorte.
      if (typeof Cropper === 'undefined') {
        console.warn('Cropper.js indisponível — seguindo sem recorte de imagem.');
        mostrarToast('Editor de imagem indisponível no momento.', 'warning', 'A foto será enviada sem recorte.');
        cropArquivoOriginal = file;
        const preview = document.getElementById('prodImgPreview');
        preview.src = URL.createObjectURL(file);
        preview.style.display = 'block';
        imagemProdutoPendente = file;
        document.getElementById('prodImagemUrl').value = '';
        const fileNameLabel = document.getElementById('prodImagemFileName');
        if (fileNameLabel) fileNameLabel.innerText = file.name;
        return;
      }

      cropArquivoOriginal = file;
      const imgSrc = document.getElementById('cropImageSource');
      imgSrc.src = URL.createObjectURL(file);

      const overlay = document.getElementById('cropModalOverlay');
      overlay.classList.add('open');
      abrirModalComFoco(overlay, overlay.querySelector('.detail-close'));

      imgSrc.onload = () => {
        if (cropperInstance) cropperInstance.destroy();
        cropperInstance = new Cropper(imgSrc, {
          aspectRatio: NaN,
          viewMode: 1,
          dragMode: 'move',
          autoCropArea: 0.9,
          background: false,
          responsive: true
        });
      };
    }

    function setCropAspect(ratio) {
      if (!cropperInstance) return;
      cropperInstance.setAspectRatio(ratio === null ? NaN : ratio);
    }

    function cancelarCrop() {
      fecharModalComFoco(document.getElementById('cropModalOverlay'));
      if (cropperInstance) { cropperInstance.destroy(); cropperInstance = null; }
      const inputFile = document.getElementById('prodImagem');
      if (inputFile) inputFile.value = '';
    }

    function confirmarCrop() {
      if (!cropperInstance) return;

      const canvas = cropperInstance.getCroppedCanvas({
        maxWidth: 1200,
        maxHeight: 1200,
        imageSmoothingQuality: 'high'
      });

      canvas.toBlob((blob) => {
        if (!blob) {
          mostrarToast('Não foi possível processar o recorte da imagem.', 'error');
          return;
        }
        const nomeArquivo = cropArquivoOriginal ? cropArquivoOriginal.name : 'produto.png';
        const arquivoRecortado = new File([blob], nomeArquivo, { type: blob.type || 'image/png' });

        const preview = document.getElementById('prodImgPreview');
        preview.src = URL.createObjectURL(arquivoRecortado);
        preview.style.display = 'block';
        imagemProdutoPendente = arquivoRecortado;
        document.getElementById('prodImagemUrl').value = '';
        const fileNameLabel = document.getElementById('prodImagemFileName');
        if (fileNameLabel) fileNameLabel.innerText = arquivoRecortado.name;

        fecharModalComFoco(document.getElementById('cropModalOverlay'));
        cropperInstance.destroy();
        cropperInstance = null;

      }, cropArquivoOriginal ? cropArquivoOriginal.type : 'image/png', 0.92);
    }

    async function enviarImagemProduto(file) {
      const formData = new FormData();
      formData.append('arquivo', file);

      const resposta = await apiFetch(API_URLS.upload, { method: 'POST', body: formData });
      if (!resposta.ok) throw new Error('Falha no upload da imagem');
      const dados = await resposta.json();
      document.getElementById('prodImagemUrl').value = dados.url;
      return dados.url;
    }

    // ===== VARIAÇÕES DO PRODUTO (tamanho/cor/etc, cada uma com seu próprio estoque) =====
    let variacaoRowSeq = 0;

    function adicionarVariacaoRow(nome = '', estoque = '') {
      const wrap = document.getElementById('variacoesList');
      if (!wrap) return;
      const rowId = 'variacaoRow' + (variacaoRowSeq++);
      const row = document.createElement('div');
      row.className = 'variacao-row';
      row.id = rowId;
      wrap.querySelector('.variacoes-empty-hint')?.remove();
      row.innerHTML = `
        <input type="text" class="form-control var-nome" placeholder="Ex: Tamanho M - Azul">
        <input type="number" class="form-control var-estoque" placeholder="Estoque" min="0" step="1">
        <button type="button" class="action-btn danger" title="Remover variação" onclick="document.getElementById('${rowId}').remove()">
          <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      `;
      row.querySelector('.var-nome').value = nome || '';
      row.querySelector('.var-estoque').value = (estoque === '' || estoque === null || estoque === undefined) ? '' : estoque;
      wrap.appendChild(row);
    }

    function coletarVariacoes() {
      return [...document.querySelectorAll('#variacoesList .variacao-row')]
        .map(row => ({
          nome_variacao: row.querySelector('.var-nome').value.trim(),
          // MEXI AQUI: nunca deixa estoque negativo entrar (Math.max com 0)
          estoque: Math.max(0, parseInt(row.querySelector('.var-estoque').value || '0', 10))
        }))
        .filter(v => v.nome_variacao);
    }

    function limparVariacoes() {
      const wrap = document.getElementById('variacoesList');
      if (wrap) wrap.innerHTML = '<span class="variacoes-empty-hint">Nenhuma variação adicionada.</span>';
    }

    function toggleArmarioNomeField() {
      const statusEl = document.getElementById('armStatus');
      const wrap = document.getElementById('armNomeWrap');
      const input = document.getElementById('armNomeCompleto');
      if (!statusEl || !wrap || !input) return;
      if (statusEl.value === 'Ocupado') {
        wrap.style.display = '';
      } else {
        wrap.style.display = 'none';
        input.value = '';
      }
    }

    // TÍTULOS E RÓTULOS POR MÓDULO
    const titulos = {
      'dashboard': ['Visão geral', 'Resumo da operação e dos indicadores da AAPM.', ''],
      'categoria': ['Categorias', 'Organização e classificação de produtos.', 'Nova Categoria'],
      'fornecedor': ['Fornecedores', 'Cadastro e histórico de fornecedores.', 'Novo Fornecedor'],
      'produto': ['Produtos', 'Catálogo e controle de itens.', 'Novo Produto'],
      'associado': ['Associados', 'Consulta e cadastro dos associados da AAPM.', 'Novo Associado'],
      'armario': ['Armários', 'Controle de disponibilidade e ocupação dos armários.', 'Novo Armário'],
      'usuario': ['Usuários', 'Controle de acessos e permissões.', 'Novo Usuário'],
      'venda': ['Vendas', 'Registro de pedidos e transações.', 'Nova Venda'],
      'relatorio': ['Relatório de Vendas', 'Faturamento, produtos mais vendidos e formas de pagamento.', '']
    };

    // MOTOR DE NAVEGAÇÃO
    function navigate(viewId, element) {
      document.querySelectorAll('.view-content').forEach(v => v.classList.remove('active'));
      document.querySelectorAll('.menu-item').forEach(i => i.classList.remove('active'));

      const target = document.getElementById(viewId);
      if (target) target.classList.add('active');
      if (element) element.classList.add('active');

      if (titulos[viewId]) {
        document.getElementById('page-title').innerHTML = 'Gestão de <span>' + titulos[viewId][0] + '</span>';
        document.getElementById('page-subtitle').innerText = titulos[viewId][1];
        document.getElementById('quickActionLabel').innerText = titulos[viewId][2];
      }

      // MEXI AQUI: ao trocar de módulo, o campo de busca reflete o termo
      // já salvo daquele módulo (em vez de sempre limpar), então voltar pra
      // uma aba onde você já buscou algo continua mostrando o resultado.
      const searchInput = document.getElementById('tableSearch');
      if (searchInput) searchInput.value = termoBuscaPorModulo[viewId] || '';

      if (viewId === 'relatorio') { renderRelatorio(); renderRelatorioVendas(); }
      if (viewId === 'dashboard') renderDashboard();

      renderStatsBar(viewId);
      renderRecentList(viewId);
      observeReveals();
    }

    function focusForm() {
      const active = document.querySelector('.view-content.active');
      if (!active) return;
      const firstInput = active.querySelector('input, select');
      active.querySelector('form')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      if (firstInput) setTimeout(() => firstInput.focus(), 350);
    }

    function abrirAtalho(viewId) {
      const itemNav = [...document.querySelectorAll('.menu-item')]
        .find(item => item.getAttribute('onclick')?.includes(`'${viewId}'`));
      navigate(viewId, itemNav);
      if (viewId !== 'relatorio') focusForm();
    }

    function toggleAssistant() {
      const panel = document.getElementById('assistantPanel');
      if (!panel) return;
      panel.classList.toggle('open');
      if (panel.classList.contains('open')) document.getElementById('assistantInput')?.focus();
    }

    function adicionarMensagemAssistente(texto, tipo) {
      const messages = document.getElementById('assistantMessages');
      if (!messages) return;
      const item = document.createElement('div');
      item.className = `assistant-message ${tipo}`;
      item.textContent = texto;
      messages.appendChild(item);
      messages.scrollTop = messages.scrollHeight;
    }

    function executarComandoAssistente(texto) {
      const comando = texto.toLowerCase();
      const comandos = [
        { termos: ['novo produto', 'cadastrar produto', 'abrir produtos', 'ver produtos'], view: 'produto', resposta: 'Abrindo o módulo de Produtos.' },
        { termos: ['nova venda', 'registrar venda', 'abrir vendas', 'ver vendas'], view: 'venda', resposta: 'Abrindo o módulo de Vendas.' },
        { termos: ['novo associado', 'cadastrar associado', 'abrir associados'], view: 'associado', resposta: 'Abrindo o módulo de Associados.' },
        { termos: ['abrir relatório', 'abrir relatorio', 'ver relatório', 'ver relatorio'], view: 'relatorio', resposta: 'Abrindo o Relatório.' },
        { termos: ['visão geral', 'visao geral', 'dashboard', 'início', 'inicio'], view: 'dashboard', resposta: 'Voltando para a Visão geral.' }
      ];
      const acao = comandos.find(item => item.termos.some(termo => comando.includes(termo)));
      if (!acao) return null;
      abrirAtalho(acao.view);
      return acao.resposta;
    }

    function responderAssistente(texto) {
      const pergunta = texto.toLowerCase();
      if (pergunta.includes('produto')) return 'Para cadastrar um produto, abra Produtos no menu ou use o atalho. Preencha os dados, adicione a foto se quiser e salve.';
      if (pergunta.includes('venda')) return 'Abra Vendas para registrar uma venda. O resumo calcula automaticamente subtotal, desconto de associado e total.';
      if (pergunta.includes('estoque')) return 'A Visão geral mostra os itens com até 5 unidades. Para editar quantidades, abra Produtos.';
      if (pergunta.includes('associado')) return 'Em Associados você pode cadastrar, editar e consultar os associados da AAPM.';
      if (pergunta.includes('relatório') || pergunta.includes('relatorio')) return 'O Relatório mostra faturamento, produtos mais vendidos e formas de pagamento, com filtro por período.';
      return 'Posso ajudar com Produtos, Vendas, Associados, Estoque ou Relatório. Tente uma dessas palavras.';
    }

    function usarSugestaoAssistente(texto) {
      document.getElementById('assistantInput').value = texto;
      enviarMensagemAssistente({ preventDefault() {} });
    }

    function enviarMensagemAssistente(event) {
      event.preventDefault();
      const input = document.getElementById('assistantInput');
      const texto = input?.value.trim();
      if (!texto) return;
      adicionarMensagemAssistente(texto, 'user');
      input.value = '';
      const resposta = executarComandoAssistente(texto) || responderAssistente(texto);
      setTimeout(() => adicionarMensagemAssistente(resposta, 'bot'), 180);
    }

    const commandModules = [
      ['dashboard', 'Visão geral'], ['categoria', 'Categorias'], ['fornecedor', 'Fornecedores'],
      ['produto', 'Produtos'], ['associado', 'Associados'], ['armario', 'Armários'],
      ['usuario', 'Usuários'], ['venda', 'Vendas'], ['relatorio', 'Relatório']
    ];

    function renderCommandResults() {
      const input = document.getElementById('commandPaletteInput');
      const results = document.getElementById('commandPaletteResults');
      if (!input || !results) return;
      const termo = input.value.trim().toLowerCase();
      const filtrados = commandModules.filter(([, label]) => label.toLowerCase().includes(termo));
      results.innerHTML = filtrados.length ? filtrados.map(([id, label]) => `
        <button type="button" class="command-result" onclick="selecionarComando('${id}')">
          <strong>${escapeHTML(id)}</strong><span>${escapeHTML(label)}</span>
        </button>
      `).join('') : '<div class="command-empty">Nenhum módulo encontrado.</div>';
    }

    function abrirCommandPalette() {
      const overlay = document.getElementById('commandPaletteOverlay');
      const input = document.getElementById('commandPaletteInput');
      if (!overlay || !input) return;
      overlay.classList.add('open');
      input.value = '';
      renderCommandResults();
      abrirModalComFoco(overlay, input);
    }

    function fecharCommandPalette(event) {
      if (event && event.target !== event.currentTarget) return;
      const overlay = document.getElementById('commandPaletteOverlay');
      if (overlay?.classList.contains('open')) fecharModalComFoco(overlay);
    }

    function selecionarComando(viewId) {
      const itemNav = [...document.querySelectorAll('.menu-item')]
        .find(item => item.getAttribute('onclick')?.includes(`'${viewId}'`));
      fecharCommandPalette();
      navigate(viewId, itemNav);
    }

    document.getElementById('commandPaletteInput')?.addEventListener('input', renderCommandResults);

    // MEXI AQUI: debounce simples na busca de tabelas — evita refiltrar a
    // lista inteira a cada tecla digitada, sem mudar a lógica de filtro.
    function debounce(fn, delay = 220) {
      let timer = null;
      return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), delay);
      };
    }
    const filtrarTabelaAtivaDebounced = debounce(filtrarTabelaAtiva, 220);

    document.addEventListener('keydown', (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        abrirCommandPalette();
      }
      if (event.key === 'Escape') fecharCommandPalette();
      if (event.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
        event.preventDefault();
        document.getElementById('tableSearch')?.focus();
      }
      if (event.key.toLowerCase() === 'n' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) focusForm();
    });

    // ===== TEMA CLARO / ESCURO =====
    function applyThemeAttribute(theme) {
      document.documentElement.setAttribute('data-theme', theme);
      try { localStorage.setItem('admin_theme', theme); } catch (e) { /* indisponível */ }
    }

    function spawnThemeBurst(x, y, toDark) {
      const palette = toDark
        ? ['255, 255, 255', '214, 50, 80', '0, 140, 255']
        : ['214, 50, 80', '0, 140, 255', '255, 210, 130'];

      const count = 16;
      for (let i = 0; i < count; i++) {
        const el = document.createElement('span');
        const angle = (Math.PI * 2 * i) / count + (Math.random() * 0.4 - 0.2);
        const distance = 46 + Math.random() * 70;
        const size = Math.random() * 4 + 2.5;
        const color = palette[Math.floor(Math.random() * palette.length)];
        const dx = Math.cos(angle) * distance;
        const dy = Math.sin(angle) * distance;

        el.style.cssText = `
          position: fixed; left: ${x}px; top: ${y}px;
          width: ${size}px; height: ${size}px;
          border-radius: 50%;
          background: rgba(${color}, 0.95);
          box-shadow: 0 0 ${size * 2.5}px rgba(${color}, 0.85);
          pointer-events: none;
          z-index: 9999;
          transform: translate(-50%, -50%) scale(1);
          opacity: 1;
          transition: transform 1.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 1.3s cubic-bezier(0.16, 1, 0.3, 1);
        `;
        document.body.appendChild(el);

        requestAnimationFrame(() => {
          el.style.transform = `translate(calc(-50% + ${dx}px), calc(-50% + ${dy}px)) scale(0.3)`;
          el.style.opacity = '0';
        });

        setTimeout(() => el.remove(), 1350);
      }

      const glow = document.createElement('span');
      glow.style.cssText = `
        position: fixed; left: ${x}px; top: ${y}px;
        width: 10px; height: 10px;
        border-radius: 50%;
        background: rgba(${palette[0]}, 0.9);
        box-shadow: 0 0 40px 14px rgba(${palette[0]}, 0.55);
        pointer-events: none;
        z-index: 9999;
        transform: translate(-50%, -50%) scale(0);
        opacity: 1;
        transition: transform 0.9s cubic-bezier(0.34, 1.56, 0.64, 1), opacity 1s ease-out;
      `;
      document.body.appendChild(glow);
      requestAnimationFrame(() => {
        glow.style.transform = 'translate(-50%, -50%) scale(6)';
        glow.style.opacity = '0';
      });
      setTimeout(() => glow.remove(), 1000);
    }

    function toggleTheme(event) {
      const html = document.documentElement;
      const isLight = html.getAttribute('data-theme') === 'light';
      const newTheme = isLight ? 'dark' : 'light';
      const logo = document.querySelector('.logo-senai-svg');

      let originX = 66;
      let originY = 60;
      if (logo) {
        const rect = logo.getBoundingClientRect();
        originX = rect.left + rect.width / 2;
        originY = rect.top + rect.height / 2;
      } else if (event && typeof event.clientX === 'number' && event.clientX) {
        originX = event.clientX;
        originY = event.clientY;
      }

      const endRadius = Math.hypot(
        Math.max(originX, window.innerWidth - originX),
        Math.max(originY, window.innerHeight - originY)
      );

      const finishUp = () => spawnThemeBurst(originX, originY, newTheme === 'dark');

      if (logo) {
        logo.style.transition = 'transform 0.18s ease-out, box-shadow 0.18s ease-out';
        logo.style.transform = 'scale(1.18)';
        logo.style.boxShadow = '0 0 0 8px rgba(214, 50, 80, 0.35), 0 4px 14px rgba(214, 50, 80, 0.55)';
      }

      const runTransition = () => {
        if (logo) {
          logo.style.transform = '';
          logo.style.boxShadow = '';
        }

        if (!document.startViewTransition || window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
          applyThemeAttribute(newTheme);
          finishUp();
          return;
        }

        const transition = document.startViewTransition(() => {
          applyThemeAttribute(newTheme);
        });

        transition.ready.then(() => {
          document.documentElement.animate(
            {
              clipPath: [
                `circle(0px at ${originX}px ${originY}px)`,
                `circle(${endRadius}px at ${originX}px ${originY}px)`
              ]
            },
            {
              duration: 1400,
              easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
              pseudoElement: '::view-transition-new(root)'
            }
          );
        }).catch(() => { /* transição não suportada nesse navegador, ignora */ });

        transition.finished.then(finishUp).catch(finishUp);
      };

      setTimeout(runTransition, logo ? 160 : 0);
    }

    (function initTheme() {
      let saved = null;
      try { saved = localStorage.getItem('admin_theme'); } catch (e) { /* indisponível */ }
      if (saved === 'light' || saved === 'dark') {
        document.documentElement.setAttribute('data-theme', saved);
      }
    })();

    // BOTÕES DE AÇÃO GENÉRICOS (EDITAR/EXCLUIR)
    function renderAcoes(tipo, id) {
      return `
        <div class="action-btn-group" onclick="event.stopPropagation()">
          <button class="action-btn" title="Editar" onclick="editarItem('${tipo}', '${id}')">
            <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          </button>
          <button class="action-btn danger" title="Excluir" onclick="removerItem('${tipo}', '${id}')">
            <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;
    }

    function renderAcoesVenda(id) {
      return `
        <div class="action-btn-group" onclick="event.stopPropagation()">
          <button class="action-btn info" title="Gerar comprovante" onclick="abrirComprovanteModal('${id}')">
            <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
          </button>
          <button class="action-btn" title="Editar" onclick="editarItem('vnd', '${id}')">
            <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
          </button>
          <button class="action-btn danger" title="Excluir" onclick="removerItem('vnd', '${id}')">
            <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          </button>
        </div>
      `;
    }

    const mapaModulos = { cat: 'categoria', forn: 'fornecedor', prod: 'produto', assoc: 'associado', arm: 'armario', usr: 'usuario', vnd: 'venda' };

    function editarItem(tipo, id) {
      const endpointKey = mapaModulos[tipo];
      if (!endpointKey) return;
      navigate(endpointKey, document.querySelector(`.menu-item[onclick*="'${endpointKey}'"]`));

      if (tipo === 'cat') {
        const item = categorias.find(c => String(c.id) === String(id));
        if (!item) return;
        document.getElementById('catId').value = item.id;
        document.getElementById('catNome').value = item.nome;
        document.getElementById('catCodigo').value = item.codigo || '';
        document.getElementById('catDesc').value = item.descricao || '';
      } else if (tipo === 'forn') {
        const item = fornecedores.find(f => String(f.id) === String(id));
        if (!item) return;
        document.getElementById('fornNome').value = item.nome;
        document.getElementById('fornDoc').value = item.documento;
        document.getElementById('fornEmail').value = item.email || '';
        document.getElementById('fornTel').value = item.telefone || '';
        document.querySelector('#fornecedor form').dataset.editId = item.id;
      } else if (tipo === 'prod') {
        const item = produtos.find(p => String(p.id) === String(id));
        if (!item) return;
        document.getElementById('prodId').value = item.id;
        document.getElementById('prodNome').value = item.nome;
        document.getElementById('prodCategoria').value = item.categoria_id || '';
        document.getElementById('prodPreco').value = item.preco;
        document.getElementById('prodTamanho').value = item.tamanho || '';
        document.getElementById('prodQuantidade').value = (item.quantidade ?? 0);
        document.getElementById('prodImagemUrl').value = item.imagem_url || '';
        if (item.imagem_url) {
          const preview = document.getElementById('prodImgPreview');
          preview.src = item.imagem_url;
          preview.style.display = 'block';
          const fileNameLabel = document.getElementById('prodImagemFileName');
          if (fileNameLabel) fileNameLabel.innerText = 'Imagem atual mantida (opcional trocar)';
        }
        limparVariacoes();
        (item.variacoes || []).forEach(v => adicionarVariacaoRow(v.nome_variacao || v.nome || v.name || '', v.estoque ?? v.quantidade ?? ''));
        document.getElementById('prodSubmitBtn').innerText = 'Salvar Alterações';
      } else if (tipo === 'assoc') {
        const item = associados.find(a => String(a.id) === String(id));
        if (!item) return;
        document.getElementById('assocId').value = item.id;
        document.getElementById('assocNome').value = item.nome;
        document.getElementById('assocEmail').value = item.email || '';
        document.getElementById('assocTelefone').value = item.telefone || '';
        document.getElementById('assocEndereco').value = item.endereco || '';
        document.getElementById('assocSubmitBtn').innerText = 'Salvar Alterações';
      } else if (tipo === 'arm') {
        const item = armarios.find(a => String(a.id) === String(id));
        if (!item) return;
        document.getElementById('armId').value = item.id;
        document.getElementById('armNumero').value = item.numero;
        document.getElementById('armLocalizacao').value = (item.localizacao === '-' ? '' : item.localizacao) || '';
        document.getElementById('armStatus').value = item.status || 'Disponível';
        document.getElementById('armNomeCompleto').value = (item.nome_completo === '-' ? '' : item.nome_completo) || '';
        toggleArmarioNomeField();
        document.getElementById('armSubmitBtn').innerText = 'Salvar Alterações';
      } else if (tipo === 'usr') {
        const item = usuarios.find(u => String(u.id) === String(id));
        if (!item) return;
        document.getElementById('usrId').value = item.id;
        document.getElementById('usrNome').value = item.nome;
        document.getElementById('usrEmail').value = item.email;
        document.getElementById('usrPerfil').value = item.perfil;
      } else if (tipo === 'vnd') {
        const item = vendas.find(v => String(v.id) === String(id));
        if (!item) return;
        document.getElementById('vendaId').value = item.id;
        document.getElementById('vendaCliente').value = item.comprador || '';
        document.getElementById('vendaProduto').value = item.produto_id ?? '';

        const produtoEdit = produtos.find(p => String(p.id) === String(item.produto_id));
        const buscaProdutoEdit = document.getElementById('vendaProdutoBusca');
        if (buscaProdutoEdit) buscaProdutoEdit.value = produtoEdit ? `${produtoEdit.nome} (${formatarMoeda(produtoEdit.preco)})` : '';

        document.getElementById('vendaQtd').value = item.quantidade ?? 1;
        const selAssoc = document.getElementById('vendaAssociado');
        if (selAssoc) selAssoc.value = item.associado_id ?? '';

        // MEXI AQUI: reconstrói as linhas de pagamento dividido a partir do
        // que veio salvo (várias formas) ou, se for um registro antigo com
        // só uma forma de pagamento em texto, cria uma única linha com ela.
        const wrapPagamentos = document.getElementById('pagamentoSplitList');
        if (wrapPagamentos) wrapPagamentos.innerHTML = '';
        pagamentoRowSeq = 0;
        if (Array.isArray(item.pagamentos) && item.pagamentos.length) {
          item.pagamentos.forEach(p => adicionarPagamentoRow(p.forma_pagamento, p.valor));
        } else {
          adicionarPagamentoRow(item.forma_pagamento || 'PIX', item.preco_total ?? item.total ?? null);
        }

        document.getElementById('vendaSubmitBtn').innerText = 'Salvar Alterações';
        atualizarResumoVenda();
      }

      focusForm();
    }

    // ===== EXCLUSÃO DE ITEM NO BANCO (DELETE) =====
    // MEXI AQUI: agora é uma atualização otimista — remove o item do array
    // local e re-renderiza só aquele módulo, sem refazer o fetch de todas
    // as 7 entidades a cada exclusão. Se a chamada falhar, desfaz a remoção
    // local e mostra erro.
    const arraysPorModulo = {
      categoria: () => categorias, fornecedor: () => fornecedores, produto: () => produtos,
      associado: () => associados, armario: () => armarios, usuario: () => usuarios, venda: () => vendas
    };

    function removerItemLocal(endpointKey, id) {
      const arr = arraysPorModulo[endpointKey]();
      const idx = arr.findIndex(i => String(i.id) === String(id));
      if (idx === -1) return null;
      return arr.splice(idx, 1)[0];
    }

    function reinserirItemLocal(endpointKey, item, indice) {
      const arr = arraysPorModulo[endpointKey]();
      arr.splice(indice, 0, item);
    }

    async function removerItem(tipo, id) {
      const confirmado = await confirmarAcao('Confirma a exclusão deste item no banco de dados?', 'Excluir');
      if (!confirmado) return;

      const endpointKey = mapaModulos[tipo];
      if (!endpointKey) return;

      const arr = arraysPorModulo[endpointKey]();
      const indiceOriginal = arr.findIndex(i => String(i.id) === String(id));
      const itemRemovido = removerItemLocal(endpointKey, id);
      if (itemRemovido) { renderTudo(); }

      try {
        const resposta = await apiFetch(`${API_URLS[endpointKey]}/${id}`, { method: 'DELETE' });
        if (resposta.ok) {
          mostrarToast(mensagemSucesso(endpointKey, 'remover'), 'success');
        } else {
          if (itemRemovido) reinserirItemLocal(endpointKey, itemRemovido, indiceOriginal);
          renderTudo();
          mostrarToast(`Erro ao excluir ${modulosConfig[endpointKey]?.nome.toLowerCase() || 'o registro'} no banco de dados.`, 'error');
        }
      } catch (erro) {
        console.error("Erro na comunicação com a API ao excluir:", erro);
        if (itemRemovido) reinserirItemLocal(endpointKey, itemRemovido, indiceOriginal);
        renderTudo();
        mostrarToast('Não foi possível conectar ao servidor para excluir o registro.', 'error');
      }
    }

    function emptyRow(cols, msg) {
      return `<tr class="empty-row"><td colspan="${cols}">${escapeHTML(msg)}</td></tr>`;
    }

    // RENDERS DAS TABELAS (agora todas passam pela busca do módulo antes de paginar)
    function renderCategorias() {
      const tbody = document.getElementById('tblCategorias');
      const lista = aplicarBusca('categoria', categorias);
      const pagina = paginarLista(lista, 'categoria');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td><span class="pill-badge">${escapeHTML(item.codigo || item.id)}</span></td>
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td>${escapeHTML(item.descricao) || '-'}</td>
          <td><span class="status-tag active">Ativo</span></td>
          <td>${renderAcoes('cat', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhuma categoria cadastrada.');
      renderPaginacaoControles('pagCategorias', 'categoria', lista.length);
    }

    function renderFornecedores() {
      const tbody = document.getElementById('tblFornecedores');
      const lista = aplicarBusca('fornecedor', fornecedores);
      const pagina = paginarLista(lista, 'fornecedor');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td><span class="pill-badge">${escapeHTML(item.documento)}</span></td>
          <td>${escapeHTML(item.email) || '-'}</td>
          <td>${escapeHTML(item.telefone) || '-'}</td>
          <td>${renderAcoes('forn', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhum fornecedor cadastrado.');
      renderPaginacaoControles('pagFornecedores', 'fornecedor', lista.length);
    }

    function nomeCategoriaPorId(categoriaId) {
      const cat = categorias.find(c => c.id === categoriaId);
      return cat ? cat.nome : '-';
    }

    function nomeAssociadoPorId(associadoId) {
      if (!associadoId) return null;
      const assoc = associados.find(a => String(a.id) === String(associadoId));
      return assoc ? assoc.nome : null;
    }

    function renderVariationChipsAdmin(item) {
      const variacoes = Array.isArray(item.variacoes) ? item.variacoes : [];
      if (!variacoes.length) {
        return item.tamanho ? escapeHTML(item.tamanho) : '-';
      }
      const chips = variacoes.map(v => {
        const nome = v.nome_variacao || v.nome || v.name || '';
        const estoque = v.estoque ?? v.quantidade ?? 0;
        return `<span class="table-variation-chip">${escapeHTML(nome)}<strong>${escapeHTML(estoque)}</strong></span>`;
      }).join('');
      return `<div class="table-variations">${chips}</div>`;
    }

    function renderProdutos() {
      const tbody = document.getElementById('tblProdutos');
      const lista = aplicarBusca('produto', produtos);
      const pagina = paginarLista(lista, 'produto');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}; cursor:pointer;" onclick="abrirProdutoModal('${item.id}')" title="Ver detalhes do produto">
          <td onclick="event.stopPropagation()"><input type="checkbox" name="produtoDeleteCheck" value="${item.id}" onchange="atualizarSelecaoTodosProdutos()" style="width: 15px; height: 15px; accent-color: var(--primary);"></td>
          <td>${item.imagem_url ? `<img class="prod-thumb" src="${escapeHTML(item.imagem_url)}" alt="${escapeHTML(item.nome)}">` : `<div class="prod-thumb"></div>`}</td>
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td>${escapeHTML(nomeCategoriaPorId(item.categoria_id))}</td>
          <td>${renderVariationChipsAdmin(item)}</td>
          <td><span class="pill-badge">${escapeHTML(item.quantidade ?? 0)}</span></td>
          <td style="font-weight: 700; color: var(--success);">${formatarMoeda(item.preco)}</td>
          <td>${renderAcoes('prod', item.id)}</td>
        </tr>
      `).join('') : emptyRow(8, 'Nenhum produto cadastrado.');
      atualizarSelecaoTodosProdutos();
      renderPaginacaoControles('pagProdutos', 'produto', lista.length);
    }

    function toggleTodosProdutos(checked) {
      document.querySelectorAll('input[name="produtoDeleteCheck"]').forEach(input => {
        input.checked = checked;
      });
      atualizarSelecaoTodosProdutos();
    }

    function atualizarSelecaoTodosProdutos() {
      const seletor = document.getElementById('selectAllProdutos');
      const itens = [...document.querySelectorAll('input[name="produtoDeleteCheck"]')];
      if (!seletor) return;
      seletor.checked = itens.length > 0 && itens.every(input => input.checked);
      seletor.indeterminate = itens.some(input => input.checked) && !seletor.checked;
    }

    async function deletarProdutosSelecionados() {
      const selecionados = [...document.querySelectorAll('input[name="produtoDeleteCheck"]:checked')].map(el => Number(el.value)).filter(Boolean);
      if (!selecionados.length) {
        mostrarToast('Selecione pelo menos um produto para apagar.', 'warning');
        return;
      }

      const confirmado = await confirmarAcao(`Deseja excluir ${selecionados.length} produto(s) selecionado(s)?`, 'Excluir');
      if (!confirmado) return;

      for (const id of selecionados) {
        try {
          const resposta = await apiFetch(`${API_URLS.produto}/${id}`, { method: 'DELETE' });
          if (!resposta.ok) {
            throw new Error(`Erro ao apagar produto ${id}`);
          }
        } catch (erro) {
          console.error(erro);
          mostrarToast('Não foi possível excluir todos os produtos selecionados.', 'error');
          await carregarDadosDoBanco();
          return;
        }
      }

      // MEXI AQUI: só um refetch completo ao final do lote (em vez de um por
      // item), já que aqui estamos apagando vários registros de uma vez.
      await carregarDadosDoBanco();
      mostrarToast(`${selecionados.length} produto(s) removido(s) com sucesso!`, 'success');
    }

    function renderAssociados() {
      const tbody = document.getElementById('tblAssociados');
      if (!tbody) return;
      const lista = aplicarBusca('associado', associados);
      const pagina = paginarLista(lista, 'associado');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td>${escapeHTML(item.email) || '-'}</td>
          <td>${escapeHTML(item.telefone) || '-'}</td>
          <td>${escapeHTML(item.endereco) || '-'}</td>
          <td><span class="status-tag ${(item.status || 'Ativo') === 'Ativo' ? 'active' : 'inactive'}">${escapeHTML(item.status || 'Ativo')}</span></td>
          <td>${renderAcoes('assoc', item.id)}</td>
        </tr>
      `).join('') : emptyRow(6, 'Nenhum associado cadastrado.');
      renderPaginacaoControles('pagAssociados', 'associado', lista.length);
    }

    function statusArmarioClasse(status) {
      if (status === 'Disponível') return 'active';
      if (status === 'Ocupado') return 'inactive';
      return 'warning';
    }

    function renderArmarios() {
      const tbody = document.getElementById('tblArmarios');
      if (!tbody) return;
      const lista = aplicarBusca('armario', armarios);
      const pagina = paginarLista(lista, 'armario');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td><span class="pill-badge">${escapeHTML(item.numero)}</span></td>
          <td>${escapeHTML(item.localizacao) || '-'}</td>
          <td><span class="status-tag ${statusArmarioClasse(item.status)}">${escapeHTML(item.status || 'Disponível')}</span></td>
          <td>${escapeHTML(item.nome_completo) || '-'}</td>
          <td>${renderAcoes('arm', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhum armário cadastrado.');
      renderPaginacaoControles('pagArmarios', 'armario', lista.length);
    }

    function renderUsuarios() {
      const tbody = document.getElementById('tblUsuarios');
      const lista = aplicarBusca('usuario', usuarios);
      const pagina = paginarLista(lista, 'usuario');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td>${escapeHTML(item.email)}</td>
          <td><span class="pill-badge">${escapeHTML(item.perfil)}</span></td>
          <td><span class="status-tag ${(item.status || 'Ativo') === 'Ativo' ? 'active' : 'inactive'}">${escapeHTML(item.status || 'Ativo')}</span></td>
          <td>${renderAcoes('usr', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhum usuário cadastrado.');
      renderPaginacaoControles('pagUsuarios', 'usuario', lista.length);
    }

    function renderVendas() {
      const tbody = document.getElementById('tblVendas');
      if (!tbody) return;
      const lista = aplicarBusca('venda', vendas);
      const pagina = paginarLista(lista, 'venda');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => {
        const nomeAssoc = nomeAssociadoPorId(item.associado_id);
        return `
        <tr style="--i:${i}">
          <td>${escapeHTML(item.data_venda) || '-'}</td>
          <td style="font-weight: 700;">${escapeHTML(item.comprador || item.cliente) || '-'}</td>
          <td>${escapeHTML(item.produto_nome) || '-'}</td>
          <td><span class="pill-badge">${escapeHTML(item.quantidade ?? 0)}</span></td>
          <td>${nomeAssoc ? `<span class="status-tag active">${escapeHTML(nomeAssoc)} · -10%</span>` : '-'}</td>
          <td style="font-weight: 700; color: var(--success);">${formatarMoeda(item.preco_total ?? item.total ?? 0)}</td>
          <td>${escapeHTML(item.forma_pagamento) || '-'}</td>
          <td>${renderAcoesVenda(item.id)}</td>
        </tr>
      `;
      }).join('') : emptyRow(8, 'Nenhuma venda registrada.');
      renderPaginacaoControles('pagVendas', 'venda', lista.length);
    }

    Object.assign(renderizadoresPorModulo, {
      categoria: renderCategorias,
      fornecedor: renderFornecedores,
      produto: renderProdutos,
      associado: renderAssociados,
      armario: renderArmarios,
      usuario: renderUsuarios,
      venda: renderVendas,
      relatorio: renderRelatorio
    });

    // BARRA DE ESTATÍSTICAS DINÂMICA
    function computeStats(viewId) {
      switch (viewId) {
        case 'dashboard':
          return [
            { value: produtos.length, label: 'Produtos no catálogo' },
            { value: associados.length, label: 'Associados cadastrados' },
            { value: vendas.length, label: 'Vendas registradas' }
          ];
        case 'categoria':
          return [
            { value: categorias.length, label: 'Categorias Cadastradas' },
            { value: categorias.length, label: 'Categorias Ativas' },
            { value: produtos.length, label: 'Produtos Vinculados' }
          ];
        case 'fornecedor':
          return [
            { value: fornecedores.length, label: 'Fornecedores Cadastrados' },
            { value: new Set(fornecedores.map(f => f.documento)).size, label: 'Documentos Únicos' },
            { value: fornecedores.filter(f => f.telefone).length, label: 'Com Telefone' }
          ];
        case 'produto':
          return [
            { value: produtos.length, label: 'Produtos Cadastrados' },
            { value: new Set(produtos.map(p => p.categoria_id)).size, label: 'Categorias Utilizadas' },
            { value: formatarMoeda(produtos.reduce((a, p) => a + Number(p.preco || 0), 0)), label: 'Valor em Catálogo' }
          ];
        case 'associado':
          return [
            { value: associados.length, label: 'Associados Cadastrados' },
            { value: associados.filter(a => (a.status || 'Ativo') === 'Ativo').length, label: 'Associados Ativos' },
            { value: associados.filter(a => a.telefone).length, label: 'Com Telefone' }
          ];
        case 'armario':
          return [
            { value: armarios.length, label: 'Armários Cadastrados' },
            { value: armarios.filter(a => a.status === 'Disponível').length, label: 'Disponíveis' },
            { value: armarios.filter(a => a.status === 'Ocupado').length, label: 'Ocupados' }
          ];
        case 'usuario':
          return [
            { value: usuarios.length, label: 'Usuários Cadastrados' },
            { value: usuarios.filter(u => (u.status || 'Ativo') === 'Ativo').length, label: 'Usuários Ativos' },
            { value: usuarios.filter(u => u.perfil === 'Administrador').length, label: 'Administradores' }
          ];
        case 'venda':
          return [
            { value: vendas.length, label: 'Vendas Registradas' },
            { value: vendas.reduce((a, v) => a + Number(v.quantidade || 0), 0), label: 'Itens Vendidos' },
            { value: formatarMoeda(vendas.reduce((a, v) => a + Number(v.preco_total || 0), 0)), label: 'Faturamento Total' }
          ];
        case 'relatorio': {
          const relatorio = carregarRelatorioNotificacoes();
          const hoje = new Date().toDateString();
          return [
            { value: relatorio.length, label: 'Notificações Lidas' },
            { value: relatorio.filter(r => new Date(r.lidoEm).toDateString() === hoje).length, label: 'Lidas Hoje' },
            { value: montarNotificacoes().length, label: 'Pendentes no Sino' }
          ];
        }
        default:
          return [];
      }
    }

    const statIcons = [
      '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>',
      '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12h4l3 8 4-16 3 8h4"/></svg>',
      '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>'
    ];

    function renderStatsBar(viewId) {
      const bar = document.getElementById('statsBar');
      if (!bar) return;
      const stats = computeStats(viewId);
      bar.innerHTML = stats.map((s, i) => `
        <div class="stat-tile reveal">
          <div class="stat-icon">${statIcons[i] || statIcons[0]}</div>
          <div class="stat-value-wrap">
            <div class="stat-value">${escapeHTML(s.value)}</div>
            <div class="stat-label">${escapeHTML(s.label)}</div>
          </div>
        </div>
      `).join('');
      observeReveals();
    }

    const recentIcon = '<svg viewBox="0 0 24 24" fill="none" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 8v4l3 3"/><circle cx="12" cy="12" r="9"/></svg>';

    function getRecentEntries(viewId) {
      switch (viewId) {
        case 'categoria':
          return categorias.slice(-3).reverse().map(c => ({ title: c.nome, sub: c.codigo || ('#' + c.id) }));
        case 'fornecedor':
          return fornecedores.slice(-3).reverse().map(f => ({ title: f.nome, sub: f.documento }));
        case 'produto':
          return produtos.slice(-3).reverse().map(p => ({ title: p.nome, sub: formatarMoeda(p.preco) }));
        case 'associado':
          return associados.slice(-3).reverse().map(a => ({ title: a.nome, sub: a.email || a.telefone || '-' }));
        case 'armario':
          return armarios.slice(-3).reverse().map(a => ({ title: 'Armário ' + a.numero, sub: a.status || 'Disponível' }));
        case 'usuario':
          return usuarios.slice(-3).reverse().map(u => ({ title: u.nome, sub: u.perfil }));
        case 'venda':
          return vendas.slice(0, 3).map(v => ({ title: v.comprador, sub: v.produto_nome }));
        case 'relatorio':
          return carregarRelatorioNotificacoes().slice(0, 3).map(r => ({ title: r.titulo, sub: r.sub || r.tipo }));
        default:
          return [];
      }
    }

    function renderRecentList(viewId) {
      const list = document.getElementById('recentList');
      if (!list) return;
      const entries = getRecentEntries(viewId);
      list.innerHTML = entries.length ? entries.map(e => `
        <div class="recent-item">
          <div class="ri-tag">${recentIcon}</div>
          <div>
            <div class="ri-title">${escapeHTML(e.title)}</div>
            <div class="ri-sub">${escapeHTML(e.sub)}</div>
          </div>
        </div>
      `).join('') : '<div class="recent-empty">Nenhum registro recente.</div>';
    }

    // ===== RELATÓRIO DE VENDAS (faturamento, top produtos, formas de pagamento) =====
    let relatorioFiltroAtual = 'hoje';

    function selecionarFiltroRelatorio(periodo) {
      relatorioFiltroAtual = periodo;
      document.querySelectorAll('#relatorioFiltroChips .filter-chip').forEach(chip => {
        chip.classList.toggle('active', chip.dataset.periodo === periodo);
      });
      renderRelatorioVendas();
    }

    function vendasNoPeriodoRelatorio() {
      if (relatorioFiltroAtual === 'tudo') return vendas;
      const agora = new Date();
      const limite = new Date(agora);
      if (relatorioFiltroAtual === 'hoje') {
        limite.setHours(0, 0, 0, 0);
      } else if (relatorioFiltroAtual === '7d') {
        limite.setDate(limite.getDate() - 7);
      } else if (relatorioFiltroAtual === '30d') {
        limite.setDate(limite.getDate() - 30);
      }
      return vendas.filter(v => {
        const data = v.data_venda ? new Date(v.data_venda) : null;
        if (!data || isNaN(data)) return relatorioFiltroAtual === 'tudo';
        return data >= limite;
      });
    }

    // Quebra cada venda em suas formas de pagamento reais (pagamentos[])
    // quando existir, ou usa o texto único de forma_pagamento como fallback
    // pra vendas antigas que não tinham divisão.
    function formasPagamentoDaVenda(item) {
      if (Array.isArray(item.pagamentos) && item.pagamentos.length) return item.pagamentos;
      return [{ forma_pagamento: item.forma_pagamento || 'Não informado', valor: Number(item.preco_total ?? item.total ?? 0) }];
    }

    function renderRelatorioVendas() {
      const kpisWrap = document.getElementById('relatorioKpis');
      const topWrap = document.getElementById('relatorioTopProdutos');
      const pagamentosWrap = document.getElementById('relatorioPagamentos');
      if (!kpisWrap || !topWrap || !pagamentosWrap) return;

      const periodo = vendasNoPeriodoRelatorio();
      const faturamento = periodo.reduce((acc, v) => acc + Number(v.preco_total || v.total || 0), 0);
      const qtdVendas = periodo.length;
      const ticketMedio = qtdVendas ? faturamento / qtdVendas : 0;
      const itensVendidos = periodo.reduce((acc, v) => acc + Number(v.quantidade || 0), 0);

      kpisWrap.innerHTML = `
        <div class="report-kpi">
          <span class="report-kpi-label">Faturamento no período</span>
          <strong>${formatarMoeda(faturamento)}</strong>
        </div>
        <div class="report-kpi blue">
          <span class="report-kpi-label">Vendas no período</span>
          <strong>${qtdVendas}</strong>
        </div>
        <div class="report-kpi green">
          <span class="report-kpi-label">Ticket médio</span>
          <strong>${formatarMoeda(ticketMedio)}</strong>
        </div>
        <div class="report-kpi gold">
          <span class="report-kpi-label">Itens vendidos</span>
          <strong>${itensVendidos}</strong>
        </div>
      `;

      // Top produtos por faturamento no período
      const porProduto = new Map();
      periodo.forEach(v => {
        const nome = v.produto_nome || 'Produto não informado';
        const atual = porProduto.get(nome) || { qtd: 0, valor: 0 };
        atual.qtd += Number(v.quantidade || 0);
        atual.valor += Number(v.preco_total || v.total || 0);
        porProduto.set(nome, atual);
      });
      const topProdutos = [...porProduto.entries()]
        .sort((a, b) => b[1].valor - a[1].valor)
        .slice(0, 5);

      topWrap.innerHTML = topProdutos.length ? topProdutos.map(([nome, dados], i) => `
        <div class="report-ranking-item">
          <div class="report-ranking-pos">${i + 1}</div>
          <div>
            <strong>${escapeHTML(nome)}</strong>
            <small>${escapeHTML(dados.qtd)} unidade(s) vendida(s)</small>
          </div>
          <div class="report-ranking-valor">${formatarMoeda(dados.valor)}</div>
        </div>
      `).join('') : '<div class="report-empty">Nenhuma venda nesse período ainda.</div>';

      // Formas de pagamento por participação no faturamento
      const porPagamento = new Map();
      periodo.forEach(v => {
        formasPagamentoDaVenda(v).forEach(p => {
          const atual = porPagamento.get(p.forma_pagamento) || 0;
          porPagamento.set(p.forma_pagamento, atual + Number(p.valor || 0));
        });
      });
      const totalPagamentos = [...porPagamento.values()].reduce((a, b) => a + b, 0);
      const pagamentosOrdenados = [...porPagamento.entries()].sort((a, b) => b[1] - a[1]);

      pagamentosWrap.innerHTML = pagamentosOrdenados.length ? pagamentosOrdenados.map(([forma, valor]) => {
        const percentual = totalPagamentos ? (valor / totalPagamentos) * 100 : 0;
        return `
          <div class="report-bar-row">
            <div class="report-bar-head">
              <span>${escapeHTML(forma)}</span>
              <span>${formatarMoeda(valor)} · ${percentual.toFixed(0)}%</span>
            </div>
            <div class="report-bar-track"><div class="report-bar-fill" style="width:${percentual}%;"></div></div>
          </div>
        `;
      }).join('') : '<div class="report-empty">Nenhum pagamento registrado nesse período.</div>';
    }

    function renderDashboard() {
      const metrics = document.getElementById('dashboardMetrics');
      const activity = document.getElementById('dashboardActivity');
      const stock = document.getElementById('dashboardStock');
      if (!metrics || !activity || !stock) return;

      const faturamento = vendas.reduce((total, venda) => total + Number(venda.preco_total || venda.total || 0), 0);
      metrics.innerHTML = [
        { value: produtos.length, label: 'Produtos no catálogo', tone: 'red' },
        { value: associados.length, label: 'Associados ativos', tone: 'blue' },
        { value: vendas.length, label: 'Vendas registradas', tone: 'green' },
        { value: formatarMoeda(faturamento), label: 'Faturamento total', tone: 'gold' }
      ].map(item => `
        <div class="dashboard-metric ${item.tone}">
          <span class="dashboard-metric-label">${escapeHTML(item.label)}</span>
          <strong>${escapeHTML(item.value)}</strong>
        </div>
      `).join('');

      const atividades = [
        ...vendas.slice(0, 3).map(v => ({ tipo: 'Venda', titulo: v.comprador || v.cliente || 'Cliente não informado', detalhe: `${v.produto_nome || 'Produto'} · ${formatarMoeda(v.preco_total || v.total || 0)}` })),
        ...produtos.slice(-2).reverse().map(p => ({ tipo: 'Produto', titulo: p.nome, detalhe: `${Number(p.quantidade ?? p.estoque ?? 0)} unidades em estoque` })),
        ...associados.slice(-1).reverse().map(a => ({ tipo: 'Associado', titulo: a.nome, detalhe: a.email || 'Cadastro recente' }))
      ].slice(0, 5);

      activity.innerHTML = atividades.length ? atividades.map(item => `
        <div class="dashboard-activity-item">
          <span class="dashboard-activity-type">${escapeHTML(item.tipo)}</span>
          <div><strong>${escapeHTML(item.titulo)}</strong><small>${escapeHTML(item.detalhe)}</small></div>
        </div>
      `).join('') : '<div class="dashboard-empty">Ainda não há movimentações recentes.</div>';

      const estoqueBaixo = produtos
        .map(produto => ({ ...produto, quantidadeDashboard: Number(produto.quantidade ?? produto.estoque ?? 0) }))
        .filter(produto => produto.quantidadeDashboard <= 5)
        .sort((a, b) => a.quantidadeDashboard - b.quantidadeDashboard)
        .slice(0, 5);

      stock.innerHTML = estoqueBaixo.length ? estoqueBaixo.map(produto => `
        <div class="dashboard-stock-item">
          <span class="dashboard-stock-count">${escapeHTML(produto.quantidadeDashboard)}</span>
          <div><strong>${escapeHTML(produto.nome)}</strong><small>unidades disponíveis</small></div>
        </div>
      `).join('') : '<div class="dashboard-empty">Nenhum item precisa de reposição.</div>';
    }

    function atualizarDataHora() {
      const agora = new Date();
      const dias = ['Domingo','Segunda-feira','Terça-feira','Quarta-feira','Quinta-feira','Sexta-feira','Sábado'];
      const meses = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez'];
      document.getElementById('dwEyebrow').innerText = dias[agora.getDay()];
      document.getElementById('dwDay').innerText = String(agora.getDate()).padStart(2, '0') + ' ' + meses[agora.getMonth()];
      document.getElementById('dwFull').innerText = agora.toLocaleDateString('pt-BR', { year: 'numeric' });
      document.getElementById('dwClock').innerText = agora.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }

    // ===== PAGAMENTO DIVIDIDO DA VENDA (uma ou mais formas + valores) =====
    let pagamentoRowSeq = 0;

    function adicionarPagamentoRow(forma = 'PIX', valor = null) {
      const wrap = document.getElementById('pagamentoSplitList');
      if (!wrap) return;
      const rowId = 'pgtoRow' + (pagamentoRowSeq++);
      const row = document.createElement('div');
      row.className = 'pagamento-row';
      row.id = rowId;
      row.innerHTML = `
        <select class="form-control pgto-forma" onchange="atualizarRestantePagamento()">
          <option value="PIX">PIX</option>
          <option value="Cartão de Crédito">Cartão de Crédito</option>
          <option value="Dinheiro">Dinheiro</option>
        </select>
        <input type="number" class="form-control pgto-valor" step="0.01" min="0" placeholder="Valor (R$)" oninput="atualizarRestantePagamento()">
        <button type="button" class="action-btn danger" title="Remover forma de pagamento" onclick="removerPagamentoRow('${rowId}')">
          <svg style="width:14px;height:14px;" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
        </button>
      `;
      row.querySelector('.pgto-forma').value = forma;
      if (valor !== null && valor !== undefined && valor !== '') {
        row.querySelector('.pgto-valor').value = Number(valor).toFixed(2);
      }
      wrap.appendChild(row);
      atualizarRestantePagamento();
    }

    function removerPagamentoRow(rowId) {
      const wrap = document.getElementById('pagamentoSplitList');
      const linhas = wrap ? wrap.querySelectorAll('.pagamento-row') : [];
      if (linhas.length <= 1) {
        mostrarToast('É preciso manter ao menos uma forma de pagamento.', 'warning');
        return;
      }
      document.getElementById(rowId)?.remove();
      atualizarRestantePagamento();
    }

    // Reseta a lista de pagamentos pra uma única linha (usado ao carregar a
    // página, depois de concluir uma venda e antes de editar outra).
    function limparPagamentoRows(formaUnica = 'PIX', valorUnico = null) {
      const wrap = document.getElementById('pagamentoSplitList');
      if (wrap) wrap.innerHTML = '';
      pagamentoRowSeq = 0;
      adicionarPagamentoRow(formaUnica, valorUnico);
    }

    function coletarPagamentos() {
      const linhas = [...document.querySelectorAll('#pagamentoSplitList .pagamento-row')];
      return linhas
        .map(row => ({
          forma_pagamento: row.querySelector('.pgto-forma').value,
          valor: Math.round((parseFloat(row.querySelector('.pgto-valor').value) || 0) * 100) / 100
        }))
        .filter(p => p.valor > 0);
    }

    function calcularTotalVendaAtual() {
      const produtoId = document.getElementById('vendaProduto').value;
      const qtd = parseInt(document.getElementById('vendaQtd').value || '0', 10);
      const associadoId = document.getElementById('vendaAssociado').value;
      const produto = produtos.find(p => String(p.id) === String(produtoId));
      if (!produto || !qtd) return 0;
      const subtotal = Number(produto.preco) * qtd;
      const desconto = associadoId ? subtotal * 0.10 : 0;
      return Math.round((subtotal - desconto) * 100) / 100;
    }

    // Recalcula quanto falta (ou sobra) pra bater com o total da venda.
    // Se só existir uma forma de pagamento, ela é mantida sincronizada
    // automaticamente com o total (não precisa digitar nada nesse caso).
    function atualizarRestantePagamento() {
      const total = calcularTotalVendaAtual();
      const linhas = [...document.querySelectorAll('#pagamentoSplitList .pagamento-row')];

      if (linhas.length === 1) {
        const campoValor = linhas[0].querySelector('.pgto-valor');
        if (campoValor && document.activeElement !== campoValor) {
          campoValor.value = total > 0 ? total.toFixed(2) : '';
        }
      }

      const pagamentos = coletarPagamentos();
      const soma = Math.round(pagamentos.reduce((acc, p) => acc + p.valor, 0) * 100) / 100;
      const restante = Math.round((total - soma) * 100) / 100;

      const label = document.getElementById('pagamentoRestanteLabel');
      if (!label) return;

      if (total <= 0) {
        label.textContent = '';
        label.className = 'pagamento-split-restante';
        return;
      }
      if (Math.abs(restante) < 0.01) {
        label.textContent = 'Valores batem com o total ✓';
        label.className = 'pagamento-split-restante ok';
      } else if (restante > 0) {
        label.textContent = `Faltam ${formatarMoeda(restante)}`;
        label.className = 'pagamento-split-restante pendente';
      } else {
        label.textContent = `${formatarMoeda(Math.abs(restante))} a mais que o total`;
        label.className = 'pagamento-split-restante pendente';
      }
    }

    // ===== RESUMO DE VALORES DA VENDA (subtotal / desconto associado 10% / total) =====
    function atualizarResumoVenda() {
      const produtoId = document.getElementById('vendaProduto').value;
      const qtd = parseInt(document.getElementById('vendaQtd').value || '0', 10);
      const associadoId = document.getElementById('vendaAssociado').value;
      const resumoWrap = document.getElementById('vendaResumoWrap');

      const produto = produtos.find(p => String(p.id) === String(produtoId));
      if (!produto || !qtd) {
        resumoWrap.style.display = 'none';
        atualizarRestantePagamento();
        return;
      }

      const subtotal = Number(produto.preco) * qtd;
      const temDesconto = !!associadoId;
      const desconto = temDesconto ? subtotal * 0.10 : 0;
      const total = subtotal - desconto;

      document.getElementById('vendaResumoSubtotal').innerText = formatarMoeda(subtotal);
      document.getElementById('vendaResumoDesconto').innerText = '- ' + formatarMoeda(desconto);
      document.getElementById('vendaResumoDescontoWrap').classList.toggle('show', temDesconto);
      document.getElementById('vendaResumoTotal').innerText = formatarMoeda(total);
      resumoWrap.style.display = 'block';

      atualizarRestantePagamento();
    }

    // ================================================================== //
    // ===== COMPROVANTE DE VENDA IMPRIMÍVEL (estilo cupom) ===== //
    // ================================================================== //

    function gerarNumeroRecibo(item) {
      const dataRef = item.data_venda ? new Date(item.data_venda) : new Date();
      const aamm = isNaN(dataRef) ? '000000' :
        String(dataRef.getFullYear()).slice(-2) + String(dataRef.getMonth() + 1).padStart(2, '0') + String(dataRef.getDate()).padStart(2, '0');
      const seq = String(item.id ?? 0).padStart(4, '0');
      return `SNSP-${aamm}-${seq}`;
    }

    function gerarCodigoValidacao(item) {
      const base = `VND${item.id ?? 0}${item.produto_id ?? 0}${item.quantidade ?? 0}`;
      let hash = 0;
      for (let i = 0; i < base.length; i++) {
        hash = (hash * 31 + base.charCodeAt(i)) >>> 0;
      }
      const hex = hash.toString(16).toUpperCase().padStart(8, '0');
      return `${hex.slice(0, 4)}-${hex.slice(4, 8)}-A2C0-4E00`;
    }

    function formatarDataHoraComprovante(item) {
      const d = item.data_venda ? new Date(item.data_venda) : new Date();
      if (isNaN(d)) return item.data_venda || '-';
      return d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
    }

    function montarComprovanteHTML(item) {
      const produto = produtos.find(p => String(p.id) === String(item.produto_id));
      const nomeItem = item.produto_nome || (produto ? produto.nome : 'Item');
      const qtd = Number(item.quantidade ?? 1);
      const totalFinal = Number(item.preco_total ?? item.total ?? (produto ? produto.preco * qtd : 0));
      const temDesconto = !!item.associado_id && Number(item.desconto_percentual || 0) > 0;
      const percentualDesconto = temDesconto ? Number(item.desconto_percentual || 10) : 0;
      const subtotalItem = temDesconto ? totalFinal / (1 - percentualDesconto / 100) : totalFinal;
      const valorDesconto = subtotalItem - totalFinal;
      const valorUnit = qtd ? subtotalItem / qtd : subtotalItem;
      const cliente = item.comprador || item.cliente || '-';
      const nomeAssoc = nomeAssociadoPorId(item.associado_id);
      const recibo = gerarNumeroRecibo(item);
      const codigoValidacao = gerarCodigoValidacao(item);

      // MEXI AQUI: se a venda teve mais de uma forma de pagamento, mostra
      // a divisão completa (forma + valor de cada uma) em vez de só o texto
      // combinado salvo em forma_pagamento.
      const pagamentosHTML = Array.isArray(item.pagamentos) && item.pagamentos.length > 1
        ? item.pagamentos.map(p => `<div class="comp-linha"><span>${escapeHTML(p.forma_pagamento)}</span><span>${formatarMoeda(p.valor)}</span></div>`).join('')
        : null;

      return `
        <div class="comp-header">
          <div class="comp-logo-badge">
            <svg viewBox="0 0 300 100" xmlns="http://www.w3.org/2000/svg">
              <rect width="300" height="100" fill="#FF0000"/>
              <text x="150" y="73" font-family="'Arial Black', 'Impact', sans-serif" font-size="62" font-weight="900" font-style="italic" fill="#FFFFFF" text-anchor="middle">SENAI</text>
            </svg>
          </div>
          <h4>SENAI — Serviço AAPM<br>Unidade São Paulo — Senai Brás</h4>
          <p>AAPM — Associação de Pais e mestres</p>
        </div>

        <div class="comp-title">COMPROVANTE DE VENDA</div>
        <div class="comp-recibo">RECIBO Nº <strong>${escapeHTML(recibo)}</strong></div>

        <div class="comp-meta">
          <span>Data/Hora: <strong style="color:#111;">${escapeHTML(formatarDataHoraComprovante(item))}</strong></span>
          <span>Venda: <strong style="color:#111;">#${escapeHTML(item.id ?? '-')}</strong></span>
        </div>

        <div class="comp-section-label">Cliente</div>
        <div class="comp-cliente-row"><span>Nome</span><span>${escapeHTML(cliente)}</span></div>
        ${nomeAssoc ? `<div class="comp-cliente-row"><span>Associado</span><span>${escapeHTML(nomeAssoc)}</span></div>` : ''}

        <div class="comp-section-label">Itens Adquiridos</div>
        <table class="comp-itens-table">
          <thead>
            <tr><th>Descrição</th><th>Qtd</th><th>Total (R$)</th></tr>
          </thead>
          <tbody>
            <tr>
              <td class="comp-item-desc">${escapeHTML(nomeItem)}</td>
              <td>${escapeHTML(qtd)}</td>
              <td>${subtotalItem.toFixed(2)}</td>
            </tr>
          </tbody>
        </table>

        <div class="comp-totais">
          <div class="comp-linha"><span>Valor Unitário</span><span>${formatarMoeda(valorUnit)}</span></div>
          ${temDesconto ? `<div class="comp-linha desconto"><span>Desconto Associado (${percentualDesconto}%)</span><span>- ${formatarMoeda(valorDesconto)}</span></div>` : ''}
          <div class="comp-linha total"><span>Total a Pagar</span><span>${formatarMoeda(totalFinal)}</span></div>
        </div>

        ${pagamentosHTML
          ? `<div class="comp-section-label">Formas de Pagamento</div>${pagamentosHTML}`
          : `<div class="comp-pagamento">Forma de Pagamento: ${escapeHTML(item.forma_pagamento) || '-'}</div>`}

        <div class="comp-validacao">
          <div class="comp-codigo">${escapeHTML(codigoValidacao)}</div>
          <div class="comp-qr">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><path d="M14 14h3v3h-3zM19 14h2v2h-2zM14 19h2v2h-2zM19 19h2v2h-2z"/></svg>
          </div>
          <p>Código para validação digital</p>
        </div>

        <div class="comp-footer">
          Transação Autorizada com Sucesso<br>
          Agradecemos a preferência! <strong>SENAI — Formando Profissionais.</strong>
        </div>
      `;
    }

    function abrirComprovanteModal(id) {
      const item = vendas.find(v => String(v.id) === String(id));
      if (!item) {
        mostrarToast('Não foi possível localizar essa venda para gerar o comprovante.', 'error');
        return;
      }
      const conteudo = document.getElementById('comprovanteConteudo');
      conteudo.innerHTML = montarComprovanteHTML(item);
      const overlay = document.getElementById('comprovanteModalOverlay');
      overlay.classList.add('open');
      abrirModalComFoco(overlay, overlay.querySelector('.detail-close'));
    }

    function fecharComprovanteModal(e) {
      if (e && e.target !== e.currentTarget) return;
      fecharModalComFoco(document.getElementById('comprovanteModalOverlay'));
    }

    function imprimirComprovante() {
      window.print();
    }

    // ===== CADASTROS/EDIÇÕES VIA API =====
    // MEXI AQUI: atualização otimista — cada form aplica a alteração no
    // array local (inserindo/atualizando o item) e re-renderiza só o
    // necessário antes mesmo da resposta do servidor voltar. Se o servidor
    // confirmar (2xx), sincroniza o item com os dados reais retornados
    // (garante que id gerado pelo backend, timestamps etc. fiquem corretos).
    // Se falhar, desfaz a alteração local e mostra o erro.
    async function salvarNoBanco(endpoint, payload, formEvent, method = 'POST', endpointKey = null, applyLocal = null, revertLocal = null) {
      // Aplica otimisticamente antes de esperar a rede, se uma função de
      // aplicação local foi fornecida.
      if (applyLocal) {
        applyLocal();
        renderTudo();
      }

      try {
        const resposta = await apiFetch(endpoint, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (resposta.ok) {
          formEvent.target.reset();
          limparImagemProduto();
          limparVariacoes();
          const submitBtn = document.getElementById('prodSubmitBtn');
          if (submitBtn) submitBtn.innerText = '+ Cadastrar Produto';
          const assocBtn = document.getElementById('assocSubmitBtn');
          if (assocBtn) assocBtn.innerText = '+ Cadastrar Associado';
          const armBtn = document.getElementById('armSubmitBtn');
          if (armBtn) armBtn.innerText = '+ Cadastrar Armário';
          const vendaBtn = document.getElementById('vendaSubmitBtn');
          if (vendaBtn) vendaBtn.innerText = '+ Concluir Venda';
          const vendaResumo = document.getElementById('vendaResumoWrap');
          if (vendaResumo) vendaResumo.style.display = 'none';
          toggleArmarioNomeField();

          // MEXI AQUI: encadeamento rápido de vendas — volta o pagamento pra
          // uma única linha em PIX e já foca o campo Cliente, pra registrar
          // a próxima venda sem precisar tocar no mouse.
          if (endpointKey === 'venda') {
            limparPagamentoRows('PIX', null);
            const campoCliente = document.getElementById('vendaCliente');
            if (campoCliente) campoCliente.focus();
          }

          // Reconcilia com o servidor: como o backend pode gerar id/campos
          // derivados, ainda buscamos os dados atualizados — mas isso agora
          // acontece DEPOIS de já termos mostrado o resultado otimista, sem
          // bloquear a UI nem gerar sensação de lentidão.
          await carregarDadosDoBanco();

          if (endpointKey) {
            const acao = method === 'POST' ? 'criar' : 'editar';
            mostrarToast(mensagemSucesso(endpointKey, acao), 'success');
          }
        } else {
          if (revertLocal) { revertLocal(); renderTudo(); }
          const erroDetalhe = await resposta.json().catch(() => ({}));
          if (erroDetalhe.detail) {
            mostrarToast(erroDetalhe.detail, 'error');
          } else {
            mostrarToast('Erro ao gravar os dados no banco de dados.', 'error', `Código: ${resposta.status}`);
          }
        }
      } catch (erro) {
        if (revertLocal) { revertLocal(); renderTudo(); }
        console.error('Erro na requisição ao servidor:', erro);
        mostrarToast('Não foi possível conectar ao servidor.', 'error', 'Verifique se o backend está no ar.');
      }
    }

    function addCategoria(e) {
      e.preventDefault();
      const id = document.getElementById('catId').value;
      const payload = {
        nome: document.getElementById('catNome').value,
        codigo: document.getElementById('catCodigo').value || '',
        descricao: document.getElementById('catDesc').value || ''
      };
      const endpoint = id ? `${API_URLS.categoria}/${id}` : API_URLS.categoria;
      salvarNoBanco(endpoint, payload, e, id ? 'PUT' : 'POST', 'categoria');
      document.getElementById('catId').value = '';
    }

    function addFornecedor(e) {
      e.preventDefault();
      const editId = e.target.dataset.editId;
      const payload = {
        nome: document.getElementById('fornNome').value,
        documento: document.getElementById('fornDoc').value,
        email: document.getElementById('fornEmail').value || '',
        telefone: document.getElementById('fornTel').value || ''
      };
      const endpoint = editId ? `${API_URLS.fornecedor}/${editId}` : API_URLS.fornecedor;
      salvarNoBanco(endpoint, payload, e, editId ? 'PUT' : 'POST', 'fornecedor');
      delete e.target.dataset.editId;
    }

    function limparImagemProduto() {
      imagemProdutoPendente = null;
      const preview = document.getElementById('prodImgPreview');
      if (preview) {
        preview.src = '';
        preview.style.display = 'none';
      }
      const input = document.getElementById('prodImagem');
      if (input) input.value = '';
      const url = document.getElementById('prodImagemUrl');
      if (url) url.value = '';
      const label = document.getElementById('prodImagemFileName');
      if (label) label.innerText = 'Escolher imagem do produto';
    }

    async function addProduto(e) {
      e.preventDefault();
      const id = document.getElementById('prodId').value;
      const submitBtn = document.getElementById('prodSubmitBtn');

      // MEXI AQUI: nunca deixa preço/quantidade negativos saírem do form
      const precoInformado = Math.max(0, parseFloat(document.getElementById('prodPreco').value) || 0);
      const quantidadeInformada = Math.max(0, parseInt(document.getElementById('prodQuantidade').value || '0', 10));

      const payload = {
        nome: document.getElementById('prodNome').value,
        categoria_id: document.getElementById('prodCategoria').value || null,
        preco: precoInformado,
        tamanho: document.getElementById('prodTamanho').value || '',
        quantidade: quantidadeInformada,
        imagem_url: document.getElementById('prodImagemUrl').value || '',
        variacoes: coletarVariacoes(),
        disponivel: 1
      };
      if (imagemProdutoPendente) {
        submitBtn.disabled = true;
        submitBtn.innerText = 'Enviando imagem...';
        try {
          payload.imagem_url = await enviarImagemProduto(imagemProdutoPendente);
        } catch (erro) {
          console.error('Erro no upload da imagem:', erro);
          mostrarToast('Não foi possível enviar a imagem do produto.', 'error');
          submitBtn.disabled = false;
          submitBtn.innerText = id ? 'Salvar Alterações' : '+ Cadastrar Produto';
          return;
        }
        submitBtn.disabled = false;
        submitBtn.innerText = id ? 'Salvar Alterações' : '+ Cadastrar Produto';
      }
      const endpoint = id ? `${API_URLS.produto}/${id}` : API_URLS.produto;
      salvarNoBanco(endpoint, payload, e, id ? 'PUT' : 'POST', 'produto');
      document.getElementById('prodId').value = '';
    }

    function addAssociado(e) {
      e.preventDefault();
      const id = document.getElementById('assocId').value;
      const payload = {
        nome: document.getElementById('assocNome').value,
        email: document.getElementById('assocEmail').value,
        telefone: document.getElementById('assocTelefone').value || '',
        endereco: document.getElementById('assocEndereco').value || '',
        status: 'Ativo'
      };
      const endpoint = id ? `${API_URLS.associado}/${id}` : API_URLS.associado;
      salvarNoBanco(endpoint, payload, e, id ? 'PUT' : 'POST', 'associado');
      document.getElementById('assocId').value = '';
    }

    function addArmario(e) {
      e.preventDefault();
      const id = document.getElementById('armId').value;
      const payload = {
        numero: document.getElementById('armNumero').value,
        localizacao: document.getElementById('armLocalizacao').value || null,
        status: document.getElementById('armStatus').value,
        nome_completo: document.getElementById('armNomeCompleto').value || null
      };
      const endpoint = id ? `${API_URLS.armario}/${id}` : API_URLS.armario;
      salvarNoBanco(endpoint, payload, e, id ? 'PUT' : 'POST', 'armario');
      document.getElementById('armId').value = '';
    }

    function addUsuario(e) {
      e.preventDefault();
      const id = document.getElementById('usrId').value;
      const payload = {
        nome: document.getElementById('usrNome').value,
        email: document.getElementById('usrEmail').value,
        perfil: document.getElementById('usrPerfil').value,
        senha: document.getElementById('usrSenha').value || null,
        status: 'Ativo'
      };
      const endpoint = id ? `${API_URLS.usuario}/${id}` : API_URLS.usuario;
      salvarNoBanco(endpoint, payload, e, id ? 'PUT' : 'POST', 'usuario');
      document.getElementById('usrId').value = '';
    }

    // MEXI AQUI: addVenda agora resolve o produto pelo campo de busca (não
    // mais um <select>), valida que o produto foi resolvido pra um ID real,
    // e monta o array de pagamentos divididos — bloqueando o envio se a
    // soma das formas de pagamento não bater com o total da venda.
    function addVenda(e) {
      e.preventDefault();
      const id = document.getElementById('vendaId').value;
      const produtoId = document.getElementById('vendaProduto').value;

      if (!produtoId) {
        mostrarToast('Selecione um produto válido na lista de sugestões.', 'error');
        document.getElementById('vendaProdutoBusca').focus();
        return;
      }

      const qtd = Math.max(1, parseInt(document.getElementById('vendaQtd').value, 10) || 1);
      const associadoIdRaw = document.getElementById('vendaAssociado').value;
      const associadoId = associadoIdRaw ? parseInt(associadoIdRaw) : null;

      const produto = produtos.find(p => String(p.id) === String(produtoId));
      const subtotal = produto ? Number(produto.preco) * qtd : 0;
      const percentualDesconto = associadoId ? 10 : 0;
      const desconto = subtotal * (percentualDesconto / 100);
      const total = Math.round((subtotal - desconto) * 100) / 100;

      const pagamentos = coletarPagamentos();
      if (!pagamentos.length) {
        mostrarToast('Informe ao menos uma forma de pagamento com valor.', 'error');
        return;
      }
      const somaPagamentos = Math.round(pagamentos.reduce((acc, p) => acc + p.valor, 0) * 100) / 100;
      if (Math.abs(somaPagamentos - total) > 0.02) {
        mostrarToast(
          `A soma dos pagamentos (${formatarMoeda(somaPagamentos)}) não bate com o total da venda (${formatarMoeda(total)}).`,
          'error'
        );
        return;
      }

      const payload = {
        cliente: document.getElementById('vendaCliente').value,
        produto_id: parseInt(produtoId),
        quantidade: qtd,
        forma_pagamento: pagamentos.map(p => p.forma_pagamento).join(' + '),
        pagamentos,
        associado_id: associadoId,
        desconto_percentual: percentualDesconto,
        preco_total: total
      };
      const endpoint = id ? `${API_URLS.venda}/${id}` : API_URLS.venda;
      salvarNoBanco(endpoint, payload, e, id ? 'PUT' : 'POST', 'venda');
      document.getElementById('vendaId').value = '';
    }

  function logout() {
  const overlay = document.getElementById('logoutOverlay');
  if (overlay) overlay.classList.add('active');

  setTimeout(() => {
    localStorage.clear();
    sessionStorage.clear();

    document.cookie.split(";").forEach((c) => {
      document.cookie = c
        .replace(/^ +/, "")
        .replace(/=.*/, "=;expires=" + new Date().toUTCString() + ";path=/");
    });

    window.location.href = '/'; 
  }, 1200);
}

    // ===== CENA ESPACIAL DE FUNDO (nebulosa + estrelas em profundidade + cadentes) =====
    (function initSpaceScene() {
      const canvas = document.getElementById('bg-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');

      function resize() {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        generateScene();
      }

      let stars = [];
      let nebulae = [];
      let shootingStars = [];

      function generateStars() {
        stars = [];
        const layers = [
          { count: Math.round((canvas.width * canvas.height) / 22000), sizeMin: 0.5, sizeMax: 1.1, alphaMax: 0.55, drift: 0.015 },
          { count: Math.round((canvas.width * canvas.height) / 16000), sizeMin: 0.8, sizeMax: 1.6, alphaMax: 0.75, drift: 0.03  },
          { count: Math.round((canvas.width * canvas.height) / 30000), sizeMin: 1.3, sizeMax: 2.3, alphaMax: 0.95, drift: 0.05  }
        ];
        layers.forEach((layer, layerIndex) => {
          for (let i = 0; i < layer.count; i++) {
            const r = Math.random();
            let color = '255, 255, 255';
            if (r < 0.15) color = '214, 50, 80';
            else if (r < 0.28) color = '0, 140, 255';
            stars.push({
              x: Math.random() * canvas.width,
              y: Math.random() * canvas.height,
              size: Math.random() * (layer.sizeMax - layer.sizeMin) + layer.sizeMin,
              baseAlpha: Math.random() * 0.4 + (layer.alphaMax - 0.4),
              twinkleSpeed: Math.random() * 0.018 + 0.004,
              twinklePhase: Math.random() * Math.PI * 2,
              drift: (Math.random() - 0.5) * layer.drift,
              layer: layerIndex,
              color
            });
          }
        });
      }

      function generateNebulae() {
        nebulae = [
          { xR: 0.20, yR: 0.25, radius: Math.max(canvas.width, canvas.height) * 0.40, hue: 344, phase: 0,   speed: 0.0016 },
          { xR: 0.82, yR: 0.60, radius: Math.max(canvas.width, canvas.height) * 0.36, hue: 205, phase: 2.1, speed: 0.0012 },
          { xR: 0.55, yR: 0.88, radius: Math.max(canvas.width, canvas.height) * 0.32, hue: 260, phase: 4.4, speed: 0.0019 }
        ];
      }

      function generateScene() {
        generateStars();
        generateNebulae();
      }

      resize();
      window.addEventListener('resize', resize);

      let mouseX = 0, mouseY = 0, parX = 0, parY = 0;
      window.addEventListener('mousemove', (e) => {
        mouseX = (e.clientX / window.innerWidth - 0.5) * 2;
        mouseY = (e.clientY / window.innerHeight - 0.5) * 2;
      });

      function maybeSpawnShootingStar() {
        if (Math.random() < 0.012 && shootingStars.length < 5) {
          const startX = Math.random() * canvas.width * 0.8 + canvas.width * 0.1;
          const big = Math.random() < 0.25;
          const tint = Math.random() < 0.25 ? '0, 140, 255' : '255, 255, 255';
          shootingStars.push({
            x: startX,
            y: -20,
            vx: -(2.6 + Math.random() * 3.2),
            vy: 3.8 + Math.random() * 3.4,
            life: 1,
            length: (big ? 130 : 80) + Math.random() * 60,
            headSize: big ? 2.6 : 1.5,
            width: big ? 2.6 : 1.6,
            color: tint
          });
        }
      }

      function isLightTheme() {
        return document.documentElement.getAttribute('data-theme') === 'light';
      }

      function drawNebulae(time) {
        if (isLightTheme()) return;
        nebulae.forEach((n) => {
          const pulse = (Math.sin(time * n.speed + n.phase) + 1) / 2;
          const cx = canvas.width * n.xR + parX * 20;
          const cy = canvas.height * n.yR + parY * 20;
          const r = n.radius * (0.85 + pulse * 0.18);
          const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
          grad.addColorStop(0, `hsla(${n.hue}, 75%, 48%, ${0.14 + pulse * 0.07})`);
          grad.addColorStop(0.5, `hsla(${n.hue}, 75%, 42%, ${0.07 + pulse * 0.04})`);
          grad.addColorStop(1, `hsla(${n.hue}, 75%, 32%, 0)`);
          ctx.fillStyle = grad;
          ctx.fillRect(0, 0, canvas.width, canvas.height);
        });
      }

      function drawStars() {
        const light = isLightTheme();
        stars.forEach((star) => {
          star.twinklePhase += star.twinkleSpeed;
          const twinkle = (Math.sin(star.twinklePhase) + 1) / 2;
          const alpha = star.baseAlpha * (0.3 + twinkle * 0.7) * (light ? 0.7 : 1);

          star.x += star.drift;
          if (star.x < 0) star.x = canvas.width;
          if (star.x > canvas.width) star.x = 0;

          const px = star.x + parX * (star.layer + 1) * 6;
          const py = star.y + parY * (star.layer + 1) * 6;

          const color = light ? (star.color === '255, 255, 255' ? '214, 50, 80' : star.color) : star.color;

          ctx.beginPath();
          ctx.fillStyle = `rgba(${color}, ${alpha})`;
          if (!light) {
            ctx.shadowColor = `rgba(${color}, ${Math.min(alpha + 0.25, 1)})`;
            ctx.shadowBlur = star.size * (2.5 + star.layer * 1.5);
          }
          ctx.arc(px, py, star.size, 0, Math.PI * 2);
          ctx.fill();
        });
        ctx.shadowBlur = 0;
      }

      function drawShootingStars() {
        const light = isLightTheme();
        shootingStars.forEach((s) => {
          const color = light ? '214, 50, 80' : s.color;
          const tailX = s.x - s.vx * (s.length / 10);
          const tailY = s.y - s.vy * (s.length / 10);
          const grad = ctx.createLinearGradient(s.x, s.y, tailX, tailY);
          grad.addColorStop(0, `rgba(${color}, ${s.life * (light ? 0.55 : 1)})`);
          grad.addColorStop(1, `rgba(${color}, 0)`);
          ctx.strokeStyle = grad;
          ctx.lineWidth = s.width;
          ctx.beginPath();
          ctx.moveTo(s.x, s.y);
          ctx.lineTo(tailX, tailY);
          ctx.stroke();

          ctx.beginPath();
          ctx.fillStyle = `rgba(${color}, ${s.life * (light ? 0.55 : 1)})`;
          if (!light) {
            ctx.shadowColor = `rgba(${color}, 0.9)`;
            ctx.shadowBlur = s.headSize * 5;
          }
          ctx.arc(s.x, s.y, s.headSize, 0, Math.PI * 2);
          ctx.fill();
          ctx.shadowBlur = 0;

          s.x += s.vx;
          s.y += s.vy;
          if (s.y > canvas.height * 0.9 || s.x < -50) s.life -= 1;
        });
        shootingStars = shootingStars.filter((s) => s.life > 0 && s.y < canvas.height + 50);
      }

      let t = 0;
      let cenaAtiva = !document.hidden;
      let animationFrameId = null;
      function animate() {
        if (!cenaAtiva) {
          animationFrameId = null;
          return;
        }
        parX += (mouseX - parX) * 0.03;
        parY += (mouseY - parY) * 0.03;

        ctx.clearRect(0, 0, canvas.width, canvas.height);
        drawNebulae(t);
        drawStars();
        maybeSpawnShootingStar();
        drawShootingStars();

        t += 1;
        animationFrameId = requestAnimationFrame(animate);
      }
      document.addEventListener('visibilitychange', () => {
        cenaAtiva = !document.hidden;
        if (cenaAtiva && animationFrameId === null) animate();
      });
      animate();
    })();

    // FUNÇÃO AUXILIAR: OBSERVA ELEMENTOS .reveal PARA ANIMAÇÃO DE ENTRADA
    function observeReveals() {
      const els = document.querySelectorAll('.reveal:not(.in-view)');
      if (!('IntersectionObserver' in window)) {
        els.forEach(el => el.classList.add('in-view'));
        return;
      }
      const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('in-view');
            observer.unobserve(entry.target);
          }
        });
      }, { threshold: 0.1 });
      els.forEach(el => observer.observe(el));
    }

    // INICIALIZAÇÃO ASSÍNCRONA
    window.onload = async function () {
      if (!await validarSessaoInicial()) return;
      document.body.classList.remove('auth-loading');
      document.body.classList.add('admin-entering');
      limparPagamentoRows('PIX', null);
      carregarDadosDoBanco();
      atualizarDataHora();
      toggleArmarioNomeField();
      setInterval(atualizarDataHora, 30000);
      observeReveals();
    };