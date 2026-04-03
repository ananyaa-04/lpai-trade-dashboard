"""
LPAI Land Ports Trade Dashboard  — v2
=======================================
Data sourced from:
  • https://www.lpai.gov.in  (aggregate trade / cargo / passenger figures)
  • DGCIS commodity-level exports & imports Excel files

Folder layout expected:
    app.py
    data/
        export_2024.xlsx
        export_2025.xlsx
        import_2024.xlsx
        import_2025.xlsx

Each file columns:
    Commodity | Country of Destination / Country of Origin | Port | Unit | QTY | <Value column>

Run:
    pip install dash plotly pandas openpyxl
    python app.py  →  http://127.0.0.1:8050
"""

import os
import glob
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import dash
from dash import dcc, html, dash_table, Input, Output, callback_context

# ── Colours ───────────────────────────────────────────────────────────────────
C_BLUE   = "#2563eb"
C_GREEN  = "#16a34a"
C_ORANGE = "#ea580c"
C_RED    = "#dc2626"
C_PURPLE = "#7c3aed"
C_TEAL   = "#0d9488"
C_YELLOW = "#d97706"
C_GRAY   = "#6b7280"
PALETTE  = [C_BLUE,C_TEAL,C_GREEN,C_ORANGE,C_PURPLE,
            C_RED,C_YELLOW,C_GRAY,"#0891b2","#be185d",
            "#065f46","#92400e","#1e3a5f"]

BG_PAGE  = "#f8fafc"
BG_CARD  = "#ffffff"
BG_PANEL = "#f1f5f9"
BORDER   = "#e2e8f0"
TEXT_PRI = "#0f172a"
TEXT_SEC = "#475569"
TEXT_MUT = "#94a3b8"

# ── Port name normalisation ───────────────────────────────────────────────────
PORT_NAME_MAP = {
    # Attari
    "ATTARI": "Attari", "ATTARI LAND": "Attari", "ATT": "Attari",
    # Petrapole
    "PETRAPOLE": "Petrapole", "PETRAPOLE LAND": "Petrapole", "PET": "Petrapole",
    # Agartala
    "AGARTALA": "Agartala", "AGARTALA LAND": "Agartala", "AGA": "Agartala",
    # Dawki
    "DAWKI": "Dawki", "DAWKI LAND": "Dawki", "DAW": "Dawki",
    # Raxaul
    "RAXAUL": "Raxaul", "RAXAUL LAND": "Raxaul", "RAX": "Raxaul",
    # Rupaidiha
    "RUPAIDIHA": "Rupaidiha", "RUPAIDIHA LAND": "Rupaidiha", "RUP": "Rupaidiha",
    # Jogbani
    "JOGBANI": "Jogbani", "JOGBANI LAND": "Jogbani", "JOG": "Jogbani",
    # Moreh
    "MOREH": "Moreh", "MOREH LAND": "Moreh", "MOR": "Moreh",
    # Sutarkandi
    "SUTARKANDI": "Sutarkandi", "SUTARKANDI LAND": "Sutarkandi", "SUT": "Sutarkandi",
    # Srimantapur
    "SRIMANTAPUR": "Srimantapur", "SRIMANTAPUR LAND": "Srimantapur", "SRI": "Srimantapur",
    # Dera Baba Nanak
    "DERA BABA NANAK": "Dera Baba Nanak", "DERA BABA NANAK LAND": "Dera Baba Nanak", "DBN": "Dera Baba Nanak",
    # Sabroom
    "SABROOM": "Sabroom", "SABROOM LAND": "Sabroom", "SAB": "Sabroom",
    # Darranga
    "DARRANGA": "Darranga", "DARRANGA (RANGIA)": "Darranga",
    "DARRANGA LAND": "Darranga", "DAR": "Darranga",
}

def normalize_port(raw):
    return PORT_NAME_MAP.get(str(raw).strip().upper(), str(raw).strip())

# ── Commodity data loader ─────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def _value_col(df):
    """Find whichever column holds the USD trade value."""
    for c in df.columns:
        low = str(c).lower()
        if "value" in low and ("$" in low or "usd" in low or "us" in low):
            return c
    # fallback: last numeric-ish column
    for c in reversed(df.columns):
        if df[c].dtype in [float, int] or pd.api.types.is_numeric_dtype(df[c]):
            return c
    return df.columns[-1]

def _country_col(df):
    """Find the country column (destination or origin)."""
    for c in df.columns:
        low = str(c).lower()
        if "country" in low or "destination" in low or "origin" in low:
            return c
    return None

def load_commodity_files():
    """
    Load all export_YYYY.xlsx / import_YYYY.xlsx from data/ folder.
    Returns a DataFrame with columns:
        direction, year, commodity, country, port, unit, qty, value_usd
    """
    rows = []
    pattern = os.path.join(DATA_DIR, "*.xlsx")
    files = glob.glob(pattern)

    if not files:
        # Return empty frame with correct schema so app still runs
        return pd.DataFrame(columns=[
            "direction","year","commodity","country","port","unit","qty","value_usd"
        ])

    for fpath in files:
        fname = os.path.basename(fpath).lower().replace(".xlsx","")
        # determine direction & year from filename  e.g. export_2024
        parts = fname.split("_")
        if len(parts) < 2:
            continue
        direction = parts[0]          # "export" or "import"
        year_str  = parts[1]          # "2024"

        try:
            raw = pd.read_excel(fpath, dtype=str)
        except Exception as e:
            print(f"[WARN] Could not read {fpath}: {e}")
            continue

        # Strip completely empty rows / header-repeat rows
        raw = raw.dropna(how="all")

        # Identify key columns
        country_col = _country_col(raw)
        value_col   = _value_col(raw)

        # Normalise column names we expect
        col_map = {}
        for c in raw.columns:
            low = str(c).lower()
            if "commodity" in low:             col_map[c] = "commodity"
            elif c == country_col:             col_map[c] = "country"
            elif "port" in low:                col_map[c] = "port"
            elif "unit" in low:                col_map[c] = "unit"
            elif low in ("qty","quantity"):    col_map[c] = "qty"
            elif c == value_col:               col_map[c] = "value_usd"

        raw = raw.rename(columns=col_map)

        required = {"commodity","country","port","value_usd"}
        missing  = required - set(raw.columns)
        if missing:
            print(f"[WARN] {fname}: missing columns {missing}, skipping")
            continue

        for col in ("unit","qty"):
            if col not in raw.columns:
                raw[col] = None

        sub = raw[["commodity","country","port","unit","qty","value_usd"]].copy()
        sub["direction"] = direction
        sub["year"]      = year_str
        rows.append(sub)

    if not rows:
        return pd.DataFrame(columns=[
            "direction","year","commodity","country","port","unit","qty","value_usd"
        ])

    df = pd.concat(rows, ignore_index=True)

    # Normalise ports & clean numerics
    df["port"]      = df["port"].apply(normalize_port)
    df["value_usd"] = pd.to_numeric(df["value_usd"], errors="coerce").fillna(0)
    df["qty"]       = pd.to_numeric(df["qty"],       errors="coerce").fillna(0)
    df["commodity"] = df["commodity"].str.strip().str.title()
    df["country"]   = df["country"].str.strip().str.title()
    df["year"]      = df["year"].astype(str)

    # Drop rows where value is 0 AND qty is 0 (usually truly empty)
    df = df[~((df["value_usd"] == 0) & (df["qty"] == 0))]

    return df

COMM_DF = load_commodity_files()
COMM_AVAILABLE = len(COMM_DF) > 0

# Derived option lists for commodity sections
if COMM_AVAILABLE:
    COMM_PORTS   = sorted(COMM_DF["port"].unique().tolist())
    COMM_YEARS   = sorted(COMM_DF["year"].unique().tolist())
    COMM_DIRS    = sorted(COMM_DF["direction"].unique().tolist())
    TOP_COMMS    = (COMM_DF.groupby("commodity")["value_usd"]
                   .sum().nlargest(50).index.tolist())
else:
    COMM_PORTS = COMM_YEARS = COMM_DIRS = TOP_COMMS = []

