// admin.html
  const token = localStorage.getItem('access_token');
  if (!token) {
    alert('Acesso restrito! Faça o login primeiro.');
    window.location.href = 'login.html';
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

    // ================================================================== //
    // MEXI AQUI: ===== CAMADA DE SEGURANÇA (auth + XSS) =====             //
    // ================================================================== //

    // Wrapper único para TODAS as chamadas à API: sempre injeta o Bearer
    // token no header e trata 401/403 fazendo logout automático. Antes,
    // nenhuma chamada `fetch()` mandava o token — o "acesso restrito" do
    // topo do arquivo era só cosmético, e qualquer requisição direta à API
    // passava sem autenticação nenhuma.
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

    // Escapa qualquer texto antes de injetar em innerHTML, prevenindo XSS.
    // Antes, campos como nome/email/descrição vindos do banco eram jogados
    // direto em template strings dentro de innerHTML sem nenhum tratamento —
    // um nome de produto ou cliente contendo HTML/JS malicioso seria executado.
    function escapeHTML(valor) {
      if (valor === null || valor === undefined) return '';
      return String(valor)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
    }

    // Formata valores monetários no padrão brasileiro (R$ 1.234,56) em vez
    // do antigo `'R$ ' + Number(x).toFixed(2)`, que não agrupava milhares
    // nem usava vírgula decimal.
    const formatadorMoeda = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
    function formatarMoeda(valor) {
      const numero = Number(valor);
      return formatadorMoeda.format(isNaN(numero) ? 0 : numero);
    }

    // Substitui window.confirm() nativo por um modal customizado que segue
    // a identidade visual do painel. Retorna uma Promise<boolean>, então o
    // código que chama continua podendo usar `await confirmarAcao(...)`.
    function confirmarAcao(mensagem, tituloBotaoConfirmar = 'Confirmar') {
      return new Promise((resolve) => {
        const overlay = document.getElementById('confirmModalOverlay');
        const textoEl = document.getElementById('confirmModalTexto');
        const btnOk = document.getElementById('confirmModalOk');
        const btnCancelar = document.getElementById('confirmModalCancelar');

        textoEl.textContent = mensagem;
        btnOk.textContent = tituloBotaoConfirmar;
        overlay.classList.add('open');

        function limpar(resultado) {
          overlay.classList.remove('open');
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

    // BASES DE DADOS (carregadas via API do Banco)
    let categorias = [];
    let fornecedores = [];
    let produtos = [];
    let associados = [];
    let armarios = [];
    let usuarios = [];
    let vendas = [];

    // MEXI AQUI: paginação client-side — mantém carregarDadosDoBanco() trazendo
    // a lista inteira de cada módulo (pois ela também alimenta stats, selects
    // e notificações), mas cada tabela agora é fatiada e exibida em páginas de
    // ITENS_POR_PAGINA itens, com os botões "Anterior/Próximo" no rodapé.
    const ITENS_POR_PAGINA = 10;
    let paginaAtual = {
      categoria: 1,
      fornecedor: 1,
      produto: 1,
      associado: 1,
      armario: 1,
      usuario: 1,
      venda: 1
    };

    // MEXI AQUI: ===== TOASTS DE FEEDBACK (sucesso / erro) PARA TODOS OS CRUDS =====
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

    // MEXI AQUI: mensagem e sub também passam por escapeHTML() antes de virar
    // innerHTML — o texto do toast normalmente vem de constantes internas,
    // mas parte dele (ex: erroDetalhe.detail vindo do backend) é dado externo.
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
        desconto_percentual: v.desconto_percentual ?? 0
      };
    }

    // ===== CONTROLADOR DE CARREGAMENTO (GET DE TODAS AS ENTIDADES) =====
    // MEXI AQUI: todas as chamadas fetch() trocadas por apiFetch(), que já
    // injeta o Bearer token automaticamente.
    async function carregarDadosDoBanco() {
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

        renderCategorias();
        renderFornecedores();
        renderProdutos();
        renderAssociados();
        renderArmarios();
        renderUsuarios();
        renderVendas();
        popularSelectsDinamicos();
        renderNotificacoes();

        const active = document.querySelector('.view-content.active');
        const activeId = active ? active.id : 'categoria';
        renderStatsBar(activeId);
        renderRecentList(activeId);
      } catch (erro) {
        console.error('Erro ao conectar e buscar dados do Banco de Dados:', erro);
      }
    }

    // MEXI AQUI: nomes de categoria/produto/associado nos <option> também
    // passam por escapeHTML() — evita que um nome cadastrado com aspas ou
    // tags quebre o innerHTML do select.
    function popularSelectsDinamicos() {
      const selCategoria = document.getElementById('prodCategoria');
      const valorAtualCat = selCategoria.value;
      selCategoria.innerHTML = '<option value="">Selecione...</option>' +
        categorias.map(c => `<option value="${escapeHTML(c.id)}">${escapeHTML(c.nome)}</option>`).join('');
      if (valorAtualCat) selCategoria.value = valorAtualCat;

      const selProduto = document.getElementById('vendaProduto');
      const valorAtualProd = selProduto.value;
      selProduto.innerHTML = '<option value="">Selecione...</option>' +
        produtos.map(p => `<option value="${escapeHTML(p.id)}">${escapeHTML(p.nome)} (${formatarMoeda(p.preco)})</option>`).join('');
      if (valorAtualProd) selProduto.value = valorAtualProd;

      const selAssociado = document.getElementById('vendaAssociado');
      if (selAssociado) {
        const valorAtualAssoc = selAssociado.value;
        selAssociado.innerHTML = '<option value="">Não é associado</option>' +
          associados.map(a => `<option value="${escapeHTML(a.id)}">${escapeHTML(a.nome)}</option>`).join('');
        if (valorAtualAssoc) selAssociado.value = valorAtualAssoc;
      }
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

    function montarNotificacoes() {
      const itens = [];
      vendas.slice(0, 3).forEach(v => itens.push({ tipo: 'venda', titulo: 'Nova venda registrada', sub: `${v.produto_nome} · ${v.data_venda || ''}`, ordem: v.id }));
      produtos.slice(-2).reverse().forEach(p => itens.push({ tipo: 'produto', titulo: 'Produto cadastrado', sub: p.nome, ordem: p.id }));
      associados.slice(-2).reverse().forEach(a => itens.push({ tipo: 'associado', titulo: 'Associado cadastrado', sub: a.nome, ordem: a.id }));
      armarios.slice(-2).reverse().forEach(a => itens.push({ tipo: 'armario', titulo: 'Armário cadastrado', sub: `Nº ${a.numero} · ${a.status}`, ordem: a.id }));
      usuarios.slice(-2).reverse().forEach(u => itens.push({ tipo: 'usuario', titulo: 'Novo usuário cadastrado', sub: u.nome, ordem: u.id }));
      categorias.slice(-1).reverse().forEach(c => itens.push({ tipo: 'categoria', titulo: 'Categoria cadastrada', sub: c.nome, ordem: c.id }));
      fornecedores.slice(-1).reverse().forEach(f => itens.push({ tipo: 'fornecedor', titulo: 'Fornecedor cadastrado', sub: f.nome, ordem: f.id }));
      return itens.sort((a, b) => (b.ordem || 0) - (a.ordem || 0)).slice(0, 6);
    }

    // MEXI AQUI: título/sub das notificações passam por escapeHTML()
    function renderNotificacoes() {
      const list = document.getElementById('notifList');
      const dot = document.querySelector('.notif-dot');
      const notificacoes = montarNotificacoes();
      list.innerHTML = notificacoes.length ? notificacoes.map(n => `
        <div class="notif-item">
          <div class="ni-icon">${notificacoesIcones[n.tipo] || notificacoesIcones.venda}</div>
          <div>
            <div class="ni-title">${escapeHTML(n.titulo)}</div>
            <div class="ni-time">${escapeHTML(n.sub)}</div>
          </div>
        </div>
      `).join('') : '<div class="recent-empty">Nenhuma notificação nova.</div>';
      if (dot) dot.style.display = notificacoes.length ? 'block' : 'none';
    }

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

      document.getElementById('avatarModalOverlay').classList.add('open');
    }

    function fecharAvatarModal(e) {
      if (e && e.target !== e.currentTarget) return;
      document.getElementById('avatarModalOverlay').classList.remove('open');
    }

    // ===== MODAL: DETALHES DO PRODUTO =====
    // MEXI AQUI: nome/categoria/tamanho e nome_variacao agora passam por
    // escapeHTML() ou são atribuídos via textContent, e não innerHTML cru.
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
      document.getElementById('produtoModalOverlay').classList.add('open');
    }

    function fecharProdutoModal(e) {
      if (e && e.target !== e.currentTarget) return;
      document.getElementById('produtoModalOverlay').classList.remove('open');
    }

    document.addEventListener('keydown', (e) => {
      if (e.key !== 'Escape') return;
      document.getElementById('produtoModalOverlay')?.classList.remove('open');
      document.getElementById('avatarModalOverlay')?.classList.remove('open');
      document.getElementById('comprovanteModalOverlay')?.classList.remove('open');
      document.getElementById('cropModalOverlay')?.classList.remove('open');
      document.getElementById('confirmModalOverlay')?.classList.remove('open');
    });

    // MEXI AQUI: ===== RECORTE DE IMAGEM DO PRODUTO (Cropper.js) =====
    let cropperInstance = null;
    let cropArquivoOriginal = null;

    function handleProdutoImagem(e) {
      const file = e.target.files && e.target.files[0];
      if (!file) return;

      cropArquivoOriginal = file;
      const imgSrc = document.getElementById('cropImageSource');
      imgSrc.src = URL.createObjectURL(file);

      document.getElementById('cropModalOverlay').classList.add('open');

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
      document.getElementById('cropModalOverlay').classList.remove('open');
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

        document.getElementById('cropModalOverlay').classList.remove('open');
        cropperInstance.destroy();
        cropperInstance = null;

        enviarImagemProduto(arquivoRecortado);
      }, cropArquivoOriginal ? cropArquivoOriginal.type : 'image/png', 0.92);
    }

    // FOTO DO PRODUTO — envia para o backend e guarda a URL retornada.
    // MEXI AQUI: usa apiFetch() em vez de fetch() para incluir o Bearer token
    // (o upload de imagem também é um endpoint autenticado).
    async function enviarImagemProduto(file) {
      const fileNameLabel = document.getElementById('prodImagemFileName');
      if (fileNameLabel) fileNameLabel.innerText = file.name;

      const submitBtn = document.getElementById('prodSubmitBtn');
      submitBtn.disabled = true;
      submitBtn.innerText = 'Enviando imagem...';

      const formData = new FormData();
      formData.append('arquivo', file);

      try {
        const resposta = await apiFetch(API_URLS.upload, { method: 'POST', body: formData });
        if (resposta.ok) {
          const dados = await resposta.json();
          document.getElementById('prodImagemUrl').value = dados.url;
        } else {
          mostrarToast('Erro ao enviar a imagem do produto.', 'error');
        }
      } catch (erro) {
        console.error('Erro no upload da imagem:', erro);
        mostrarToast('Erro na comunicação com o servidor ao enviar a imagem.', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.innerText = document.getElementById('prodId').value ? 'Salvar Alterações' : '+ Cadastrar Produto';
      }
    }

    // ===== VARIAÇÕES DO PRODUTO (tamanho/cor/etc, cada uma com seu próprio estoque) =====
    let variacaoRowSeq = 0;

    // MEXI AQUI: o valor de "nome" agora é atribuído via propriedade .value
    // do input (depois de criado), não mais interpolado dentro do innerHTML —
    // elimina o escape manual de aspas que só cobria um caso e ainda deixava
    // brecha para XSS via outros caracteres.
    function adicionarVariacaoRow(nome = '', estoque = '') {
      const wrap = document.getElementById('variacoesList');
      if (!wrap) return;
      const rowId = 'variacaoRow' + (variacaoRowSeq++);
      const row = document.createElement('div');
      row.className = 'variacao-row';
      row.id = rowId;
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
          estoque: parseInt(row.querySelector('.var-estoque').value || '0', 10)
        }))
        .filter(v => v.nome_variacao);
    }

    function limparVariacoes() {
      const wrap = document.getElementById('variacoesList');
      if (wrap) wrap.innerHTML = '';
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
      'categoria': ['Categorias', 'Organização e classificação de produtos.', 'Nova Categoria'],
      'fornecedor': ['Fornecedores', 'Cadastro e histórico de fornecedores.', 'Novo Fornecedor'],
      'produto': ['Produtos', 'Catálogo e controle de itens.', 'Novo Produto'],
      'associado': ['Associados', 'Consulta e cadastro dos associados da AAPM.', 'Novo Associado'],
      'armario': ['Armários', 'Controle de disponibilidade e ocupação dos armários.', 'Novo Armário'],
      'usuario': ['Usuários', 'Controle de acessos e permissões.', 'Novo Usuário'],
      'venda': ['Vendas', 'Registro de pedidos e transações.', 'Nova Venda']
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

      const searchInput = document.getElementById('tableSearch');
      if (searchInput) searchInput.value = '';

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

    // TEMA CLARO / ESCURO
    function toggleTheme() {
      const html = document.documentElement;
      const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
    }

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

    // Preenche o formulário do módulo com os dados do item para edição
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
        document.getElementById('vendaQtd').value = item.quantidade ?? 1;
        document.getElementById('vendaPagamento').value = item.forma_pagamento || 'PIX';
        const selAssoc = document.getElementById('vendaAssociado');
        if (selAssoc) selAssoc.value = item.associado_id ?? '';
        document.getElementById('vendaSubmitBtn').innerText = 'Salvar Alterações';
        atualizarResumoVenda();
      }

      focusForm();
    }

    // ===== EXCLUSÃO DE ITEM NO BANCO (DELETE) =====
    // MEXI AQUI: troca window.confirm() pelo modal customizado confirmarAcao(),
    // e fetch() por apiFetch() para incluir autenticação.
    async function removerItem(tipo, id) {
      const confirmado = await confirmarAcao('Confirma a exclusão deste item no banco de dados?', 'Excluir');
      if (!confirmado) return;

      const endpointKey = mapaModulos[tipo];
      if (!endpointKey) return;

      try {
        const resposta = await apiFetch(`${API_URLS[endpointKey]}/${id}`, { method: 'DELETE' });
        if (resposta.ok) {
          await carregarDadosDoBanco();
          mostrarToast(mensagemSucesso(endpointKey, 'remover'), 'success');
        } else {
          mostrarToast(`Erro ao excluir ${modulosConfig[endpointKey]?.nome.toLowerCase() || 'o registro'} no banco de dados.`, 'error');
        }
      } catch (erro) {
        console.error("Erro na comunicação com a API ao excluir:", erro);
        mostrarToast('Não foi possível conectar ao servidor para excluir o registro.', 'error');
      }
    }

    function emptyRow(cols, msg) {
      return `<tr class="empty-row"><td colspan="${cols}">${escapeHTML(msg)}</td></tr>`;
    }

    // RENDERS DAS TABELAS
    // MEXI AQUI: todo campo de texto vindo do banco (nome, descrição, código,
    // email, telefone, endereço, forma de pagamento etc.) agora passa por
    // escapeHTML() antes de entrar no innerHTML das linhas da tabela.
    function renderCategorias() {
      const tbody = document.getElementById('tblCategorias');
      const pagina = paginarLista(categorias, 'categoria');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td><span class="pill-badge">${escapeHTML(item.codigo || item.id)}</span></td>
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td>${escapeHTML(item.descricao) || '-'}</td>
          <td><span class="status-tag active">Ativo</span></td>
          <td>${renderAcoes('cat', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhuma categoria cadastrada.');
      renderPaginacaoControles('pagCategorias', 'categoria', categorias.length);
    }

    function renderFornecedores() {
      const tbody = document.getElementById('tblFornecedores');
      const pagina = paginarLista(fornecedores, 'fornecedor');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td><span class="pill-badge">${escapeHTML(item.documento)}</span></td>
          <td>${escapeHTML(item.email) || '-'}</td>
          <td>${escapeHTML(item.telefone) || '-'}</td>
          <td>${renderAcoes('forn', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhum fornecedor cadastrado.');
      renderPaginacaoControles('pagFornecedores', 'fornecedor', fornecedores.length);
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

    // MEXI AQUI: monta as chips de variação com escapeHTML() no nome e no estoque
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
      const pagina = paginarLista(produtos, 'produto');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}; cursor:pointer;" onclick="abrirProdutoModal('${item.id}')" title="Ver detalhes do produto">
          <td onclick="event.stopPropagation()"><input type="checkbox" name="produtoDeleteCheck" value="${item.id}" style="width: 15px; height: 15px; accent-color: var(--primary);"></td>
          <td>${item.imagem_url ? `<img class="prod-thumb" src="${escapeHTML(item.imagem_url)}" alt="${escapeHTML(item.nome)}">` : `<div class="prod-thumb"></div>`}</td>
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td>${escapeHTML(nomeCategoriaPorId(item.categoria_id))}</td>
          <td>${renderVariationChipsAdmin(item)}</td>
          <td><span class="pill-badge">${escapeHTML(item.quantidade ?? 0)}</span></td>
          <td style="font-weight: 700; color: var(--success);">${formatarMoeda(item.preco)}</td>
          <td>${renderAcoes('prod', item.id)}</td>
        </tr>
      `).join('') : emptyRow(8, 'Nenhum produto cadastrado.');
      renderPaginacaoControles('pagProdutos', 'produto', produtos.length);
    }

    // MEXI AQUI: troca window.confirm() pelo modal customizado confirmarAcao()
    // e fetch() por apiFetch().
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
          return;
        }
      }

      await carregarDadosDoBanco();
      mostrarToast(`${selecionados.length} produto(s) removido(s) com sucesso!`, 'success');
    }

    function renderAssociados() {
      const tbody = document.getElementById('tblAssociados');
      if (!tbody) return;
      const pagina = paginarLista(associados, 'associado');
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
      renderPaginacaoControles('pagAssociados', 'associado', associados.length);
    }

    function statusArmarioClasse(status) {
      if (status === 'Disponível') return 'active';
      if (status === 'Ocupado') return 'inactive';
      return 'warning';
    }

    function renderArmarios() {
      const tbody = document.getElementById('tblArmarios');
      if (!tbody) return;
      const pagina = paginarLista(armarios, 'armario');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td><span class="pill-badge">${escapeHTML(item.numero)}</span></td>
          <td>${escapeHTML(item.localizacao) || '-'}</td>
          <td><span class="status-tag ${statusArmarioClasse(item.status)}">${escapeHTML(item.status || 'Disponível')}</span></td>
          <td>${escapeHTML(item.nome_completo) || '-'}</td>
          <td>${renderAcoes('arm', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhum armário cadastrado.');
      renderPaginacaoControles('pagArmarios', 'armario', armarios.length);
    }

    function renderUsuarios() {
      const tbody = document.getElementById('tblUsuarios');
      const pagina = paginarLista(usuarios, 'usuario');
      tbody.innerHTML = pagina.length ? pagina.map((item, i) => `
        <tr style="--i:${i}">
          <td style="font-weight: 700;">${escapeHTML(item.nome)}</td>
          <td>${escapeHTML(item.email)}</td>
          <td><span class="pill-badge">${escapeHTML(item.perfil)}</span></td>
          <td><span class="status-tag ${(item.status || 'Ativo') === 'Ativo' ? 'active' : 'inactive'}">${escapeHTML(item.status || 'Ativo')}</span></td>
          <td>${renderAcoes('usr', item.id)}</td>
        </tr>
      `).join('') : emptyRow(5, 'Nenhum usuário cadastrado.');
      renderPaginacaoControles('pagUsuarios', 'usuario', usuarios.length);
    }

    function renderVendas() {
      const tbody = document.getElementById('tblVendas');
      if (!tbody) return;
      const pagina = paginarLista(vendas, 'venda');
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
      renderPaginacaoControles('pagVendas', 'venda', vendas.length);
    }

    Object.assign(renderizadoresPorModulo, {
      categoria: renderCategorias,
      fornecedor: renderFornecedores,
      produto: renderProdutos,
      associado: renderAssociados,
      armario: renderArmarios,
      usuario: renderUsuarios,
      venda: renderVendas
    });

    // BARRA DE ESTATÍSTICAS DINÂMICA
    // MEXI AQUI: valores monetários usam formatarMoeda() em vez de toFixed(2) cru
    function computeStats(viewId) {
      switch (viewId) {
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

    function refreshStats() {
      const active = document.querySelector('.view-content.active');
      if (active) {
        renderStatsBar(active.id);
        renderRecentList(active.id);
      }
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
        default:
          return [];
      }
    }

    // MEXI AQUI: título/sub dos "últimos registros" passam por escapeHTML()
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

    function filtrarTabelaAtiva() {
      const termo = document.getElementById('tableSearch').value.trim().toLowerCase();
      const active = document.querySelector('.view-content.active');
      if (!active) return;
      const rows = active.querySelectorAll('tbody tr:not(.empty-row)');
      rows.forEach(row => {
        const texto = row.innerText.toLowerCase();
        row.style.display = texto.includes(termo) ? '' : 'none';
      });
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

    // MEXI AQUI: ===== RESUMO DE VALORES DA VENDA (subtotal / desconto associado 10% / total) =====
    // Agora usa formatarMoeda() em vez de 'R$ ' + toFixed(2).
    function atualizarResumoVenda() {
      const produtoId = document.getElementById('vendaProduto').value;
      const qtd = parseInt(document.getElementById('vendaQtd').value || '0', 10);
      const associadoId = document.getElementById('vendaAssociado').value;
      const resumoWrap = document.getElementById('vendaResumoWrap');

      const produto = produtos.find(p => String(p.id) === String(produtoId));
      if (!produto || !qtd) {
        resumoWrap.style.display = 'none';
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
    }

    // ================================================================== //
    // MEXI AQUI: ===== COMPROVANTE DE VENDA IMPRIMÍVEL (estilo cupom) ===== //
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

    // Monta o HTML do cupom a partir dos dados de uma venda já registrada.
    // MEXI AQUI: campos vindos de dados do cliente/associado/produto agora
    // passam por escapeHTML(), e valores monetários usam formatarMoeda().
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

        <div class="comp-pagamento">Forma de Pagamento: ${escapeHTML(item.forma_pagamento) || '-'}</div>

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
      document.getElementById('comprovanteModalOverlay').classList.add('open');
    }

    function fecharComprovanteModal(e) {
      if (e && e.target !== e.currentTarget) return;
      document.getElementById('comprovanteModalOverlay').classList.remove('open');
    }

    function imprimirComprovante() {
      window.print();
    }

    // ===== CADASTROS/EDIÇÕES VIA API =====
    // MEXI AQUI: usa apiFetch() em vez de fetch() para incluir o Bearer token
    // em toda operação de escrita (POST/PUT).
    async function salvarNoBanco(endpoint, payload, formEvent, method = 'POST', endpointKey = null) {
      try {
        const resposta = await apiFetch(endpoint, {
          method,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });

        if (resposta.ok) {
          formEvent.target.reset();
          const prodPreview = document.getElementById('prodImgPreview');
          if (prodPreview) prodPreview.style.display = 'none';
          const fileNameLabel = document.getElementById('prodImagemFileName');
          if (fileNameLabel) fileNameLabel.innerText = 'Escolher imagem do produto';
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
          await carregarDadosDoBanco();

          if (endpointKey) {
            const acao = method === 'POST' ? 'criar' : 'editar';
            mostrarToast(mensagemSucesso(endpointKey, acao), 'success');
          }
        } else {
          const erroDetalhe = await resposta.json().catch(() => ({}));
          if (erroDetalhe.detail) {
            mostrarToast(erroDetalhe.detail, 'error');
          } else {
            mostrarToast('Erro ao gravar os dados no banco de dados.', 'error', `Código: ${resposta.status}`);
          }
        }
      } catch (erro) {
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

    function addProduto(e) {
      e.preventDefault();
      const id = document.getElementById('prodId').value;
      const payload = {
        nome: document.getElementById('prodNome').value,
        categoria_id: document.getElementById('prodCategoria').value || null,
        preco: parseFloat(document.getElementById('prodPreco').value),
        tamanho: document.getElementById('prodTamanho').value || '',
        quantidade: parseInt(document.getElementById('prodQuantidade').value || '0', 10),
        imagem_url: document.getElementById('prodImagemUrl').value || '',
        variacoes: coletarVariacoes(),
        disponivel: 1
      };
      const endpoint = id ? `${API_URLS.produto}/${id}` : API_URLS.produto;
      salvarNoBanco(endpoint, payload, e, id ? 'PUT' : 'POST', 'produto');
      document.getElementById('prodId').value = '';
      document.getElementById('prodImagemUrl').value = '';
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

    function addVenda(e) {
      e.preventDefault();
      const id = document.getElementById('vendaId').value;
      const produtoId = document.getElementById('vendaProduto').value;
      const qtd = parseInt(document.getElementById('vendaQtd').value);
      const associadoIdRaw = document.getElementById('vendaAssociado').value;
      const associadoId = associadoIdRaw ? parseInt(associadoIdRaw) : null;

      const produto = produtos.find(p => String(p.id) === String(produtoId));
      const subtotal = produto ? Number(produto.preco) * qtd : 0;
      const percentualDesconto = associadoId ? 10 : 0;
      const desconto = subtotal * (percentualDesconto / 100);
      const total = subtotal - desconto;

      const payload = {
        cliente: document.getElementById('vendaCliente').value,
        produto_id: parseInt(produtoId),
        quantidade: qtd,
        forma_pagamento: document.getElementById('vendaPagamento').value,
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

    (function initInteractiveCanvas() {
      const canvas = document.getElementById('bg-canvas');
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      let particles = [];

      function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }
      resize();
      window.addEventListener('resize', resize);

      class Particle {
        constructor() {
          this.x = Math.random() * canvas.width;
          this.y = Math.random() * canvas.height;
          this.size = Math.random() * 2 + 1;
          this.speedX = (Math.random() - 0.5) * 0.4;
          this.speedY = (Math.random() - 0.5) * 0.4;
        }
        update() {
          this.x += this.speedX; this.y += this.speedY;
          if (this.x < 0 || this.x > canvas.width) this.speedX *= -1;
          if (this.y < 0 || this.y > canvas.height) this.speedY *= -1;
        }
        draw() {
          ctx.fillStyle = 'rgba(0, 140, 255, 0.4)';
          ctx.beginPath();
          ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
          ctx.fill();
        }
      }

      for (let i = 0; i < 50; i++) particles.push(new Particle());

      function animate() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        particles.forEach(p => { p.update(); p.draw(); });
        requestAnimationFrame(animate);
      }
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
    window.onload = function () {
      carregarDadosDoBanco();
      atualizarDataHora();
      toggleArmarioNomeField();
      setInterval(atualizarDataHora, 30000);
      observeReveals();
    };