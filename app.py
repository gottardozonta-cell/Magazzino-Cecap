import streamlit as st
import pandas as pd
import re
from urllib.parse import parse_qs, urlparse

def converti_link_drive(url):
    """
    Converte i link condivisi di Fogli Google e dei file Drive in URL leggibili da pandas.
    """
    url = url.strip().strip("<>")
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
            return f"https://drive.google.com/uc?export=download&id={id_file}"

    return None

# Configurazione iniziale della pagina web
st.set_page_config(page_title="Gestore Inventario", layout="wide")

# Creiamo il menu laterale a sinistra
st.sidebar.header("Menu di Configurazione")
link_drive = st.sidebar.text_input("Incolla qui il link di Google Drive:")
file_excel = st.sidebar.file_uploader(
    "Oppure carica direttamente un file Excel (.xlsx):",
    type=["xlsx"],
)

# Titolo principale al centro della pagina
st.title("Gestione Inventario e Prodotti")

# Controlliamo se l'utente ha inserito un link o caricato un file
if file_excel or link_drive:
    link_diretto = converti_link_drive(link_drive) if link_drive and not file_excel else None

    if file_excel or link_diretto:
        try:
            # La riga 2 contiene le intestazioni reali delle colonne.
            df = pd.read_excel(file_excel or link_diretto, header=1)
            
            # Puliamo i dati rimuovendo le righe dove la colonna 'Nome Prodotto' è vuota
            df = df.dropna(subset=['Nome Prodotto'])
            
            # Rimuoviamo eventuali colonne completamente vuote senza nome
            df = df.loc[:, ~df.columns.str.contains('^Unnamed')]
            
            st.sidebar.success("File Excel caricato con successo!")

            # Mostriamo la tabella interattiva completa sullo schermo
            st.subheader("Tabella Completa dell'Inventario")
            st.dataframe(df, use_container_width=True)

            # Creiamo un filtro interattivo per Categoria
            st.markdown("---")
            st.subheader("Filtra i prodotti per categoria")
            
            # Estraiamo l'elenco di tutte le categorie uniche presenti nel file
            categorie_disponibili = df['Categoria'].dropna().unique()
            categoria_selezionata = st.selectbox("Seleziona una categoria dal menu:", categorie_disponibili)

            # Mostriamo solo i prodotti della categoria scelta
            df_filtrato = df[df['Categoria'] == categoria_selezionata]
            st.write(f"Prodotti trovati nella categoria **{categoria_selezionata}**:")
            st.dataframe(df_filtrato[['Nome Prodotto', 'Codice', 'Prezzo', 'Quantità']], use_container_width=True)
            
        except Exception as e:
            st.error(f"Errore durante la lettura del file: {e}")
            if not file_excel and "Name or service not known" in str(e):
                st.info(
                    "Il server non riesce a risolvere l'indirizzo di Google. "
                    "Scarica il foglio come file .xlsx e caricalo direttamente nel menu laterale, "
                    "oppure verifica la connessione DNS del server."
                )
            else:
                st.info("Nota: Assicurati che il file su Google Drive sia impostato su 'Chiunque abbia il link può visualizzare'.")
    else:
        st.sidebar.error("Link non riconosciuto. Incolla un link Google valido o carica un file Excel.")
else:
    # Messaggio mostrato all'avvio quando la casella del link è vuota
    st.info("👋 Benvenuto! Per iniziare, inserisci il link del tuo file Excel di Google Drive nel menu laterale a sinistra.")