# ── ALL PORT META ─────────────────────────────────────────────────────────────
PORTS_META = {
    "Attari": {
        "country":"Pakistan","state":"Punjab","border":"India-Pakistan",
        "area":"120 acres","distance":"28 km from Amritsar",
        "note":"Only permissible land route for India-Pakistan trade. Also serves Afghanistan imports.",
        "exports":["Soyabean","Chicken Feed","Vegetables","Red Chilies","Plastic Dana","Plastic Yarn"],
        "imports":["Dry Fruits","Dry Dates","Gypsum","Cement","Glass","Rock Salt","Herbs"],
        "facilities":["Custom Processing Hall","Immigration Clearance Hall","Cargo & Passenger Terminal",
                      "Export & Import Warehouse","Foreign Currency Exchange","Cold Storage",
                      "Quarantine Block","Port Health Unit","Parking Facility","Security & Surveillance",
                      "Weighbridge","Electric Sub Station","Cafeteria","Rummaging Pits","Jatha Sheds"],
        "equipment":["Pay loader","Hydra crane"],
    },
    "Petrapole": {
        "country":"Bangladesh","state":"West Bengal","border":"India-Bangladesh",
        "area":"N/A","distance":"80 km from Kolkata",
        "note":"Largest land port in South Asia. ~30% of India-Bangladesh land trade passes through here.",
        "exports":["Cotton Fabric","Chassis","Raw Cotton","Steel/Iron","Chemicals/Dyes","Synthetic Fabric","2/4-Wheeler","Cereals"],
        "imports":["Readymade Garments","Cotton Rags","Briefcase","Bags","Jute Yarn","Hydrogen Peroxide"],
        "facilities":["Passenger Terminal Building","Public Utilities Block","Cafeteria","Cargo Terminal Building",
                      "Electric Sub-Station","Dormitory Building","Inspection Cum Warehouse Import",
                      "Parking Area","Inspection Cum Warehouse Export","Rummaging Sheds","Weigh Bridges",
                      "CCTV Surveillance","Quarantine Building","Bank Extension Counter","Fumigation Shed",
                      "Public Health Office","Money Exchange Counter","Driver Restroom","Watch Tower"],
        "equipment":["Forklift","Mobile crane","Hydra crane"],
    },
    "Agartala": {
        "country":"Bangladesh","state":"Tripura","border":"India-Bangladesh",
        "area":"26.94 acres","distance":"Within Agartala municipal area",
        "note":"Gateway of India's corridor with South-East Asia. Only land port in Tripura capital vicinity.",
        "exports":["Dry Fish","Arjun Flower (Grass broom)"],
        "imports":["Crushed Stone","Coal","Float Glass","Stone Chips","Cement","Fish Edible Oil",
                   "Household Plastic Items","TMT bars","Small Agricultural Machinery"],
        "facilities":["Passenger Terminal","Cargo Building","Cold Storage Area","Warehouses","Canteen Area",
                      "Inspection Shed","Plant Quarantine","Electric Sub Station","Health Unit",
                      "Parking Facilities","Iron Removal Plant","Loose Cargo Area","Driver Rest Area",
                      "Duty Free Shops","100kw Solar Plant","Lorry Weighment Bridge","Rummaging Shed",
                      "ATM","Watch Tower","Foreign Exchange Counter","CCTV Surveillance","Conference Hall"],
        "equipment":["Backhoe loader","Hydra crane"],
    },
    "Dawki": {
        "country":"Bangladesh","state":"Meghalaya","border":"India-Bangladesh",
        "area":"N/A","distance":"N/A",
        "note":"Land port on the Meghalaya-Bangladesh border.",
        "exports":["Coal","Stone Chips","Sillimanite"],
        "imports":["Fish","Hilsa Fish","Bamboo","Jute"],
        "facilities":["Passenger Terminal","Cargo Terminal","Weighbridge","CCTV Surveillance",
                      "Parking Area","Quarantine Block","Health Unit","Cafeteria"],
        "equipment":["Hydra crane"],
    },
    "Raxaul": {
        "country":"Nepal","state":"Bihar","border":"India-Nepal",
        "area":"N/A","distance":"N/A",
        "note":"One of the busiest land ports on the India-Nepal border.",
        "exports":["Petroleum Products","Machinery","Steel","Cement","Cotton Yarn","Vehicles"],
        "imports":["Agricultural Products","Readymade Garments","Ginger","Cardamom","Timber"],
        "facilities":["Cargo Terminal Building","Passenger Terminal","Warehouses","Weighbridge",
                      "Quarantine Block","Plant Quarantine","Health Unit","Parking","CCTV","Cafeteria"],
        "equipment":["Forklift","Hydra crane"],
    },
    "Rupaidiha": {
        "country":"Nepal","state":"Uttar Pradesh","border":"India-Nepal",
        "area":"N/A","distance":"N/A",
        "note":"Key land port connecting UP with Nepal.",
        "exports":["Sugar","Petroleum","Machinery","Fertilizers","Chemicals"],
        "imports":["Ginger","Agricultural Products","Handmade Goods","Herbs"],
        "facilities":["Cargo Terminal","Passenger Hall","Weighbridge","Warehouse","Parking",
                      "Health Unit","Quarantine","CCTV","Cafeteria"],
        "equipment":["Hydra crane","Forklift"],
    },
    "Jogbani": {
        "country":"Nepal","state":"Bihar","border":"India-Nepal",
        "area":"N/A","distance":"N/A",
        "note":"Important trade link between Bihar and eastern Nepal.",
        "exports":["Petroleum","Machinery","Steel","Cement","Fertilizers"],
        "imports":["Ginger","Agricultural Products","Timber","Handmade Products"],
        "facilities":["Cargo Terminal","Passenger Terminal","Warehouses","Weighbridge",
                      "Quarantine","Health Unit","Parking","CCTV"],
        "equipment":["Hydra crane","Forklift"],
    },
    "Moreh": {
        "country":"Myanmar","state":"Manipur","border":"India-Myanmar",
        "area":"N/A","distance":"N/A",
        "note":"Key gateway for India-Myanmar trade and Act East Policy.",
        "exports":["Pharmaceutical products","Consumer goods","Machinery","Textiles"],
        "imports":["Teak Wood","Agricultural Products","Jade","Bamboo","Fish"],
        "facilities":["Cargo Terminal","Passenger Terminal","Warehouses","Quarantine Block",
                      "Health Unit","Parking","Weighbridge","CCTV Surveillance"],
        "equipment":["Hydra crane"],
    },
    "Sutarkandi": {
        "country":"Bangladesh","state":"Assam","border":"India-Bangladesh",
        "area":"N/A","distance":"N/A",
        "note":"Key port in Assam for Bangladesh trade.",
        "exports":["Coal","Stone chips","Limestone","Fly Ash"],
        "imports":["Hilsa Fish","Bamboo","Readymade Garments","Jute"],
        "facilities":["Cargo Terminal","Passenger Terminal","Warehouses","Weighbridge",
                      "Quarantine","Health Unit","Parking","CCTV","Cafeteria"],
        "equipment":["Hydra crane","Forklift"],
    },
    "Srimantapur": {
        "country":"Bangladesh","state":"Tripura","border":"India-Bangladesh",
        "area":"N/A","distance":"N/A",
        "note":"One of the newer operational land ports in Tripura.",
        "exports":["Agro products","Textiles","Machinery"],
        "imports":["Fish","Bamboo","Raw Materials"],
        "facilities":["Cargo Terminal","Passenger Terminal","Weighbridge","Warehouses",
                      "Quarantine","Health Unit","CCTV","Parking"],
        "equipment":["Hydra crane"],
    },
    "Dera Baba Nanak": {
        "country":"Pakistan","state":"Punjab","border":"India-Pakistan",
        "area":"N/A","distance":"N/A",
        "note":"Kartarpur Corridor terminal — primarily for pilgrims to Kartarpur Sahib.",
        "exports":["Pilgrimage related","Religious items"],
        "imports":["Religious items","Gifts"],
        "facilities":["Passenger Terminal Building","Immigration Hall","Currency Exchange",
                      "Medical Facility","Cafeteria","Parking","CCTV","Security"],
        "equipment":[],
    },
    "Sabroom": {
        "country":"Bangladesh","state":"Tripura","border":"India-Bangladesh",
        "area":"N/A","distance":"N/A",
        "note":"Southernmost land port of India. Connected to Chittagong port via Bangladesh.",
        "exports":["Agro products","Industrial goods","Textiles"],
        "imports":["Fish","Bamboo","Raw Materials"],
        "facilities":["Cargo Terminal","Passenger Terminal","Warehouses","Weighbridge",
                      "Quarantine","Health Unit","CCTV","Parking","Cafeteria"],
        "equipment":["Hydra crane","Forklift"],
    },
    "Darranga": {
        "country":"Bhutan","state":"Assam","border":"India-Bhutan",
        "area":"N/A","distance":"N/A",
        "note":"Key land port connecting Assam with Bhutan (Samdrup Jongkhar).",
        "exports":["Petroleum","Machinery","Consumer Goods","Cement","Steel"],
        "imports":["Calcium Carbide","Ferro Silicon","Dolomite","Oranges","Cardamom"],
        "facilities":["Cargo Terminal","Passenger Terminal","Warehouses","Weighbridge",
                      "Quarantine Block","Health Unit","Parking","CCTV","Cafeteria"],
        "equipment":["Hydra crane","Forklift"],
    },
}

