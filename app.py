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
COLONNE_DETTAGLIO = [
    "Nome Prodotto",
    "Codice",
    "Codice a Barre",
    "Quantita",
    "Prezzo",
    "Foto",
]
NOMI_COLONNA_FOTO = ["foto", "immagine", "image", "img", "picture", "url foto", "link foto"]


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


def normalizza_url_immagine(valore):
    """Estrae un URL immagine da cella (URL puro o formula IMAGE)."""
    if valore is None or (isinstance(valore, float) and pd.isna(valore)):
        return None
    testo = str(valore).strip()
    if not testo or testo.lower() in {"nan", "none", ""}:
        return None

    # Formula tipo =IMAGE("https://...")
    m = re.search(r'IMAGE\s*\(\s*["\']?(https?://[^"\')\s]+)', testo, re.IGNORECASE)
    if m:
        testo = m.group(1)

    if not re.match(r"^https?://", testo, re.IGNORECASE):
        return None

    # Converte link Drive "view" in link diretto immagine
    parsed = urlparse(testo)
    host = (parsed.hostname or "").lower()
    if "drive.google.com" in host:
        match = re.match(r"^/file/d/([a-zA-Z0-9_-]+)", parsed.path or "")
        id_file = match.group(1) if match else parse_qs(parsed.query).get("id", [None])[0]
        if id_file:
            return f"https://drive.google.com/uc?export=view&id={id_file}"
    return testo


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

    obiettivo_no_accent = (
        obiettivo.replace("à", "a")
        .replace("è", "e")
        .replace("é", "e")
        .replace("ì", "i")
        .replace("ò", "o")
        .replace("ù", "u")
    )
    for colonna in df.columns:
        c = pulisci(colonna)
        c = (
            c.replace("à", "a")
            .replace("è", "e")
            .replace("é", "e")
            .replace("ì", "i")
            .replace("ò", "o")
            .replace("ù", "u")
        )
        if c == obiettivo_no_accent:
            return colonna
    return None


def trova_colonna_foto(df):
    """Cerca una colonna che contenga URL di immagini."""
    for nome in NOMI_COLONNA_FOTO:
        col = trova_colonna(df, nome)
        if col is not None:
            return col

    # Se non c'e' un nome chiaro, cerca una colonna con URL
    for col in df.columns:
        campione = df[col].dropna().astype(str).head(15)
        if len(campione) == 0:
            continue
        url_count = sum(1 for v in campione if normalizza_url_immagine(v))
        if url_count >= max(1, len(campione) // 3):
            return col
    return None


@st.cache_data(show_spinner="Caricamento del file in corso...")
def leggi_da_bytes(contenuto, riga_intestazione):
    return pd.read_excel(
        io.BytesIO(contenuto), header=riga_intestazione, engine="openpyxl"
    )


@st.cache_data(ttl=300, show_spinner="Download del file da Google in corso...")
def leggi_da_url(url, riga_intestazione):
    return pd.read_excel(url, header=riga_intestazione, engine="openpyxl")


# ---------------------------------------------------------------------------
# Menu laterale
# ---------------------------------------------------------------------------
st.sidebar.header("Menu di Configurazione")
link_drive = st.sidebar.text_input(
    "Incolla qui il link di Google Drive:",
    value="",
)
file_excel = st.sidebar.file_uploader(
    "Oppure carica direttamente un file Excel (.xlsx):",
    type=["xlsx"],
)

riga_intestazioni = st.sidebar.number_input(
    "Riga che contiene le intestazioni delle colonne:",
    min_value=1,
    max_value=50,
    value=1,
    step=1,
    help="Di base e' 1. Cambialo solo se le intestazioni sono piu' in basso.",
)

if st.sidebar.button("Ricarica dati da Google"):
    leggi_da_url.clear()

st.title("Gestione Inventario e Prodotti")

# ---------------------------------------------------------------------------
# Nessun input
# ---------------------------------------------------------------------------
if not file_excel and not link_drive:
    st.info(
        "Benvenuto! Inserisci il link del foglio Google Drive nel menu laterale "
        "oppure carica un file .xlsx."
    )
    st.caption(
        "Per le foto: metti gli URL pubblici delle immagini in una colonna chiamata "
        "**Foto** (oppure Immagine). Le immagini inserite solo come 'immagine nella cella' "
        "senza URL non possono essere lette dall'app."
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
        "Manca la libreria openpyxl. Aggiungi openpyxl al requirements.txt e riavvia l'app."
    )
    st.stop()
except Exception as e:
    messaggio = str(e)
    st.error(f"Errore durante la lettura del file: {messaggio}")
    if not file_excel and (
        "Name or service not known" in messaggio or "Temporary failure" in messaggio
    ):
        st.info(
            "Il server non riesce a raggiungere Google. Scarica il foglio come .xlsx "
            "e caricalo dal menu laterale."
        )
    elif not file_excel:
        st.info(
            "Assicurati che il file sia condiviso come "
            "'Chiunque abbia il link puo visualizzare'."
        )
    st.stop()

df = normalizza_colonne(df)

# ---------------------------------------------------------------------------
# Colonne obbligatorie
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
        "Se le intestazioni sono in un'altra riga, cambia il numero nel menu laterale."
    )
    st.stop()

