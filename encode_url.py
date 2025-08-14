"""
fichier: encoded_url.py
Rôle:
- Ce fichier génère une URL encodée au format utilisé par Google Flights.
- Il prend des données binaires représentant un vol (date, aéroports, etc.).
- Ensuite, il ré-encode ces données en base64 et les transforme pour obtenir une URL exploitable.
- Utile pour tester la génération d’URLs et comprendre le format utilisé par Google Flights.
"""
import base64  # Librairie standard Python pour encodage/décodage en base64

# Données binaires représentant un vol "one way" (aller simple).
# Ces données contiennent :
# - la date du vol
# - l'aéroport de départ (ex: LAX)
# - l'aéroport d'arrivée (ex: SFO)
# - des indicateurs de type de vol et d’options
one_way = b'\x08\x1c\x10\x02\x1a\x1e\x12\n2025-01-12j\x07\x08\x01\x12\x03LAXr\x07\x08\x01\x12\x03SFO@\x01H\x01p\x01\x82\x01\x0b\x08\xfc\x06`\x04\x08'

# Étape 1 : Ré-encoder les données binaires en base64 (chaîne lisible)
re_encoded_str = base64.b64encode(one_way).decode('utf-8')

# Étape 2 : Modifier la chaîne encodée
# Google Flights insère souvent des underscores pour "paddings" dans ses URLs.
# Ici, on ajoute 7 underscores à la 6ᵉ position avant la fin de la chaîne.
insert_index = len(re_encoded_str) - 6
modified_str = re_encoded_str[:insert_index] + '_' * 7 + re_encoded_str[insert_index:]

# Étape 3 : Construire l’URL finale de recherche Google Flights
url = f'https://www.google.com/travel/flights/search?tfs={modified_str}'

# Affichage du résultat → URL directement exploitable dans un navigateur
print(url)

