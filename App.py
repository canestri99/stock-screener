import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Dynamic Small-Cap Screener", layout="wide")

st.title("🛰️ Dynamic Market Small-Cap Screener")
st.caption("Scansione automatica dell'intero universo Small-Cap reale tramite API di Mercato Ufficiali.")

# --- CHIAVE API INTEGRATA ---
FMP_API_KEY = "ICeBE4Wh9Y795Dft93PWjwE0lxfzx8Wp"

# --- SIDEBAR: PARAMETRI ---
st.sidebar.header("⚙️ Parametri Screening")
top_n = st.sidebar.slider("Numero di opportunità da trovare:", 5, 20, 15)
min_price = st.sidebar.number_input("Prezzo Minimo ($):", value=2.0, step=0.5)
max_price = st.sidebar.number_input("Prezzo Massimo ($):", value=50.0, step=5.0)
min_market_cap = st.sidebar.number_input("Cap. di Mercato Minima ($M):", value=300, step=100) * 1000000
max_market_cap = st.sidebar.number_input("Cap. di Mercato Massima ($M):", value=2000, step=500) * 1000000

w_perf = st.sidebar.slider("Peso Momentum (%)", 0, 100, 50) / 100
w_high = st.sidebar.slider("Peso Volume/Liquidità (%)", 0, 100, 50) / 100

# Optional: permette di sovrascrivere l'API key dalla sidebar se necessario
user_api_key = st.sidebar.text_input("API Key (Opzionale):", value=FMP_API_KEY, type="password")
active_api_key = user_api_key if user_api_key else FMP_API_KEY

# --- FUNZIONE: SCANNER MERCATO VIA API ---
@st.cache_data(ttl=1800)
def fetch_screener_data(api_key, min_p, max_p, min_cap, max_cap):
    """Esegue uno screening automatico di mercato direttamente sulle API FMP"""
    url = f"https://financialmodelingprep.com/api/v3/stock-screener?marketCapMoreThan={min_cap}&marketCapLowerThan={max_cap}&priceMoreThan={min_p}&priceLowerThan={max_p}&isActivelyTrading=true&limit=200&apikey={api_key}"
    
    try:
        response = requests.get(url, timeout=12)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Errore di connessione API: {e}")
    return pd.DataFrame()

# --- BOTTONE ED ESECUZIONE ---
if st.button("🔍 Scansiona Mercato Reale Ora"):
    with st.spinner("Connessione ai feed di mercato via API ed estrazione dati Small-Cap in corso..."):
        df_raw = fetch_screener_data(active_api_key, min_price, max_price, min_market_cap, max_market_cap)
        
    if not df_raw.empty:
        # Pulizia e conversione dati numerici
        df_raw['changesPercentage'] = pd.to_numeric(df_raw['changesPercentage'], errors='coerce').fillna(0)
        df_raw['price'] = pd.to_numeric(df_raw['price'], errors='coerce')
        df_raw['volume'] = pd.to_numeric(df_raw['volume'], errors='coerce').fillna(0)
        
        # Algoritmo di Scoring basato su Variazione % e Attività/Volume
        df_raw['Score Momentum'] = np.clip((df_raw['changesPercentage'] + 10) * 4, 0, 100)
        df_raw['Score Liquidita'] = np.clip(np.log10(df_raw['volume'] + 1) * 15, 0, 100)
        
        df_raw['Score Potenziale'] = (df_raw['Score Momentum'] * w_perf) + (df_raw['Score Liquidita'] * w_high)
        df_raw['Score Potenziale'] = df_raw['Score Potenziale'].round(1)
        
        # Ordina per il punteggio migliore
        df_sorted = df_raw.sort_values(by="Score Potenziale", ascending=False).reset_index(drop=True)
        top_df = df_sorted.head(top_n).copy()
        top_df.index += 1
        
        # Rinomina colonne per una tabella chiara in italiano
        rename_dict = {
            'symbol': 'Ticker',
            'companyName': 'Nome Azienda',
            'price': 'Prezzo ($)',
            'changesPercentage': 'Perf. Giornaliera (%)',
            'marketCap': 'Cap. di Mercato ($)',
            'sector': 'Settore',
            'exchangeShortName': 'Borsa'
        }
        top_df = top_df.rename(columns=rename_dict)
        
        st.markdown("---")
        st.subheader(f"🏆 Top {len(top_df)} Opportunità Small-Cap Trovate Live")
        
        # Tabella Principale
        cols_to_show = ['Ticker', 'Nome Azienda', 'Prezzo ($)', 'Perf. Giornaliera (%)', 'Settore', 'Borsa', 'Score Potenziale']
        st.dataframe(
            top_df[[c for c in cols_to_show if c in top_df.columns]],
            use_container_width=True
        )
        
        st.markdown("---")
        st.subheader("📊 Dettaglio Scheda Titolo")
        selected = st.selectbox("Seleziona un'azienda trovata per analizzare la scheda:", top_df["Ticker"].tolist())
        stock = top_df[top_df["Ticker"] == selected].iloc[0]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Score Potenziale", f"{stock['Score Potenziale']} / 100")
        c2.metric("Prezzo Attuale", f"${stock['Prezzo ($)']}")
        c3.metric("Spinta Recente", f"{stock['Perf. Giornaliera (%)']}%")
        
        st.write(f"**Analisi per {stock['Nome Azienda']} ({stock['Ticker']}):**")
        st.write(f"- Settore di appartenenza: **{stock.get('Settore', 'N/A')}**")
        st.write(f"- Quotata su: **{stock.get('Borsa', 'N/A')}**")
        
        mcap = stock.get('Cap. di Mercato ($)', 0)
        if isinstance(mcap, (int, float)) and mcap > 0:
            st.write(f"- Capitalizzazione di mercato: **${mcap:,.0f}**")
    else:
        st.warning("Nessun titolo trovato con i parametri attuali o quota API momentaneamente esaurita.")
        
