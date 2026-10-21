Sì. **Sostituisci tutto il contenuto del file principale** su GitHub (per esempio `app.py`) con questo codice:

```python
import io
import re
import unicodedata
import zipfile
from urllib.parse import parse_qs, urlencode, urlparse

import pandas as pd
import requests
import streamlit as st


st.set_page_config(page_title="Gestore Inventario", layout="wide")


def converti_link_drive(url):
    """Converte i link di Fogli Google o Drive in link di download XLSX."""
    if not url:
        return None

    url = str(url).strip().strip("<>").strip()

    if not re.match(r"^https?://", url, re.IGNORECASE):
        url = f"https://{url}"

    parsed_url = urlparse(url)
    host = (parsed_url.hostname or "").lower()
    parametri = parse_qs(parsed_url.query)
    resource_key = parametri.get("resourcekey", [None])[0]

    # Link a un Foglio Google
    if host in {"docs.google.com", "www.docs.google.com"}:
        match = re.search(
            r"/spreadsheets/(?:u/\d+/)?d/([A-Za-z0-9_-]+)(?:/|$)",
            parsed_url.path,
        )

        if match:
            id_file = match.group(1)
            query = {"format": "xlsx"}

            if resource_key:
                query["resourcekey"] = resource_key

            return (
                f"https://docs.google.com/spreadsheets/d/{id_file}/export?"
                f"{urlencode(query)}"
            )

    # Link a un file caricato su Google Drive
    if host in {"drive.google.com", "www.drive.google.com"}:
        match = re.match(
            r"^/file/d/([A-Za-z0-9_-]+)(?:/|$)",
            parsed_url.path,
        )

        id_file = (
            match.group(1)
            if match
            else parametri.get("id", [None])[0]
        )

        if id_file and re.fullmatch(r"[A-Za-z0-9_-]+", id_file):
            query = {
                "export": "download",
                "id": id_file,
            }

            if resource_key:
                query["resourcekey"] = resource_key

            return f"https://drive.google.com/uc?{urlencode(query)}"

    return None


@st.cache_data(ttl=60, show_spinner=False)
def leggi_excel_da_url(url, riga_intestazioni):
    """Scarica e legge un file XLSX da Google."""
    risposta = requests.get(
        url,
        timeout=(10, 45),
        allow_redirects=True,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    risposta.raise_for_status()

    contenuto = risposta.content

    if not contenuto:
        raise ValueError("Il file scaricato è vuoto.")

    if not zipfile.is_zipfile(io.BytesIO(contenuto)):
        raise ValueError(
            "Google non ha restituito un file Excel .xlsx. "
            "Controlla la condivisione del file oppure scaricalo e caricalo "
            "direttamente nell'app."
        )

    return pd.read_excel(
        io.BytesIO(contenuto),
        header=riga_intestazioni,
        engine="openpyxl",
    )


def pulisci_colonne(df):
    """Normalizza le intestazioni ed elimina quelle vuote o 'Unnamed'."""
    df = df.copy()
    indici_da_tenere = []
    nomi_colonne = []
    nomi_usati = set()

    for indice, colonna in enumerate(df.columns):
        try:
            colonna_mancante = bool(pd.isna(colonna))
        except (TypeError, ValueError):
            colonna_mancante = False

        nome = "" if colonna_mancante else str(colonna).strip()

        if not nome or nome.casefold().startswith("unnamed"):
            continue

        # Evita errori se due intestazioni diventano uguali dopo la pulizia.
        nome_base = nome
        suffisso = 2

        while nome.casefold() in nomi_usati:
            nome = f"{nome_base} ({suffisso})"
            suffisso += 1

        nomi_usati.add(nome.casefold())
        indici_da_tenere.append(indice)
        nomi_colonne.append(nome)

    df = df.iloc[:, indici_da_tenere].copy()
    df.columns = nomi_colonne
    return df.dropna(axis=1, how="all")


def chiave_colonna(nome):
    """Confronta intestazioni ignorando maiuscole, spazi e accenti."""
    testo = unicodedata.normalize("NFKD", str(nome))
    testo = "".join(
        carattere
        for carattere in testo
        if not unicodedata.combining(carattere)
    )
    return re.sub(r"\s+", " ", testo).strip().casefold()


def trova_colonna(df, nome_cercato):
    """Restituisce il nome effettivo della colonna, se presente."""
    chiave = chiave_colonna(nome_cercato)

    for colonna in df.columns:
        if chiave_colonna(colonna) == chiave:
            return colonna

    return None


# Sidebar
st.sidebar.header("Menu di configurazione")

link_drive = st.sidebar.text_input(
    "Incolla qui il link di Google Drive:"
).strip()

file_excel = st.sidebar.file_uploader(
    "Oppure carica direttamente un file Excel (.xlsx):",
    type=["xlsx"],
)

riga_intestazioni = st.sidebar.number_input(
    "Riga delle intestazioni nel file Excel",
    min_value=1,
    max_value=100,
    value=2,
    step=1,
    help="Il valore iniziale è 2, come nel file originale. Se le intestazioni "
         "sono sulla prima riga, seleziona 1.",
)

if st.sidebar.button("🔄 Aggiorna dati dal link Google"):
    leggi_excel_da_url.clear()


# Contenuto principale
st.title("Gestione Inventario e Prodotti")

if file_excel is None and not link_drive:
    st.info(
        "👋 Benvenuto! Inserisci un link Google Drive nel menu laterale "
        "oppure carica un file Excel .xlsx."
    )
    st.stop()

link_diretto = None

if file_excel is None:
    link_diretto = converti_link_drive(link_drive)

    if not link_diretto:
        st.sidebar.error(
            "Link non riconosciuto. Incolla un link valido a un Foglio Google "
            "o a un file Google Drive."
        )
        st.stop()


# Lettura del file
try:
    with st.spinner("Caricamento del file Excel..."):
        indice_intestazioni = int(riga_intestazioni) - 1

        if file_excel is not None:
            df = pd.read_excel(
                io.BytesIO(file_excel.getvalue()),
                header=indice_intestazioni,
                engine="openpyxl",
            )
            st.sidebar.success("File Excel caricato con successo!")
        else:
            df = leggi_excel_da_url(link_diretto, indice_intestazioni)
            st.sidebar.success("File Google caricato con successo!")

except requests.exceptions.Timeout:
    st.error("Il download da Google è scaduto. Riprova tra poco.")
    st.info(
        "Puoi anche scaricare il file in formato .xlsx e caricarlo "
        "direttamente dal menu laterale."
    )
    st.stop()

except requests.exceptions.RequestException as errore:
    st.error(f"Non è stato possibile scaricare il file da Google: {errore}")
    st.info(
        "Verifica che il file sia accessibile con il link oppure carica "
        "direttamente il file .xlsx."
    )
    st.stop()

except Exception as errore:
    st.error(f"Errore durante la lettura del file: {errore}")
    st.info(
        "Controlla che il file sia un .xlsx valido e che la riga indicata "
        "nel menu laterale contenga le intestazioni."
    )
    st.stop()


# Pulizia e controllo delle colonne
df = pulisci_colonne(df)

colonna_nome = trova_colonna(df, "Nome Prodotto")

if colonna_nome is None:
    st.error("Non trovo la colonna obbligatoria 'Nome Prodotto'.")
    st.write("Intestazioni rilevate nel file:", list(df.columns))
    st.info(
        "Controlla la riga delle intestazioni nel menu laterale e verifica "
        "che il file contenga una colonna chiamata 'Nome Prodotto'."
    )
    st.stop()


# Elimina le righe senza nome prodotto
maschera_prodotti = (
    df[colonna_nome].notna()
    & df[colonna_nome].astype("string").str.strip().ne("")
)
df = df.loc[maschera_prodotti.fillna(False)].copy()

if df.empty:
    st.warning("Il file è stato letto, ma non contiene prodotti da mostrare.")
    st.stop()


# Tabella completa
st.subheader("Tabella completa dell'inventario")
st.dataframe(df, width="stretch")


# Filtro per categoria
colonna_categoria = trova_colonna(df, "Categoria")

if colonna_categoria is None:
    st.warning(
        "Non trovo la colonna 'Categoria': mostro la tabella completa "
        "senza filtro."
    )
    st.stop()

categorie = [
    categoria
    for categoria in df[colonna_categoria].dropna().unique().tolist()
    if not (isinstance(categoria, str) and not categoria.strip())
]

if not categorie:
    st.warning(
        "La colonna 'Categoria' è presente, ma non contiene categorie "
        "da selezionare."
    )
    st.stop()

st.markdown("---")
st.subheader("Filtra i prodotti per categoria")

categoria_selezionata = st.selectbox(
    "Seleziona una categoria:",
    options=categorie,
)

maschera_categoria = (
    df[colonna_categoria]
    .eq(categoria_selezionata)
    .fillna(False)
)
df_filtrato = df.loc[maschera_categoria].copy()

st.write(
    f"Categoria selezionata: {categoria_selezionata} — "
    f"prodotti trovati: {len(df_filtrato)}"
)

# Mostra le colonne di dettaglio disponibili nel file
nomi_dettaglio = [
    "Nome Prodotto",
    "Codice",
    "Prezzo",
    "Quantità",
]

colonne_dettaglio = []
colonne_mancanti = []

for nome in nomi_dettaglio:
    colonna = trova_colonna(df_filtrato, nome)

    if colonna is None:
        if nome != "Nome Prodotto":
            colonne_mancanti.append(nome)
    elif colonna not in colonne_dettaglio:
        colonne_dettaglio.append(colonna)

if colonne_mancanti:
    st.caption(
        "Colonne facoltative non presenti: "
        + ", ".join(colonne_mancanti)
    )

st.dataframe(
    df_filtrato[colonne_dettaglio],
    width="stretch",
)
```

Se nel repository **non esiste già** un `requirements.txt`, aggiungilo nella cartella principale con questo contenuto:

```text
streamlit>=1.51
pandas>=2.0
openpyxl>=3.1
requests>=2.31
```

Il codice conserva l’impostazione delle intestazioni alla riga 2, ma puoi cambiarla dal menu laterale. Il link Google viene memorizzato in cache per 60 secondi; il pulsante **“Aggiorna dati dal link Google”** la svuota. Streamlit documenta la cache dei dati e il metodo per cancellarla; pandas indica `openpyxl` come motore per i file `.xlsx`. 

In GitHub, sostituisci il file principale indicato nelle impostazioni dell’app, incolla il codice e fai **Commit changes**.
