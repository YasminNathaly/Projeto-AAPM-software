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
    raise RuntimeError(f"Servidor não iniciou em {url}")

def test_loja_senai_completa():
    # Sobe o FastAPI automaticamente em segundo plano
    servidor = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        aguardar_servidor("http://127.0.0.1:8000/")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False, slow_mo=350)
            page = browser.new_page()
            page.goto("http://127.0.0.1:8000/")

            # 1. Testa o link "Conheça a Loja" abrindo a aba Produtos
            page.click("text=Conheça a Loja")
            page.wait_for_selector("#produtos.active")

            # 2. Se houver chips de variação disponíveis, clica no primeiro ativo
            chips = page.locator(".variation-chip:not(.out-of-stock)")
            if chips.count() > 0:
                chips.first.click()

            # 3. Adiciona o primeiro produto disponível ao carrinho
            add_btns = page.locator(".product-add-btn")
            if add_btns.count() > 0:
                add_btns.first.click()
                page.wait_for_timeout(600)

                # 4. Abre o carrinho e testa o modal customizado de esvaziar
                page.click("#cartBtn")
                page.wait_for_selector("#cartDrawer.active")
                page.click("text=Esvaziar carrinho")
                page.wait_for_selector("#clearCartModal.active")
                page.click("#clearCartModal >> text=Esvaziar")
                page.click("#cartDrawer >> .modal-close")

            # 5. Testa navegação pelas demais abas públicas
            page.click(".nav-item >> text=Associados")
            page.wait_for_selector("#associados.active")

            page.click(".nav-item >> text=Armários")
            page.wait_for_selector("#armarios.active")

            browser.close()
    finally:
        servidor.terminate()
        servidor.wait(timeout=5)