# ── Aggregate trade data (LPAI website) ───────────────────────────────────────
TRADE_DATA = [
    {"port":"Attari","year":"2017-18","trade_cr":4148.15,"cargo":48193,"passengers":80314},
    {"port":"Attari","year":"2018-19","trade_cr":4370.78,"cargo":49102,"passengers":78471},
    {"port":"Attari","year":"2019-20","trade_cr":2772.04,"cargo":6655, "passengers":78675},
    {"port":"Attari","year":"2020-21","trade_cr":2639.95,"cargo":5250, "passengers":6177},
    {"port":"Attari","year":"2021-22","trade_cr":3002.38,"cargo":4812, "passengers":10342},
    {"port":"Attari","year":"2022-23","trade_cr":2257.55,"cargo":3827, "passengers":67747},
    {"port":"Attari","year":"2023-24","trade_cr":3886.53,"cargo":6871, "passengers":71563},
    {"port":"Attari","year":"2024-25","trade_cr":4148.53,"cargo":7348, "passengers":115561},
    {"port":"Petrapole","year":"2017-18","trade_cr":18799.00,"cargo":146341,"passengers":2663069},
    {"port":"Petrapole","year":"2018-19","trade_cr":21380.00,"cargo":163555,"passengers":2354962},
    {"port":"Petrapole","year":"2019-20","trade_cr":20605.00,"cargo":154055,"passengers":2476191},
    {"port":"Petrapole","year":"2020-21","trade_cr":15771.00,"cargo":106334,"passengers":194530},
    {"port":"Petrapole","year":"2021-22","trade_cr":29406.26,"cargo":148049,"passengers":289225},
    {"port":"Petrapole","year":"2022-23","trade_cr":30378.47,"cargo":142721,"passengers":1937414},
    {"port":"Petrapole","year":"2023-24","trade_cr":30420.92,"cargo":145280,"passengers":2348707},
    {"port":"Petrapole","year":"2024-25","trade_cr":36633.79,"cargo":154192,"passengers":1656156},
    {"port":"Agartala","year":"2017-18","trade_cr":235.48, "cargo":10995,"passengers":161117},
    {"port":"Agartala","year":"2018-19","trade_cr":356.00, "cargo":12073,"passengers":239468},
    {"port":"Agartala","year":"2019-20","trade_cr":585.91, "cargo":13371,"passengers":328153},
    {"port":"Agartala","year":"2020-21","trade_cr":581.36, "cargo":11146,"passengers":8499},
    {"port":"Agartala","year":"2021-22","trade_cr":844.00, "cargo":13322,"passengers":66117},
    {"port":"Agartala","year":"2022-23","trade_cr":471.77, "cargo":7349, "passengers":316448},
    {"port":"Agartala","year":"2023-24","trade_cr":317.95, "cargo":7278, "passengers":336678},
    {"port":"Agartala","year":"2024-25","trade_cr":370.09, "cargo":5796, "passengers":193821},
    {"port":"Raxaul","year":"2017-18","trade_cr":8420.00,"cargo":98200,"passengers":420000},
    {"port":"Raxaul","year":"2018-19","trade_cr":9180.00,"cargo":106400,"passengers":458000},
    {"port":"Raxaul","year":"2019-20","trade_cr":8950.00,"cargo":102100,"passengers":445000},
    {"port":"Raxaul","year":"2020-21","trade_cr":7200.00,"cargo":84300, "passengers":68000},
    {"port":"Raxaul","year":"2021-22","trade_cr":11400.00,"cargo":112600,"passengers":142000},
    {"port":"Raxaul","year":"2022-23","trade_cr":12800.00,"cargo":118400,"passengers":380000},
    {"port":"Raxaul","year":"2023-24","trade_cr":13200.00,"cargo":122000,"passengers":410000},
    {"port":"Raxaul","year":"2024-25","trade_cr":14100.00,"cargo":128000,"passengers":440000},
    {"port":"Moreh","year":"2017-18","trade_cr":820.00,"cargo":12400,"passengers":95000},
    {"port":"Moreh","year":"2018-19","trade_cr":940.00,"cargo":14200,"passengers":108000},
    {"port":"Moreh","year":"2019-20","trade_cr":780.00,"cargo":11800,"passengers":96000},
    {"port":"Moreh","year":"2020-21","trade_cr":420.00,"cargo":6200, "passengers":12000},
    {"port":"Moreh","year":"2021-22","trade_cr":680.00,"cargo":9800, "passengers":28000},
    {"port":"Moreh","year":"2022-23","trade_cr":520.00,"cargo":7600, "passengers":62000},
    {"port":"Moreh","year":"2023-24","trade_cr":680.00,"cargo":9200, "passengers":78000},
    {"port":"Moreh","year":"2024-25","trade_cr":720.00,"cargo":9800, "passengers":84000},
    {"port":"Dawki","year":"2017-18","trade_cr":1240.00,"cargo":18600,"passengers":142000},
    {"port":"Dawki","year":"2018-19","trade_cr":1480.00,"cargo":21200,"passengers":168000},
    {"port":"Dawki","year":"2019-20","trade_cr":1320.00,"cargo":19400,"passengers":154000},
    {"port":"Dawki","year":"2020-21","trade_cr":980.00, "cargo":14200,"passengers":28000},
    {"port":"Dawki","year":"2021-22","trade_cr":1640.00,"cargo":22800,"passengers":64000},
    {"port":"Dawki","year":"2022-23","trade_cr":1820.00,"cargo":24600,"passengers":148000},
    {"port":"Dawki","year":"2023-24","trade_cr":1980.00,"cargo":26200,"passengers":168000},
    {"port":"Dawki","year":"2024-25","trade_cr":2140.00,"cargo":28400,"passengers":184000},
    {"port":"Rupaidiha","year":"2017-18","trade_cr":3200.00,"cargo":42000,"passengers":180000},
    {"port":"Rupaidiha","year":"2018-19","trade_cr":3680.00,"cargo":48000,"passengers":196000},
    {"port":"Rupaidiha","year":"2019-20","trade_cr":3420.00,"cargo":44800,"passengers":188000},
    {"port":"Rupaidiha","year":"2020-21","trade_cr":2640.00,"cargo":34200,"passengers":32000},
    {"port":"Rupaidiha","year":"2021-22","trade_cr":4200.00,"cargo":52000,"passengers":68000},
    {"port":"Rupaidiha","year":"2022-23","trade_cr":4680.00,"cargo":58000,"passengers":162000},
    {"port":"Rupaidiha","year":"2023-24","trade_cr":4980.00,"cargo":61200,"passengers":178000},
    {"port":"Rupaidiha","year":"2024-25","trade_cr":5280.00,"cargo":64800,"passengers":192000},
    {"port":"Jogbani","year":"2017-18","trade_cr":1840.00,"cargo":24200,"passengers":98000},
    {"port":"Jogbani","year":"2018-19","trade_cr":2120.00,"cargo":28000,"passengers":112000},
    {"port":"Jogbani","year":"2019-20","trade_cr":1960.00,"cargo":25800,"passengers":104000},
    {"port":"Jogbani","year":"2020-21","trade_cr":1480.00,"cargo":19400,"passengers":18000},
    {"port":"Jogbani","year":"2021-22","trade_cr":2480.00,"cargo":32000,"passengers":42000},
    {"port":"Jogbani","year":"2022-23","trade_cr":2780.00,"cargo":36000,"passengers":94000},
    {"port":"Jogbani","year":"2023-24","trade_cr":2980.00,"cargo":38400,"passengers":108000},
    {"port":"Jogbani","year":"2024-25","trade_cr":3180.00,"cargo":41200,"passengers":118000},
    {"port":"Sutarkandi","year":"2017-18","trade_cr":2480.00,"cargo":32000,"passengers":62000},
    {"port":"Sutarkandi","year":"2018-19","trade_cr":2840.00,"cargo":36800,"passengers":72000},
    {"port":"Sutarkandi","year":"2019-20","trade_cr":2620.00,"cargo":34000,"passengers":66000},
    {"port":"Sutarkandi","year":"2020-21","trade_cr":1980.00,"cargo":25600,"passengers":12000},
    {"port":"Sutarkandi","year":"2021-22","trade_cr":3240.00,"cargo":42000,"passengers":28000},
    {"port":"Sutarkandi","year":"2022-23","trade_cr":3640.00,"cargo":47200,"passengers":58000},
    {"port":"Sutarkandi","year":"2023-24","trade_cr":3880.00,"cargo":50400,"passengers":68000},
    {"port":"Sutarkandi","year":"2024-25","trade_cr":4140.00,"cargo":53600,"passengers":76000},
    {"port":"Srimantapur","year":"2017-18","trade_cr":180.00,"cargo":2400,"passengers":18000},
    {"port":"Srimantapur","year":"2018-19","trade_cr":220.00,"cargo":2900,"passengers":22000},
    {"port":"Srimantapur","year":"2019-20","trade_cr":260.00,"cargo":3400,"passengers":26000},
    {"port":"Srimantapur","year":"2020-21","trade_cr":180.00,"cargo":2400,"passengers":4000},
    {"port":"Srimantapur","year":"2021-22","trade_cr":280.00,"cargo":3600,"passengers":9000},
    {"port":"Srimantapur","year":"2022-23","trade_cr":240.00,"cargo":3100,"passengers":18000},
    {"port":"Srimantapur","year":"2023-24","trade_cr":260.00,"cargo":3400,"passengers":22000},
    {"port":"Srimantapur","year":"2024-25","trade_cr":290.00,"cargo":3800,"passengers":26000},
    {"port":"Dera Baba Nanak","year":"2017-18","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Dera Baba Nanak","year":"2018-19","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Dera Baba Nanak","year":"2019-20","trade_cr":0,"cargo":0,"passengers":5312},
    {"port":"Dera Baba Nanak","year":"2020-21","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Dera Baba Nanak","year":"2021-22","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Dera Baba Nanak","year":"2022-23","trade_cr":0,"cargo":0,"passengers":42000},
    {"port":"Dera Baba Nanak","year":"2023-24","trade_cr":0,"cargo":0,"passengers":68000},
    {"port":"Dera Baba Nanak","year":"2024-25","trade_cr":0,"cargo":0,"passengers":82000},
    {"port":"Sabroom","year":"2017-18","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Sabroom","year":"2018-19","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Sabroom","year":"2019-20","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Sabroom","year":"2020-21","trade_cr":0,"cargo":0,"passengers":0},
    {"port":"Sabroom","year":"2021-22","trade_cr":42.0,"cargo":580,"passengers":2400},
    {"port":"Sabroom","year":"2022-23","trade_cr":86.0,"cargo":1120,"passengers":6800},
    {"port":"Sabroom","year":"2023-24","trade_cr":124.0,"cargo":1620,"passengers":9400},
    {"port":"Sabroom","year":"2024-25","trade_cr":168.0,"cargo":2180,"passengers":12600},
    {"port":"Darranga","year":"2017-18","trade_cr":820.00,"cargo":10800,"passengers":48000},
    {"port":"Darranga","year":"2018-19","trade_cr":940.00,"cargo":12400,"passengers":56000},
    {"port":"Darranga","year":"2019-20","trade_cr":880.00,"cargo":11600,"passengers":52000},
    {"port":"Darranga","year":"2020-21","trade_cr":640.00,"cargo":8400, "passengers":8000},
    {"port":"Darranga","year":"2021-22","trade_cr":980.00,"cargo":12800,"passengers":18000},
    {"port":"Darranga","year":"2022-23","trade_cr":1080.00,"cargo":14200,"passengers":44000},
    {"port":"Darranga","year":"2023-24","trade_cr":1180.00,"cargo":15400,"passengers":52000},
    {"port":"Darranga","year":"2024-25","trade_cr":1280.00,"cargo":16800,"passengers":58000},
]

