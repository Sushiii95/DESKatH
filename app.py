# DESKatH — Cross-Asset Market Monitor
# Projet final Python (PGE M1, SKEMA) — Louis Diguet-Guyenne
# Lancement : source .venv/bin/activate  puis  streamlit run app.py
# Packages requis (voir requirements.txt) : streamlit, yfinance, pandas, altair
# Thème (couleurs, polices) : fichier .streamlit/config.toml

import streamlit as st
import yfinance as yf
import pandas as pd
import altair as alt
import html
import math
import urllib.request
import re
import xml.etree.ElementTree as ElementTree
from concurrent.futures import ThreadPoolExecutor
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo
from datetime import date, datetime, timedelta


# CONFIGURATION

# Actions, regroupées par zone : la liste est longue, chaque zone se déplie à la demande.
EQUITY_GROUPS = {
    "United States": {
        "Apple": "AAPL",
        "Microsoft": "MSFT",
        "Nvidia": "NVDA",
        "Alphabet": "GOOGL",
        "Amazon": "AMZN",
        "Meta": "META",
        "Tesla": "TSLA",
        "Broadcom": "AVGO",
        "Oracle": "ORCL",
        "AMD": "AMD",
        "Intel": "INTC",
        "Palantir": "PLTR",
        "Netflix": "NFLX",
        "Berkshire Hathaway": "BRK-B",
        "JPMorgan Chase": "JPM",
        "Goldman Sachs": "GS",
        "Morgan Stanley": "MS",
        "Bank of America": "BAC",
        "Citigroup": "C",
        "BlackRock": "BLK",
        "Visa": "V",
        "Mastercard": "MA",
        "Exxon Mobil": "XOM",
        "Chevron": "CVX",
        "Johnson & Johnson": "JNJ",
        "Eli Lilly": "LLY",
        "Pfizer": "PFE",
        "UnitedHealth": "UNH",
        "Procter & Gamble": "PG",
        "Coca-Cola": "KO",
        "PepsiCo": "PEP",
        "McDonald's": "MCD",
        "Walmart": "WMT",
        "Costco": "COST",
        "Disney": "DIS",
        "Boeing": "BA",
        "Caterpillar": "CAT",
    },
    "France": {
        "TotalEnergies": "TTE.PA",
        "LVMH": "MC.PA",
        "BNP Paribas": "BNP.PA",
        "L'Oréal": "OR.PA",
        "Hermès": "RMS.PA",
        "Sanofi": "SAN.PA",
        "Airbus": "AIR.PA",
        "Schneider Electric": "SU.PA",
        "Air Liquide": "AI.PA",
        "Safran": "SAF.PA",
        "AXA": "CS.PA",
        "Société Générale": "GLE.PA",
        "Crédit Agricole": "ACA.PA",
        "Vinci": "DG.PA",
        "Kering": "KER.PA",
        "Danone": "BN.PA",
        "Orange": "ORA.PA",
        "Engie": "ENGI.PA",
        "Capgemini": "CAP.PA",
        "Dassault Systèmes": "DSY.PA",
        "Renault": "RNO.PA",
        "Stellantis": "STLAP.PA",
        "Michelin": "ML.PA",
        "Saint-Gobain": "SGO.PA",
        "Pernod Ricard": "RI.PA",
        "Thales": "HO.PA",
        "Veolia": "VIE.PA",
        "Carrefour": "CA.PA",
        "Publicis": "PUB.PA",
        "Legrand": "LR.PA",
    },
    "Germany": {
        "SAP": "SAP.DE",
        "Siemens": "SIE.DE",
        "Allianz": "ALV.DE",
        "Deutsche Telekom": "DTE.DE",
        "Mercedes-Benz": "MBG.DE",
        "BMW": "BMW.DE",
        "Volkswagen": "VOW3.DE",
        "BASF": "BAS.DE",
        "Bayer": "BAYN.DE",
        "Deutsche Bank": "DBK.DE",
        "Adidas": "ADS.DE",
        "Infineon": "IFX.DE",
        "Rheinmetall": "RHM.DE",
        "Munich Re": "MUV2.DE",
    },
    "Rest of Europe": {
        "ASML": "ASML.AS",
        "ING": "INGA.AS",
        "Adyen": "ADYEN.AS",
        "Santander": "SAN.MC",
        "Inditex": "ITX.MC",
        "Iberdrola": "IBE.MC",
        "UniCredit": "UCG.MI",
        "Intesa Sanpaolo": "ISP.MI",
        "Ferrari": "RACE.MI",
        "Eni": "ENI.MI",
        "Nestlé": "NESN.SW",
        "Roche": "RO.SW",
        "Novartis": "NOVN.SW",
        "UBS": "UBSG.SW",
        "Novo Nordisk": "NOVO-B.CO",
    },
    "United Kingdom": {
        "Shell": "SHEL.L",
        "AstraZeneca": "AZN.L",
        "HSBC": "HSBA.L",
        "BP": "BP.L",
        "Unilever": "ULVR.L",
        "Barclays": "BARC.L",
        "Rio Tinto": "RIO.L",
        "GSK": "GSK.L",
    },
    "Asia": {
        "Toyota": "7203.T",
        "Sony": "6758.T",
        "Mitsubishi UFJ": "8306.T",
        "TSMC (ADR)": "TSM",
        "Alibaba (ADR)": "BABA",
        "Tencent": "0700.HK",
    },
}

# Devises : les 8 grandes devises, croisées deux à deux (28 paires). L'ordre suit la convention de marché : EUR/USD et non USD/EUR.
CURRENCY_ORDER = ["EUR", "GBP", "AUD", "NZD", "USD", "CAD", "CHF", "JPY"]
CURRENCY_GROUPS = {"USD pairs": {}, "EUR crosses": {}, "GBP crosses": {}, "Other crosses": {}}
for position, first in enumerate(CURRENCY_ORDER):
    for second in CURRENCY_ORDER[position + 1:]:
        group = "USD pairs" if "USD" in (first, second) else f"{first} crosses" if first in ("EUR", "GBP") else "Other crosses"
        CURRENCY_GROUPS[group][f"{first}/{second}"] = f"{first}{second}=X"

# Pages dont la liste est présentée par groupes repliables
ASSET_GROUPS = {"Equities": EQUITY_GROUPS, "Currencies": CURRENCY_GROUPS}


# Regroupe les groupes d'une page en une seule liste : nom affiché -> ticker
def merge_groups(groups):
    merged = {}
    for names in groups.values():
        merged.update(names)
    return merged


# Dictionnaire à deux niveaux : catégorie -> nom affiché -> ticker Yahoo Finance. Chaque catégorie devient une page de l'appli.
ASSET_UNIVERSE = {
    "Indices": {
        "S&P 500": "^GSPC",
        "CAC 40": "^FCHI",
        "Euro Stoxx 50": "^STOXX50E",
        "DAX": "^GDAXI",
        "Nikkei 225": "^N225",
    },
    "Equities": merge_groups(EQUITY_GROUPS),
    "Currencies": merge_groups(CURRENCY_GROUPS),
    "Rates": {
        "US 3M T-Bill": "^IRX",
        "US 5Y Treasury": "^FVX",
        "US 10Y Treasury": "^TNX",
        "US 30Y Treasury": "^TYX",
        "OAT 2Y (Nov 2028)": "ETANM.PA",
        "OAT 5Y (Nov 2031)": "ETAPJ.PA",
        "OAT 7Y (Nov 2033)": "ETAQB.PA",
        "OAT 10Y": "MFR10.AS",
        "OAT 20Y (May 2045)": "ETALX.PA",
        "OAT 30Y (May 2054)": "ETAPV.PA",
        "Bund 2Y": "BUND2Y",
        "Bund 5Y": "BUND5Y",
        "Bund 7Y": "BUND7Y",
        "Bund 10Y": "BUND10Y",
        "Bund 20Y": "BUND20Y",
        "Bund 30Y": "BUND30Y",
    },
    "Commodities": {
        "Gold": "GC=F",
        "Silver": "SI=F",
        "WTI Crude": "CL=F",
        "Brent Crude": "BZ=F",
        "Natural Gas": "NG=F",
        "Copper": "HG=F",
    },
    "Bonds": {
        "US Treasuries 1-3Y (SHY)": "SHY",
        "US Treasuries 7-10Y (IEF)": "IEF",
        "US Treasuries 20Y+ (TLT)": "TLT",
        "US Investment Grade (LQD)": "LQD",
        "US High Yield (HYG)": "HYG",
    },
}

# OAT 10 ans : indice de rendement dont Yahoo ne donne l'historique qu'en données horaires (une cotation par jour)
INTRADAY_HISTORY_TICKERS = ["MFR10.AS"]

# Autres OAT : vraies lignes cotées à Paris (coupon en %, date de remboursement). Le rendement est calculé à partir de leur prix.
# Leur maturité réelle baisse avec le temps : la date figure dans leur nom affiché.
OAT_LINES = {
    "ETANM.PA": (0.75, date(2028, 11, 25)),
    "ETAPJ.PA": (0.0, date(2031, 11, 25)),
    "ETAQB.PA": (3.5, date(2033, 11, 25)),
    "ETALX.PA": (3.25, date(2045, 5, 25)),
    "ETAPV.PA": (3.0, date(2054, 5, 25)),
}

# Bund : taux officiels de la Bundesbank, par maturité résiduelle (courbe de Svensson, données publiques sans clé)
BUND_SERIES = {
    "BUND2Y": "R02XX",
    "BUND5Y": "R05XX",
    "BUND7Y": "R07XX",
    "BUND10Y": "R10XX",
    "BUND20Y": "R20XX",
    "BUND30Y": "R30XX",
}
BUND_URL = "https://api.statistiken.bundesbank.de/rest/download/BBSIS/D.I.ZST.ZI.EUR.S1311.B.A604.{code}.R.A.A._Z._Z.A?format=csv&lang=en"

# Icône de chaque page dans la barre de navigation (bibliothèque d'icônes Google Material)
PAGE_ICONS = {
    "Indices": ":material/public:",
    "Equities": ":material/business:",
    "Bonds": ":material/account_balance:",
    "Commodities": ":material/oil_barrel:",
    "Currencies": ":material/currency_exchange:",
    "Rates": ":material/percent:",
}

# Accueil : l'actif de référence et la description de chaque classe d'actifs
HOME_TILES = {
    "Indices": ("S&P 500", "Global equity benchmarks across the US, Europe and Japan."),
    "Equities": ("Nvidia", "Large caps from the US, Europe, the UK and Asia."),
    "Currencies": ("EUR/USD", "The eight major currencies crossed together: 28 pairs."),
    "Rates": ("OAT 10Y", "US Treasury, French OAT and German Bund yields, moves in basis points."),
    "Commodities": ("Gold", "Precious metals, crude oil, natural gas and copper."),
    "Bonds": ("US Treasuries 7-10Y (IEF)", "Treasury and credit ETFs along the risk spectrum."),
}

# Nom du site. Le "at" central se détache du reste : DESK at Highest, DESK at Home.
BRAND_HTML = '<span class="xad-name">DESK<span class="xad-at">at</span>H</span>'

# Page d'entrée : quantité de défilement à accumuler pour entrer dans le site (environ 3 gestes sur un pavé tactile). À augmenter pour un défilement plus long.
LANDING_SCROLL_DISTANCE = 1800

# News : flux RSS publics. On ne reprend que le titre, la date et le lien : l'article se lit sur le site d'origine.
# Google News donne accès aux sites qui n'ont pas de flux ouvert. Son flux public est filtré par site, et ses liens mènent à l'article d'origine.
GOOGLE_NEWS_FR = "https://news.google.com/rss/search?q=site:{site}+when:3d&hl=fr&gl=FR&ceid=FR:fr"
GOOGLE_NEWS_EN = "https://news.google.com/rss/search?q=site:{site}+when:3d&hl=en-US&gl=US&ceid=US:en"

