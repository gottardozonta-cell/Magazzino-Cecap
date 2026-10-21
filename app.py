import io
import re
from urllib.parse import parse_qs, urlparse

import pandas as pd
import streamlit as st

# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Gestore Inventario", layout="wide")

COLONNA_NOME = "Nome Prodotto"
COLONNA_CATEGORIA = "Categoria"
COLONNE_DETTAGLIO = ["Nome Prodotto", "Codice", "Prezzo", "Quantita"]


# ---------------------------------------------------------------------------
# Funzioni di supporto
# ---------------------------------------------------------------------------
def converti_link_drive(url):
    """Converte i link di Fogli Google / Drive in URL scaricabili da pandas."""
    url = (url or "").strip().strip("<>")
    if not url:
        return None
    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"

    parsed_url = urlparse(url)
    host = (parsed_url.hostname or "").lower()

    if host in {"docs.google.com", "www.docs.google.com"}:
        match = re.match(
            r"^/spreadsheets/(?:u/\d+/)?d/([a-zA-Z0-9_-]+)(?:/|$)",
            parsed_url.path,
        )
        if match:
            id_file = match.group(1)
            return f"https://docs.google.com/spreadsheets/d/{id_file}/export?format=xlsx"

    if host in {"drive.google.com", "www.drive.google.com"}:
        match = re.match(r"^/file/d/([a-zA-Z0-9_-]+)(?:/|$)", parsed_url.path)
        id_file = match.group(1) if match else parse_qs(parsed_url.query).get("id", [None])[0]
        if id_file and re.fullmatch(r"[a-zA-Z0-9_-]+", id_file):
            return f"https://drive.google.com/uc?export=download&confirm=t&id={id_file}"

    return None


def normalizza_colonne(df):
    """Converte le intestazioni in testo, toglie spazi e rimuove colonne vuote/Unnamed."""
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    da_tenere = [
        not (c.startswith("Unnamed") or c == "" or c.lower() == "nan")
        for c in df.columns
    ]
    df = df.loc[:, da_tenere]
    df = df.dropna(axis=1, how="all")
    return df


def trova_colonna(df, nome_cercato):
    """Trova una colonna ignorando maiuscole/minuscole e spazi multipli."""
    def pulisci(testo):
        return re.sub(r"\s+", " ", str(testo)).strip().casefold()

    obiettivo = pulisci(nome_cercato)
    for colonna in df.columns:
        if pulisci(colonna) == obiettivo:
            return colonna
    # Prova anche senza accenti (Quantita / Quantita)
    obiettivo_no_accent = obiettivo.replace("à", "a").replace("è", "e").replace("é", "e")
    for colonna in df.columns:
        c = pulisci(colonna).replace("à", "a").replace("è", "e").replace("é", "e")
        if c == obiettivo_no_accent:
            return colonna
    return None


@st.cache_data(show_spinner="Caricamento del file in corso...")
def leggi_da_bytes(contenuto, riga_intestazione):
    return pd.read_excel(io.BytesIO(contenuto), header=riga_intestazione, engine="openpyxl")


@st.cache_data(ttl=300, show_spinner="Download del file da Google in corso...")
def leggi_da_url(url, riga_intestazione):
    return pd.read_excel(url, header=riga_intestazione, engine="openpyxl")


# ---------------------------------------------------------------------------
# Menu laterale
# ---------------------------------------------------------------------------
st.sidebar.header("Menu di Configurazione")
link_drive = st.sidebar.text_input("Incolla qui il link di Google Drive:")
file_excel = st.sidebar.file_uploader(
    "Oppure carica direttamente un file Excel (.xlsx):",
    type=["xlsx"],
)
riga_intestazioni = st.sidebar.number_input(
    "Riga che contiene le intestazioni delle colonne:",
    min_value=1,
    max_value=50,
    value=2,
    step=1,
    help="Nel file originale le intestazioni sono nella riga 2.",
)
if st.sidebar.button("Ricarica dati da Google"):
    leggi_da_url.clear()