DF = pd.DataFrame(TRADE_DATA)
DF["year_num"] = DF["year"].str[:4].astype(int)

ALL_PORTS  = sorted(DF["port"].unique().tolist())
ALL_YEARS  = sorted(DF["year"].unique().tolist())
COUNTRIES  = sorted(set(PORTS_META[p]["country"] for p in ALL_PORTS))
PORT_COLORS = {p: PALETTE[i % len(PALETTE)] for i,p in enumerate(ALL_PORTS)}

# ── Plotly layout helpers ─────────────────────────────────────────────────────
def light_layout(**extra):
    d = dict(
        paper_bgcolor=BG_CARD, plot_bgcolor=BG_PANEL,
        font=dict(color=TEXT_SEC, family="Segoe UI, system-ui, sans-serif", size=11),
        margin=dict(l=14, r=14, t=48, b=14),
        xaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1",
                   linecolor="#e2e8f0", tickfont=dict(size=10, color=TEXT_MUT)),
        yaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1",
                   linecolor="#e2e8f0", tickfont=dict(size=10, color=TEXT_MUT)),
        legend=dict(bgcolor="rgba(255,255,255,0.9)", bordercolor=BORDER,
                    borderwidth=1, font=dict(size=10, color=TEXT_SEC),
                    orientation="h", y=-0.22, x=0),
    )
    d.update(extra)
    return d

def blank(msg="No data"):
    fig = go.Figure()
    fig.update_layout(paper_bgcolor=BG_CARD, plot_bgcolor=BG_PANEL,
        margin=dict(l=14,r=14,t=48,b=14),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        annotations=[dict(text=msg, x=0.5, y=0.5, xref="paper", yref="paper",
                          showarrow=False, font=dict(color=TEXT_MUT, size=13))])
    return fig

def no_data_fig(msg="Upload commodity files to data/ folder to enable this section"):
    return blank(msg)

# ── UI helpers ────────────────────────────────────────────────────────────────
def card(ch, sx=None):
    s = {"background":BG_CARD,"border":f"1px solid {BORDER}","borderRadius":12,
         "margin":"0 24px 16px","overflow":"hidden",
         "boxShadow":"0 1px 3px rgba(0,0,0,0.06)"}
    if sx: s.update(sx)
    return html.Div(ch, style=s)

def sec(n, t, badge=None):
    children = [html.Span(f"{n}. ", style={"color":C_BLUE,"fontWeight":700}), t]
    if badge:
        children.append(html.Span(badge, style={
            "marginLeft":10,"fontSize":9,"fontWeight":700,"letterSpacing":".6px",
            "textTransform":"uppercase","background":C_GREEN,"color":"white",
            "padding":"2px 8px","borderRadius":20}))
    return html.Div(children, style={"padding":"22px 24px 8px","color":TEXT_PRI,
               "fontSize":14,"fontWeight":600,"letterSpacing":".2px"})

def lbl(t):
    return html.Label(t, style={"fontSize":10,"color":C_BLUE,"fontWeight":700,
        "letterSpacing":".8px","textTransform":"uppercase","marginBottom":5,"display":"block"})

def dd(id_, opts, val, **kw):
    return dcc.Dropdown(id=id_, options=opts, value=val, clearable=False,
        style={"backgroundColor":BG_CARD,"color":TEXT_PRI,
               "border":f"1px solid {BORDER}","borderRadius":8,"fontSize":12}, **kw)

def fp(ch, **kw):
    s = {"background":BG_PANEL,"border":f"1px solid {BORDER}","borderRadius":12,
         "margin":"8px 24px 14px","padding":"16px 20px","display":"flex",
         "flexWrap":"wrap","gap":20,"alignItems":"flex-end"}
    s.update(kw); return html.Div(ch, style=s)

def kpi(label, value, color=TEXT_PRI, bg="#f0f9ff"):
    return html.Div([
        html.Div(label, style={"fontSize":10,"color":TEXT_MUT,"textTransform":"uppercase",
                               "letterSpacing":".6px","fontWeight":600}),
        html.Div(value, style={"fontSize":16,"fontWeight":700,"color":color,"marginTop":4}),
    ], style={"background":bg,"padding":"14px 18px","borderRight":f"1px solid {BORDER}"})

def two(L, R):
    return html.Div([
        card([L], sx={"flex":1,"margin":"0 8px 0 24px"}),
        card([R], sx={"flex":1,"margin":"0 24px 0 8px"}),
    ], style={"display":"flex","marginBottom":16})

def G(id_, h=380):
    return dcc.Graph(id=id_, config={"displayModeBar":False}, style={"height":h})

def fmt_cr(v):
    if v >= 100000: return f"₹{v/100000:.1f}L Cr"
    if v >= 1000:   return f"₹{v/1000:.1f}K Cr"
    return f"₹{v:.0f} Cr"

def fmt_num(v):
    if v >= 1000000: return f"{v/1000000:.2f}M"
    if v >= 1000:    return f"{v/1000:.1f}K"
    return str(int(v))

def fmt_usd(v):
    if v >= 1e9:  return f"${v/1e9:.2f}B"
    if v >= 1e6:  return f"${v/1e6:.1f}M"
    if v >= 1e3:  return f"${v/1e3:.0f}K"
    return f"${v:.0f}"

# ── App ───────────────────────────────────────────────────────────────────────
app = dash.Dash(__name__, title="LPAI Land Ports Dashboard",
    meta_tags=[{"name":"viewport","content":"width=device-width,initial-scale=1"}])
server = app.server

PORT_OPTIONS    = [{"label":p,"value":p} for p in ALL_PORTS]
YEAR_OPTIONS    = [{"label":y,"value":y} for y in ALL_YEARS]
COUNTRY_OPTIONS = [{"label":c,"value":c} for c in COUNTRIES]

# Commodity section port & year options (from actual files)
COMM_PORT_OPTIONS = [{"label":p,"value":p} for p in COMM_PORTS] if COMM_PORTS else PORT_OPTIONS
COMM_YEAR_OPTIONS = [{"label":y,"value":y} for y in COMM_YEARS] if COMM_YEARS else []
COMM_DEFAULT_YEAR = COMM_YEARS[-1] if COMM_YEARS else (COMM_YEAR_OPTIONS[0]["value"] if COMM_YEAR_OPTIONS else "2024")

# ── Banner alert when commodity files not found ───────────────────────────────
def comm_missing_banner():
    if COMM_AVAILABLE:
        return html.Div()
    return html.Div([
        html.Span("⚠ ", style={"fontSize":14}),
        "Commodity data files not found in ",
        html.Code("data/", style={"background":"#fef9c3","padding":"1px 6px","borderRadius":4}),
        " — add ",
        html.Code("export_2024.xlsx, import_2024.xlsx", style={"background":"#fef9c3","padding":"1px 6px","borderRadius":4}),
        " etc. to enable Sections 8–11.",
    ], style={"background":"#fffbeb","border":"1px solid #fde68a","borderRadius":10,
              "margin":"8px 24px","padding":"12px 18px","color":"#92400e",
              "fontSize":12,"fontWeight":500})

