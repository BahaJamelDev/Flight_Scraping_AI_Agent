"""
fichier: flight_recommender.py
Rôle:
- Ce fichier définit l’agent IA chargé de recommander des vols.
- Il charge les données de vols nettoyées depuis `flight_data.csv`.
- Il applique des filtres (escales, budget, période de la journée).
- Il expose un outil `FlightSearch` utilisable par l’agent IA LangChain.
- L’agent IA utilise le modèle `deepseek-ai/DeepSeek-V3` via l’API Together.
"""


import pandas as pd
from langchain_openai import ChatOpenAI
from langchain.agents import initialize_agent, Tool
from langchain.agents.agent_types import AgentType
from datetime import datetime
import re
import os
from dotenv import load_dotenv

# Charger les variables d'environnement (.env) → contient la clé API
load_dotenv()

def load_flight_data():
    """
    Charge et nettoie les données de vols à partir du fichier CSV.

    Étapes :
    - Lit flight_data.csv dans un DataFrame pandas.
    - Nettoie la colonne des prix (supprime les symboles, garde les nombres → float).
    - Corrige les heures d’arrivée et de départ :
        * Supprime les décalages (+1, +2)
        * Supprime les espaces insécables
        * Convertit en objets datetime.time
    - Ajoute une colonne booléenne "Is_Stopover" indiquant si le vol a une escale.

    Returns:
        pd.DataFrame: tableau nettoyé des vols
    """
    df = pd.read_csv("flight_data.csv")

    # Nettoyage prix
    df["Price"] = df["Price"].astype(str).str.replace(r"[^\d.]", "", regex=True).astype(float)

    # Conversion heures
    # Supprimer tout ce qui est après un + (exemple 11:20 AM+1 -> 11:20 AM)
    df["Arrival Time"] = df["Arrival Time"].astype(str).str.replace(r"\+.*$", "", regex=True)

    # Supprimer les espaces insécables
    df["Arrival Time"] = df["Arrival Time"].str.replace("\u202f", " ")

    # Conversion en datetime puis en heure pure
    df["Arrival Time"] = pd.to_datetime(df["Arrival Time"], format="%I:%M %p", errors="coerce").dt.time

    df["Departure Time"] = df["Departure Time"].astype(str).str.replace(r"\+.*$", "", regex=True)
    df["Departure Time"] = df["Departure Time"].str.replace("\u202f", " ")
    df["Departure Time"] = pd.to_datetime(df["Departure Time"], format="%I:%M %p", errors="coerce").dt.time

    # Escale booléen
    df["Is_Stopover"] = df["Stops"].str.contains("1 stop", case=False, na=False)

    return df

def search_flights(query: str):
    """
    Recherche des vols en fonction d’une requête textuelle de l’utilisateur.

    Args:
        query (str): La requête utilisateur (ex: "vol sans escale le matin moins de 200 euros")

    Étapes :
    - Charge les données de vols (load_flight_data()).
    - Filtre selon les critères détectés dans la requête :
        * Escales : "sans escale" ou "avec escale"
        * Budget : détection d’un montant + unité (€ / TND / USD)
        * Période : matin, après-midi, soir
    - Trie les résultats par prix puis heure de départ.
    - Retourne une chaîne de texte contenant les résultats formatés.

    Returns:
        str: description textuelle des vols trouvés ou message d’erreur.
    """
    df = load_flight_data()

    # Filtrage escale
    if re.search(r"\bsans\s+escale\b|\bdirect\b", query, re.IGNORECASE):
        df = df[df["Is_Stopover"] == False]
    elif re.search(r"\bavec\s+escale\b", query, re.IGNORECASE):
        df = df[df["Is_Stopover"] == True]

    # Filtrage budget
    budget_match = re.search(r"(\d+)\s?(tnd|€|euro|usd|dollars?)", query, re.IGNORECASE)
    if budget_match:
        max_budget = float(budget_match.group(1))
        df = df[df["Price"] <= max_budget]

    # Filtrage période
    if re.search(r"\bmatin\b", query, re.IGNORECASE):
        df = df[pd.to_datetime(df["Departure Time"].astype(str)).dt.hour < 12]
    elif re.search(r"\b(après-midi|apres-midi|apm)\b", query, re.IGNORECASE):
        df = df[(pd.to_datetime(df["Departure Time"].astype(str)).dt.hour >= 12) &
                (pd.to_datetime(df["Departure Time"].astype(str)).dt.hour < 18)]
    elif re.search(r"\bsoir\b", query, re.IGNORECASE):
        df = df[pd.to_datetime(df["Departure Time"].astype(str)).dt.hour >= 18]

    if df.empty:
        return "❌ Aucun vol trouvé après filtrage."

    df = df.sort_values(by=["Price", "Departure Time"])
    result = df[["Departure Time", "Airline Company", "Stops", "Price", "Flight Duration", "co2 emissions"]]
    return "✈️ Vols trouvés :\n\n" + result.to_string(index=False)

# Définition de l’outil "FlightSearch" utilisable par l’agent IA
flight_tool = Tool(
    name="FlightSearch",
    func=search_flights,
    description="Cherche un vol selon période de la journée (matin, après-midi, soir) + escale + budget."
)

# Configuration du modèle IA via l’API Together
llm = ChatOpenAI(
    model="deepseek-ai/DeepSeek-V3",
    temperature=0.2,
    api_key=os.getenv("TOGETHER_API_KEY"),
    base_url="https://api.together.xyz/v1"
)

# Initialisation de l’agent IA avec l’outil de recherche de vols
agent = initialize_agent(
    tools=[flight_tool],
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,   # L’agent raisonne étape par étape sans entraînement spécifique
    verbose=True,   # Affiche les logs pour debug
    handle_parsing_errors=True   # Gère les erreurs de parsing automatiquement
)