df = df.dropna(subset=[col_nome]).reset_index(drop=True)

# Rimuove eventuale riga "totale"
df = df[~df[col_nome].astype(str).str.strip().str.lower().eq("totale")].reset_index(
    drop=True
)

# Colonna foto (se presente)
col_foto = trova_colonna_foto(df)
if col_foto is not None:
    df["_foto_url"] = df[col_foto].map(normalizza_url_immagine)
else:
    df["_foto_url"] = None

st.sidebar.success(f"File caricato con successo! ({len(df)} prodotti)")
if col_foto is None:
    st.sidebar.warning(
        "Nessuna colonna Foto con URL trovata. "
        "Aggiungi una colonna 'Foto' con i link delle immagini."
    )
else:
    n_foto = df["_foto_url"].notna().sum()
    st.sidebar.info(f"Colonna foto: '{col_foto}' ({n_foto} immagini con URL valido)")

# ---------------------------------------------------------------------------
# Tabella completa
# ---------------------------------------------------------------------------
st.subheader("Tabella Completa dell'Inventario")

colonne_tabella = []
for nome in COLONNE_DETTAGLIO:
    if nome.lower() in {"foto", "immagine"}:
        continue
    c = trova_colonna(df, nome)
    if c and c not in colonne_tabella:
        colonne_tabella.append(c)

df_view = df[colonne_tabella].copy()
if col_foto is not None and df["_foto_url"].notna().any():
    df_view.insert(0, "Foto", df["_foto_url"])

column_config = {}
if "Foto" in df_view.columns:
    column_config["Foto"] = st.column_config.ImageColumn("Foto", width="small")

st.dataframe(
    df_view,
    use_container_width=True,
    hide_index=True,
    column_config=column_config if column_config else None,
)

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
].copy()

st.write(
    f"Prodotti trovati nella categoria **{categoria_selezionata}**: {len(df_filtrato)}"
)

# Vista a schede con foto (piu' comoda)
mostra_schede = st.toggle("Mostra come schede con foto", value=True)

if mostra_schede:
    if df_filtrato.empty:
        st.info("Nessun prodotto in questa categoria.")
    else:
        n_cols = 3
        cols = st.columns(n_cols)
        for i, (_, row) in enumerate(df_filtrato.iterrows()):
            with cols[i % n_cols]:
                with st.container(border=True):
                    url_foto = row.get("_foto_url")
                    if url_foto:
                        st.image(url_foto, use_container_width=True)
                    else:
                        st.caption("Nessuna foto")

                    nome = row.get(col_nome, "")
                    st.markdown(f"**{nome}**")

                    pezzi = []
                    for label, chiave in [
                        ("Codice", "Codice"),
                        ("Barcode", "Codice a Barre"),
                        ("Formato", "Quantita"),
                        ("Prezzo", "Prezzo"),
                    ]:
                        c = trova_colonna(df, chiave)
                        if c and pd.notna(row.get(c)) and str(row.get(c)).strip():
                            pezzi.append(f"{label}: {row.get(c)}")
                    if pezzi:
                        st.caption("  \n".join(pezzi))
else:
    df_f_view = df_filtrato[colonne_tabella].copy()
    if col_foto is not None and df_filtrato["_foto_url"].notna().any():
        df_f_view.insert(0, "Foto", df_filtrato["_foto_url"].values)

    st.dataframe(
        df_f_view,
        use_container_width=True,
        hide_index=True,
        column_config=column_config if column_config else None,
    )