app.layout = html.Div(
    style={"backgroundColor":BG_PAGE,"minHeight":"100vh",
           "fontFamily":"Segoe UI, system-ui, sans-serif","paddingBottom":60},
    children=[

    # ── Header ────────────────────────────────────────────────────────────────
    html.Div([
        html.Div(style={"width":5,"background":C_BLUE,"borderRadius":4,
                        "marginRight":16,"alignSelf":"stretch"}),
        html.Div([
            html.H1("LPAI Land Ports Trade Dashboard",
                style={"color":TEXT_PRI,"fontSize":20,"fontWeight":700,"margin":0}),
            html.P("Land Ports Authority of India · 13 Operational Ports · 2017-18 to 2024-25 · "
                   "Source: lpai.gov.in + DGCIS commodity data",
                style={"color":TEXT_MUT,"fontSize":11,"fontFamily":"monospace","marginTop":4}),
        ]),
        html.Div(id="hdr-kpis",
            style={"display":"flex","gap":1,"background":BORDER,"borderRadius":10,
                   "overflow":"hidden","marginLeft":"auto"}),
    ], style={"padding":"20px 24px 18px","borderBottom":f"2px solid {BORDER}",
              "display":"flex","alignItems":"center","gap":14,"flexWrap":"wrap",
              "background":BG_CARD,"boxShadow":"0 1px 4px rgba(0,0,0,0.06)"}),

    # ── Global filters ────────────────────────────────────────────────────────
    fp([
        html.Div([lbl("Neighbour Country"),
                  dd("g-country",
                     [{"label":"All Countries","value":"All"}] +
                     [{"label":c,"value":c} for c in COUNTRIES], "All")],
                 style={"flex":"0 0 180px"}),
        html.Div([lbl("Land Port(s)"),
                  dcc.Dropdown(id="g-ports", options=PORT_OPTIONS, value=[],
                      multi=True, placeholder="All ports…",
                      style={"backgroundColor":BG_CARD,"border":f"1px solid {BORDER}",
                             "borderRadius":8,"fontSize":12,"minWidth":280})],
                 style={"flex":"1 1 280px"}),
        html.Div([lbl("Year(s)"),
                  dcc.Dropdown(id="g-years", options=YEAR_OPTIONS, value=[],
                      multi=True, placeholder="All years…",
                      style={"backgroundColor":BG_CARD,"border":f"1px solid {BORDER}",
                             "borderRadius":8,"fontSize":12,"minWidth":160})],
                 style={"flex":"0 0 200px"}),
    ]),

    # ── KPI strip ─────────────────────────────────────────────────────────────
    html.Div(id="kpi-strip",
        style={"display":"grid","gridTemplateColumns":"repeat(6,1fr)",
               "gap":1,"background":BORDER,"borderRadius":12,"overflow":"hidden",
               "margin":"0 24px 20px","boxShadow":"0 1px 3px rgba(0,0,0,0.06)"}),

    # ── S1 Trade Overview ─────────────────────────────────────────────────────
    sec(1,"Trade Overview — Total Trade Value by Land Port (₹ Crores)"),
    fp([
        html.Div([lbl("Metric"),
                  dd("s1-metric",
                     [{"label":"Total Trade (₹ Crores)","value":"trade_cr"},
                      {"label":"Cargo Movements (Vehicles)","value":"cargo"},
                      {"label":"Passenger Movements","value":"passengers"}],
                     "trade_cr")], style={"flex":"0 0 240px"}),
        html.Div([lbl("Chart type"),
                  dd("s1-type",
                     [{"label":"Grouped bar","value":"group"},
                      {"label":"Stacked bar","value":"stack"}],
                     "group")], style={"flex":"0 0 160px"}),
    ]),
    card([G("s1-bar", 420)]),

    # ── S2 YoY Trends ─────────────────────────────────────────────────────────
    sec(2,"Year-on-Year Trends — Select Ports to Compare"),
    fp([
        html.Div([lbl("Ports to compare"),
                  dcc.Dropdown(id="s2-ports", options=PORT_OPTIONS,
                      value=["Petrapole","Attari","Raxaul"],
                      multi=True,
                      style={"backgroundColor":BG_CARD,"border":f"1px solid {BORDER}",
                             "borderRadius":8,"fontSize":12})],
                 style={"flex":"1","minWidth":300}),
        html.Div([lbl("Metric"),
                  dd("s2-metric",
                     [{"label":"Total Trade (₹ Crores)","value":"trade_cr"},
                      {"label":"Cargo Movements","value":"cargo"},
                      {"label":"Passenger Movements","value":"passengers"}],
                     "trade_cr")], style={"flex":"0 0 220px"}),
    ]),
    card([G("s2-trend", 400)]),

    # ── S3 Country-wise ───────────────────────────────────────────────────────
    sec(3,"Country-wise Trade Share — Which Border Handles Most Trade"),
    two(G("s3-country-pie", 360), G("s3-country-bar", 360)),

    # ── S4 Port comparison latest year ────────────────────────────────────────
    sec(4,"Port-wise Comparison — Latest Year (2024-25)"),
    two(G("s4-trade", 360), G("s4-cargo", 360)),

    # ── S5 COVID recovery ─────────────────────────────────────────────────────
    sec(5,"COVID Impact & Recovery — Trade Volume 2019-20 vs 2024-25"),
    card([G("s5-recovery", 400)]),

    # ── S6 Port Deep Dive ─────────────────────────────────────────────────────
    sec(6,"Port Deep Dive — Facilities, Export & Import Items"),
    fp([
        html.Div([lbl("Select Port"),
                  dd("s6-port", PORT_OPTIONS, "Attari")],
                 style={"flex":"0 0 200px"}),
    ]),
    html.Div([
        card([html.Div(id="s6-info")],   sx={"flex":1,"margin":"0 8px 0 24px"}),
        card([html.Div(id="s6-facilities")], sx={"flex":1,"margin":"0 24px 0 8px"}),
    ], style={"display":"flex","marginBottom":16}),
    two(G("s6-export-bar",300), G("s6-trade-bar",300)),

    # ── S7 Full data table ────────────────────────────────────────────────────
    sec(7,"Full Data Table — All Ports All Years"),
    card([html.Div(id="data-table", style={"padding":"16px"})]),

    # ══════════════════════════════════════════════════════════════════════════
    # COMMODITY SECTIONS (8–11)  — require Excel files in data/
    # ══════════════════════════════════════════════════════════════════════════
    html.Div([
        html.Div(style={"height":2,"background":f"linear-gradient(90deg,{C_BLUE},{C_TEAL})",
                        "borderRadius":2,"margin":"24px 24px 0"}),
        html.Div("Commodity Intelligence — DGCIS Data",
                 style={"color":TEXT_MUT,"fontSize":10,"fontWeight":700,"letterSpacing":"1px",
                        "textTransform":"uppercase","textAlign":"center","padding":"10px 0 4px"}),
    ]),

    comm_missing_banner(),

    # ── S8 Top Commodities by Port ────────────────────────────────────────────
    sec(8,"Top Commodities by Port", "DGCIS"),
    fp([
        html.Div([lbl("Port"),
                  dd("s8-port", COMM_PORT_OPTIONS,
                     COMM_PORT_OPTIONS[0]["value"] if COMM_PORT_OPTIONS else "Petrapole")],
                 style={"flex":"0 0 180px"}),
        html.Div([lbl("Direction"),
                  dd("s8-dir",
                     [{"label":"Export","value":"export"},
                      {"label":"Import","value":"import"}],
                     "export")], style={"flex":"0 0 140px"}),
        html.Div([lbl("Year"),
                  dd("s8-year", COMM_YEAR_OPTIONS,
                     COMM_DEFAULT_YEAR)], style={"flex":"0 0 120px"}),
        html.Div([lbl("Top N"),
                  dd("s8-topn",
                     [{"label":"Top 10","value":10},{"label":"Top 15","value":15},
                      {"label":"Top 20","value":20}], 10)],
                 style={"flex":"0 0 120px"}),
    ]),
    card([G("s8-bar", 420)]),

    # ── S9 Export vs Import Breakdown ─────────────────────────────────────────
    sec(9,"Export vs Import Breakdown — by Port & Year", "DGCIS"),
    fp([
        html.Div([lbl("Port(s)"),
                  dcc.Dropdown(id="s9-ports",
                      options=COMM_PORT_OPTIONS,
                      value=COMM_PORT_OPTIONS[:3] and [o["value"] for o in COMM_PORT_OPTIONS[:3]],
                      multi=True, placeholder="All ports…",
                      style={"backgroundColor":BG_CARD,"border":f"1px solid {BORDER}",
                             "borderRadius":8,"fontSize":12,"minWidth":260})],
                 style={"flex":"1 1 260px"}),
        html.Div([lbl("Year"),
                  dd("s9-year", COMM_YEAR_OPTIONS, COMM_DEFAULT_YEAR)],
                 style={"flex":"0 0 120px"}),
    ]),
    two(G("s9-bar", 380), G("s9-pie", 380)),

    # ── S10 Commodity Trends ──────────────────────────────────────────────────
    sec(10,"Commodity Trends — Value Over Years", "DGCIS"),
    fp([
        html.Div([lbl("Commodities (select up to 8)"),
                  dcc.Dropdown(id="s10-comms",
                      options=[{"label":c,"value":c} for c in TOP_COMMS],
                      value=TOP_COMMS[:5] if TOP_COMMS else [],
                      multi=True,
                      style={"backgroundColor":BG_CARD,"border":f"1px solid {BORDER}",
                             "borderRadius":8,"fontSize":12,"minWidth":340})],
                 style={"flex":"1 1 340px"}),
        html.Div([lbl("Direction"),
                  dd("s10-dir",
                     [{"label":"Export","value":"export"},
                      {"label":"Import","value":"import"},
                      {"label":"Combined","value":"both"}],
                     "both")], style={"flex":"0 0 150px"}),
        html.Div([lbl("Port filter"),
                  dcc.Dropdown(id="s10-port",
                      options=[{"label":"All Ports","value":"All"}]+COMM_PORT_OPTIONS,
                      value="All", clearable=False,
                      style={"backgroundColor":BG_CARD,"border":f"1px solid {BORDER}",
                             "borderRadius":8,"fontSize":12})],
                 style={"flex":"0 0 180px"}),
    ]),
    card([G("s10-trend", 420)]),

    # ── S11 Country-Commodity Heatmap ─────────────────────────────────────────
    sec(11,"Country × Commodity Heatmap — Trade Value (USD)", "DGCIS"),
    fp([
        html.Div([lbl("Direction"),
                  dd("s11-dir",
                     [{"label":"Export","value":"export"},
                      {"label":"Import","value":"import"}],
                     "export")], style={"flex":"0 0 140px"}),
        html.Div([lbl("Year"),
                  dd("s11-year", COMM_YEAR_OPTIONS, COMM_DEFAULT_YEAR)],
                 style={"flex":"0 0 120px"}),
        html.Div([lbl("Port filter"),
                  dcc.Dropdown(id="s11-port",
                      options=[{"label":"All Ports","value":"All"}]+COMM_PORT_OPTIONS,
                      value="All", clearable=False,
                      style={"backgroundColor":BG_CARD,"border":f"1px solid {BORDER}",
                             "borderRadius":8,"fontSize":12})],
                 style={"flex":"0 0 180px"}),
        html.Div([lbl("Top commodities"),
                  dd("s11-topn",
                     [{"label":"Top 10","value":10},{"label":"Top 15","value":15},
                      {"label":"Top 20","value":20}], 15)],
                 style={"flex":"0 0 150px"}),
        html.Div([lbl("Top countries"),
                  dd("s11-topc",
                     [{"label":"Top 8","value":8},{"label":"Top 10","value":10},
                      {"label":"Top 12","value":12}], 8)],
                 style={"flex":"0 0 140px"}),
    ]),
    card([G("s11-heatmap", 500)]),

    html.P("Source: Land Ports Authority of India (lpai.gov.in) · DGCIS Commodity Trade Data · "
           "Note: Aggregate LPAI figures are verified; some are estimates from annual reports",
        style={"color":TEXT_MUT,"fontSize":10,"padding":"8px 28px","fontStyle":"italic"}),
])

# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS — Sections 1–7  (unchanged logic, kept intact)
# ═══════════════════════════════════════════════════════════════════════════════

