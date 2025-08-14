"""
fichier: app.py
Rôle:
- Ce fichier contient l'interface utilisateur construite avec Streamlit.
- Il permet à l'utilisateur de saisir ses préférences de vol (ville de départ, destination, date, budget, etc.).
- Il lance le scraping via le module flight_scraper.
- Il applique un filtrage des résultats (budget, heure, escales).
- Il appelle l'agent IA (flight_recommender) pour générer une réponse finale claire.
"""
import streamlit as st # Interface utilisateur web 
from datetime import date, datetime # Gestion des dates
from flight_scraper import scrape_and_save # Fonction de scraping 
from flight_recommender import agent # Agent IA qui analyse et formule la réponse
import asyncio
import sys
import html
import re
import pandas as pd

# Fix boucle asyncio sous Windows
if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Configuration générale de la page Streamlit
st.set_page_config(
    page_title="Assistant Vol IA",
    page_icon="🛫",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# Titre et description de l'application
st.title("🛫 Assistant Vol IA – Recherche Automatique")
st.markdown("💡 **Trouvez rapidement le meilleur vol sur Google Flights** grâce à notre assistant IA.")


# Formulaire principal pour saisir les informations du vol
with st.form("flight_form"):
    col1, col2 = st.columns(2)
    with col1:
        # Champ pour la ville/aéroport de départ (code IATA)
        departure_city = st.text_input("📍 Ville de départ", placeholder="Ex: TUN (code IATA)")
    with col2:
        # Champ pour la ville/aéroport d’arrivée (code IATA)
        destination_city = st.text_input("🏁 Ville de destination", placeholder="Ex: CDG (code IATA)")

    col3, col4 = st.columns(2)
    with col3:
        # Sélection de la date du vol
        flight_date = st.date_input("📅 Date du vol", value=date.today())
    with col4:
        # Choix de la période de vol (matin/après-midi/soir)
        period_choice = st.selectbox(
            "🕒 Période du vol",
            ["Matin (00h-12h)", "Après-midi (12h-18h)", "Soir (18h-24h)"],
            index=0
        )

    col5, col6 = st.columns(2)
    with col5:
        # Choix sur les escales
        stopover_pref = st.selectbox(
            "✈️ Préférence de vol",
            ["Peu importe", "Sans escale", "Avec escale"]
        )
    with col6:
        # Saisie du budget maximal
        max_budget = st.number_input(
            "💰 Budget maximal (€)",
            min_value=0,
            step=50,
            format="%d"
        )

    # Bouton de soumission du formulaire
    submitted = st.form_submit_button("🔍 Rechercher le vol idéal")


# Si l'utilisateur valide le formulaire
if submitted:
    if not departure_city or not destination_city:
        # Vérifie que les champs obligatoires sont remplis
        st.warning("⚠️ Merci de remplir tous les champs obligatoires.")
    else:
        # Formatage de la date en chaîne
        formatted_date = flight_date.strftime("%Y-%m-%d")

        # Étape 1 : Scraping des vols avec flight_scraper
        with st.spinner("🕷️ Scraping des vols..."):
            scrape_and_save(departure_city, destination_city, formatted_date)

        try:
            # Étape 2 : Lecture des données de vol extraites
            df = pd.read_csv("flight_data.csv")

            # Nettoyage prix → float
            df['Price'] = df['Price'].astype(str).str.replace(r"[^\d.]", "", regex=True).astype(float)
            df['Departure Time'] = pd.to_datetime(df['Departure Time'], errors='coerce')

            # Étape 3 : Filtrage par budget
            if max_budget > 0:
                df = df[df['Price'] <= max_budget]

            # Étape 4 : Filtrage par période de vol
            if "Matin" in period_choice:
                df = df[df['Departure Time'].dt.hour < 12]
            elif "Après-midi" in period_choice:
                df = df[(df['Departure Time'].dt.hour >= 12) & (df['Departure Time'].dt.hour < 18)]
            else:
                df = df[df['Departure Time'].dt.hour >= 18]

            # Si aucun vol ne correspond
            if df.empty:
                st.error("❌ Aucun vol trouvé pour vos critères.")
                st.stop()
            # Étape 5 : Sélection du meilleur vol (prix puis heure)
            best_flight = df.sort_values(by=["Price", "Departure Time"]).iloc[0]

            # Étape 6 : Préparation de la requête pour l'agent IA
            query = f"""
Vol recommandé :
- Compagnie : {best_flight['Airline Company']}
- Départ : {best_flight['Departure Time'].strftime('%H:%M')}
- Arrivée : {best_flight['Arrival Time']}
- Durée : {best_flight['Flight Duration']}
- Prix : {best_flight['Price']} €
- Escales : {best_flight['Stops']}
"""
        except Exception as e:
            st.error(f"❌ Erreur lors du traitement des données : {e}")
            st.stop()
        # Étape 7 : Appel de l'agent IA pour générer la réponse finale
        with st.spinner("🤖 L'IA prépare la réponse..."):
            response = agent.invoke(query)
            message = response.get("output", "") if isinstance(response, dict) else response
            message = html.unescape(message)
            message = re.sub(r'\\[nrt]', '\n', message)

            st.markdown("### 🧠 Résultat final")
            st.markdown(
                f"<pre style='white-space: pre-wrap; color: white; background-color: #1e1e1e; padding: 1rem;'>{message}</pre>",
                unsafe_allow_html=True
            )