# Pour chaque flux : source affichée, adresse, section par défaut. Sans section par défaut, un article n'est gardé que si son titre parle de marchés.
NEWS_FEEDS = [
    # Sources françaises
    ("BFM Bourse", "https://www.tradingsat.com/rssbourse.xml", "Equities"),
    ("Le Figaro", "https://www.lefigaro.fr/rss/figaro_bourse.xml", "Markets"),
    ("Le Figaro", "https://www.lefigaro.fr/rss/figaro_flash-eco.xml", None),
    ("Investing.com", "https://fr.investing.com/rss/news_25.rss", "Equities"),
    ("Investing.com", "https://fr.investing.com/rss/news_1.rss", "Currencies"),
    ("Investing.com", "https://fr.investing.com/rss/news_11.rss", "Commodities"),
    ("Investing.com", "https://fr.investing.com/rss/news_14.rss", "Economy"),
    ("Investing.com", "https://fr.investing.com/rss/news_95.rss", "Economy"),
    ("Challenges", "https://www.challenges.fr/rss.xml", None),
    ("Le Revenu", "https://www.lerevenu.com/rss.xml", "Markets"),
    ("Café de la Bourse", "https://www.cafedelabourse.com/feed", "Markets"),
    ("Le Monde", "https://www.lemonde.fr/argent/rss_full.xml", None),
    ("BFM", "https://www.bfmtv.com/rss/economie/", None),
    ("La Tribune", "https://www.latribune.fr/rss/rubriques/bourse.html", None),
    ("Zonebourse", GOOGLE_NEWS_FR.format(site="zonebourse.com"), "Markets"),
    ("Boursorama", GOOGLE_NEWS_FR.format(site="boursorama.com"), None),
    ("Les Echos", GOOGLE_NEWS_FR.format(site="lesechos.fr"), None),
    ("Investir", GOOGLE_NEWS_FR.format(site="investir.lesechos.fr"), "Equities"),
    ("Boursier.com", GOOGLE_NEWS_FR.format(site="boursier.com"), "Markets"),
    ("L'Agefi", GOOGLE_NEWS_FR.format(site="agefi.fr"), None),
    ("Capital", GOOGLE_NEWS_FR.format(site="capital.fr"), None),
    # Sources internationales
    ("Bloomberg", "https://feeds.bloomberg.com/markets/news.rss", "Markets"),
    ("Bloomberg", "https://feeds.bloomberg.com/economics/news.rss", "Economy"),
    ("Financial Times", "https://www.ft.com/markets?format=rss", "Markets"),
    ("Financial Times", "https://www.ft.com/companies?format=rss", None),
    ("Reuters", GOOGLE_NEWS_EN.format(site="reuters.com"), None),
    ("CNBC", "https://www.cnbc.com/id/10000664/device/rss/rss.html", None),
    ("CNBC", "https://www.cnbc.com/id/15839069/device/rss/rss.html", None),
    ("CNBC", "https://www.cnbc.com/id/15839135/device/rss/rss.html", "Equities"),
    ("CNBC", "https://www.cnbc.com/id/19836768/device/rss/rss.html", "Commodities"),
    ("CNBC", "https://www.cnbc.com/id/20910258/device/rss/rss.html", "Economy"),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_topstories", None),
    ("MarketWatch", "https://feeds.content.dowjones.io/public/rss/mw_bulletins", "Markets"),
    ("Yahoo Finance", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EGSPC,%5EFCHI&region=US&lang=en-US", "Markets"),
    ("Seeking Alpha", "https://seekingalpha.com/market_currents.xml", "Equities"),
    ("Nasdaq", "https://www.nasdaq.com/feed/rssoutbound?category=Markets", "Equities"),
    ("Investing.com", "https://www.investing.com/rss/news_25.rss", "Equities"),
    ("Investing.com", "https://www.investing.com/rss/news_1.rss", "Currencies"),
    ("Investing.com", "https://www.investing.com/rss/news_11.rss", "Commodities"),
    ("Investing.com", "https://www.investing.com/rss/news_95.rss", "Economy"),
    ("investingLive", "https://investinglive.com/feed/", None),
    ("FXStreet", "https://www.fxstreet.com/rss/news", "Currencies"),
    ("Oilprice", "https://oilprice.com/rss/main", "Commodities"),
    ("Mining.com", "https://www.mining.com/feed/", "Commodities"),
    ("The Economist", "https://www.economist.com/finance-and-economics/rss.xml", "Economy"),
    ("The Guardian", "https://www.theguardian.com/business/rss", None),
    ("BBC", "https://feeds.bbci.co.uk/news/business/rss.xml", None),
    ("New York Times", "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml", None),
    # Banques centrales
    ("ECB", "https://www.ecb.europa.eu/rss/press.html", "Rates"),
    ("Federal Reserve", "https://www.federalreserve.gov/feeds/press_all.xml", "Rates"),
    ("Bank of England", "https://www.bankofengland.co.uk/rss/news", "Rates"),
]
NEWS_SECTIONS = ["All", "Indices", "Equities", "Currencies", "Rates", "Commodities", "Bonds", "Economy", "Markets"]
NEWS_MAX_ARTICLES = 150
NEWS_MAX_PER_FEED = 40
NEWS_MAX_AGE_DAYS = 7
NEWS_SAME_STORY_SIMILARITY = 0.6

# Classement d'après les mots du titre, en français et en anglais. Le premier thème reconnu l'emporte : les sujets précis passent avant les plus larges.
NEWS_KEYWORDS = {
    "Commodities": r"\b(pétrole|brent|wti|gaz|cuivre|l'or|once d'or|matières premières|oil|crude|gold|silver|copper|natural gas|commodit(y|ies))\b",
    "Currencies": r"\b(eur/usd|usd/jpy|forex|devises?|currenc(y|ies)|livre sterling|sterling|yen|franc suisse|(face (au|à)|le|du) dollar|(face à|l')euro)\b",
    "Rates": r"\b(taux(?! de chômage)|rendements?|oat|bund|treasur(y|ies)|bons du trésor|yields?|interest rates?|rate (hike|cut)s?|fed|bce|ecb|banque centrale|central bank)\b",
    "Bonds": r"\b(obligations?|obligataires?|bonds?|high yield|dette (souveraine|d'état|française))\b",
    "Indices": r"\b(cac 40|s&p 500|sbf 120|nasdaq|dow( jones)?|stoxx|dax|nikkei|wall street|indices?|bourse de paris|bourses? (européennes?|mondiales?|asiatiques?))\b",
    "Equities": r"\b(actions?|objectif de cours|résultats|introduction en bourse|stocks?|shares?|earnings|ipo)\b",
    "Economy": r"\b(inflation|pib|gdp|chômage|emplois?|jobs? report|unemployment|payrolls?|récession|recession|economy|économie)\b",
}

# Portefeuille : devises de référence proposées, et devise de cotation selon la place de marché (suffixe du ticker, vérifié chez Yahoo).
# Sans suffixe, le titre est coté en USD. Londres cote en pence : 100 GBp = 1 GBP.
PORTFOLIO_CURRENCIES = ["EUR", "USD", "GBP", "CHF", "JPY", "CAD", "AUD", "NZD"]
QUOTE_CURRENCIES = {".PA": "EUR", ".DE": "EUR", ".AS": "EUR", ".MC": "EUR", ".MI": "EUR", ".L": "GBp", ".SW": "CHF", ".CO": "DKK", ".T": "JPY", ".HK": "HKD"}

# Durée de conservation des cours déjà téléchargés (secondes)
PRICE_STORE_TTL = 3600

# Classes d'actifs affichées en % (taux) au lieu de la base 100
RATE_CATEGORIES = ["Rates"]

# Tables de correspondance, toutes catégories confondues : nom -> ticker et nom -> catégorie (utile au comparateur)
NAME_TO_TICKER = {}
NAME_TO_CATEGORY = {}
for category, assets in ASSET_UNIVERSE.items():
    NAME_TO_TICKER.update(assets)
    for name in assets:
        NAME_TO_CATEGORY[name] = category

# Graphiques : police et palette de couleurs (bleus, verts, ambre... lisibles sur fond sombre, une couleur par actif)
CHART_FONT = "IBM Plex Sans"
CHART_PALETTE = ["#7DA2FF", "#4ADE80", "#FBBF24", "#F472B6", "#22D3EE", "#FB923C",
                 "#A3E635", "#F87171", "#2DD4BF", "#FDE68A", "#93C5FD", "#86EFAC", "#FDBA74", "#FBCFE8", "#67E8F9", "#CBD5E1"]

# Étapes de la visite guidée affichée à l'ouverture de l'appli (titre, texte)
ONBOARDING_STEPS = [
    (f"Welcome to {BRAND_HTML}",
     "A cross-asset market monitor: indices, equities, bonds, commodities, currencies and rates in one place."),
    ("Pick an asset class",
     "Use the menu at the top of the page to open an asset class: Indices, Equities, Currencies, Rates, Commodities or Bonds."),
    ("Build your chart",
     "Choose a period, then click an instrument: it appears on the chart straight away. Click it again to remove it."),
    ("Read the chart",
     "Hover over the chart to see the exact value and the change since the start. Tick Short MA or Long MA under the chart to add moving averages."),
    ("Build your comparator",
     "On the Comparator page, open an asset class and click its instruments, or tick Add to comparator under a chart."),
    ("Track your portfolio",
     "On the Portfolio page, search for a company, enter your purchase date and quantity, and follow your gains and losses."),
    ("Read the news",
     "On the News page, filter the latest headlines by section and click one to read the full article on its original site."),
]

# Feuille de style CSS : polices IBM Plex Sans (texte, chiffres) et IBM Plex Serif (titres), titre couleur or, libellés en petites majuscules espacées.
# La règle sur stIconMaterial protège les icônes, qui ont leur propre police.
CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:ital,wght@0,500;0,600;1,500&display=swap');

/* Échelle d'espacement unique (multiples de 4 px) et courbe d'animation */
:root {
    --space-8: 0.5rem;
    --space-12: 0.75rem;
    --space-16: 1rem;
    --space-24: 1.5rem;
    --space-40: 2.5rem;
    --space-64: 4rem;
    --ease-out: cubic-bezier(0.23, 1, 0.32, 1);
}

html, body, .stApp, p, li, label, input, textarea, button, [data-testid="stMarkdownContainer"] {
    font-family: "IBM Plex Sans", sans-serif !important;
}
h1, h2, h3, h4 {
    font-family: "IBM Plex Serif", sans-serif !important;
    text-transform: uppercase;
    letter-spacing: 0.06em !important;
    text-wrap: balance;
}
h3 {
    padding-top: var(--space-40) !important;
    padding-bottom: var(--space-8) !important;
}
span[data-testid="stIconMaterial"] {
    font-family: "Material Symbols Rounded" !important;
}

/* Barre du haut : le nom à gauche (dessiné en CSS, donc présent sur toutes les pages), les pages réparties sur le reste de la ligne */
[data-testid="stHeader"] {
    background: #050816;
    border-bottom: 1px solid rgba(148, 163, 184, 0.14);
}
.xad-brand {
    position: fixed;
    top: 0;
    left: var(--space-24);
    z-index: 999991;
    display: flex;
    align-items: center;
    height: 60px;
    font-family: "IBM Plex Serif", serif;
    font-size: 1.125rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    white-space: nowrap;
    color: #D9B872;
    pointer-events: none;
}
/* Le nom garde ses majuscules et minuscules partout. Le "at" se détache : minuscule, italique, blanc. */
.xad-name {
    text-transform: none;
    letter-spacing: 0.04em;
}
.xad-step-title .xad-name {
    letter-spacing: inherit;
}
.xad-at {
    margin: 0 0.04em;
    font-style: italic;
    font-weight: 500;
    color: #F8FAFC;
}
/* Titre de la fenêtre : même écriture que le nom du site dans la barre du haut */
[role="dialog"] h2 {
    text-transform: none !important;
}
[role="dialog"] h2 p {
    font-family: "IBM Plex Serif", serif !important;
    font-size: 1.125rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    color: #D9B872;
}
[role="dialog"] h2 em {
    margin: 0 0.04em;
    font-family: "IBM Plex Serif", serif !important;
    font-weight: 500;
    color: #F8FAFC;
}
/* Titres repliables du comparateur : même style que le menu du haut */
[data-testid="stExpander"] summary p {
    font-size: 0.8125rem;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
[data-testid="stTopNav"] {
    margin-left: 11rem;
    margin-right: var(--space-16);
    justify-content: space-evenly;
}
[data-testid="stTopNavLink"] {
    height: 2.5rem;
    padding: 0 0.625rem;
}
[data-testid="stTopNavLink"] p, [data-testid="stTopNavLink"] span:not([data-testid="stIconMaterial"]) {
    font-size: 0.8125rem;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
/* Page active et survol : teinte or au lieu du bleu par défaut de Streamlit */
[data-testid="stTopNavLink"][aria-current="page"] {
    background-color: rgba(217, 184, 114, 0.16) !important;
}
@media (hover: hover) and (pointer: fine) {
    [data-testid="stTopNavLink"]:hover {
        background-color: rgba(217, 184, 114, 0.10) !important;
    }
}
/* Écran moyen : on retire les icônes pour garder toutes les pages visibles */
@media (max-width: 1280px) {
    [data-testid="stTopNavLink"] [data-testid="stIconMaterial"] {
        display: none;
    }
    [data-testid="stTopNav"] {
        margin-left: 11.5rem;
        margin-right: var(--space-8);
    }
    [data-testid="stTopNavLink"] {
        padding: 0 0.375rem;
    }
    [data-testid="stTopNavLink"] p, [data-testid="stTopNavLink"] span:not([data-testid="stIconMaterial"]) {
        font-size: 0.75rem;
        letter-spacing: 0.06em;
    }
}
/* Petit écran d'ordinateur : le menu se resserre pour garder toutes les pages sur la ligne */
@media (max-width: 1100px) {
    [data-testid="stTopNav"] {
        margin-left: 7.5rem;
        margin-right: var(--space-8);
    }
    [data-testid="stTopNavLink"] {
        padding: 0 0.125rem;
    }
    [data-testid="stTopNavLink"] p, [data-testid="stTopNavLink"] span:not([data-testid="stIconMaterial"]) {
        font-size: 0.6875rem;
        letter-spacing: 0;
    }
}
/* Téléphone : le menu est replié par Streamlit, le nom se place après son bouton */
@media (max-width: 767px) {
    .xad-nav-glide {
        display: none;
    }
    .xad-brand {
        left: 3.5rem;
    }
}

/* Page d'entrée : elle couvre tout l'écran à l'ouverture. Le défilement est capté par le script et déroule la courbe du S&P 500. */
.xad-landing {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    text-align: center;
    background: #050816;
    transition: opacity 320ms var(--ease-out);
}
.xad-landing.is-leaving {
    opacity: 0;
}
.xad-landing-curve {
    position: absolute;
    inset: auto 0 0 0;
    height: 42%;
    transform-origin: bottom;
}
.xad-landing-curve svg {
    display: block;
    width: 100%;
    height: 100%;
}
.xad-landing-dot {
    display: none;
    position: absolute;
    width: 10px;
    height: 10px;
    margin: -5px 0 0 -5px;
    border-radius: 50%;
    background: #D9B872;
    box-shadow: 0 0 0 6px rgba(217, 184, 114, 0.18);
}
.xad-landing-content {
    position: relative;
    max-width: 44rem;
    padding: 0 var(--space-24) 9rem var(--space-24);
}
.stApp h1.xad-landing-title {
    margin: 0;
    padding: 0;
    font-size: clamp(2.75rem, 8vw, 6rem);
    font-weight: 600;
    line-height: 1.1;
    white-space: nowrap;
    text-transform: none;
    color: #D9B872;
}
.xad-landing-signature {
    margin-top: var(--space-12);
    color: #94A3B8;
    font-size: 0.875rem;
    letter-spacing: 0.08em;
}
.xad-word {
    transition: opacity 180ms ease;
}
.xad-landing-text {
    margin: var(--space-24) 0 var(--space-16) 0;
    color: #CBD5E1;
    font-size: 1.125rem;
    line-height: 1.6;
    text-wrap: balance;
}
.xad-landing-howto, .xad-landing-cue {
    padding: var(--space-8) var(--space-12);
    border: 0;
    background: none;
    color: #E2E8F0;
    font-family: "IBM Plex Sans", sans-serif;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    cursor: pointer;
}
.xad-landing-howto {
    color: #D9B872;
}
.xad-landing-cue {
    position: absolute;
    bottom: var(--space-24);
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-8);
    white-space: nowrap;
}
.xad-landing-chevron {
    width: 12px;
    height: 12px;
    margin-top: -4px;
    border-right: 2px solid #D9B872;
    border-bottom: 2px solid #D9B872;
    transform: rotate(45deg);
    animation: xad-nudge 1400ms ease-in-out 3;
}
.xad-landing-track {
    width: 9rem;
    height: 2px;
    background: rgba(148, 163, 184, 0.3);
}
.xad-landing-bar {
    width: 100%;
    height: 100%;
    background: #D9B872;
    transform: scaleX(0);
    transform-origin: left;
}
@keyframes xad-nudge {
    50% { transform: translateY(5px) rotate(45deg); }
}

/* Boutons cachés que le script de la page d'entrée actionne */
.st-key-xad_enter, .st-key-xad_howto {
    position: absolute;
    left: -9999px;
}

/* Accueil : grand titre centré, chiffres qui défilent, beaucoup d'air */
.stApp h1.xad-home-title {
    margin: var(--space-24) 0 0 0;
    padding: 0;
    font-size: clamp(2rem, 4.5vw, 3.5rem);
    font-weight: 600;
    line-height: 1.1;
    letter-spacing: 0.04em !important;
    text-align: center;
}
.stApp p.xad-home-text {
    max-width: 34rem;
    margin: var(--space-16) auto var(--space-40) auto !important;
    color: #94A3B8;
    font-size: 1.0625rem;
    line-height: 1.6;
    text-align: center;
    text-wrap: balance;
}
.xad-stats {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: var(--space-16);
    max-width: 52rem;
    margin: 0 auto var(--space-64) auto;
    text-align: center;
}
.xad-stat-value {
    color: #D9B872;
    font-family: "IBM Plex Serif", serif;
    font-size: 2.25rem;
    font-weight: 600;
    line-height: 1.2;
}
.xad-stat-label {
    color: #94A3B8;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
@media (max-width: 640px) {
    .xad-stats {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
/* Les tuiles arrivent en cascade juste après la page d'entrée */
.st-key-home_enter [class*="st-key-tile_"] {
    animation: xad-enter 420ms var(--ease-out) backwards;
}
.st-key-home_enter .st-key-tile_Equities { animation-delay: 60ms; }
.st-key-home_enter .st-key-tile_Currencies { animation-delay: 120ms; }
.st-key-home_enter .st-key-tile_Rates { animation-delay: 180ms; }
.st-key-home_enter .st-key-tile_Commodities { animation-delay: 240ms; }
.st-key-home_enter .st-key-tile_Bonds { animation-delay: 300ms; }

/* Haut de page : barre translucide dont le filet apparaît au défilement, et fine barre de progression dorée */
[data-testid="stHeader"] {
    background: rgba(5, 8, 22, 0.72) !important;
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
    border-bottom-color: transparent !important;
    transition: border-color 200ms ease;
}
[data-testid="stHeader"].is-scrolled {
    border-bottom-color: rgba(148, 163, 184, 0.14) !important;
}
.xad-scroll-bar {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 999992;
    width: 100%;
    height: 2px;
    background: #D9B872;
    transform: scaleX(0);
    transform-origin: left;
    pointer-events: none;
}

/* Menu : une pastille dorée glisse d'un onglet à l'autre sous la souris */
[data-testid="stTopNavLink"] [data-testid="stIconMaterial"] {
    display: none;
}
.xad-nav-glide {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 0;
    height: 2.5rem;
    border-radius: 8px;
    background: rgba(217, 184, 114, 0.14);
    opacity: 0;
    pointer-events: none;
    transition: transform 240ms var(--ease-out), width 240ms var(--ease-out), opacity 160ms ease;
}
.xad-has-glide [data-testid="stTopNavLink"],
.xad-has-glide [data-testid="stTopNavLink"]:hover,
.xad-has-glide [data-testid="stTopNavLink"][aria-current="page"] {
    position: relative;
    z-index: 1;
    background-color: transparent !important;
}

/* Cartes et tuiles : halo qui suit la souris, légère montée au survol */
.xad-card, [class*="st-key-tile_"] {
    position: relative;
    transition: transform 200ms var(--ease-out), border-color 200ms ease, box-shadow 200ms ease;
}
.xad-card::before, [class*="st-key-tile_"]::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    background: radial-gradient(260px circle at var(--mx, 50%) var(--my, 50%), rgba(217, 184, 114, 0.10), transparent 70%);
    opacity: 0;
    pointer-events: none;
    transition: opacity 240ms ease;
}
.xad-card-dot {
    transition: transform 200ms var(--ease-out);
}
[class*="st-key-tile_"] [data-testid="stPageLink"] [data-testid="stIconMaterial"] {
    transition: transform 200ms var(--ease-out);
}
@media (hover: hover) and (pointer: fine) {
    .xad-card:hover, [class*="st-key-tile_"]:hover {
        transform: translateY(-2px);
        border-color: rgba(217, 184, 114, 0.35);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.32);
    }
    .xad-card:hover::before, [class*="st-key-tile_"]:hover::before {
        opacity: 1;
    }
    .xad-card:hover .xad-card-dot {
        transform: scale(1.4);
    }
    [class*="st-key-tile_"]:hover [data-testid="stPageLink"] [data-testid="stIconMaterial"] {
        transform: translateX(4px);
    }
}

/* Boutons d'instruments : réaction au survol et au clic */
[data-testid="stButtonGroup"] button {
    transition: transform 160ms var(--ease-out), border-color 160ms ease, background-color 160ms ease, color 160ms ease;
}
[data-testid="stButtonGroup"] button:active {
    transform: scale(0.96);
}
@media (hover: hover) and (pointer: fine) {
    [data-testid="stButtonGroup"] button:hover {
        transform: translateY(-1px);
        border-color: #D9B872;
    }
}

/* Groupes repliables : le titre se décale et passe en or au survol, le contenu glisse à l'ouverture */
[data-testid="stExpander"] summary p {
    transition: transform 200ms var(--ease-out), color 160ms ease;
}
[data-testid="stExpander"] details[open] > :not(summary) {
    animation: xad-enter 240ms var(--ease-out) backwards;
}
[data-testid="stExpander"] details {
    transition: border-color 200ms ease;
}
@media (hover: hover) and (pointer: fine) {
    [data-testid="stExpander"] details:hover {
        border-color: rgba(217, 184, 114, 0.35);
    }
    [data-testid="stExpander"] summary:hover p {
        transform: translateX(3px);
        color: #D9B872;
    }
}

/* Boutons encadrés ("Clear all", "Remove selected", "Undo") : contour visible, or au survol */
button[data-testid^="stBaseButton-secondary"] {
    border-color: rgba(148, 163, 184, 0.35);
    transition: transform 160ms var(--ease-out), border-color 160ms ease, color 160ms ease;
}
@media (hover: hover) and (pointer: fine) {
    button[data-testid^="stBaseButton-secondary"]:hover {
        border-color: #D9B872;
        color: #D9B872;
    }
    button[data-testid^="stBaseButton-secondary"]:hover p {
        color: #D9B872;
    }
}

/* Boutons discrets ("How it works", "Clear") : un trait doré se dessine sous le texte au survol */
button[data-testid^="stBaseButton-tertiary"] p {
    padding-bottom: 2px;
    background: linear-gradient(#D9B872, #D9B872) left bottom / 0 1px no-repeat;
    transition: background-size 240ms var(--ease-out), color 160ms ease;
}
@media (hover: hover) and (pointer: fine) {
    button[data-testid^="stBaseButton-tertiary"]:hover p {
        background-size: 100% 1px;
        color: #D9B872;
    }
}

/* Champs de date : le contour s'illumine au survol */
[data-testid="stDateInputField"] {
    transition: border-color 160ms ease;
}
@media (hover: hover) and (pointer: fine) {
    [data-testid="stDateInputField"]:hover {
        border-color: rgba(217, 184, 114, 0.5);
    }
}

/* Une nouvelle carte apparaît en grandissant légèrement ; les éléments plus bas arrivent quand on défile jusqu'à eux */
.xad-new {
    animation: xad-card-in 300ms var(--ease-out) backwards;
}
@keyframes xad-card-in {
    from { opacity: 0; transform: translateY(8px) scale(0.98); }
    to { opacity: 1; transform: none; }
}
.xad-chart-ghost {
    position: absolute;
    top: 0;
    left: 0;
    pointer-events: none;
}
.xad-reveal-wait {
    opacity: 0;
    transform: translateY(18px);
}
.xad-reveal-in {
    opacity: 1;
    transform: none;
    transition: opacity 520ms var(--ease-out), transform 520ms var(--ease-out);
}
.st-key-xad_motion {
    position: absolute;
    height: 0;
    overflow: hidden;
}

/* Dates : seul le calendrier sert à choisir. Les blocs année / mois / jour ne réagissent plus à la souris ; ils restent accessibles au clavier. */
[data-testid="stDateInputField"] {
    cursor: pointer;
}
[data-testid="stDateInputField"] [role="spinbutton"] {
    pointer-events: none;
}

/* Accueil : une tuile par classe d'actifs, avec son actif de référence sur un an et un lien vers sa page */
[data-testid="stColumn"]:has([class*="st-key-tile_"]) > div,
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-tile_"]) {
    height: 100%;
}
[class*="st-key-tile_"] {
    height: 100%;
    justify-content: space-between;
    padding: var(--space-24);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 12px;
    background: rgba(14, 18, 35, 0.6);
}
.xad-tile-class {
    font-family: "IBM Plex Serif", serif;
    font-size: 1.375rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: #E2E8F0;
}
.xad-tile-text {
    color: #94A3B8;
    font-size: 0.875rem;
    line-height: 1.5;
    margin: var(--space-8) 0 var(--space-16) 0;
}
[class*="st-key-tile_"] [data-testid="stPageLink"] a {
    padding-left: 0;
    margin-top: var(--space-8);
}
/* Toute la case est cliquable : le lien "Open ..." s'étend sur toute sa surface */
[class*="st-key-tile_"] {
    cursor: pointer;
}
[class*="st-key-tile_"] [data-testid="stElementContainer"], [class*="st-key-tile_"] [data-testid="stPageLink"], [class*="st-key-tile_"] [data-testid="stPageLink"] > * {
    position: static;
}
[class*="st-key-tile_"] [data-testid="stPageLink"] a::after {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: 12px;
}
.xad-tile-class {
    transition: color 160ms ease;
}
@media (hover: hover) and (pointer: fine) {
    [class*="st-key-tile_"]:hover .xad-tile-class {
        color: #D9B872;
    }
}
[class*="st-key-tile_"] [data-testid="stPageLink"] p {
    color: #D9B872;
    font-weight: 500;
}

.xad-meta {
    text-align: left;
    color: #94A3B8;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

/* Libellés des widgets et boutons : petites majuscules espacées, comme sur Pulsar */
[data-testid="stWidgetLabel"] p, .xad-label {
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-size: 0.75rem;
    color: #94A3B8;
}
button p {
    text-transform: uppercase;
    letter-spacing: 0.14em;
}

/* Étiquettes de la liste d'instruments : texte sombre, lisible sur l'accent or */
[data-baseweb="tag"], [data-baseweb="tag"] span, [data-baseweb="tag"] svg {
    color: #050816 !important;
}

/* Boutons principaux : texte sombre, plus lisible sur l'accent or */
button[data-testid^="stBaseButton-primary"] p {
    color: #050816;
    font-weight: 600;
}
@media (hover: hover) and (pointer: fine) {
    button[data-testid^="stBaseButton-primary"]:hover {
        background-color: #E8CF96;
        border-color: #E8CF96;
    }
}

/* Finitions générales : moins de vide en haut, contour visible au clavier, sélection de texte aux couleurs de l'appli, chiffres alignés */
[data-testid="stMainBlockContainer"] {
    padding-top: 5.5rem;
}
button:focus-visible, a:focus-visible {
    outline: 2px solid #D9B872 !important;
    outline-offset: 2px;
}
::selection {
    background: rgba(217, 184, 114, 0.35);
}
.stApp {
    font-variant-numeric: tabular-nums;
}

/* Visite guidée */
.xad-step {
    color: #D9B872;
    font-size: 0.75rem;
    font-weight: 500;
    letter-spacing: 0.16em;
    text-align: center;
}
.xad-step-title {
    font-family: "IBM Plex Serif", sans-serif;
    font-weight: 600;
    font-size: 2.2rem;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    text-align: center;
    text-wrap: balance;
    margin: 0.4rem 0 0.6rem 0;
}
.xad-step-text {
    text-align: center;
    color: #CBD5E1;
    font-size: 1rem;
    line-height: 1.6;
    text-wrap: balance;
}
.xad-dots {
    text-align: center;
    color: #334155;
    font-size: 1.1rem;
    letter-spacing: 0.3em;
    margin: var(--space-16) 0;
}
.xad-dots .active {
    color: #D9B872;
}

/* Finitions (règles d'Emil Kowalski) : retour visuel au clic, apparition douce de la visite */
button {
    transition: transform 160ms var(--ease-out), background-color 160ms ease, border-color 160ms ease;
}
button:active {
    transform: scale(0.97);
}
[data-testid="stForm"] {
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 16px;
    background: rgba(14, 18, 35, 0.6);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.28);
}
.xad-step, .xad-step-title, .xad-step-text {
    animation: xad-enter 320ms var(--ease-out) both;
}
.xad-step-title { animation-delay: 40ms; }
.xad-step-text { animation-delay: 80ms; }
@keyframes xad-enter {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
}
@keyframes xad-fade {
    from { opacity: 0; }
    to { opacity: 1; }
}

/* Mouvement réduit : plus de déplacement, mais un fondu garde le retour visuel */
@media (prefers-reduced-motion: reduce) {
    [data-testid="stMain"] {
        scroll-behavior: auto;
    }
    .xad-landing-chevron {
        animation: none;
    }
    .st-key-home_enter [class*="st-key-tile_"] {
        animation: xad-fade 200ms ease backwards;
    }
    .xad-card, [class*="st-key-tile_"], [data-testid="stButtonGroup"] button, [data-testid="stExpander"] summary p, .xad-nav-glide {
        transform: none !important;
        transition: opacity 160ms ease, border-color 160ms ease, color 160ms ease;
    }
    .xad-new, .xad-news-row {
        animation: xad-fade 200ms ease backwards;
    }
    .xad-news-title {
        transform: none !important;
    }
    .xad-reveal-wait {
        opacity: 1;
        transform: none;
    }
    button {
        transition: background-color 160ms ease, border-color 160ms ease;
    }
    button:active {
        transform: none;
    }
    .xad-step, .xad-step-title, .xad-step-text {
        animation: xad-fade 200ms ease backwards;
    }
}

/* Cartes d'indicateurs : une par actif, autant que la largeur le permet */
.xad-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: var(--space-12);
    margin: var(--space-8) 0 var(--space-16) 0;
}
/* Sur téléphone : deux cartes par ligne, plus compactes, pour atteindre le graphique plus vite */
@media (max-width: 640px) {
    .xad-cards {
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: var(--space-8);
    }
    .xad-card {
        padding: var(--space-12) !important;
    }
    .xad-card-last {
        font-size: 1.5rem !important;
    }
}
.xad-card {
    padding: var(--space-16);
    border: 1px solid rgba(148, 163, 184, 0.12);
    border-radius: 12px;
    background: rgba(14, 18, 35, 0.6);
}
.xad-card-name {
    color: #CBD5E1;
    font-size: 0.875rem;
    font-weight: 500;
}
.xad-card-dot {
    display: inline-block;
    width: 0.6rem;
    height: 0.6rem;
    margin-right: 0.45rem;
    border-radius: 50%;
}
.xad-card-last {
    color: #F8FAFC;
    font-family: "IBM Plex Sans", sans-serif;
    font-size: 1.75rem;
    font-weight: 600;
    line-height: 1.3;
    margin: 0.25rem 0 var(--space-8) 0;
}
.xad-card-row {
    display: flex;
    justify-content: space-between;
    color: #94A3B8;
    font-size: 0.75rem;
    line-height: 1.6;
}
.xad-up { color: #4ADE80; font-weight: 600; }
.xad-down { color: #F87171; font-weight: 600; }
.xad-flat { color: #CBD5E1; font-weight: 600; }
.xad-vol { color: #CBD5E1; }

/* News : une liste sobre, comme un fil de salle de marché. Au survol, le titre passe en or et se décale, et une flèche apparaît. */
.xad-news-day {
    margin: var(--space-40) 0 var(--space-8) 0;
    color: #D9B872;
    font-size: 0.8125rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}
.xad-news-row {
    display: grid;
    grid-template-columns: 3.5rem 7rem 1fr auto;
    align-items: baseline;
    gap: var(--space-16);
    padding: var(--space-12) var(--space-8);
    border-top: 1px solid rgba(148, 163, 184, 0.12);
    color: inherit !important;
    text-decoration: none !important;
    animation: xad-enter 280ms var(--ease-out) backwards;
    transition: background-color 160ms ease;
}
.xad-news-row:nth-of-type(2) { animation-delay: 30ms; }
.xad-news-row:nth-of-type(3) { animation-delay: 60ms; }
.xad-news-row:nth-of-type(4) { animation-delay: 90ms; }
.xad-news-row:nth-of-type(n+5) { animation-delay: 120ms; }
.xad-news-time {
    color: #94A3B8;
    font-size: 0.8125rem;
    font-variant-numeric: tabular-nums;
}
.xad-news-section {
    color: #D9B872;
    font-size: 0.6875rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}
.xad-news-title {
    color: #E2E8F0;
    font-size: 1rem;
    font-weight: 500;
    line-height: 1.45;
    text-wrap: pretty;
    transition: transform 200ms var(--ease-out), color 160ms ease;
}
.xad-news-source {
    color: #94A3B8;
    font-size: 0.75rem;
    white-space: nowrap;
}
.xad-news-source::after {
    content: "→";
    display: inline-block;
    margin-left: var(--space-8);
    color: #D9B872;
    opacity: 0;
    transform: translateX(-4px);
    transition: opacity 160ms ease, transform 200ms var(--ease-out);
}
@media (hover: hover) and (pointer: fine) {
    .xad-news-row:hover {
        background-color: rgba(217, 184, 114, 0.05);
    }
    .xad-news-row:hover .xad-news-title {
        color: #D9B872;
        transform: translateX(3px);
    }
    .xad-news-row:hover .xad-news-source::after {
        opacity: 1;
        transform: none;
    }
}
@media (max-width: 767px) {
    .xad-news-row {
        grid-template-columns: 3rem 1fr;
        gap: var(--space-8);
    }
    .xad-news-title {
        grid-column: 1 / -1;
    }
    .xad-news-source {
        grid-column: 1 / -1;
    }
}

/* Pied de page */
.xad-footer {
    text-align: center;
    color: #94A3B8;
    font-size: 0.75rem;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: var(--space-64);
}
</style>
"""

FOOTER_HTML = '<div class="xad-footer">Educational tool — not investment advice · Data: Yahoo Finance · by Louis DIGUET--GUYENNE</div>'


# FONCTIONS — DONNÉES

# Récupère les données horaires d'un instrument et garde la dernière cotation de chaque jour. Yahoo limite ces données à 730 jours.
def download_intraday_close(ticker, start, end):
    intraday = yf.download(
        ticker,
        start=max(start, date.today() - timedelta(days=729)),
        end=end + timedelta(days=1),
        interval="1h",
        auto_adjust=True,
        progress=False,
    )
    if intraday.empty:
        return pd.Series(dtype=float)
    values = intraday["Close"]
    values = values.iloc[:, 0] if isinstance(values, pd.DataFrame) else values
    values = values.dropna()
    values.index = values.index.tz_localize(None).normalize()
    return values.groupby(level=0).last()


# Rendement actuariel d'une OAT à partir de son prix hors coupon (coupon annuel). On ajoute le coupon couru,
# puis on cherche par dichotomie le taux qui égalise les flux actualisés et le prix payé.
def oat_yield(clean_price, coupon, maturity, as_of):
    years = (maturity - as_of).days / 365.25
    if years <= 0:
        return float("nan")
    n_flows = math.ceil(years)
    to_next_coupon = years - (n_flows - 1)
    dirty_price = clean_price + coupon * (1 - to_next_coupon)
    times = [to_next_coupon + i for i in range(n_flows)]

    low, high = -0.05, 0.30
    for _ in range(60):
        rate = (low + high) / 2
        value = sum(coupon / (1 + rate) ** t for t in times) + 100 / (1 + rate) ** times[-1]
        if value > dirty_price:
            low = rate
        else:
            high = rate
    return 100 * rate


# Taux d'un Bund publié par la Bundesbank. En cas de problème, renvoie une série vide : l'actif sera signalé comme sans données.
def download_bund_yield(ticker, start, end):
    try:
        with urllib.request.urlopen(BUND_URL.format(code=BUND_SERIES[ticker]), timeout=20) as response:
            table = pd.read_csv(response, header=None, usecols=[0, 1], names=["Date", "Yield"], skiprows=1, encoding="utf-8-sig")
    except (OSError, ValueError):
        return pd.Series(dtype=float)
    table["Date"] = pd.to_datetime(table["Date"], format="%Y-%m-%d", errors="coerce")
    table["Yield"] = pd.to_numeric(table["Yield"], errors="coerce")
    table = table.dropna().set_index("Date")["Yield"]
    return table[(table.index.date >= start) & (table.index.date <= end)]


# Télécharge les cours de clôture quotidiens (ajustés des dividendes et splits) et renvoie aussi l'heure du téléchargement.
# Les OAT et les Bund ont leur propre source (voir plus haut) ; leurs séries sont ajoutées au tableau, une colonne par instrument.
# @st.cache_data garde le résultat 1 h : relancer la même analyse ne retélécharge rien, et l'heure renvoyée reste celle du vrai téléchargement.
@st.cache_data(ttl=3600, show_spinner=False)
def download_close_prices(tickers, start, end):
    market_tickers = [t for t in tickers if t not in OAT_LINES and t not in BUND_SERIES]
    close = pd.DataFrame()
    if market_tickers:
        data = yf.download(
            market_tickers,
            start=start,
            end=end + timedelta(days=1),
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if not data.empty:
            close = data["Close"]
            # Un seul ticker peut renvoyer une Series au lieu d'un DataFrame : on harmonise.
            if isinstance(close, pd.Series):
                close = close.to_frame(name=market_tickers[0])
    fetched_at = datetime.now()

    extra_series = {}
    for ticker in tickers:
        if ticker in INTRADAY_HISTORY_TICKERS:
            values = download_intraday_close(ticker, start, end)
            extra_series[ticker] = values.combine_first(close[ticker]) if ticker in close else values
        elif ticker in OAT_LINES:
            coupon, maturity = OAT_LINES[ticker]
            prices = download_intraday_close(ticker, start, end)
            extra_series[ticker] = pd.Series(
                [oat_yield(price, coupon, maturity, day.date()) for day, price in prices.items()],
                index=prices.index, dtype=float,
            )
        elif ticker in BUND_SERIES:
            extra_series[ticker] = download_bund_yield(ticker, start, end)

    for ticker, values in extra_series.items():
        if not values.empty:
            close = close.reindex(close.index.union(values.index))
            close[ticker] = values
    return close, fetched_at


# Renvoie les cours demandés en gardant en mémoire chaque instrument déjà téléchargé : cliquer sur un nouveau bouton ne télécharge que celui-là.
def fetch_prices(tickers, start_date, end_date):
    store = st.session_state.setdefault("price_store", {})
    now = datetime.now()
    missing = [
        ticker for ticker in tickers
        if (ticker, start_date, end_date) not in store
        or (now - store[(ticker, start_date, end_date)][1]).total_seconds() > PRICE_STORE_TTL
    ]
    if missing:
        with st.spinner("Downloading market data..."):
            close, fetched_at = download_close_prices(missing, start_date, end_date)
        for ticker in missing:
            values = close[ticker].dropna() if ticker in close else pd.Series(dtype=float)
            store[(ticker, start_date, end_date)] = (values, fetched_at)
        st.session_state["last_updated"] = fetched_at

    columns = {ticker: store[(ticker, start_date, end_date)][0] for ticker in tickers}
    filled = {ticker: values for ticker, values in columns.items() if not values.empty}
    return pd.DataFrame(filled) if filled else pd.DataFrame()


# Télécharge puis nettoie les données : ordre de sélection, noms lisibles, actifs sans données retirés, trous de calendrier comblés.
# Renvoie None en cas de problème (le message est déjà affiché).
def load_prices(selected_names, start_date, end_date):
    tickers = [NAME_TO_TICKER[name] for name in selected_names]

    try:
        close = fetch_prices(tickers, start_date, end_date)
    except Exception as error:
        st.error(f"The market data could not be downloaded: {error}")
        return None

    if close.empty:
        st.warning("No quotations were returned. Check the instruments and the period.")
        return None

    close = close.reindex(columns=tickers)
    close.columns = selected_names
    close = close.dropna(how="all")

    missing_assets = [name for name in selected_names if close[name].isna().all()]
    if missing_assets:
        st.warning(f"No data returned for: {', '.join(missing_assets)}. Excluded from the analysis.")
        close = close.drop(columns=missing_assets)

    if close.empty:
        st.warning("None of the selected instruments returned data for this period.")
        return None

    # Historique plus court que la période demandée (cas de l'OAT et du Bund) : on le signale au lieu de le laisser passer inaperçu.
    for name in close.columns:
        first_date = close[name].first_valid_index().date()
        if (first_date - start_date).days > 10:
            st.warning(f"{name}: data is only available from {first_date:%d/%m/%Y}.")

    return close.ffill()


# FONCTIONS — COMPARATEUR

# Appelée par Streamlit quand on coche / décoche "Add to comparator" : ajoute ou retire l'actif de la liste mémorisée.
def toggle_comparator(name, checkbox_key):
    comparator = st.session_state["comparator"]
    if st.session_state[checkbox_key] and name not in comparator:
        comparator.append(name)
    elif not st.session_state[checkbox_key] and name in comparator:
        comparator.remove(name)


# Appelée quand on clique sur un bouton d'instrument : la liste mémorisée suit les boutons de ce bloc, sans toucher aux autres blocs.
def sync_pills(store_key, pills_key, options):
    selected = st.session_state[pills_key] or []
    others = [name for name in st.session_state[store_key] if name not in options]
    st.session_state[store_key] = others + [name for name in options if name in selected]


# Appelée quand on clique sur un actif de la ligne "Selected" : il sort de la sélection
def sync_selected_row(store_key, row_key):
    st.session_state[store_key] = list(st.session_state[row_key] or [])


# Boutons d'instruments d'un bloc. La liste mémorisée pilote les boutons : on les recale avant de les afficher.
def render_pills(store_key, label, options, show_label):
    pills_key = f"{store_key}__{label}"
    st.session_state[pills_key] = [name for name in options if name in st.session_state[store_key]]
    st.pills(label, options, selection_mode="multi", key=pills_key, label_visibility="visible" if show_label else "collapsed",
             on_change=sync_pills, args=(store_key, pills_key, options))


# Ligne qui rappelle ce qui est choisi, même si son groupe est replié. Un clic retire l'actif.
def render_selected_row(store_key):
    if st.session_state[store_key]:
        row_key = f"{store_key}__row"
        st.session_state[row_key] = list(st.session_state[store_key])
        st.pills("Selected", list(st.session_state[store_key]), selection_mode="multi", key=row_key,
                 on_change=sync_selected_row, args=(store_key, row_key))


# VISITE GUIDÉE

# Fenêtre (st.dialog) qui présente l'appli en plusieurs étapes. Cliquer sur un bouton de la fenêtre ne relance que la fenêtre :
# "Next" passe à l'étape suivante, "Skip" ou "Start" ferment la fenêtre avec st.rerun(), qui relance toute l'appli sans la fenêtre.
@st.dialog("DESK*at*H")
def show_onboarding():
    step = st.session_state.get("onboarding_step", 0)
    total = len(ONBOARDING_STEPS)
    title, text = ONBOARDING_STEPS[step]

    dots = "".join('<span class="active">●</span>' if i == step else "●" for i in range(total))
    st.markdown(
        f"""
        <div class="xad-step">STEP {step + 1} / {total}</div>
        <div class="xad-step-title">{title}</div>
        <div class="xad-step-text">{text}</div>
        <div class="xad-dots">{dots}</div>
        """,
        unsafe_allow_html=True,
    )

    skip_col, next_col = st.columns(2)
    if skip_col.button("Skip", type="tertiary", width="stretch"):
        st.rerun()
    is_last = step == total - 1
    if next_col.button("Start" if is_last else "Next", type="primary", width="stretch"):
        if is_last:
            st.rerun()
        st.session_state["onboarding_step"] = step + 1
        st.rerun(scope="fragment")


# Ouvre la visite depuis la 1re étape (bouton "How it works" de l'en-tête)
def restart_onboarding():
    st.session_state["onboarding_step"] = 0
    st.session_state["show_onboarding"] = True


# FONCTIONS — CARTES D'INDICATEURS

# Calcule dernier cours, variation sur la période et volatilité annualisée d'un actif (en % pour les prix, en points de base pour les taux).
# Les jours recopiés par ffill() sont retirés pour la volatilité : leur variation de 0 la ferait baisser artificiellement.
def compute_metrics(series, is_rate):
    values = series.dropna()
    first, last = values.iloc[0], values.iloc[-1]
    traded_days = values[values.diff().fillna(1) != 0]
    if is_rate:
        change = (last - first) * 100
        daily_moves = traded_days.diff() * 100
    else:
        change = last / first - 1
        daily_moves = traded_days.pct_change()
    return last, change, daily_moves.std() * math.sqrt(252)


# Couleur d'un actif : elle dépend de sa place dans la liste complète, donc elle ne change pas quand on ajoute ou retire un autre actif.
def asset_color(name, universe):
    return CHART_PALETTE[universe.index(name) % len(CHART_PALETTE)]


# Met en forme le dernier cours et la variation : % et points de base pour les taux, signe toujours affiché.
def format_last_and_change(last, change, is_rate, decimals):
    last_text = f"{last:,.{decimals}f}" + ("%" if is_rate else "")
    change_text = f"{change:+,.0f} bp" if is_rate else f"{change:+.2%}"
    return last_text, change_text


# Affiche une carte par actif : point de la couleur de sa courbe, dernier cours, variation (signe + couleur), volatilité.
# Le HTML est écrit sans indentation : sinon Markdown le prendrait pour un bloc de code. html.escape protège le "&" de "S&P 500".
def render_metric_cards(close_prices, is_rate, decimals, universe):
    cards = []
    for name in close_prices.columns:
        last, change, volatility = compute_metrics(close_prices[name], is_rate)
        last_text, change_text = format_last_and_change(last, change, is_rate, decimals)
        if NAME_TO_TICKER[name] in OAT_LINES:
            # Lignes d'OAT : les cotations quotidiennes sont trop bruitées pour donner une volatilité fiable
            vol_text = "n/a"
        elif is_rate:
            vol_text = "n/a" if pd.isna(volatility) else f"{volatility:,.0f} bp"
        else:
            vol_text = "n/a" if pd.isna(volatility) else f"{volatility:.1%}"
        tone = "xad-up" if change > 0 else "xad-down" if change < 0 else "xad-flat"
        dot_color = asset_color(name, universe)
        cards.append(
            f'<div class="xad-card">'
            f'<div class="xad-card-name"><span class="xad-card-dot" style="background:{dot_color}"></span>{html.escape(name)}</div>'
            f'<div class="xad-card-last">{last_text}</div>'
            f'<div class="xad-card-row"><span>Period change</span><span class="{tone}">{change_text}</span></div>'
            f'<div class="xad-card-row"><span>Volatility (ann.)</span><span class="xad-vol">{vol_text}</span></div>'
            f'</div>'
        )
    st.markdown(f'<div class="xad-cards">{"".join(cards)}</div>', unsafe_allow_html=True)


# FONCTIONS — GRAPHIQUES

# Graphique Altair : une couleur par actif, moyennes mobiles en pointillés de la même couleur.
# Au survol : ligne verticale + bulle avec la date, la valeur de chaque actif et sa variation depuis le début (% pour les prix, points de base pour les taux).
def plot_chart(series_by_type, y_title, is_rate=False, universe=None):
    prices = series_by_type["Close"]
    assets = list(prices.columns)

    # Format "long" pour les courbes : une ligne par date, actif et type de courbe (Close, MA 20, MA 50...)
    frames = []
    for series_type, df in series_by_type.items():
        part = df.copy()
        part.index.name = "Date"
        part = part.reset_index().melt(id_vars="Date", var_name="Asset", value_name="Value")
        part["Type"] = series_type
        frames.append(part)
    long_data = pd.concat(frames).dropna()

    # Format "large" pour la bulle : une ligne par date, avec la valeur et la variation depuis le début de chaque actif
    tooltip_data = prices.copy()
    first_values = prices.bfill().iloc[0]
    tooltip_fields = [alt.Tooltip("Date:T", title="Date", format="%d/%m/%Y")]
    for asset in assets:
        change_field = f"{asset} Δ"
        if is_rate:
            tooltip_data[change_field] = (prices[asset] - first_values[asset]) * 100
            change_format, change_title = "+.0f", f"{asset} — change (bp)"
        else:
            tooltip_data[change_field] = prices[asset] / first_values[asset] - 1
            change_format, change_title = "+.2%", f"{asset} — change"
        tooltip_fields.append(alt.Tooltip(field=asset, type="quantitative", format=".2f", title=asset))
        tooltip_fields.append(alt.Tooltip(field=change_field, type="quantitative", format=change_format, title=change_title))
    tooltip_data.index.name = "Date"
    tooltip_data = tooltip_data.reset_index()

    # Sélection "la date la plus proche de la souris" : pilote la ligne verticale et les points sur les courbes
    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["Date"], empty=False)

    x = alt.X("Date:T", title=None, scale=alt.Scale(nice=False))
    y = alt.Y("Value:Q", title=y_title, scale=alt.Scale(zero=False))
    color = alt.Color(
        "Asset:N", sort=assets, title=None,
        scale=alt.Scale(domain=assets, range=[asset_color(asset, universe or assets) for asset in assets]),
        # Noms jamais tronqués ; 1 ou 2 colonnes au maximum pour que la légende tienne aussi sur téléphone
        legend=alt.Legend(orient="bottom", labelLimit=0, columns=1 if any(len(a) > 20 for a in assets) else min(len(assets), 2)),
    )
    # Légende des traits (Close, MA) au-dessus du graphique : à côté de celle des actifs, elle sortirait de l'écran sur téléphone
    dash_legend = alt.Legend(orient="top") if len(series_by_type) > 1 else None

    lines = alt.Chart(long_data).mark_line(strokeWidth=2).encode(
        x=x,
        y=y,
        color=color,
        strokeDash=alt.StrokeDash("Type:N", sort=list(series_by_type), title=None, legend=dash_legend),
    )
    points = alt.Chart(long_data[long_data["Type"] == "Close"]).mark_point(filled=True, size=60).encode(
        x=x,
        y=y,
        color=color,
        opacity=alt.condition(nearest, alt.value(1), alt.value(0)),
    )
    rules = alt.Chart(tooltip_data).mark_rule(color="#94A3B8").encode(
        x="Date:T",
        opacity=alt.condition(nearest, alt.value(0.5), alt.value(0)),
        tooltip=tooltip_fields,
    ).add_params(nearest)

    # Habillage : police IBM Plex Sans, grille discrète, textes gris clair, pas de cadre autour du graphique
    chart = (
        alt.layer(lines, points, rules)
        .properties(height=420)
        .interactive()
        .configure(font=CHART_FONT)
        .configure_axis(gridColor="#1E293B", domainColor="#334155", labelColor="#94A3B8", titleColor="#94A3B8")
        .configure_legend(labelColor="#CBD5E1")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, width="stretch")


# PAGES

# Télécharge un an de cours pour les actifs de référence de l'accueil. En cas d'échec, l'accueil reste affiché, sans chiffres.
def load_home_prices():
    tickers = [NAME_TO_TICKER[name] for name, _ in HOME_TILES.values()]
    try:
        close, _ = download_close_prices(tickers, date.today() - timedelta(days=365), date.today())
    except Exception:
        return pd.DataFrame()
    return close


# Dessine la courbe de la page d'entrée en SVG à partir des vrais cours (x : le temps, y : le cours ramené entre 0 et 1).
def build_landing_curve(series):
    values = series.dropna()
    if len(values) < 2:
        return ""
    low, high = values.min(), values.max()
    line = " ".join(
        f"{i / (len(values) - 1) * 1000:.1f},{290 - (value - low) / (high - low) * 270:.1f}"
        for i, value in enumerate(values)
    )
    # st.html retire les balises SVG : on transmet seulement les points, et le script dessine la courbe.
    return f'<div class="xad-landing-data" data-points="{line}" hidden></div>'


# Script de la page d'entrée. Il capte le défilement (molette, pavé tactile, doigt, clavier) sans faire bouger la page et cumule une progression de 0 à 1.
# Cette progression déroule la courbe et fait remonter le texte. À 100 %, il actionne le bouton caché qui ouvre le site.
LANDING_SCRIPT = """
<script>
(function () {
    if (window.__deskathLanding) { window.__deskathLanding(); }

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const clamp = (value, low, high) => Math.min(high, Math.max(low, value));

    let target = window.__deskathProgress || 0;
    let current = target;
    let leaving = false;
    let lastFrame = 0;
    let frame = 0;
    let points = [];

    // La courbe arrive quand les cours sont téléchargés : le script la dessine dès que ses points sont disponibles
    function buildCurve(root) {
        const curve = root.querySelector(".xad-landing-curve");
        const data = document.querySelector(".xad-landing-data");
        if (!data || !data.dataset.points || curve.querySelector("svg")) { return; }
        const line = data.dataset.points;
        points = line.split(" ").map(p => p.split(",").map(Number));
        // Le filtre de Streamlit supprime un script qui contient du texte en forme de balise : le chevron ouvrant est donc écrit par son code
        const open = String.fromCharCode(60);
        curve.insertAdjacentHTML("afterbegin",
            open + 'svg viewBox="0 0 1000 300" preserveAspectRatio="none">'
            + open + 'defs>' + open + 'linearGradient id="xad-area" x1="0" y1="0" x2="0" y2="1">'
            + open + 'stop offset="0" stop-color="#D9B872" stop-opacity="0.16"/>' + open + 'stop offset="1" stop-color="#D9B872" stop-opacity="0"/>'
            + open + '/linearGradient>' + open + '/defs>'
            + open + 'polygon points="0,300 ' + line + ' 1000,300" fill="url(#xad-area)"/>'
            + open + 'polyline points="' + line + '" fill="none" stroke="#D9B872" stroke-opacity="0.7" stroke-width="1.5" vector-effect="non-scaling-stroke"/>'
            + open + '/svg>');
        curve.querySelector(".xad-landing-dot").style.display = "block";
    }

    // Affiche l'état correspondant à une progression : courbe dévoilée, point en bout de courbe, texte qui s'efface
    function draw(root, progress) {
        const curve = root.querySelector(".xad-landing-curve");
        const svg = curve.querySelector("svg");
        const content = root.querySelector(".xad-landing-content");
        const shown = reduced ? 1 : 0.15 + 0.85 * progress;
        if (svg && points.length) {
            svg.style.clipPath = "inset(-20px " + (100 - shown * 100) + "% 0 0)";
            const position = shown * (points.length - 1);
            const index = Math.floor(position);
            const next = points[Math.min(index + 1, points.length - 1)];
            const y = points[index][1] + (next[1] - points[index][1]) * (position - index);
            const dot = curve.querySelector(".xad-landing-dot");
            dot.style.left = shown * 100 + "%";
            dot.style.top = y / 3 + "%";
            // La courbe part inclinée vers l'arrière et se redresse en grandissant ; le point est compensé pour rester bien rond
            if (!reduced) {
                const stretch = 1 + 0.45 * progress;
                const tilt = 26 * (1 - clamp(progress / 0.7, 0, 1));
                curve.style.transform = "perspective(900px) rotateX(" + tilt + "deg) scaleY(" + stretch + ")";
                dot.style.transform = "scaleY(" + 1 / stretch + ")";
            }
        }
        // Les mots de la description s'allument un à un au début du défilement, puis tout le texte s'efface
        const words = content.querySelectorAll(".xad-word");
        words.forEach(function (word, index) {
            const start = 0.45 * index / Math.max(words.length, 1);
            word.style.opacity = 0.32 + 0.68 * clamp((progress - start) / 0.08, 0, 1);
        });
        content.style.opacity = 1 - clamp((progress - 0.62) / 0.33, 0, 1);
        if (!reduced) { content.style.transform = "translateY(" + (-70 * progress) + "px)"; }
        root.querySelector(".xad-landing-bar").style.transform = "scaleX(" + progress + ")";
    }

    // Fondu de sortie, puis clic sur le bouton caché : Streamlit affiche alors la vraie page d'accueil
    function enter(root) {
        if (leaving) { return; }
        leaving = true;
        root.classList.add("is-leaving");
        window.setTimeout(function () {
            const button = document.querySelector(".st-key-xad_enter button");
            if (button) { button.click(); }
        }, 300);
    }

    // Avance en douceur vers la progression demandée. Quand la page d'entrée a disparu, le script s'arrête.
    function splitWords(root) {
        const text = root.querySelector(".xad-landing-text");
        if (reduced || !text || text.dataset.split) { return; }
        text.dataset.split = "1";
        const words = text.textContent.trim().split(" ");
        text.textContent = "";
        words.forEach(function (word, index) {
            const span = document.createElement("span");
            span.className = "xad-word";
            span.textContent = word + (index === words.length - 1 ? "" : " ");
            text.appendChild(span);
        });
    }
    function step() {
        lastFrame = performance.now();
        const root = document.querySelector(".xad-landing");
        if (!root) {
            if (leaving) { destroy(); }
            return;
        }
        buildCurve(root);
        splitWords(root);
        current = reduced ? target : current + (target - current) * 0.14;
        draw(root, current);
        if (target >= 1 && current > 0.985) { enter(root); }
    }
    function loop() {
        step();
        if (window.__deskathLanding) { frame = window.requestAnimationFrame(loop); }
    }
    // Si le navigateur suspend les images (onglet en arrière-plan), l'état continue quand même d'avancer
    const watchdog = window.setInterval(function () {
        if (performance.now() - lastFrame > 200) { step(); }
    }, 100);

    function advance(amount) {
        if (document.querySelector('[role="dialog"]') || leaving) { return; }
        target = clamp(target + amount, 0, 1);
        window.__deskathProgress = target;
    }

    // Molette et pavé tactile. Une molette classique envoie de grands crans réguliers : on les compte davantage pour qu'elle ne demande pas 20 crans.
    function onWheel(event) {
        const root = document.querySelector(".xad-landing");
        if (!root) { return; }
        event.preventDefault();
        let delta = event.deltaMode === 1 ? event.deltaY * 30 : event.deltaY;
        if (Math.abs(delta) >= 100 && Number.isInteger(delta)) { delta *= 2.5; }
        advance(delta / Number(root.dataset.distance));
    }
    let touchY = null;
    function onTouchStart(event) { touchY = event.touches[0].clientY; }
    function onTouchMove(event) {
        const root = document.querySelector(".xad-landing");
        if (!root) { return; }
        event.preventDefault();
        advance((touchY - event.touches[0].clientY) * 3 / Number(root.dataset.distance));
        touchY = event.touches[0].clientY;
    }
    function onKey(event) {
        if (document.querySelector('[role="dialog"]')) { return; }
        if (["ArrowDown", "PageDown"].includes(event.key) || (event.key === " " && event.target.tagName !== "BUTTON")) {
            event.preventDefault();
            advance(0.34);
        }
        if (["ArrowUp", "PageUp"].includes(event.key)) {
            event.preventDefault();
            advance(-0.34);
        }
    }
    function onClick(event) {
        if (!event.target.closest) { return; }
        if (event.target.closest(".xad-landing-cue")) { advance(1); }
        if (event.target.closest(".xad-landing-howto")) {
            const button = document.querySelector(".st-key-xad_howto button");
            if (button) { button.click(); }
        }
    }

    window.addEventListener("wheel", onWheel, { passive: false });
    window.addEventListener("touchstart", onTouchStart, { passive: true });
    window.addEventListener("touchmove", onTouchMove, { passive: false });
    window.addEventListener("keydown", onKey);
    window.addEventListener("click", onClick);

    // Nettoyage : l'ancien script ne doit pas rester actif si Streamlit le relance, ni après l'entrée dans le site
    function destroy() {
        window.cancelAnimationFrame(frame);
        window.clearInterval(watchdog);
        window.removeEventListener("wheel", onWheel);
        window.removeEventListener("touchstart", onTouchStart);
        window.removeEventListener("touchmove", onTouchMove);
        window.removeEventListener("keydown", onKey);
        window.removeEventListener("click", onClick);
        window.__deskathLanding = null;
    }
    window.__deskathLanding = destroy;
    loop();
})();
</script>
"""


# Script commun à toutes les pages du site : il ajoute ce que le CSS seul ne sait pas faire.
# Il ne s'installe qu'une fois et surveille la page, car Streamlit la réécrit à chaque clic. Tout le contenu reste visible s'il ne se lance pas.
MOTION_SCRIPT = """
<script>
(function () {
    if (window.__deskathMotion) { return; }
    window.__deskathMotion = true;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const easeOut = t => 1 - Math.pow(1 - t, 3);

    // Halo des cartes : il suit la souris
    document.addEventListener("pointermove", function (event) {
        if (!event.target.closest) { return; }
        const card = event.target.closest('.xad-card, [class*="st-key-tile_"]');
        if (!card) { return; }
        const box = card.getBoundingClientRect();
        card.style.setProperty("--mx", (event.clientX - box.left) + "px");
        card.style.setProperty("--my", (event.clientY - box.top) + "px");
    }, { passive: true });

    // Pastille du menu : elle rejoint l'onglet survolé, puis revient sur la page active
    let glide = null;
    let hoveredLink = null;
    function moveGlide(link) {
        if (!glide || !link) { return; }
        const box = link.getBoundingClientRect();
        const parent = glide.parentElement.getBoundingClientRect();
        glide.style.width = box.width + "px";
        glide.style.height = box.height + "px";
        glide.style.transform = "translate(" + (box.left - parent.left) + "px, " + (box.top - parent.top) + "px)";
        glide.style.opacity = "1";
    }
    function activeLink() {
        return document.querySelector('[data-testid="stTopNavLink"][aria-current="page"]');
    }
    function setupGlide() {
        const nav = document.querySelector('[data-testid="stTopNav"]');
        if (!nav || !nav.parentElement) { return; }
        const host = nav.parentElement;
        if (!host.querySelector(".xad-nav-glide")) {
            glide = document.createElement("div");
            glide.className = "xad-nav-glide";
            host.style.position = "relative";
            host.insertBefore(glide, nav);
            host.classList.add("xad-has-glide");
        }
        moveGlide(hoveredLink && hoveredLink.isConnected ? hoveredLink : activeLink());
    }
    document.addEventListener("pointerover", function (event) {
        if (!event.target.closest) { return; }
        const link = event.target.closest('[data-testid="stTopNavLink"]');
        if (link) {
            hoveredLink = link;
            moveGlide(link);
        } else if (!event.target.closest('[data-testid="stTopNav"]')) {
            hoveredLink = null;
            moveGlide(activeLink());
        }
    }, { passive: true });
    window.addEventListener("resize", function () { moveGlide(activeLink()); });

    // Barre de progression et filet du menu, selon le défilement
    const bar = document.createElement("div");
    bar.className = "xad-scroll-bar";
    document.body.appendChild(bar);
    document.addEventListener("scroll", function () {
        const main = document.querySelector('[data-testid="stMain"]');
        if (!main) { return; }
        const room = main.scrollHeight - main.clientHeight;
        bar.style.transform = "scaleX(" + (room > 40 ? main.scrollTop / room : 0) + ")";
        const header = document.querySelector('[data-testid="stHeader"]');
        if (header) { header.classList.toggle("is-scrolled", main.scrollTop > 8); }
    }, { passive: true, capture: true });

    // Chiffres : ils défilent de leur ancienne valeur vers la nouvelle, en gardant le format affiché
    function tween(element, from, to, format, duration) {
        if (reduced) { element.textContent = format(to); return; }
        const start = performance.now();
        function frame(now) {
            const progress = Math.min(1, (now - start) / duration);
            element.textContent = format(from + (to - from) * easeOut(progress));
            if (progress === 1) { return; }
            window.requestAnimationFrame(frame);
        }
        window.requestAnimationFrame(frame);
    }
    function countStats() {
        document.querySelectorAll("[data-count]:not([data-counted])").forEach(function (element) {
            element.dataset.counted = "1";
            tween(element, 0, Number(element.dataset.count), value => String(Math.round(value)), 1100);
        });
    }

    // Cartes : une carte nouvelle apparaît en douceur, une valeur qui change défile. Les cartes déjà là ne bougent pas quand Streamlit réécrit la page.
    const known = new Map();
    function parseNumber(text) {
        const match = text.match(/^([+-]?)([0-9][0-9,]*)(\\.[0-9]+)?(.*)$/);
        if (!match) { return null; }
        return {
            value: Number((match[1] + match[2]).replace(/,/g, "") + (match[3] || "")),
            decimals: match[3] ? match[3].length - 1 : 0,
            signed: match[1] !== "",
            suffix: match[4],
        };
    }
    function formatNumber(parsed, value) {
        const body = Math.abs(value).toLocaleString("en-US", { minimumFractionDigits: parsed.decimals, maximumFractionDigits: parsed.decimals });
        const sign = value < 0 ? "-" : parsed.signed ? "+" : "";
        return sign + body + parsed.suffix;
    }
    function updateCards() {
        const page = location.pathname;
        document.querySelectorAll(".xad-card").forEach(function (card) {
            const name = card.querySelector(".xad-card-name");
            const last = card.querySelector(".xad-card-last");
            if (!name || !last || card.dataset.tracked) { return; }
            card.dataset.tracked = "1";
            const key = page + "|" + name.textContent;
            const before = known.get(key);
            const text = last.textContent;
            if (before === undefined) { card.classList.add("xad-new"); }
            if (before !== undefined && before !== text) {
                const old = parseNumber(before);
                const fresh = parseNumber(text);
                if (old && fresh && old.suffix === fresh.suffix) {
                    tween(last, old.value, fresh.value, value => formatNumber(fresh, value), 500);
                }
            }
            known.set(key, text);
        });
    }

    // Éléments encore sous l'écran : ils arrivent quand on défile jusqu'à eux. Ce qui est déjà visible n'est jamais masqué.
    const seen = new WeakSet();
    const reveal = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (!entry.isIntersecting) { return; }
            entry.target.classList.add("xad-reveal-in");
            entry.target.classList.remove("xad-reveal-wait");
            reveal.unobserve(entry.target);
        });
    }, { threshold: 0.08 });
    function prepareReveal() {
        if (reduced) { return; }
        document.querySelectorAll('[data-testid="stVegaLiteChart"], [data-testid="stDataFrame"], .xad-card, [class*="st-key-tile_"], .xad-stats').forEach(function (element) {
            if (seen.has(element)) { return; }
            seen.add(element);
            if (element.getBoundingClientRect().top > window.innerHeight) {
                element.classList.add("xad-reveal-wait");
                reveal.observe(element);
            }
        });
    }

    // Graphiques : Streamlit remplace tout le dessin à chaque clic. On compare le nouveau dessin au précédent pour rendre le changement fluide :
    // une courbe nouvelle se trace de gauche à droite, une courbe retirée s'efface, celles qui restent glissent vers leur nouvelle position.
    // Le zoom ne remplace pas le dessin : il n'est donc pas concerné.
    const chartMemory = new Map();
    const processedCharts = new WeakSet();
    const NUMBERS = /-?[0-9]*[.]?[0-9]+(?:e-?[0-9]+)?/g;

    // Identité d'une courbe, lue dans sa description : par exemple "Asset: CAC 40; Type: Close"
    function lineKey(path) {
        return (path.getAttribute("aria-label") || "").split(";").map(part => part.trim())
            .filter(part => /^(Asset|Type|Series):/.test(part)).join(";");
    }
    function drawLine(path) {
        path.setAttribute("pathLength", "1");
        path.style.strokeDasharray = "1";
        const animation = path.animate([{ strokeDashoffset: 1 }, { strokeDashoffset: 0 }], { duration: 850, easing: "cubic-bezier(0.23, 1, 0.32, 1)", fill: "both" });
        animation.onfinish = function () {
            animation.cancel();
            path.removeAttribute("pathLength");
            path.style.strokeDasharray = "";
        };
    }
    function morphLine(path, fromPath, toPath) {
        const from = fromPath.match(NUMBERS).map(Number);
        const to = toPath.match(NUMBERS).map(Number);
        const pieces = toPath.split(NUMBERS);
        if (from.length !== to.length) {
            path.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 320, easing: "ease" });
            return;
        }
        const start = performance.now();
        function frame(now) {
            if (!path.isConnected) { return; }
            const progress = Math.min(1, (now - start) / 480);
            const eased = easeOut(progress);
            let built = pieces[0];
            for (let i = 0; i !== to.length; i += 1) {
                built += (from[i] + (to[i] - from[i]) * eased).toFixed(2) + pieces[i + 1];
            }
            path.setAttribute("d", progress === 1 ? toPath : built);
            if (progress !== 1) { window.requestAnimationFrame(frame); }
        }
        path.setAttribute("d", fromPath);
        window.requestAnimationFrame(frame);
    }
    function fadeOutLine(parent, line) {
        const ghost = document.createElementNS("http://www.w3.org/2000/svg", "path");
        ghost.setAttribute("d", line.d);
        ghost.setAttribute("fill", "none");
        ghost.setAttribute("stroke", line.stroke);
        ghost.setAttribute("stroke-width", line.width);
        ghost.setAttribute("aria-hidden", "true");
        parent.appendChild(ghost);
        ghost.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 280, easing: "ease" }).onfinish = () => ghost.remove();
    }
    function updateCharts() {
        if (reduced) { return; }
        document.querySelectorAll('[data-testid="stVegaLiteChart"]').forEach(function (chart, chartIndex) {
            const key = location.pathname + "|" + chartIndex;
            const memory = chartMemory.get(key);
            const svg = chart.querySelector("svg.marks:not(.xad-chart-ghost)");

            // Le temps que le nouveau dessin arrive, l'ancien reste affiché : le graphique ne clignote pas et la page ne saute pas
            if (!svg) {
                if (memory && memory.svg && !chart.querySelector(".xad-chart-ghost")) {
                    chart.style.minHeight = memory.height + "px";
                    memory.svg.classList.add("xad-chart-ghost");
                    chart.appendChild(memory.svg);
                }
                return;
            }
            if (processedCharts.has(svg)) { return; }
            const paths = [...svg.querySelectorAll(".mark-line path")];
            if (!paths.length) { return; }
            processedCharts.add(svg);
            const oldGhost = chart.querySelector(".xad-chart-ghost");
            if (oldGhost) { oldGhost.remove(); }
            chart.style.minHeight = "";

            const lines = new Map();
            paths.forEach(function (path) {
                const id = lineKey(path);
                const toPath = path.getAttribute("d");
                const before = memory && memory.lines.get(id);
                const dashed = (path.getAttribute("stroke-dasharray") || "1,0") !== "1,0";
                if (!before) {
                    if (dashed) { path.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 420, easing: "ease" }); }
                    else { drawLine(path); }
                } else if (before.d !== toPath) {
                    morphLine(path, before.d, toPath);
                }
                lines.set(id, { d: toPath, stroke: path.getAttribute("stroke"), width: path.getAttribute("stroke-width") || "2" });
            });
            if (memory) {
                memory.lines.forEach(function (line, id) {
                    if (!lines.has(id)) { fadeOutLine(paths[0].parentElement, line); }
                });
            }
            svg.querySelectorAll(".role-axis").forEach(function (axis) {
                axis.animate([{ opacity: 0.35 }, { opacity: 1 }], { duration: 320, easing: "ease" });
            });
            chartMemory.set(key, { lines: lines, svg: svg, height: chart.offsetHeight });
        });
    }

    function refresh() {
        setupGlide();
        countStats();
        updateCards();
        updateCharts();
        prepareReveal();
    }
    let pending = false;
    new MutationObserver(function () {
        // Les courbes sont traitées tout de suite, avant que le navigateur n'affiche le nouveau dessin
        updateCharts();
        if (pending) { return; }
        pending = true;
        window.setTimeout(function () { pending = false; refresh(); }, 60);
    }).observe(document.body, { childList: true, subtree: true });
    refresh();
})();
</script>
"""


# Assemble la page d'entrée. La flèche et le bouton sont cliquables, pour ceux qui ne peuvent pas défiler.
def build_landing():
    return (
        f'<section class="xad-landing" data-distance="{LANDING_SCROLL_DISTANCE}">'
        '<div class="xad-landing-curve" aria-hidden="true"><div class="xad-landing-dot"></div></div>'
        '<div class="xad-landing-content">'
        f'<h1 class="xad-landing-title">{BRAND_HTML}</h1>'
        '<div class="xad-landing-signature">by Louis DIGUET--GUYENNE</div>'
        '<p class="xad-landing-text">Follow indices, equities, bonds, commodities, currencies and rates, then compare them side by side in one market monitor.</p>'
        '<button class="xad-landing-howto" type="button">How it works</button>'
        '</div>'
        '<button class="xad-landing-cue" type="button">Scroll to enter'
        '<span class="xad-landing-chevron" aria-hidden="true"></span>'
        '<div class="xad-landing-track"><div class="xad-landing-bar"></div></div>'
        f'</button></section>{LANDING_SCRIPT}'
    )


# Appelée par le bouton caché quand le défilement arrive au bout
def enter_site():
    st.session_state["entered"] = True
    st.session_state["just_entered"] = True


# Page d'entrée : le texte s'affiche tout de suite, la courbe arrive dès que les cours sont téléchargés. Le menu du haut reste caché.
def render_landing():
    st.markdown('<style>[data-testid="stHeader"] { display: none; }</style>', unsafe_allow_html=True)
    st.button("Enter", key="xad_enter", on_click=enter_site)
    st.button("Open how it works", key="xad_howto", on_click=restart_onboarding)
    st.html(build_landing(), unsafe_allow_javascript=True)
    prices = load_home_prices()
    sp500_ticker = NAME_TO_TICKER["S&P 500"]
    if sp500_ticker in prices:
        st.html(build_landing_curve(prices[sp500_ticker]))


# Vraie page d'accueil : une tuile par classe d'actifs, avec le chiffre de son actif de référence sur un an.
def render_home_page():
    prices = load_home_prices()
    just_entered = st.session_state.pop("just_entered", False)

    with st.container(key="home_enter" if just_entered else "home_static"):
        # Grand titre centré, une phrase, puis les chiffres du site : ils sont calculés, pour rester justes quand on ajoute des actifs
        stats = [
            (len(NAME_TO_TICKER), "Instruments"),
            (len(ASSET_UNIVERSE["Equities"]), "Equities"),
            (len(ASSET_UNIVERSE["Currencies"]), "Currency pairs"),
            (len(ASSET_UNIVERSE["Rates"]), "Government yields"),
        ]
        stats_html = "".join(
            f'<div><div class="xad-stat-value" data-count="{value}">{value}</div><div class="xad-stat-label">{label}</div></div>'
            for value, label in stats
        )
        st.markdown(
            '<h1 class="xad-home-title">Six asset classes, one desk</h1>'
            '<p class="xad-home-text">Follow every market in one place, compare them side by side and track your own portfolio.</p>'
            f'<div class="xad-stats">{stats_html}</div>',
            unsafe_allow_html=True,
        )

        # Deux lignes de trois tuiles. Chaque tuile mène à sa page.
        categories = list(HOME_TILES)
        for row_start in range(0, len(categories), 3):
            for column, category in zip(st.columns(3), categories[row_start:row_start + 3]):
                benchmark, description = HOME_TILES[category]
                ticker = NAME_TO_TICKER[benchmark]
                is_rate = category in RATE_CATEGORIES
                figures = ""
                if ticker in prices and prices[ticker].notna().any():
                    last, change, _ = compute_metrics(prices[ticker], is_rate)
                    decimals = 4 if category == "Currencies" else 2
                    last_text, change_text = format_last_and_change(last, change, is_rate, decimals)
                    tone = "xad-up" if change > 0 else "xad-down" if change < 0 else "xad-flat"
                    figures = (
                        f'<div class="xad-card-name">{html.escape(benchmark)}</div>'
                        f'<div class="xad-card-last">{last_text}</div>'
                        f'<div class="xad-card-row"><span>12-month change</span><span class="{tone}">{change_text}</span></div>'
                    )
                with column.container(key=f"tile_{category}"):
                    st.markdown(
                        f'<div class="xad-tile-class">{category}</div>'
                        f'<div class="xad-tile-text">{description}</div>{figures}',
                        unsafe_allow_html=True,
                    )
                    st.page_link(CLASS_PAGES[category], label=f"Open {category}", icon=":material/arrow_forward:")


# Choix de la période, commun à toutes les pages : deux calendriers et une vérification. Renvoie None si les dates sont incohérentes.
def choose_period(prefix):
    start_key, end_key = f"start_{prefix}", f"end_{prefix}"
    saved = st.session_state.get("saved_periods", {}).get(prefix)
    st.session_state.setdefault(start_key, saved[0] if saved else date.today() - timedelta(days=365))
    st.session_state.setdefault(end_key, saved[1] if saved else date.today())

    date_col1, date_col2 = st.columns(2)
    start_date = date_col1.date_input("Start date", max_value=date.today(), format="DD/MM/YYYY", key=start_key)
    end_date = date_col2.date_input("End date", max_value=date.today(), format="DD/MM/YYYY", key=end_key)
    st.session_state.setdefault("saved_periods", {})[prefix] = (start_date, end_date)

    if start_date >= end_date:
        st.error("The start date must be earlier than the end date.")
        return None
    return start_date, end_date


# Boutons "Select all" et "Clear" : ils remplissent ou vident la sélection d'une page
def set_selection(store_key, names):
    st.session_state[store_key] = list(names)


# Page générique d'une classe d'actifs : la même fonction sert aux 6 pages, seule la catégorie change.
# Pas de bouton de validation : chaque clic relance la page et met le graphique à jour.
def render_class_page(category):
    assets = list(ASSET_UNIVERSE[category])
    is_rate = category in RATE_CATEGORIES
    store_key = f"selected_{category}"
    st.session_state.setdefault(store_key, [])
    normalize_key = f"normalize_{category}"
    memory = st.session_state.setdefault("page_memory", {}).setdefault(category, {"normalize": True})

    st.header(category)

    # 1. La période
    period = choose_period(category)

    # 2. Les instruments : un clic ajoute au graphique, un second clic retire. Les longues listes se déplient par groupe.
    if category in ASSET_GROUPS:
        for group, group_assets in ASSET_GROUPS[category].items():
            with st.expander(group):
                render_pills(store_key, group, list(group_assets), False)
        selected_col, clear_col = st.columns([9, 1], vertical_alignment="bottom")
        with selected_col:
            render_selected_row(store_key)
    else:
        pills_col, select_col, clear_col = st.columns([8, 1, 1], vertical_alignment="bottom")
        with pills_col:
            render_pills(store_key, "Instruments", assets, True)
        select_col.button("Select all", type="tertiary", on_click=set_selection, args=(store_key, assets), key=f"all_{category}", width="stretch")
    clear_col.button("Clear", type="tertiary", on_click=set_selection, args=(store_key, []), key=f"clear_{category}", width="stretch")
    names = st.session_state[store_key]

    # 3. L'échelle. Pour les taux, la base 100 n'a pas de sens : on affiche directement les rendements en %.
    if is_rate:
        normalize = False
        st.caption("Yields are displayed in % — base 100 is not meaningful for interest rates.")
    else:
        st.session_state.setdefault(normalize_key, memory["normalize"])
        normalize = st.checkbox("Normalise prices to base 100", key=normalize_key)
        memory["normalize"] = normalize

    if period is None:
        return
    start_date, end_date = period
    if not names:
        st.info("Click one or several instruments to draw the chart.")
        return

    # L'ordre de la liste complète, pour que les courbes et les cartes gardent toujours la même place
    selected_names = [name for name in assets if name in names]
    close_prices = load_prices(selected_names, start_date, end_date)
    if close_prices is None:
        return

    # Base 100 (facteur = 100 / premier cours valide) ou valeurs brutes (facteur = 1)
    if normalize:
        scale = 100 / close_prices.bfill().iloc[0]
        axis_label = "Normalised value (base 100)"
    else:
        scale = 1
        axis_label = "Yield (%)" if is_rate else "Price"
    display_prices = close_prices * scale

    st.subheader("Yields" if is_rate else "Performance")
    st.caption(f"{start_date:%d/%m/%Y} → {end_date:%d/%m/%Y} · {len(close_prices)} daily observations")

    # Cartes d'indicateurs, toujours sur les cours bruts (même si le graphique est en base 100). Les devises ont besoin de 4 décimales.
    render_metric_cards(close_prices, is_rate, 4 if category == "Currencies" else 2, assets)

    # On réserve la place du graphique (st.container) mais on le dessine après les cases : il doit connaître leur valeur.
    chart_area = st.container()

    # Moyennes mobiles, sous le graphique : la fenêtre n'apparaît que si la case est cochée.
    ma_row = st.container(horizontal=True, vertical_alignment="center")
    show_short_ma = ma_row.checkbox("Short MA", key=f"short_ma_{category}")
    if show_short_ma:
        short_window = ma_row.number_input(
            "Short MA window", min_value=2, max_value=100, value=20, step=1, width=120,
            key=f"short_win_{category}", label_visibility="collapsed",
        )
    show_long_ma = ma_row.checkbox("Long MA", key=f"long_ma_{category}")
    if show_long_ma:
        long_window = ma_row.number_input(
            "Long MA window", min_value=3, max_value=250, value=50, step=1, width=120,
            key=f"long_win_{category}", label_visibility="collapsed",
        )

    # Calcul des MA sur les prix bruts puis même facteur que les prix. On prévient si la fenêtre est incohérente.
    series_by_type = {"Close": display_prices}
    n_obs = len(close_prices)
    if show_short_ma and show_long_ma and short_window >= long_window:
        st.warning("The short MA window should be smaller than the long one.")
    for show, window in [(show_short_ma, short_window if show_short_ma else None),
                         (show_long_ma, long_window if show_long_ma else None)]:
        if show:
            if window > n_obs:
                st.warning(f"The {window}-day window is longer than the period ({n_obs} days).")
            series_by_type[f"MA {window}"] = close_prices.rolling(window=int(window)).mean() * scale

    with chart_area:
        plot_chart(series_by_type, axis_label, is_rate, assets)

    # Comparateur : une case par actif analysé. Cocher l'ajoute, décocher le retire (via la fonction toggle_comparator). Les taux n'y vont pas.
    if is_rate:
        return
    st.markdown('<div class="xad-label">Add to comparator</div>', unsafe_allow_html=True)
    comparator_row = st.container(horizontal=True)  # chaque case prend la largeur de son texte et passe à la ligne si besoin
    for name in display_prices.columns:
        checkbox_key = f"cmp_{category}_{name}"
        comparator_row.checkbox(
            name,
            value=name in st.session_state["comparator"],
            key=checkbox_key,
            on_change=toggle_comparator,
            args=(name, checkbox_key),
        )


# Page Comparateur : réunit des actifs de toutes les classes sur une période commune.
# Seuls les titres des classes d'actifs sont affichés : un clic sur la flèche déplie leurs instruments, pour que la page reste lisible quand la liste s'allonge.
def render_comparator_page():
    title_col, clear_col = st.columns([9, 1], vertical_alignment="bottom")
    title_col.header("Comparator")
    clear_col.button("Clear all", on_click=set_selection, args=("comparator", []), width="stretch")

    period = choose_period("comparator")

    # Les taux n'y figurent pas : un rendement en % ne se compare pas à des prix en base 100.
    categories = [category for category in ASSET_UNIVERSE if category not in RATE_CATEGORIES]
    for category in categories:
        with st.expander(category):
            if category in ASSET_GROUPS:
                for group, group_assets in ASSET_GROUPS[category].items():
                    render_pills("comparator", group, list(group_assets), True)
            else:
                render_pills("comparator", category, list(ASSET_UNIVERSE[category]), False)
    render_selected_row("comparator")

    comparator = st.session_state["comparator"]
    if period is None:
        return
    start_date, end_date = period
    if not comparator:
        st.info("Open an asset class and click its instruments to compare them.")
        return

    # L'ordre de la liste complète, pour que les courbes gardent toujours leur couleur
    universe = [name for category in categories for name in ASSET_UNIVERSE[category]]
    selected_names = [name for name in universe if name in comparator]

    st.subheader("Performance (base 100)")
    prices = load_prices(selected_names, start_date, end_date)
    if prices is not None:
        plot_chart({"Close": prices * (100 / prices.bfill().iloc[0])}, "Normalised value (base 100)", universe=universe)


# PORTEFEUILLE — CALCULS

# Cours de clôture bruts. Contrairement aux autres pages, ils ne sont pas ajustés des dividendes :
# ajuster ferait baisser le cours du jour d'achat et ne correspondrait plus au prix réellement payé.
@st.cache_data(ttl=3600, show_spinner=False)
def download_raw_closes(tickers, start, end):
    data = yf.download(tickers, start=start, end=end + timedelta(days=1), interval="1d", auto_adjust=False, progress=False)
    if data.empty:
        return pd.DataFrame()
    close = data["Close"]
    return close.to_frame(name=tickers[0]) if isinstance(close, pd.Series) else close


# Devise de cotation d'un titre : renvoie le code affiché, la vraie devise et le facteur d'unité (les pence valent 0,01 GBP)
def quote_currency(ticker):
    for suffix, currency in QUOTE_CURRENCIES.items():
        if ticker.endswith(suffix):
            return ("GBp", "GBP", 0.01) if currency == "GBp" else (currency, currency, 1.0)
    return "USD", "USD", 1.0


# Ticker Yahoo du taux de change vers la devise de référence (None si le titre est déjà dans cette devise)
def fx_ticker(currency, base):
    return None if currency == base else f"{currency}{base}=X"


# Calcule chaque ligne du portefeuille et son évolution. Tout est converti dans la devise de référence :
# le montant investi au taux de change du jour d'achat, la valeur au taux du jour. Les gains incluent donc l'effet de change.
# Les dividendes reçus ne sont pas comptés.
def compute_portfolio(positions, base, closes):
    closes = closes.sort_index().ffill()
    rows, skipped = [], []
    value_history = pd.Series(0.0, index=closes.index)
    invested_history = pd.Series(0.0, index=closes.index)

    for position_index, position in enumerate(positions):
        ticker = NAME_TO_TICKER[position["name"]]
        label, currency, unit = quote_currency(ticker)
        buy_day = pd.Timestamp(position["date"])
        prices = closes[ticker].dropna() if ticker in closes else pd.Series(dtype=float)
        prices_until_buy = prices.loc[:buy_day]
        if prices_until_buy.empty:
            skipped.append(position["name"])
            continue

        # Taux de change : 1 si le titre est déjà dans la devise de référence
        rate_ticker = fx_ticker(currency, base)
        if rate_ticker is None:
            rates = pd.Series(1.0, index=closes.index)
        elif rate_ticker in closes and closes[rate_ticker].notna().any():
            rates = closes[rate_ticker].bfill()
        else:
            skipped.append(position["name"])
            continue

        # Prix payé : celui saisi, sinon la dernière clôture connue à la date d'achat
        buy_price = position["price"] or float(prices_until_buy.iloc[-1])
        invested = position["quantity"] * buy_price * unit * float(rates.loc[:buy_day].iloc[-1] if not rates.loc[:buy_day].empty else rates.iloc[0])
        last_price = float(prices.iloc[-1])
        value = position["quantity"] * last_price * unit * float(rates.iloc[-1])

        rows.append({
            "index": position_index,
            "Asset": position["name"],
            "Bought on": position["date"],
            "Quantity": position["quantity"],
            "Currency": label,
            "Buy price": buy_price,
            "Last price": last_price,
            "Invested": invested,
            "Value": value,
            "P&L": value - invested,
            "P&L %": (value - invested) / invested if invested else 0.0,
        })

        # Évolution : la ligne ne compte qu'à partir de sa date d'achat
        held = closes.index >= buy_day
        line_value = closes[ticker].reindex(closes.index) * position["quantity"] * unit * rates
        value_history = value_history.add(line_value.where(held, 0.0).fillna(0.0))
        invested_history = invested_history.add(pd.Series(invested, index=closes.index).where(held, 0.0))

    history = pd.DataFrame({"Value": value_history, "Invested": invested_history})
    return rows, history[history["Invested"] > 0], skipped


# PORTEFEUILLE — AFFICHAGE

# Appelée par le bouton "Add to portfolio" : enregistre la ligne et remet la recherche à zéro
def add_position():
    st.session_state.setdefault("portfolio", []).append({
        "name": st.session_state["portfolio_search"],
        "date": st.session_state["portfolio_date"],
        "quantity": st.session_state["portfolio_quantity"],
        "price": st.session_state["portfolio_price"],
    })
    st.session_state.pop("portfolio_backup", None)
    st.session_state["portfolio_search"] = None
    for key in ("portfolio_quantity", "portfolio_price"):
        st.session_state.pop(key, None)


# Appelée par le bouton "Remove selected" : retire les lignes cochées dans le tableau
def remove_positions(rows):
    selected = st.session_state.get("portfolio_table", {}).get("selection", {}).get("rows", [])
    removed = {rows[i]["index"] for i in selected}
    st.session_state["portfolio"] = [p for i, p in enumerate(st.session_state["portfolio"]) if i not in removed]


# Appelée par le bouton "Clear all" : vide le portefeuille en gardant une copie pour pouvoir annuler
def clear_portfolio():
    st.session_state["portfolio_backup"] = st.session_state["portfolio"]
    st.session_state["portfolio"] = []


# Appelée par le bouton "Undo" : remet le portefeuille tel qu'il était
def undo_clear_portfolio():
    st.session_state["portfolio"] = st.session_state.pop("portfolio_backup", [])


# Vert si positif, rouge si négatif
def pnl_color(value):
    return "color: #4ADE80" if value > 0 else "color: #F87171" if value < 0 else ""


# Évolution de la valeur du portefeuille face aux montants investis, avec une bulle au survol
def plot_portfolio_history(history, base):
    data = history.copy()
    data.index.name = "Date"
    data["P&L"] = data["Value"] - data["Invested"]
    data = data.reset_index()
    long_data = data.melt(id_vars="Date", value_vars=["Value", "Invested"], var_name="Series", value_name="Amount")

    nearest = alt.selection_point(nearest=True, on="pointerover", fields=["Date"], empty=False)
    lines = alt.Chart(long_data).mark_line(strokeWidth=2).encode(
        x=alt.X("Date:T", title=None, scale=alt.Scale(nice=False)),
        y=alt.Y("Amount:Q", title=f"Amount ({base})", scale=alt.Scale(zero=False)),
        color=alt.Color("Series:N", title=None, sort=["Value", "Invested"],
                        scale=alt.Scale(domain=["Value", "Invested"], range=["#D9B872", "#64748B"]),
                        legend=alt.Legend(orient="bottom")),
    )
    rules = alt.Chart(data).mark_rule(color="#94A3B8").encode(
        x="Date:T",
        opacity=alt.condition(nearest, alt.value(0.5), alt.value(0)),
        tooltip=[alt.Tooltip("Date:T", format="%d/%m/%Y"), alt.Tooltip("Value:Q", format=",.2f"),
                 alt.Tooltip("Invested:Q", format=",.2f"), alt.Tooltip("P&L:Q", format="+,.2f")],
    ).add_params(nearest)
    chart = (
        alt.layer(lines, rules).properties(height=360)
        .configure(font=CHART_FONT)
        .configure_axis(gridColor="#1E293B", domainColor="#334155", labelColor="#94A3B8", titleColor="#94A3B8")
        .configure_legend(labelColor="#CBD5E1")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, width="stretch")


# Gain ou perte par actif : barres vertes si positif, rouges si négatif, de la plus forte à la plus faible
def plot_pnl_by_asset(table, base):
    data = table.groupby("Asset", as_index=False)["P&L"].sum().sort_values("P&L", ascending=False)
    chart = (
        alt.Chart(data).mark_bar().encode(
            x=alt.X("P&L:Q", title=f"P&L ({base})"),
            y=alt.Y("Asset:N", title=None, sort=list(data["Asset"]), axis=alt.Axis(labelLimit=0)),
            color=alt.condition("datum['P&L'] >= 0", alt.value("#4ADE80"), alt.value("#F87171")),
            tooltip=[alt.Tooltip("Asset:N"), alt.Tooltip("P&L:Q", format="+,.2f")],
        ).properties(height=max(120, 34 * len(data)))
        .configure(font=CHART_FONT)
        .configure_axis(gridColor="#1E293B", domainColor="#334155", labelColor="#94A3B8", titleColor="#94A3B8")
        .configure_view(strokeWidth=0)
    )
    st.altair_chart(chart, width="stretch")


# Page Portefeuille : une barre de recherche, les questions sur l'achat, puis le tableau, les chiffres et les graphiques.
def render_portfolio_page():
    st.header("Portfolio")
    st.session_state.setdefault("portfolio", [])

    search_col, base_col = st.columns([4, 1], vertical_alignment="bottom")
    investable = list(ASSET_UNIVERSE["Equities"]) + list(ASSET_UNIVERSE["Bonds"])
    name = search_col.selectbox(
        "Add a position", investable, index=None, placeholder="Search a company, e.g. TotalEnergies", key="portfolio_search",
    )
    # Streamlit oublie un menu quand on quitte la page : on garde la devise choisie à part pour la restaurer
    st.session_state.setdefault("portfolio_base", st.session_state.get("portfolio_base_saved", "EUR"))
    base = base_col.selectbox("Portfolio currency", PORTFOLIO_CURRENCIES, key="portfolio_base")
    st.session_state["portfolio_base_saved"] = base

    # Une fois l'actif choisi, on demande la date d'achat, la quantité et, si on le connaît, le prix payé
    if name:
        label, _, _ = quote_currency(NAME_TO_TICKER[name])
        with st.form("portfolio_form"):
            date_col, quantity_col, price_col = st.columns(3)
            date_col.date_input("Purchase date", value=date.today() - timedelta(days=365), max_value=date.today(),
                                format="DD/MM/YYYY", key="portfolio_date")
            quantity_col.number_input("Quantity", min_value=0.0001, value=10.0, step=1.0, key="portfolio_quantity")
            price_col.number_input(f"Price paid per unit in {label} (0 = close of that day)", min_value=0.0, value=0.0, step=1.0,
                                   key="portfolio_price")
            st.form_submit_button(f"Add {name} to portfolio", type="primary", on_click=add_position)

    positions = st.session_state["portfolio"]
    if not positions:
        # Après un "Clear all", on laisse la possibilité d'annuler : le portefeuille n'est enregistré nulle part ailleurs
        if st.session_state.get("portfolio_backup"):
            st.info("Portfolio cleared.")
            st.button("Undo", on_click=undo_clear_portfolio)
        else:
            st.info("Search for a company above to add your first position.")
        return

    # Téléchargement des cours et des taux de change nécessaires, depuis la plus ancienne date d'achat
    tickers = {NAME_TO_TICKER[position["name"]] for position in positions}
    for ticker in list(tickers):
        rate_ticker = fx_ticker(quote_currency(ticker)[1], base)
        if rate_ticker:
            tickers.add(rate_ticker)
    start = min(position["date"] for position in positions) - timedelta(days=10)
    with st.spinner("Downloading market data..."):
        try:
            closes = download_raw_closes(sorted(tickers), start, date.today())
        except Exception as error:
            st.error(f"The market data could not be downloaded: {error}")
            return
    st.session_state["last_updated"] = datetime.now()
    if closes.empty:
        st.warning("No quotations were returned for these positions.")
        return

    rows, history, skipped = compute_portfolio(positions, base, closes)
    if skipped:
        st.warning(f"No price available at the purchase date for: {', '.join(skipped)}. Excluded from the totals.")
    if not rows:
        return

    # Chiffres clés, en vert ou en rouge selon le signe
    table = pd.DataFrame(rows)
    invested, value = table["Invested"].sum(), table["Value"].sum()
    pnl = value - invested
    tone = "xad-up" if pnl > 0 else "xad-down" if pnl < 0 else "xad-flat"
    by_asset = table.groupby("Asset")["P&L"].sum()
    cards = [
        ("Portfolio value", f"{value:,.2f} {base}", "", ""),
        ("Invested", f"{invested:,.2f} {base}", "", ""),
        ("Total P&L", f"{pnl:+,.2f} {base}", tone, f"{pnl / invested:+.2%}" if invested else ""),
        ("Best position", html.escape(by_asset.idxmax()), "xad-up" if by_asset.max() > 0 else "xad-down", f"{by_asset.max():+,.2f} {base}"),
        ("Worst position", html.escape(by_asset.idxmin()), "xad-up" if by_asset.min() > 0 else "xad-down", f"{by_asset.min():+,.2f} {base}"),
    ]
    items = "".join(
        f'<div class="xad-card"><div class="xad-card-name">{title}</div>'
        f'<div class="xad-card-last {card_tone if title == "Total P&L" else ""}">{main}</div>'
        f'<div class="xad-card-row"><span class="{card_tone}">{detail}</span></div></div>'
        for title, main, card_tone, detail in cards
    )
    st.markdown(f'<div class="xad-cards">{items}</div>', unsafe_allow_html=True)

    if len(history) >= 2:
        st.subheader("Portfolio value")
        plot_portfolio_history(history, base)

    st.subheader("Positions")
    display = table.drop(columns="index")
    styled = display.style.format({
        "Bought on": lambda day: f"{day:%d/%m/%Y}", "Quantity": "{:,.4g}", "Buy price": "{:,.2f}", "Last price": "{:,.2f}",
        "Invested": "{:,.2f}", "Value": "{:,.2f}", "P&L": "{:+,.2f}", "P&L %": "{:+.2%}",
    }).map(pnl_color, subset=["P&L", "P&L %"])
    st.dataframe(styled, hide_index=True, width="stretch", key="portfolio_table", on_select="rerun", selection_mode="multi-row")
    buttons = st.container(horizontal=True)
    buttons.button("Remove selected", on_click=remove_positions, args=(rows,))
    buttons.button("Clear all", on_click=clear_portfolio)
    st.caption(f"Amounts in {base}, converted at each day's exchange rate. Prices exclude dividends. Your portfolio is kept until you close or reload the page.")

    st.subheader("P&L by asset")
    plot_pnl_by_asset(table, base)


# NEWS — DONNÉES

# Trouve la section d'un article d'après son titre. Sans mot reconnu : section par défaut du flux (None : article hors sujet, écarté).
def classify_news(title, default_section):
    lowered = title.lower().replace("’", "'")
    for section, pattern in NEWS_KEYWORDS.items():
        if re.search(pattern, lowered):
            return section
    return default_section


# Lit la date d'un article et la ramène à l'heure de Paris. Les flux utilisent deux formats ; une date sans fuseau est lue en heure universelle.
def parse_news_date(text):
    text = (text or "").strip()
    try:
        moment = parsedate_to_datetime(text)
    except (TypeError, ValueError):
        try:
            moment = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo("UTC"))
    return moment.astimezone(ZoneInfo("Europe/Paris"))


# Lit un flux : renvoie ses articles, ou None si le site ne répond pas. Pas de commande Streamlit ici : cette fonction tourne en parallèle.
def fetch_news_feed(feed):
    source, url, default_section = feed
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh) DESKatH student project"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            root = ElementTree.fromstring(response.read())
    except (OSError, ElementTree.ParseError):
        return source, None

    oldest = datetime.now(ZoneInfo("Europe/Paris")) - timedelta(days=NEWS_MAX_AGE_DAYS)
    articles = []
    for item in root.iter("item"):
        title = html.unescape(item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = parse_news_date(item.findtext("pubDate"))
        # Google News ajoute " - Nom du site" à la fin du titre : on le retire
        publisher = item.findtext("source")
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3]
        section = classify_news(title, default_section)
        if title and link.startswith("https://") and published and published >= oldest and section:
            articles.append({"title": title, "link": link, "date": published, "section": section, "source": source})
    return source, sorted(articles, key=lambda article: article["date"], reverse=True)[:NEWS_MAX_PER_FEED]


# Les mots significatifs d'un titre, pour reconnaître une même information chez plusieurs sources
def title_words(title):
    return {word for word in re.findall(r"[a-zà-ÿ0-9]+", title.lower()) if len(word) > 3}


# Regroupe les titres quasi identiques : un article garde sa place, et les autres sources qui en parlent lui sont rattachées.
def group_same_stories(articles):
    stories = []
    for article in articles:
        words = title_words(article["title"])
        twin = None
        for story in stories:
            shared = len(words & story["words"])
            total = len(words | story["words"])
            if total and shared / total >= NEWS_SAME_STORY_SIMILARITY and abs(story["date"] - article["date"]) <= timedelta(days=2):
                twin = story
                break
        if twin is None:
            stories.append({**article, "words": words, "also": []})
        elif article["source"] != twin["source"] and article["source"] not in twin["also"]:
            twin["also"].append(article["source"])
    return stories


# Lit tous les flux en même temps, retire les doublons, regroupe les mêmes informations. Résultat gardé 5 minutes.
@st.cache_data(ttl=300, show_spinner=False)
def load_news():
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(fetch_news_feed, NEWS_FEEDS))

    answered = {source for source, articles in results if articles is not None}
    failed = sorted({source for source, articles in results if articles is None} - answered)
    unique = {}
    for _, articles in results:
        for article in articles or []:
            unique.setdefault(article["link"], article)
    newest_first = sorted(unique.values(), key=lambda article: article["date"], reverse=True)
    return group_same_stories(newest_first), failed, datetime.now()


# Une ligne d'article. Les textes viennent de sites extérieurs : html.escape les rend inoffensifs. Le lien s'ouvre dans un nouvel onglet.
def news_row_html(article):
    others = f" +{len(article['also'])}" if article["also"] else ""
    all_sources = ", ".join([article["source"], *article["also"]])
    return (
        f'<a class="xad-news-row" href="{html.escape(article["link"], quote=True)}" target="_blank" rel="noopener noreferrer">'
        f'<span class="xad-news-time">{article["date"]:%H:%M}</span>'
        f'<span class="xad-news-section">{article["section"]}</span>'
        f'<span class="xad-news-title">{html.escape(article["title"])}</span>'
        f'<span class="xad-news-source" title="{html.escape(all_sources, quote=True)}">{html.escape(article["source"])}{others}</span>'
        '</a>'
    )


# NEWS — PAGE

# Page News : un filtre par section et par source, puis les articles regroupés par jour, du plus récent au plus ancien.
def render_news_page():
    st.header("News")
    with st.spinner("Loading the latest headlines..."):
        articles, failed, fetched_at = load_news()
    st.session_state["last_updated"] = fetched_at

    if failed:
        st.warning(f"Temporarily unavailable: {', '.join(failed)}.")
    if not articles:
        st.error("No headlines could be loaded. Please check your connection and try again.")
        return

    # Streamlit oublie les boutons d'une page quittée : on garde les filtres à part pour les restaurer
    memory = st.session_state.setdefault("news_memory", {"section": "All", "sources": []})
    st.session_state.setdefault("news_section", memory["section"])
    section = st.pills("Section", NEWS_SECTIONS, key="news_section") or "All"
    memory["section"] = section

    # Beaucoup de sources : elles sont repliées, pour que la page reste lisible
    sources = sorted({article["source"] for article in articles}, key=str.lower)
    st.session_state.setdefault("news_sources", [name for name in memory["sources"] if name in sources])
    with st.expander(f"Sources ({len(sources)})"):
        chosen_sources = st.pills("Source", sources, selection_mode="multi", key="news_sources", label_visibility="collapsed") or []
    memory["sources"] = chosen_sources

    shown = [
        article for article in articles
        if (section == "All" or article["section"] == section)
        and (not chosen_sources or article["source"] in chosen_sources or set(chosen_sources) & set(article["also"]))
    ][:NEWS_MAX_ARTICLES]
    if not shown:
        st.info("No headlines match these filters right now.")
        return

    # Regroupement par jour : "Today", "Yesterday", puis la date
    today = datetime.now(ZoneInfo("Europe/Paris")).date()
    blocks, current_day = [], None
    for article in shown:
        day = article["date"].date()
        if day != current_day:
            current_day = day
            label = "Today" if day == today else "Yesterday" if day == today - timedelta(days=1) else f"{day:%d/%m/%Y}"
            blocks.append(f'<div class="xad-news-day">{label}</div>')
        blocks.append(news_row_html(article))
    st.markdown(f'<div class="xad-news-list" data-filter="{section}">{"".join(blocks)}</div>', unsafe_allow_html=True)
    st.caption(f"Headlines from {len(sources)} sources through public RSS feeds, sorted by section automatically from their titles. \"+2\" means two more sources report the same story; hover to see them. Articles open on the publisher's site. Times are Paris time.")


# CONFIGURATION DE LA PAGE ET EN-TÊTE COMMUN

st.set_page_config(page_title="DESKatH", page_icon="📈", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# Mémoire de l'appli : comparateur vide et visite guidée à afficher, au premier lancement uniquement.
if "comparator" not in st.session_state:
    st.session_state["comparator"] = []
if "show_onboarding" not in st.session_state:
    st.session_state["show_onboarding"] = True
    st.session_state["onboarding_step"] = 0


# NAVIGATION — barre en haut de la page

# Accueil + une page par classe d'actifs + le Comparateur + le Portefeuille + les News. c=category fige la catégorie de chaque page (sinon les 6 afficheraient "Rates").
CLASS_PAGES = {
    category: st.Page(
        lambda c=category: render_class_page(c),
        title=category,
        icon=PAGE_ICONS[category],
        url_path=category.lower(),
    )
    for category in ASSET_UNIVERSE
}
home_page = st.Page(render_home_page, title="Home", icon=":material/home:", default=True)
comparator_page = st.Page(render_comparator_page, title="Comparator", icon=":material/compare_arrows:", url_path="comparator")
portfolio_page = st.Page(render_portfolio_page, title="Portfolio", icon=":material/account_balance_wallet:", url_path="portfolio")
news_page = st.Page(render_news_page, title="News", icon=":material/newspaper:", url_path="news")
all_pages = [home_page, *CLASS_PAGES.values(), comparator_page, portfolio_page, news_page]

# À l'ouverture du site, on reste sur la page d'entrée tant que le visiteur n'a pas défilé jusqu'au bout. Elle n'est pas dans le menu : on n'y revient pas.
entered = st.session_state.get("entered", False)
current_page = st.navigation(all_pages, position="top" if entered else "hidden")
is_home = current_page.url_path == ""

# La visite s'ouvre à la première ouverture du site, sur la page d'entrée, ou dès qu'on clique sur "How it works".
# On remet le drapeau à False tout de suite : fermer la fenêtre avec la croix ne la fait pas revenir.
if st.session_state["show_onboarding"]:
    st.session_state["show_onboarding"] = False
    show_onboarding()

if not entered:
    render_landing()
    st.stop()

# Nom du site, toujours visible à gauche de la barre du haut
st.markdown(f'<div class="xad-brand">{BRAND_HTML}</div>', unsafe_allow_html=True)

# Animations communes à toutes les pages
with st.container(key="xad_motion"):
    st.html(MOTION_SCRIPT, unsafe_allow_javascript=True)

# Hors accueil, "Last updated" en haut de page (rempli après la page, cf. plus bas)
last_updated_slot = st.empty() if not is_home else None

current_page.run()

# Sur toutes les pages, le bouton pour revoir la visite est en bas
st.space("medium")
st.container(horizontal_alignment="center").button("How it works", type="tertiary", on_click=restart_onboarding)


# "LAST UPDATED" ET PIED DE PAGE (après la page, pour afficher l'heure du téléchargement qui vient d'avoir lieu)

if last_updated_slot is not None:
    last_updated = st.session_state.get("last_updated")
    last_updated_text = f"Last updated {last_updated:%d/%m/%Y %H:%M}" if last_updated else "No data downloaded yet"
    last_updated_slot.markdown(f'<div class="xad-meta">{last_updated_text}</div>', unsafe_allow_html=True)

st.markdown(FOOTER_HTML, unsafe_allow_html=True)