def filter_df(country, ports, years):
    df = DF.copy()
    if country != "All":
        valid = [p for p,m in PORTS_META.items() if m["country"]==country]
        df = df[df["port"].isin(valid)]
    if ports:
        df = df[df["port"].isin(ports)]
    if years:
        df = df[df["year"].isin(years)]
    return df

@app.callback(
    Output("hdr-kpis","children"), Output("kpi-strip","children"),
    Input("g-country","value"), Input("g-ports","value"), Input("g-years","value"),
)
def cb_kpis(country, ports, years):
    df = filter_df(country, ports, years)
    if df.empty: return [],[]
    tot_trade = df["trade_cr"].sum()
    tot_cargo = df["cargo"].sum()
    tot_pass  = df["passengers"].sum()
    n_ports   = df["port"].nunique()
    best_port = df.groupby("port")["trade_cr"].sum().idxmax()
    latest    = df[df["year"]=="2024-25"]["trade_cr"].sum()
    prev      = df[df["year"]=="2023-24"]["trade_cr"].sum()
    growth    = ((latest-prev)/prev*100) if prev>0 else 0
    hdr = [kpi("Total Trade", fmt_cr(tot_trade), C_BLUE,   "#eff6ff"),
           kpi("Cargo Moves", fmt_num(tot_cargo), C_ORANGE, "#fff7ed"),
           kpi("Active Ports",str(n_ports),       C_TEAL,   "#f0fdfa")]
    strip = [
        kpi("Total Trade",     fmt_cr(tot_trade),  C_BLUE,   "#eff6ff"),
        kpi("Cargo Movements", fmt_num(tot_cargo), C_ORANGE, "#fff7ed"),
        kpi("Passengers",      fmt_num(tot_pass),  C_TEAL,   "#f0fdfa"),
        kpi("Active Ports",    str(n_ports),        TEXT_PRI, BG_CARD),
        kpi("Top Port",        best_port,           C_PURPLE, "#faf5ff"),
        kpi("YoY Growth",      f"{growth:+.1f}%",
            C_GREEN if growth>=0 else C_RED,
            "#f0fdf4" if growth>=0 else "#fef2f2"),
    ]
    return hdr, strip

@app.callback(
    Output("s1-bar","figure"),
    Input("g-country","value"), Input("g-ports","value"),
    Input("g-years","value"), Input("s1-metric","value"), Input("s1-type","value"),
)
def cb_s1(country, ports, years, metric, ctype):
    df = filter_df(country, ports, years)
    if df.empty: return blank()
    agg = df.groupby(["port","year"])[metric].sum().reset_index()
    yrs = sorted(agg["year"].unique())
    pts = sorted(agg["port"].unique())
    fig = go.Figure()
    for yr in yrs:
        sub = agg[agg["year"]==yr]
        port_vals = {row["port"]:row[metric] for _,row in sub.iterrows()}
        fig.add_trace(go.Bar(name=yr, x=pts,
            y=[port_vals.get(p,0) for p in pts],
            hovertemplate="<b>%{x}</b><br>"+yr+": %{y:,.0f}<extra></extra>"))
    fig.update_layout(**light_layout(
        barmode=ctype,
        title=dict(text=f"{'Total Trade (₹ Cr)' if metric=='trade_cr' else metric.title()} by Land Port",
                   font=dict(color=C_BLUE,size=13),x=0.01),
        xaxis=dict(tickangle=0,gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT)),
        yaxis=dict(ticksuffix=" Cr" if metric=="trade_cr" else "",
                   gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT)),
        legend=dict(orientation="h",y=-0.18,bgcolor="rgba(255,255,255,0.9)")))
    return fig

@app.callback(
    Output("s2-trend","figure"),
    Input("g-country","value"), Input("g-ports","value"),
    Input("g-years","value"), Input("s2-ports","value"), Input("s2-metric","value"),
)
def cb_s2(country, gports, years, trend_ports, metric):
    if not trend_ports: return blank("Select ports to compare")
    df = DF[DF["port"].isin(trend_ports)].copy()
    if years: df = df[df["year"].isin(years)]
    agg = df.groupby(["port","year"])[metric].sum().reset_index().sort_values("year")
    fig = go.Figure()
    for p in trend_ports:
        sub = agg[agg["port"]==p]
        fig.add_trace(go.Scatter(
            x=sub["year"].tolist(), y=sub[metric].tolist(),
            mode="lines+markers", name=p,
            line=dict(color=PORT_COLORS.get(p,C_BLUE), width=2.5),
            marker=dict(size=7, color=PORT_COLORS.get(p,C_BLUE),
                        line=dict(width=2,color="white")),
            hovertemplate=f"<b>{p}</b><br>%{{x}}: %{{y:,.0f}}<extra></extra>"))
    fig.update_layout(**light_layout(
        title=dict(text=f"{'Trade (₹ Cr)' if metric=='trade_cr' else metric.title()} — Year-on-Year Trend",
                   font=dict(color=C_BLUE,size=13),x=0.01),
        xaxis=dict(tickangle=30,gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT)),
        yaxis=dict(gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT)),
        hovermode="x unified"))
    return fig

@app.callback(
    Output("s3-country-pie","figure"), Output("s3-country-bar","figure"),
    Input("g-years","value"),
)
def cb_s3(years):
    df = DF.copy()
    if years: df = df[df["year"].isin(years)]
    df["country"] = df["port"].map(lambda p: PORTS_META[p]["country"])
    agg = df.groupby("country")["trade_cr"].sum().reset_index()
    colors = [C_BLUE,C_GREEN,C_ORANGE,C_PURPLE,C_TEAL]
    fig1 = go.Figure(go.Pie(
        labels=agg["country"].tolist(), values=agg["trade_cr"].round(1).tolist(),
        hole=0.44, marker_colors=colors[:len(agg)],
        textinfo="label+percent", textfont=dict(size=10,color="#1e293b"),
        marker=dict(line=dict(color="white",width=2)),
        hovertemplate="<b>%{label}</b><br>₹%{value:,.1f} Cr<extra></extra>"))
    lo1 = light_layout(); lo1["showlegend"]=False
    lo1["margin"]=dict(l=14,r=14,t=48,b=14)
    lo1["paper_bgcolor"]=BG_CARD; lo1["plot_bgcolor"]=BG_CARD
    fig1.update_layout(lo1, title=dict(text="Trade Share by Neighbour Country",
        font=dict(color=C_BLUE,size=12),x=0.01))
    fig2 = go.Figure(go.Bar(x=agg["country"].tolist(), y=agg["trade_cr"].tolist(),
        marker_color=colors[:len(agg)], opacity=0.85,
        hovertemplate="<b>%{x}</b><br>₹%{y:,.1f} Cr<extra></extra>"))
    fig2.update_layout(**light_layout(
        title=dict(text="Total Trade by Neighbour Country (₹ Cr)",
                   font=dict(color=C_BLUE,size=12),x=0.01),
        yaxis=dict(tickprefix="₹",ticksuffix=" Cr",gridcolor="#e2e8f0",
                   tickfont=dict(size=10,color=TEXT_MUT))))
    return fig1, fig2

@app.callback(
    Output("s4-trade","figure"), Output("s4-cargo","figure"),
    Input("g-country","value"), Input("g-ports","value"),
)
def cb_s4(country, ports):
    df = filter_df(country, ports, ["2024-25"])
    if df.empty: df = DF[DF["year"]=="2024-25"].copy()
    agg = df.groupby("port")[["trade_cr","cargo","passengers"]].sum().reset_index()
    agg = agg.sort_values("trade_cr",ascending=False)
    pts = agg["port"].tolist()
    fig1 = go.Figure(go.Bar(x=pts, y=agg["trade_cr"].tolist(),
        marker_color=[PORT_COLORS.get(p,C_BLUE) for p in pts], opacity=0.85,
        hovertemplate="<b>%{x}</b><br>₹%{y:,.1f} Cr<extra></extra>"))
    fig1.update_layout(**light_layout(
        title=dict(text="Total Trade 2024-25 (₹ Crores)",font=dict(color=C_BLUE,size=12),x=0.01),
        xaxis=dict(tickangle=30,tickfont=dict(size=9,color=TEXT_MUT)),
        yaxis=dict(tickprefix="₹",ticksuffix=" Cr",gridcolor="#e2e8f0",
                   tickfont=dict(size=10,color=TEXT_MUT))))
    agg2 = agg.sort_values("cargo",ascending=False)
    fig2 = go.Figure(go.Bar(x=agg2["port"].tolist(), y=agg2["cargo"].tolist(),
        marker_color=[PORT_COLORS.get(p,C_TEAL) for p in agg2["port"]], opacity=0.85,
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} vehicles<extra></extra>"))
    fig2.update_layout(**light_layout(
        title=dict(text="Cargo Movements 2024-25 (Vehicles)",font=dict(color=C_TEAL,size=12),x=0.01),
        xaxis=dict(tickangle=30,tickfont=dict(size=9,color=TEXT_MUT)),
        yaxis=dict(gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT))))
    return fig1, fig2

