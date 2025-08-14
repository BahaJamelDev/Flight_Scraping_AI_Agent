"""
Fichier : flight_scraper.py

Rôle global :
---------------
Ce fichier permet de générer dynamiquement une URL Google Flights encodée en base64,
d’ouvrir cette page via Playwright (navigateur automatisé), de collecter les informations
des vols (heures, prix, durée, compagnie, émissions CO2, etc.) et de les sauvegarder
dans un fichier CSV.

Il combine :
- La génération d’URL (classe FlightURLBuilder).
- Le scraping automatisé (fonction _scrape).
- L’extraction de texte ciblé (_text).
- L’orchestration et la sauvegarde (scrape_and_save).
"""
import asyncio, csv, base64, pandas as pd
from playwright.async_api import async_playwright
from typing import List, Dict
import os
class FlightURLBuilder:
    """Classe utilitaire pour construire une URL Google Flights encodée en base64."""
    @staticmethod
    def build_url(dep: str, dst: str, date: str) -> str:
        """
        Rôle :
        -------
        Créer une URL Google Flights valide à partir de :
        - dep : aéroport de départ
        - dst : aéroport d’arrivée
        - date : date du vol (format YYYY-MM-DD)

        Étapes :
        1. Construit une séquence binaire (bytes) respectant la structure attendue par Google.
        2. Encode cette séquence en base64.
        3. Ajoute des underscores pour correspondre au format de Google Flights.
        4. Retourne l’URL complète.
        """
        # Création de la séquence binaire (contient la date, l’aéroport de départ et d’arrivée)
        raw = (
            b'\x08\x1c\x10\x02\x1a\x1e\x12\n' + date.encode() +
            b'j\x07\x08\x01\x12\x03' + dep.encode() +
            b'r\x07\x08\x01\x12\x03' + dst.encode() +
            b'@\x01H\x01p\x01\x82\x01\x0b\x08\xfc\x06`\x04\x08'
        )
        # Encodage en base64
        b64 = base64.b64encode(raw).decode()
        insert = len(b64) - 6
        # Ajout de 7 underscores avant la fin (format spécifique Google)
        b64 = b64[:insert] + '_' * 7 + b64[insert:]
        # Retourne l’URL Google Flights complète
        return f"https://www.google.com/travel/flights/search?tfs={b64}"

async def _scrape(dep: str, dst: str, date: str) -> List[Dict[str, str]]:
    """
    Rôle :
    -------
    Ouvrir une page Google Flights, extraire la liste des vols proposés
    et renvoyer leurs détails sous forme de dictionnaires.

    Paramètres :
    - dep : aéroport de départ
    - dst : aéroport d’arrivée
    - date : date du vol

    Retour :
    - Liste de dictionnaires contenant les infos de chaque vol.
    """
    # Construction de l’URL dynamique
    url = FlightURLBuilder.build_url(dep, dst, date)


     # Lancement de Playwright avec un navigateur Chromium en mode headless
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Accès à l’URL générée
        await page.goto(url, timeout=60_000)

        # Attente que les résultats de vols apparaissent (élément ".pIav2d")
        await page.wait_for_selector(".pIav2d")
        # Récupération de tous les vols
        flights = await page.query_selector_all(".pIav2d")

        data = []
        # Extraction des infos principales de chaque vo
        for f in flights:
            data.append({
                "Departure Time": await _text(f, 'span[aria-label*="Departure time"]'),
                "Arrival Time":   await _text(f, 'span[aria-label*="Arrival time"]'),
                "Airline Company":await _text(f, ".sSHqwe"),
                "Flight Duration":await _text(f, "div.gvkrdb"),
                "Stops":          await _text(f, "div.EfT7Ae span.ogfYpf"),
                "Price":          await _text(f, "div.FpEdX span"),
                "co2 emissions":  await _text(f, "div.O7CXue"),
                "emissions variation": await _text(f, "div.N6PNV"),
            })

        # Fermeture du navigateur
        await browser.close()
        return data

async def _text(el, sel):
    node = await el.query_selector(sel)
    return await node.inner_text() if node else ""



def scrape_and_save(dep: str, dst: str, date: str, out: str = "flight_data.csv"):
    """
    Fonction synchrone pour scrapper les vols et sauvegarder dans un CSV.
    Compatible Streamlit (threads sans event loop).
    """

    if os.path.exists(out):
        print(f"[Scraper] Le fichier {out} existe déjà, chargement depuis le CSV.")
        return

    # Création manuelle d'un event loop pour le thread courant
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        data = loop.run_until_complete(_scrape(dep, dst, date))
    finally:
        loop.close()

    # Sauvegarde CSV
    pd.DataFrame(data).to_csv(out, index=False, encoding="utf-8")
    print(f"[Scraper] {len(data)} vols sauvegardés dans {out}")