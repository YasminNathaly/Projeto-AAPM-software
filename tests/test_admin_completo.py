import os
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

def aguardar_servidor(url, timeout=15):
    inicio = time.time()
    while time.time() - inicio < timeout:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except Exception:
            time.sleep(0.3)
    raise RuntimeError(f"Servidor nao iniciou em {url}")

def ir_para_modulo(page, modulo):
    page.locator(f".menu-item[onclick*=\"navigate('{modulo}'\"]").first.click()
    page.wait_for_selector(f"#{modulo}", state="visible", timeout=5000)
    page.wait_for_timeout(300)

def test_painel_admin_detalhado():
    admin_email = os.getenv("ADMIN_EMAIL", "admin@sp.senai.br")
    admin_senha = os.getenv("ADMIN_SENHA", "123456")

    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    erros_js = []
    erros_api = []
    falhas_etapas = []

    def executar_etapa(nome, fn):
        try:
            fn()
            print(f"  [OK] {nome}")
        except Exception as e:
            falhas_etapas.append(f"{nome}: {e}")
            print(f"  [FALHOU] {nome} -> {e}")

    try:
        aguardar_servidor("http://127.0.0.1:8000/")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=220)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            page.on("pageerror", lambda err: erros_js.append(str(err)))
            page.on(
                "response",
                lambda res: erros_api.append(f"{res.status} {res.url}")
                if "/api/" in res.url and res.status >= 500
                else None,
            )

            # 1. LOGIN NO ADMIN
            page.goto("http://127.0.0.1:8000/login")
            page.locator("input[type='email'], input[type='text']").first.fill(admin_email)
            page.locator("input[type='password']").first.fill(admin_senha)
            page.locator("button[type='submit']").first.click()
            page.wait_for_url("**/admin**", timeout=10000)
            page.wait_for_load_state("networkidle")

            # 2. COMMAND PALETTE, TEMA, NOTIFICACOES E ASSISTENTE
            def testar_atalhos_topo():
                page.click("button[onclick='abrirCommandPalette()']")
                page.wait_for_selector("#commandPaletteInput", state="visible", timeout=3000)
                page.fill("#commandPaletteInput", "produto")
                page.click("button[onclick='fecharCommandPalette()']")

                page.click("button[onclick='toggleTheme(event)']")
                page.wait_for_timeout(250)
                page.click("button[onclick='toggleTheme(event)']")

                page.click("button[onclick='toggleNotifications(event)']")
                page.wait_for_selector("#notifPanel", state="visible", timeout=3000)
                page.click("span[onclick='toggleNotifications(event, true)']")

                page.click("button[onclick='toggleAssistant()']")
                page.wait_for_selector("#assistantInput", state="visible", timeout=3000)
                page.fill("#assistantInput", "Como cadastrar um produto?")
                page.click("#assistantPanel button[type='submit']")
                page.wait_for_timeout(400)
                page.click("button[onclick='toggleAssistant()']")
            executar_etapa("Atalhos do Topo (Busca Rapida, Tema, Notificacoes, Assistente)", testar_atalhos_topo)

            # 3. CATEGORIA (Criar -> Buscar)
            def testar_categoria():
                ir_para_modulo(page, "categoria")
                page.fill("#catNome", "_CAT_ROBO_E2E_")
                page.fill("#catCodigo", "E2E-CAT")
                page.fill("#catDesc", "Categoria criada pelo robo")
                page.locator("#categoria form button[type='submit']").click()
                page.wait_for_timeout(600)
                page.fill("#tableSearch", "_CAT_ROBO_E2E_")
                page.wait_for_selector("#tblCategorias >> text=_CAT_ROBO_E2E_", timeout=4000)
                page.fill("#tableSearch", "")
            executar_etapa("Modulo Categoria (Cadastro e Busca)", testar_categoria)

            # 4. FORNECEDOR (Criar -> Buscar)
            def testar_fornecedor():
                ir_para_modulo(page, "fornecedor")
                page.fill("#fornNome", "_FORN_ROBO_E2E_")
                page.fill("#fornDoc", "99.999.999/0001-99")
                page.fill("#fornEmail", "robo@fornecedor.com")
                page.fill("#fornTel", "(11) 98888-7777")
                page.locator("#fornecedor form button[type='submit']").click()
                page.wait_for_timeout(600)
                page.fill("#tableSearch", "_FORN_ROBO_E2E_")
                page.wait_for_selector("#tblFornecedores >> text=_FORN_ROBO_E2E_", timeout=4000)
                page.fill("#tableSearch", "")
            executar_etapa("Modulo Fornecedor (Cadastro e Busca)", testar_fornecedor)

            # 5. PRODUTO + VARIACOES + MODAL DE DETALHES
            def testar_produto():
                ir_para_modulo(page, "produto")
                page.fill("#prodNome", "_PROD_ROBO_E2E_")
                if page.locator("#prodCategoria option").count() > 1:
                    page.locator("#prodCategoria").select_option(index=1)
                page.fill("#prodPreco", "50.00")
                page.fill("#prodTamanho", "Unico")
                page.fill("#prodQuantidade", "10")

                # Adiciona variacao
                page.click("button[onclick='adicionarVariacaoRow()']")
                var_inputs = page.locator("#variacoesList input")
                if var_inputs.count() >= 2:
                    var_inputs.nth(0).fill("M")
                    var_inputs.nth(1).fill("5")

                page.click("#prodSubmitBtn")
                page.wait_for_timeout(700)
                page.fill("#tableSearch", "_PROD_ROBO_E2E_")
                page.wait_for_selector("#produtosGrid >> text=_PROD_ROBO_E2E_", timeout=4000)
                page.fill("#tableSearch", "")
            executar_etapa("Modulo Produto + Variacoes (Cadastro e Busca)", testar_produto)

            # 6. ASSOCIADO (Criar -> Buscar)
            def testar_associado():
                ir_para_modulo(page, "associado")
                page.fill("#assocNome", "_ASSOC_ROBO_E2E_")
                page.fill("#assocEmail", "robo.assoc@sp.senai.br")
                page.fill("#assocTelefone", "(11) 97777-6666")
                page.fill("#assocEndereco", "Rua Correia de Andrade, 232")
                page.click("#assocSubmitBtn")
                page.wait_for_timeout(600)
                page.fill("#tableSearch", "_ASSOC_ROBO_E2E_")
                page.wait_for_selector("#tblAssociados >> text=_ASSOC_ROBO_E2E_", timeout=4000)
                page.fill("#tableSearch", "")
            executar_etapa("Modulo Associado (Cadastro e Busca)", testar_associado)

            # 7. ARMARIO (Criar -> Ocupar -> Buscar)
            def testar_armario():
                ir_para_modulo(page, "armario")
                page.fill("#armNumero", "E2E-999")
                page.fill("#armLocalizacao", "Corredor Teste")
                page.select_option("#armStatus", "Ocupado")
                page.fill("#armNomeCompleto", "_ASSOC_ROBO_E2E_")
                page.click("#armSubmitBtn")
                page.wait_for_timeout(600)
                page.fill("#tableSearch", "E2E-999")
                page.wait_for_selector("#tblArmarios >> text=E2E-999", timeout=4000)
                page.fill("#tableSearch", "")
            executar_etapa("Modulo Armario (Cadastro Ocupado e Busca)", testar_armario)

            # 8. USUARIOS (Apenas abre e valida listagem)
            def testar_usuario():
                ir_para_modulo(page, "usuario")
                page.wait_for_selector("#tblUsuarios", timeout=3000)
            executar_etapa("Modulo Usuarios (Carregamento da Tabela)", testar_usuario)

            # 9. VENDA (Seleciona produto, calcula resumo e registra)
            def testar_venda():
                ir_para_modulo(page, "venda")
                page.fill("#vendaCliente", "_CLIENTE_ROBO_E2E_")
                page.fill("#vendaProdutoBusca", "_PROD_ROBO_E2E_")
                page.evaluate("resolverProdutoBusca()")
                page.fill("#vendaQtd", "1")
                page.evaluate("atualizarResumoVenda()")
                page.wait_for_timeout(300)
                page.click("#vendaSubmitBtn")
                page.wait_for_timeout(700)
            executar_etapa("Modulo Venda (Calculo e Registro)", testar_venda)

            # 10. RELATORIO (Filtros de periodo)
            def testar_relatorio():
                ir_para_modulo(page, "relatorio")
                for periodo in ["hoje", "7d", "30d", "tudo"]:
                    page.click(f".filter-chip[data-periodo='{periodo}']")
                    page.wait_for_timeout(200)
            executar_etapa("Modulo Relatorio (Filtros de Periodo)", testar_relatorio)

            # 11. VITRINE PUBLICA (Verifica se o produto aparece e limpa carrinho)
            def testar_vitrine():
                loja = context.new_page()
                loja.goto("http://127.0.0.1:8000/")
                loja.click("text=Conheça a Loja")
                loja.fill("#productSearchInput", "_PROD_ROBO_E2E_")
                loja.wait_for_selector("text=_PROD_ROBO_E2E_", timeout=4000)
                loja.close()
            executar_etapa("Sincronizacao com Vitrine Publica", testar_vitrine)

            # 11B. TESTA CHECKOUT PIX AUTOMATICO + BAIXA DE ESTOQUE VIA API E WEBHOOK
            def testar_pix_e_baixa_estoque():
                prods = page.request.get("http://127.0.0.1:8000/api/produtos").json()
                prod_teste = next((p for p in prods if p.get("nome") == "_PROD_ROBO_E2E_"), None)
                assert prod_teste is not None, "Produto E2E nao encontrado para teste PIX"
                estoque_antes = int(prod_teste.get("quantidade") or prod_teste.get("estoque") or 0)

                resp_pix = page.request.post(
                    "http://127.0.0.1:8000/api/checkout/pix",
                    data={
                        "cliente": "_CLIENTE_PIX_E2E_",
                        "itens": [{"produto_id": prod_teste["id"], "quantidade": 2}],
                    },
                )
                assert resp_pix.status == 201, f"Falha ao gerar PIX: {resp_pix.text()}"
                dados_pix = resp_pix.json()
                assert "pix_copia_cola" in dados_pix and dados_pix["venda_id"]

                resp_wh = page.request.post(f"http://127.0.0.1:8000/api/checkout/pix/webhook/{dados_pix['venda_id']}")
                assert resp_wh.status == 200, f"Falha no webhook PIX: {resp_wh.text()}"

                prods_depois = page.request.get("http://127.0.0.1:8000/api/produtos").json()
                prod_depois = next((p for p in prods_depois if p["id"] == prod_teste["id"]), None)
                estoque_depois = int(prod_depois.get("quantidade") or prod_depois.get("estoque") or 0)
                assert estoque_depois == max(0, estoque_antes - 2), f"Estoque nao baixou: {estoque_antes} -> {estoque_depois}"
            executar_etapa("Checkout PIX Automatico + Webhook + Baixa de Estoque", testar_pix_e_baixa_estoque)

            # 12. LIMPEZA AUTOMATICA DOS REGISTROS DE TESTE (_E2E_)
            for rota, campo in [
                ("/api/vendas", "cliente"),
                ("/api/armarios", "numero"),
                ("/api/associados", "nome"),
                ("/api/produtos", "nome"),
                ("/api/fornecedores", "nome"),
                ("/api/categorias", "nome"),
            ]:
                resp = page.request.get(f"http://127.0.0.1:8000{rota}")
                if resp.status == 200:
                    itens = resp.json()
                    if isinstance(itens, list):
                        for item in itens:
                            valor = str(item.get(campo, "") or item.get("cliente_nome", ""))
                            if "E2E" in valor:
                                page.request.delete(f"http://127.0.0.1:8000{rota}/{item['id']}")

            browser.close()

        assert not erros_js, f"Erros de JavaScript no console: {erros_js}"
        assert not erros_api, f"Erros internos de API (500+): {erros_api}"
        assert not falhas_etapas, "Falhas detectadas:\n - " + "\n - ".join(falhas_etapas)
    finally:
        servidor.terminate()
        servidor.wait(timeout=5)