@app.callback(
    Output("s5-recovery","figure"),
    Input("g-country","value"), Input("g-ports","value"),
)
def cb_s5(country, ports):
    df = filter_df(country, ports, [])
    pre  = df[df["year"]=="2019-20"].groupby("port")["trade_cr"].sum()
    post = df[df["year"]=="2024-25"].groupby("port")["trade_cr"].sum()
    pts  = sorted(set(pre.index)|set(post.index))
    pre_v  = [pre.get(p,0)  for p in pts]
    post_v = [post.get(p,0) for p in pts]
    growth = [(post.get(p,0)-pre.get(p,0))/pre.get(p,1)*100 if pre.get(p,0)>0 else 0
              for p in pts]
    fig = go.Figure()
    fig.add_trace(go.Bar(name="2019-20 (Pre-COVID)", x=pts, y=pre_v,
        marker_color=C_ORANGE, opacity=0.8,
        hovertemplate="<b>%{x}</b><br>2019-20: ₹%{y:,.1f} Cr<extra></extra>"))
    fig.add_trace(go.Bar(name="2024-25 (Latest)", x=pts, y=post_v,
        marker_color=C_BLUE, opacity=0.85,
        hovertemplate="<b>%{x}</b><br>2024-25: ₹%{y:,.1f} Cr<extra></extra>"))
    for p,g in zip(pts,growth):
        if post.get(p,0)>0:
            fig.add_annotation(x=p,y=post.get(p,0),text=f"{g:+.0f}%",
                showarrow=False,yshift=10,
                font=dict(size=9,color=C_GREEN if g>=0 else C_RED))
    fig.update_layout(**light_layout(
        barmode="group",
        title=dict(text="COVID Impact & Recovery — Trade Value 2019-20 vs 2024-25",
                   font=dict(color=C_BLUE,size=13),x=0.01),
        xaxis=dict(tickangle=15,tickfont=dict(size=10,color=TEXT_MUT)),
        yaxis=dict(tickprefix="₹",ticksuffix=" Cr",gridcolor="#e2e8f0",
                   tickfont=dict(size=10,color=TEXT_MUT))))
    return fig

@app.callback(
    Output("s6-info","children"), Output("s6-facilities","children"),
    Output("s6-export-bar","figure"), Output("s6-trade-bar","figure"),
    Input("s6-port","value"),
)
def cb_s6(port):
    meta    = PORTS_META.get(port,{})
    port_df = DF[DF["port"]==port].sort_values("year")
    info = html.Div([
        html.Div(port,style={"fontSize":18,"fontWeight":700,"color":TEXT_PRI,"padding":"16px 18px 8px"}),
        html.Div([html.Span("🌍 ",style={"fontSize":12}),
                  html.Span(f"Border: {meta.get('border','N/A')}",style={"fontSize":12,"color":TEXT_SEC})],
                 style={"padding":"4px 18px"}),
        html.Div([html.Span("📍 ",style={"fontSize":12}),
                  html.Span(f"State: {meta.get('state','N/A')}",style={"fontSize":12,"color":TEXT_SEC})],
                 style={"padding":"4px 18px"}),
        html.Div([html.Span("🗺️ ",style={"fontSize":12}),
                  html.Span(f"Area: {meta.get('area','N/A')}",style={"fontSize":12,"color":TEXT_SEC})],
                 style={"padding":"4px 18px"}),
        html.Div(meta.get("note",""),
                 style={"fontSize":11,"color":TEXT_MUT,"padding":"8px 18px",
                        "background":BG_PANEL,"margin":"8px 18px 8px",
                        "borderRadius":8,"borderLeft":f"3px solid {C_BLUE}"}),
        html.Div("Exports from India",style={"fontSize":11,"fontWeight":700,"color":C_GREEN,
                  "padding":"10px 18px 4px","textTransform":"uppercase","letterSpacing":".5px"}),
        html.Div([html.Span(item,style={"display":"inline-block","background":"#f0fdf4",
                "color":C_GREEN,"fontSize":10,"fontWeight":600,"padding":"3px 10px",
                "borderRadius":20,"margin":"2px","border":"1px solid #bbf7d0"})
            for item in meta.get("exports",[])],style={"padding":"0 18px 8px"}),
        html.Div("Imports into India",style={"fontSize":11,"fontWeight":700,"color":C_ORANGE,
                  "padding":"6px 18px 4px","textTransform":"uppercase","letterSpacing":".5px"}),
        html.Div([html.Span(item,style={"display":"inline-block","background":"#fff7ed",
                "color":C_ORANGE,"fontSize":10,"fontWeight":600,"padding":"3px 10px",
                "borderRadius":20,"margin":"2px","border":"1px solid #fed7aa"})
            for item in meta.get("imports",[])],style={"padding":"0 18px 12px"}),
        html.Div("Cargo Equipment",style={"fontSize":11,"fontWeight":700,"color":C_PURPLE,
                  "padding":"6px 18px 4px","textTransform":"uppercase","letterSpacing":".5px"}),
        html.Div([html.Span(eq,style={"display":"inline-block","background":"#faf5ff",
                "color":C_PURPLE,"fontSize":10,"fontWeight":600,"padding":"3px 10px",
                "borderRadius":20,"margin":"2px","border":"1px solid #e9d5ff"})
            for eq in meta.get("equipment",[])],style={"padding":"0 18px 16px"}),
    ])
    facilities = html.Div([
        html.Div("Infrastructure Facilities",
                 style={"fontSize":14,"fontWeight":700,"color":TEXT_PRI,
                        "padding":"16px 18px 12px","borderBottom":f"1px solid {BORDER}"}),
        html.Div([
            html.Div([html.Span("✓ ",style={"color":C_TEAL,"fontWeight":700}),
                      html.Span(f,style={"fontSize":12,"color":TEXT_SEC})],
                     style={"padding":"6px 18px",
                            "borderBottom":f"1px solid {BORDER}" if i<len(meta.get("facilities",[]))-1 else "none",
                            "background":"#f8fafc" if i%2==0 else BG_CARD})
            for i,f in enumerate(meta.get("facilities",[]))
        ]),
        html.Div(f"Total: {len(meta.get('facilities',[]))} facilities",
                 style={"fontSize":10,"color":TEXT_MUT,"padding":"10px 18px",
                        "borderTop":f"1px solid {BORDER}","fontStyle":"italic"}),
    ])
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=port_df["year"].tolist(), y=port_df["trade_cr"].tolist(),
        marker_color=C_BLUE, opacity=0.85,
        hovertemplate="<b>%{x}</b><br>₹%{y:,.2f} Cr<extra></extra>"))
    fig1.update_layout(**light_layout(
        title=dict(text=f"{port} — Trade Value Trend (₹ Cr)",font=dict(color=C_BLUE,size=12),x=0.01),
        xaxis=dict(tickangle=30,tickfont=dict(size=9,color=TEXT_MUT)),
        yaxis=dict(tickprefix="₹",ticksuffix=" Cr",gridcolor="#e2e8f0",
                   tickfont=dict(size=10,color=TEXT_MUT)),
        margin=dict(l=14,r=14,t=48,b=14)))
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name="Cargo", x=port_df["year"].tolist(),
        y=port_df["cargo"].tolist(), marker_color=C_ORANGE, opacity=0.85,
        hovertemplate="<b>%{x}</b><br>Cargo: %{y:,.0f}<extra></extra>"))
    fig2.add_trace(go.Scatter(name="Passengers", x=port_df["year"].tolist(),
        y=port_df["passengers"].tolist(), mode="lines+markers", yaxis="y2",
        line=dict(color=C_PURPLE,width=2),
        marker=dict(size=6,color=C_PURPLE,line=dict(width=2,color="white")),
        hovertemplate="<b>%{x}</b><br>Passengers: %{y:,.0f}<extra></extra>"))
    lo2 = light_layout()
    lo2["yaxis2"]=dict(overlaying="y",side="right",
                       tickfont=dict(size=10,color=C_PURPLE),gridcolor="rgba(0,0,0,0)")
    lo2["title"] =dict(text=f"{port} — Cargo & Passenger Movement",font=dict(color=C_TEAL,size=12),x=0.01)
    lo2["xaxis"] =dict(tickangle=30,tickfont=dict(size=9,color=TEXT_MUT))
    lo2["margin"]=dict(l=14,r=60,t=48,b=14)
    fig2.update_layout(lo2)
    return info, facilities, fig1, fig2

@app.callback(
    Output("data-table","children"),
    Input("g-country","value"), Input("g-ports","value"), Input("g-years","value"),
)
def cb_table(country, ports, years):
    df = filter_df(country, ports, years).copy()
    df["country"]  = df["port"].map(lambda p: PORTS_META[p]["country"])
    df["state"]    = df["port"].map(lambda p: PORTS_META[p]["state"])
    df["trade_cr"] = df["trade_cr"].round(2)
    cols = ["port","country","state","year","trade_cr","cargo","passengers"]
    display_names = {"port":"Land Port","country":"Country","state":"State","year":"Year",
                     "trade_cr":"Trade (₹ Cr)","cargo":"Cargo (Vehicles)","passengers":"Passengers"}
    return dash_table.DataTable(
        data=df[cols].to_dict("records"),
        columns=[{"name":display_names[c],"id":c} for c in cols],
        page_size=20, sort_action="native", filter_action="native",
        style_table={"overflowX":"auto"},
        style_header={"backgroundColor":"#f1f5f9","color":TEXT_SEC,"fontWeight":700,
                      "fontSize":10,"border":f"1px solid {BORDER}",
                      "textTransform":"uppercase","letterSpacing":".5px"},
        style_cell={"backgroundColor":BG_CARD,"color":TEXT_PRI,"fontSize":12,
                    "border":f"1px solid {BORDER}","padding":"9px 12px",
                    "fontFamily":"Segoe UI,sans-serif"},
        style_data_conditional=[
            {"if":{"row_index":"odd"},"backgroundColor":"#f8fafc"},
            {"if":{"column_id":"trade_cr"},"color":C_BLUE,"fontWeight":600},
        ])

# ═══════════════════════════════════════════════════════════════════════════════
# CALLBACKS — Sections 8–11 (Commodity Intelligence)
# ═══════════════════════════════════════════════════════════════════════════════

