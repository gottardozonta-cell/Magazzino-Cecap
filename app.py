import streamlit as st
import pandas as pd
import re

def converti_link_drive(url):
    """
    Questo blocco di codice prende il link di condivisione di Google Drive 
    e lo trasforma in un link di download diretto che Python riesce a leggere.
    """
    match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
    if match:
        id_file = match.group(1)
        return f'https://google.com{id_file}/export?format=xlsx'
    return None

# Configurazione iniziale della pagina web
st.set_page_config(page_title="Gestore Inventario", layout="wide")

# Creiamo il menu laterale a sinistra
st.sidebar.header("Menu di Configurazione")
link_drive = st.sidebar.text_input("Incolla qui il link di Google Drive:")

# Titolo principale al centro della pagina
st.title("Gestione Inventario e Prodotti")

# Controlliamo se l'utente ha inserito il link
if link_drive:
    link_diretto = converti_link_drive(link_drive)
    
    if link_diretto:
        try:
            # Carichiamo l'Excel direttamente da internet usando il link convertito
            # 'header=1' dice a Python che i titoli veri delle colonne sono nella seconda riga del file (Riga 2)
            df = pd.read_excel(link_diretto, header=1)
            
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
            st.info("Nota: Assicurati che il file su Google Drive sia impostato su 'Chiunque abbia il link può visualizzare'.")
    else:
        st.sidebar.error("Il link inserito non sembra un link valido di Google Drive.")
else:
    # Messaggio mostrato all'avvio quando la casella del link è vuota
    st.info("👋 Benvenuto! Per iniziare, inserisci il link del tuo file Excel di Google Drive nel menu laterale a sinistra.")