st.title("Gestione Inventario e Prodotti")

# ---------------------------------------------------------------------------
# Nessun input: messaggio di benvenuto
# ---------------------------------------------------------------------------
if not file_excel and not link_drive:
    st.info(
        "Benvenuto! Per iniziare, inserisci il link del tuo file Excel di "
        "Google Drive nel menu laterale a sinistra, oppure carica un file .xlsx."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Caricamento dati
# ---------------------------------------------------------------------------
header_index = int(riga_intestazioni) - 1

try:
    if file_excel:
        df = leggi_da_bytes(file_excel.getvalue(), header_index)
    else:
        link_diretto = converti_link_drive(link_drive)
        if not link_diretto:
            st.sidebar.error(
                "Link non riconosciuto. Incolla un link Google valido o carica un file Excel."
            )
            st.stop()
        df = leggi_da_url(link_diretto, header_index)
except ImportError:
    st.error(
        "Manca la libreria openpyxl. Aggiungi la riga openpyxl al file "
        "requirements.txt del repository e riavvia l'app."
    )
    st.stop()
except Exception as e:
    messaggio = str(e)
    st.error(f"Errore durante la lettura del file: {messaggio}")
    if not file_excel and (
        "Name or service not known" in messaggio or "Temporary failure" in messaggio
    ):
        st.info(
            "Il server non riesce a raggiungere Google. Scarica il foglio come file "
            ".xlsx e caricalo direttamente nel menu laterale."
        )
    elif not file_excel:
        st.info(
            "Assicurati che il file su Google Drive sia condiviso come "
            "'Chiunque abbia il link puo visualizzare' e che sia un file Excel/Foglio Google."
        )
    st.stop()

df = normalizza_colonne(df)

# ---------------------------------------------------------------------------
# Controllo colonne obbligatorie
# ---------------------------------------------------------------------------
col_nome = trova_colonna(df, COLONNA_NOME)
col_categoria = trova_colonna(df, COLONNA_CATEGORIA)

mancanti = [
    nome
    for nome, trovata in [(COLONNA_NOME, col_nome), (COLONNA_CATEGORIA, col_categoria)]
    if trovata is None
]
if mancanti:
    st.error(f"Nel file mancano queste colonne obbligatorie: {', '.join(mancanti)}")
    st.write("Colonne trovate nel file:", list(df.columns))
    st.info(
        "Probabilmente le intestazioni sono in una riga diversa: "
        "modifica il valore 'Riga che contiene le intestazioni' nel menu laterale."
    )
    st.stop()

df = df.dropna(subset=[col_nome]).reset_index(drop=True)
st.sidebar.success(f"File caricato con successo! ({len(df)} prodotti)")

# ---------------------------------------------------------------------------
# Tabella completa
# ---------------------------------------------------------------------------
st.subheader("Tabella Completa dell'Inventario")
st.dataframe(df, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Filtro per categoria
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Filtra i prodotti per categoria")

categorie_disponibili = sorted(
    df[col_categoria].dropna().astype(str).str.strip().unique()
)

if not categorie_disponibili:
    st.warning("Nessuna categoria trovata nel file.")
    st.stop()

categoria_selezionata = st.selectbox(
    "Seleziona una categoria dal menu:", categorie_disponibili
)

df_filtrato = df[
    df[col_categoria].astype(str).str.strip() == categoria_selezionata
]

colonne_da_mostrare = []
colonne_assenti = []
for nome in COLONNE_DETTAGLIO:
    trovata = trova_colonna(df, nome)
    if trovata:
        colonne_da_mostrare.append(trovata)
    else:
        colonne_assenti.append(nome)

st.write(
    f"Prodotti trovati nella categoria **{categoria_selezionata}**: {len(df_filtrato)}"
)
st.dataframe(
    df_filtrato[colonne_da_mostrare], use_container_width=True, hide_index=True
)

if colonne_assenti:
    st.caption(
        "Colonne non presenti nel file e quindi non mostrate: "
        + ", ".join(colonne_assenti)
    )
