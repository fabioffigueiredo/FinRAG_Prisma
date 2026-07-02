"""Captura clipes .webm reais do FinNLP dirigindo o app via Playwright.

Cada clipe é gravado em seu próprio contexto (um arquivo de vídeo por contexto).
Pré-requisito: app rodando em http://localhost:5001 (python app/app.py).
Saída: linkedin-launch/video/capture/videos-raw/<clip>/*.webm
Depois renomeados para linkedin-launch/video/capture/raw/<clip>.webm
"""
from __future__ import annotations
import shutil
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5001"
ROOT = Path(__file__).resolve().parents[1]          # linkedin-launch/video
RAW_DIR = ROOT / "capture" / "raw"
TMP_DIR = ROOT / "capture" / "videos-raw"
VIEWPORT = {"width": 1920, "height": 1080}

HEADLINE = ("Nokia reported record profit growth this quarter, "
            "beating analyst estimates.")


def _new_context(browser, slug: str):
    """Cria um contexto que grava vídeo num subdir próprio (1 arquivo/contexto)."""
    out = TMP_DIR / slug
    out.mkdir(parents=True, exist_ok=True)
    ctx = browser.new_context(
        viewport=VIEWPORT,
        record_video_dir=str(out),
        record_video_size=VIEWPORT,
    )
    return ctx


def _go_module(page, module: str):
    """Clica no item de menu e espera o módulo montar em #content."""
    page.click(f'.nav-item[data-module="{module}"]')
    page.wait_for_timeout(1200)


def _finish(ctx, slug: str):
    """Fecha o contexto (finaliza o .webm) e move o arquivo para raw/<slug>.webm."""
    ctx.close()
    src = next((TMP_DIR / slug).glob("*.webm"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    dst = RAW_DIR / f"{slug}.webm"
    shutil.move(str(src), str(dst))
    print(f"[ok] {slug} -> {dst}")


def clip_live(browser):
    """Mercado Live: o app puxa notícias SOZINHO via SSE (ingestão automática)."""
    ctx = _new_context(browser, "live")
    page = ctx.new_page()
    page.goto(BASE, wait_until="domcontentloaded")
    _go_module(page, "live")
    # deixa o SSE despejar notícias por ~12s (a prova visual da automação)
    page.wait_for_timeout(12000)
    _finish(ctx, "live")


def clip_analysis(browser):
    """Análise manual pontual: cola manchete, clica Analisar, mostra veredito."""
    ctx = _new_context(browser, "analysis")
    page = ctx.new_page()
    page.goto(BASE, wait_until="domcontentloaded")
    _go_module(page, "analysis")
    page.fill("#analyze-text", HEADLINE)
    page.wait_for_timeout(800)
    page.click("#analyze-btn")
    # espera o card de resultado renderizar e dá tempo de leitura
    page.wait_for_selector("#analysis-results .card", timeout=30000)
    page.wait_for_timeout(6000)
    _finish(ctx, "analysis")


def clip_graph(browser):
    """Grafo de conhecimento (PyVis): espera render e arrasta um nó."""
    ctx = _new_context(browser, "graph")
    page = ctx.new_page()
    page.goto(BASE, wait_until="domcontentloaded")
    _go_module(page, "graph")
    page.wait_for_timeout(6000)  # PyVis monta em iframe/canvas
    # leve interação de mouse para dar vida (drag no centro do canvas)
    page.mouse.move(960, 540)
    page.mouse.down()
    page.mouse.move(1060, 600, steps=20)
    page.mouse.up()
    page.wait_for_timeout(3000)
    _finish(ctx, "graph")


def clip_history(browser):
    """Histórico SCD2: consulta uma entidade e mostra a timeline temporal.

    O módulo usa um input de texto (#history-input) + botão (#history-btn).
    TeliaSonera é o hub central do grafo — casa com a narração de rastreabilidade.
    """
    ctx = _new_context(browser, "history")
    page = ctx.new_page()
    page.goto(BASE, wait_until="domcontentloaded")
    _go_module(page, "history")
    page.wait_for_timeout(2000)
    page.fill("#history-input", "TeliaSonera")
    page.wait_for_timeout(600)
    page.click("#history-btn")
    # espera a timeline sair do estado vazio
    page.wait_for_timeout(6000)
    _finish(ctx, "history")


def clip_metrics(browser):
    """Métricas ML: matriz de confusão / comparação de classificadores."""
    ctx = _new_context(browser, "metrics")
    page = ctx.new_page()
    page.goto(BASE, wait_until="domcontentloaded")
    _go_module(page, "metrics")
    page.wait_for_timeout(6000)
    _finish(ctx, "metrics")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        clip_live(browser)
        clip_analysis(browser)
        clip_graph(browser)
        clip_history(browser)
        clip_metrics(browser)
        browser.close()
    # limpeza dos subdirs temporários
    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)
    print("\nClipes em:", RAW_DIR)


if __name__ == "__main__":
    main()
