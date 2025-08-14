"""
fichier: flight_scraper_proxy.py
Rôle:
- Ce fichier gère le scraping (extraction automatique) des informations de vols
  depuis Google Flights.
- Il construit une URL encodée pour une recherche spécifique (ville départ,
  destination, date).
- Il ouvre un navigateur automatisé avec Playwright (avec configuration proxy si besoin).
- Il extrait les informations principales de chaque vol (heures, prix, durée,
  escales, émissions CO2, etc.).
- Les données sont sauvegardées dans un fichier CSV nettoyé et réutilisable.
"""

import asyncio
import csv
import os
import base64
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from typing import List, Dict, Optional
import pandas as pd

# Load environment variables from .env file
load_dotenv()

class FlightURLBuilder:
    """Classe utilitaire pour construire une URL Google Flights encodée en base64."""

    
    @staticmethod
    def _create_one_way_bytes(departure: str, destination: str, date: str) -> bytes:
        """Créer les bytes représentant un vol aller simple (date, départ, arrivée)."""

        return (
            b'\x08\x1c\x10\x02\x1a\x1e\x12\n' + date.encode() +
            b'j\x07\x08\x01\x12\x03' + departure.encode() +
            b'r\x07\x08\x01\x12\x03' + destination.encode() +
            b'@\x01H\x01p\x01\x82\x01\x0b\x08\xfc\x06`\x04\x08'
        )
    
    @staticmethod
    def _modify_base64(encoded_str: str) -> str:
        """Insérer des underscores dans la chaîne base64 (format spécifique Google)."""
        insert_index = len(encoded_str) - 6
        return encoded_str[:insert_index] + '_' * 7 + encoded_str[insert_index:]

    @classmethod
    def build_url(
        cls,
        departure: str,
        destination: str,
        departure_date: str
    ) -> str:
        """Construire l’URL finale pour un vol aller simple."""
        flight_bytes = cls._create_one_way_bytes(departure, destination, departure_date)
        base64_str = base64.b64encode(flight_bytes).decode('utf-8')
        modified_str = cls._modify_base64(base64_str)
        return f'https://www.google.com/travel/flights/search?tfs={modified_str}'

class ProxyConfig:
    """Classe pour charger et gérer la configuration du proxy depuis .env."""
    def __init__(self):
        """Initialise la config proxy (serveur, user, mot de passe, bypass)."""
        self.server = os.getenv('PROXY_SERVER')
        self.username = os.getenv('PROXY_USERNAME')
        self.password = os.getenv('PROXY_PASSWORD')
        self.bypass = os.getenv('PROXY_BYPASS')

    def get_proxy_settings(self) -> Optional[Dict]:
        """Retourne la configuration proxy au format attendu par Playwright."""
        if not self.server:
            return None

        proxy_settings = {
            "server": self.server
        }
        if self.username and self.password:
            proxy_settings.update({
                "username": self.username,
                "password": self.password
            })
        if self.bypass:
            proxy_settings["bypass"] = self.bypass
        return proxy_settings

    @property
    def is_configured(self) -> bool:
        """Vérifie si un proxy est bien configuré dans .env."""
        return bool(self.server)

async def setup_browser():
    """"Démarre Playwright et ouvre un navigateur (avec proxy si défini dans .env)."""

    p = await async_playwright().start()
    
    browser_settings = {
        "headless": False
    }
    
    # Initialiser la configuration  de proxy depuis environment variables
    proxy_config = ProxyConfig()
    if proxy_config.is_configured:
        proxy_settings = proxy_config.get_proxy_settings()
        if proxy_settings:
            browser_settings["proxy"] = proxy_settings
    
    browser = await p.chromium.launch(**browser_settings)
    page = await browser.new_page()
    
    return p, browser, page


async def extract_flight_element_text(flight, selector: str, aria_label: Optional[str] = None) -> str:
    """Extraire le texte d’un élément de vol (via un sélecteur CSS et éventuellement aria-label)."""

    if aria_label:
        element = await flight.query_selector(f'{selector}[aria-label*="{aria_label}"]')
    else:
        element = await flight.query_selector(selector)
    return await element.inner_text() if element else "N/A"

async def scrape_flight_info(flight) -> Dict[str, str]:
    """Récupérer toutes les infos utiles d’un vol (heures, prix, durée, escale, CO2...)."""
    departure_time = await extract_flight_element_text(flight, 'span', "Departure time")
    arrival_time =  await extract_flight_element_text(flight, 'span', "Arrival time")
    airline = await extract_flight_element_text(flight, ".sSHqwe")
    duration = await extract_flight_element_text(flight, "div.gvkrdb")
    stops =  await extract_flight_element_text(flight, "div.EfT7Ae span.ogfYpf")
    price =  await extract_flight_element_text(flight, "div.FpEdX span")
    co2_emissions =  await extract_flight_element_text(flight, "div.O7CXue")
    emissions_variation =  await extract_flight_element_text(flight, "div.N6PNV")
    return {
        "Departure Time": departure_time,
        "Arrival Time": arrival_time,
        "Airline Company": airline,
        "Flight Duration": duration,
        "Stops": stops,
        "Price": price,
        "co2 emissions": co2_emissions,
        "emissions variation": emissions_variation
    }

def clean_csv(filename: str):
    """Nettoyer les caractères indésirables du CSV (Â, espaces spéciaux, etc.)."""
    data = pd.read_csv(filename, encoding="utf-8")
    
    def clean_text(value):
        if isinstance(value, str):
            return value.replace('Â', '').replace(' ', ' ').replace('Ã', '').replace('¶', '').strip()
        return value

    cleaned_data = data.applymap(clean_text)
    cleaned_file_path = f"{filename}"
    cleaned_data.to_csv(cleaned_file_path, index=False)
    print(f"Cleaned CSV saved to: {cleaned_file_path}")

def save_to_csv(data: List[Dict[str, str]], filename: str = "flight_data_proxy.csv") -> None:
    """Sauvegarder la liste de vols dans un fichier CSV et nettoyer ensuite."""
    if not data:
        return
    
    headers = list(data[0].keys())
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)
    
    
    clean_csv(filename)

async def scrape_flight_data(one_way_url):
    """Scraper tous les vols depuis une URL Google Flights et sauvegarder en CSV."""

    flight_data = []

    
    playwright, browser, page = await setup_browser()
    
    try:
        await page.goto(one_way_url)
        
        
        await page.wait_for_selector(".pIav2d")
        
        
        flights = await page.query_selector_all(".pIav2d")
        for flight in flights:
            flight_info = await scrape_flight_info(flight)
            flight_data.append(flight_info)
        
        
        save_to_csv(flight_data)
            
    finally:
        await browser.close()
        await playwright.stop()


if __name__ == "__main__":
    one_way_url = FlightURLBuilder.build_url(
        departure="TUN",
        destination="ORY",
        departure_date="2025-08-29"
    )
    print("One-way URL:", one_way_url)

    # Run the scraper
    asyncio.run(scrape_flight_data(one_way_url))

