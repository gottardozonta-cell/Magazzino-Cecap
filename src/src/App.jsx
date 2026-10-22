import { useEffect, useMemo, useState } from 'react';
import * as XLSX from 'xlsx';

function estraiGoogleInfo(url) {
  const sheet = url.match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/);
  if (sheet) return { tipo: 'sheet', id: sheet[1] };

  const drive =
    url.match(/\/file\/d\/([a-zA-Z0-9_-]+)/) ||
    url.match(/[?&]id=([a-zA-Z0-9_-]+)/);

  if (drive) return { tipo: 'drive', id: drive[1] };

  return null;
}

function leggiWorkbook(workbook) {
  const nomeFoglio = workbook.SheetNames[0];

  if (!nomeFoglio) {
    throw new Error('Il file non contiene fogli.');
  }

  const foglio = workbook.Sheets[nomeFoglio];

  return XLSX.utils.sheet_to_json(foglio, {
    defval: '',
    raw: false
  });
}

async function leggiFileExcel(file) {
  const buffer = await file.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array' });
  return leggiWorkbook(workbook);
}

async function scaricaSorgenteGoogle(url) {
  const info = estraiGoogleInfo(url);

  if (!info) {
    throw new Error(
      'Link non valido. Inserisci un link Google Sheets o un link a un file Excel su Google Drive.'
    );
  }

  let downloadUrl;

  if (info.tipo === 'sheet') {
    downloadUrl = `https://docs.google.com/spreadsheets/d/${info.id}/export?format=xlsx`;
  } else {
    downloadUrl = `https://drive.google.com/uc?export=download&id=${info.id}`;
  }

  const risposta = await fetch(downloadUrl);

  if (!risposta.ok) {
    throw new Error(
      'Impossibile scaricare il file. Controlla che sia condiviso con “Chiunque abbia il link”.'
    );
  }

  const buffer = await risposta.arrayBuffer();
  const workbook = XLSX.read(buffer, { type: 'array' });

  return {
    dati: leggiWorkbook(workbook),
    sorgente: {
      url,
      tipo: info.tipo,
      id: info.id
    }
  };
}

export default function App() {
  const [articoli, setArticoli] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('magazzino_articoli') || '[]');
    } catch {
      return [];
    }
  });

  const [urlGoogle, setUrlGoogle] = useState(() => {
    try {
      const sorgente = JSON.parse(localStorage.getItem('magazzino_sorgente') || 'null');
      return sorgente?.url || '';
    } catch {
      return '';
    }
  });

  const [ricerca, setRicerca] = useState('');
  const [stato, setStato] = useState('');
  const [caricamento, setCaricamento] = useState(false);
  const [ultimaImportazione, setUltimaImportazione] = useState(() => {
    return localStorage.getItem('magazzino_ultima_importazione') || '';
  });

  useEffect(() => {
    localStorage.setItem('magazzino_articoli', JSON.stringify(articoli));
  }, [articoli]);

  const colonne = useMemo(() => {
    if (articoli.length === 0) return [];
    return Object.keys(articoli[0]);
  }, [articoli]);

  const articoliFiltrati = useMemo(() => {
    const testo = ricerca.trim().toLowerCase();

    if (!testo) return articoli;

    return articoli.filter((articolo) =>
      Object.values(articolo).some((valore) =>
        String(valore).toLowerCase().includes(testo)
      )
    );
  }, [articoli, ricerca]);

  function salvaDati(dati) {
    setArticoli(dati);
    const data = new Date().toLocaleString('it-IT');
    setUltimaImportazione(data);
    localStorage.setItem('magazzino_ultima_importazione', data);
  }

  async function importaFileLocale(evento) {
    const file = evento.target.files?.[0];
    if (!file) return;

    setCaricamento(true);
    setStato('');

    try {
      const dati = await leggiFileExcel(file);
      salvaDati(dati);
      setStato(`Importati ${dati.length} articoli dal file ${file.name}.`);
    } catch (errore) {
      setStato(`Errore: ${errore.message}`);
    } finally {
      setCaricamento(false);
      evento.target.value = '';
    }
  }

  async function importaGoogle() {
    if (!urlGoogle.trim()) {
      setStato('Incolla prima un link Google Sheets o Google Drive.');
      return;
    }

    setCaricamento(true);
    setStato('');

    try {
      const risultato = await scaricaSorgenteGoogle(urlGoogle.trim());

      salvaDati(risultato.dati);
      localStorage.setItem(
        'magazzino_sorgente',
        JSON.stringify(risultato.sorgente)
      );

      setStato(`Sincronizzazione completata: ${risultato.dati.length} articoli importati.`);
    } catch (errore) {
      setStato(`Errore: ${errore.message}`);
    } finally {
      setCaricamento(false);
    }
  }

  function svuotaMagazzino() {
    if (!window.confirm('Vuoi eliminare tutti i dati del magazzino salvati nell’app?')) {
      return;
    }

    setArticoli([]);
    setRicerca('');
    setStato('Magazzino svuotato.');
    localStorage.removeItem('magazzino_articoli');
  }

  return (
    <main className="pagina">
      <header>
        <h1>📦 Magazzino Cecap</h1>
        <p>Importazione da Excel, Google Sheets e Google Drive.</p>
      </header>

      <section className="scheda">
        <h2>1. Importa file Excel dal dispositivo</h2>
        <p className="nota">
          Seleziona un file <strong>.xlsx</strong> o <strong>.xls</strong> salvato sul telefono o sul PC.
        </p>

        <input
          type="file"
          accept=".xlsx,.xls"
          onChange={importaFileLocale}
          disabled={caricamento}
        />
      </section>

      <section className="scheda">
        <h2>2. Collega Google Sheets oppure Google Drive</h2>
        <p className="nota">
          Incolla il link di un Google Foglio oppure di un file Excel salvato su Drive.
          Il file deve essere impostato come <strong>“Chiunque abbia il link - Visualizzatore”</strong>.
        </p>

        <div className="riga">
          <input
            className="campo-url"
            type="url"
            value={urlGoogle}
            placeholder="https://docs.google.com/spreadsheets/d/..."
            onChange={(e) => setUrlGoogle(e.target.value)}
            disabled={caricamento}
          />

          <button onClick={importaGoogle} disabled={caricamento}>
            {caricamento ? 'Importazione...' : 'Sincronizza ora'}
          </button>
        </div>
      </section>

      {stato && <div className="messaggio">{stato}</div>}

      <section className="scheda">
        <div className="titolo-tabella">
          <div>
            <h2>Articoli in magazzino: {articoli.length}</h2>
            {ultimaImportazione && (
              <p className="nota">Ultimo aggiornamento: {ultimaImportazione}</p>
            )}
          </div>

          <button className="pulsante-rosso" onClick={svuotaMagazzino}>
            Svuota dati
          </button>
        </div>

        {articoli.length > 0 && (
          <input
            className="ricerca"
            value={ricerca}
            onChange={(e) => setRicerca(e.target.value)}
            placeholder="Cerca codice, descrizione, quantità..."
          />
        )}

        {articoli.length === 0 ? (
          <p className="vuoto">Non hai ancora importato nessun file di magazzino.</p>
        ) : (
          <div className="tabella-contenitore">
            <table>
              <thead>
                <tr>
                  {colonne.map((colonna) => (
                    <th key={colonna}>{colonna}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {articoliFiltrati.map((articolo, indice) => (
                  <tr key={indice}>
                    {colonne.map((colonna) => (
                      <td key={colonna}>{String(articolo[colonna] ?? '')}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