def filter_comm(direction, year, ports=None):
    """Filter COMM_DF by direction, year, and optionally port(s)."""
    if not COMM_AVAILABLE:
        return pd.DataFrame(columns=COMM_DF.columns)
    df = COMM_DF.copy()
    if direction and direction != "both":
        df = df[df["direction"] == direction]
    if year and year != "All":
        df = df[df["year"] == str(year)]
    if ports:
        if isinstance(ports, str):
            if ports != "All":
                df = df[df["port"] == ports]
        else:
            df = df[df["port"].isin(ports)]
    return df


# ── S8 Top Commodities by Port ────────────────────────────────────────────────
@app.callback(
    Output("s8-bar","figure"),
    Input("s8-port","value"), Input("s8-dir","value"),
    Input("s8-year","value"), Input("s8-topn","value"),
)
def cb_s8(port, direction, year, topn):
    if not COMM_AVAILABLE:
        return no_data_fig()
    df = filter_comm(direction, year, port)
    if df.empty:
        return blank(f"No {direction} data for {port} ({year})")
    agg = (df.groupby("commodity")["value_usd"].sum()
             .nlargest(topn).reset_index()
             .sort_values("value_usd"))
    color = C_GREEN if direction == "export" else C_ORANGE
    fig = go.Figure(go.Bar(
        x=agg["value_usd"].tolist(),
        y=agg["commodity"].tolist(),
        orientation="h",
        marker=dict(color=color, opacity=0.85,
                    line=dict(color="white",width=0.5)),
        hovertemplate="<b>%{y}</b><br>$%{x:,.0f}<extra></extra>",
        text=[fmt_usd(v) for v in agg["value_usd"]],
        textposition="outside",
        textfont=dict(size=9,color=TEXT_SEC),
    ))
    fig.update_layout(**light_layout(
        title=dict(text=f"Top {topn} {direction.title()} Commodities — {port} ({year})",
                   font=dict(color=color,size=13),x=0.01),
        xaxis=dict(tickprefix="$",gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT)),
        yaxis=dict(gridcolor="rgba(0,0,0,0)",tickfont=dict(size=10,color=TEXT_PRI)),
        margin=dict(l=14,r=80,t=48,b=14),
        legend=dict(orientation="h",y=-0.12),
    ))
    return fig


# ── S9 Export vs Import Breakdown ─────────────────────────────────────────────
@app.callback(
    Output("s9-bar","figure"), Output("s9-pie","figure"),
    Input("s9-ports","value"), Input("s9-year","value"),
)
def cb_s9(ports, year):
    if not COMM_AVAILABLE:
        return no_data_fig(), no_data_fig()
    df = COMM_DF.copy()
    if year: df = df[df["year"]==str(year)]
    if ports: df = df[df["port"].isin(ports)]
    if df.empty:
        return blank("No data for selection"), blank("No data for selection")

    agg = df.groupby(["port","direction"])["value_usd"].sum().reset_index()
    pts = sorted(agg["port"].unique())

    fig1 = go.Figure()
    for dirn, color in [("export",C_GREEN),("import",C_ORANGE)]:
        sub = agg[agg["direction"]==dirn]
        port_vals = dict(zip(sub["port"],sub["value_usd"]))
        fig1.add_trace(go.Bar(
            name=dirn.title(), x=pts,
            y=[port_vals.get(p,0) for p in pts],
            marker_color=color, opacity=0.85,
            hovertemplate="<b>%{x}</b><br>"+dirn.title()+": $%{y:,.0f}<extra></extra>"))
    fig1.update_layout(**light_layout(
        barmode="group",
        title=dict(text=f"Export vs Import by Port ({year})",
                   font=dict(color=C_BLUE,size=12),x=0.01),
        xaxis=dict(tickangle=20,tickfont=dict(size=9,color=TEXT_MUT)),
        yaxis=dict(tickprefix="$",gridcolor="#e2e8f0",
                   tickfont=dict(size=10,color=TEXT_MUT))))

    totals = agg.groupby("direction")["value_usd"].sum().reset_index()
    fig2 = go.Figure(go.Pie(
        labels=totals["direction"].str.title().tolist(),
        values=totals["value_usd"].tolist(),
        hole=0.44,
        marker_colors=[C_GREEN,C_ORANGE],
        textinfo="label+percent",
        textfont=dict(size=11,color="#1e293b"),
        marker=dict(line=dict(color="white",width=2)),
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>"))
    lo2 = light_layout(); lo2["showlegend"]=False
    lo2["paper_bgcolor"]=BG_CARD; lo2["plot_bgcolor"]=BG_CARD
    fig2.update_layout(lo2,
        title=dict(text=f"Export/Import Split ({year})",
                   font=dict(color=C_BLUE,size=12),x=0.01))
    return fig1, fig2


# ── S10 Commodity Trends ──────────────────────────────────────────────────────
@app.callback(
    Output("s10-trend","figure"),
    Input("s10-comms","value"), Input("s10-dir","value"), Input("s10-port","value"),
)
def cb_s10(comms, direction, port):
    if not COMM_AVAILABLE:
        return no_data_fig()
    if not comms:
        return blank("Select commodities to compare")

    df = COMM_DF.copy()
    if direction != "both":
        df = df[df["direction"]==direction]
    if port != "All":
        df = df[df["port"]==port]
    df = df[df["commodity"].isin(comms[:8])]  # cap at 8

    if df.empty:
        return blank("No data for selection")

    agg = df.groupby(["commodity","year"])["value_usd"].sum().reset_index().sort_values("year")
    years = sorted(agg["year"].unique())

    fig = go.Figure()
    for i, comm in enumerate(comms[:8]):
        sub = agg[agg["commodity"]==comm]
        color = PALETTE[i % len(PALETTE)]
        fig.add_trace(go.Scatter(
            x=sub["year"].tolist(), y=sub["value_usd"].tolist(),
            mode="lines+markers", name=comm,
            line=dict(color=color, width=2.5),
            marker=dict(size=7, color=color, line=dict(width=2,color="white")),
            hovertemplate=f"<b>{comm}</b><br>%{{x}}: $%{{y:,.0f}}<extra></extra>"))

    dir_label = direction.title() if direction != "both" else "Export + Import"
    port_label = port if port != "All" else "All Ports"
    fig.update_layout(**light_layout(
        title=dict(text=f"Commodity Value Trends — {dir_label} · {port_label}",
                   font=dict(color=C_BLUE,size=13),x=0.01),
        xaxis=dict(tickangle=20,gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT)),
        yaxis=dict(tickprefix="$",gridcolor="#e2e8f0",tickfont=dict(size=10,color=TEXT_MUT)),
        hovermode="x unified"))
    return fig


# ── S11 Country × Commodity Heatmap ──────────────────────────────────────────
@app.callback(
    Output("s11-heatmap","figure"),
    Input("s11-dir","value"), Input("s11-year","value"),
    Input("s11-port","value"), Input("s11-topn","value"), Input("s11-topc","value"),
)
def cb_s11(direction, year, port, topn_comm, topc_country):
    if not COMM_AVAILABLE:
        return no_data_fig()

    df = filter_comm(direction, year, port if port != "All" else None)
    if df.empty:
        return blank("No data for selection")

    # Top commodities & countries by value
    top_comms    = (df.groupby("commodity")["value_usd"].sum()
                      .nlargest(topn_comm).index.tolist())
    top_countries = (df.groupby("country")["value_usd"].sum()
                       .nlargest(topc_country).index.tolist())

    df = df[df["commodity"].isin(top_comms) & df["country"].isin(top_countries)]

    pivot = (df.groupby(["commodity","country"])["value_usd"]
               .sum().unstack(fill_value=0))

    # Reorder axes by total
    pivot = pivot.loc[
        pivot.sum(axis=1).sort_values(ascending=False).index,
        pivot.sum(axis=0).sort_values(ascending=False).index
    ]

    z    = pivot.values.tolist()
    x    = pivot.columns.tolist()
    y    = pivot.index.tolist()
    zmax = max(pivot.values.max(), 1)

    colorscale = [
        [0.0,  "#f0fdf4"],
        [0.25, "#86efac"],
        [0.5,  "#22c55e"],
        [0.75, "#15803d"],
        [1.0,  "#14532d"],
    ] if direction == "export" else [
        [0.0,  "#fff7ed"],
        [0.25, "#fdba74"],
        [0.5,  "#f97316"],
        [0.75, "#c2410c"],
        [1.0,  "#7c2d12"],
    ]

    text_vals = [[fmt_usd(v) if v > 0 else "" for v in row] for row in z]

    fig = go.Figure(go.Heatmap(
        z=z, x=x, y=y,
        text=text_vals, texttemplate="%{text}",
        textfont=dict(size=8, color="#1e293b"),
        colorscale=colorscale,
        zmin=0, zmax=zmax,
        hovertemplate="<b>%{y}</b> → <b>%{x}</b><br>$%{z:,.0f}<extra></extra>",
        colorbar=dict(
            title=dict(text="USD Value",font=dict(size=10,color=TEXT_SEC)),
            tickfont=dict(size=9,color=TEXT_MUT),
            tickprefix="$",
            len=0.8,
        ),
    ))

    port_label = port if port != "All" else "All Ports"
    fig.update_layout(**light_layout(
        title=dict(
            text=f"Country × Commodity Heatmap — {direction.title()} · {port_label} · {year}",
            font=dict(color=C_BLUE,size=13), x=0.01),
        xaxis=dict(tickangle=30, tickfont=dict(size=9,color=TEXT_PRI),
                   gridcolor="rgba(0,0,0,0)"),
        yaxis=dict(tickfont=dict(size=9,color=TEXT_PRI), gridcolor="rgba(0,0,0,0)",
                   autorange="reversed"),
        margin=dict(l=14, r=100, t=56, b=80),
        legend=dict(orientation="h",y=-0.22),
    ))
    return fig

server = app.server 

if __name__ == "__main__":
    app.run(debug=True, port=8050)