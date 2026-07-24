import streamlit as st
import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup

# Configurazione Pagina
st.set_page_config(page_title="Small Cap Screener", layout="wide")

st.title("🚀 Global Small-Cap Screener (3 Mesi)")
st.caption("Analisi automatizzata multifattoriale su azioni a piccola capitalizzazione.")

# --- LISTA SIMBOLI DA ANALIZZARE ---
TICKERS_DEFAULT = ["SOUN", "IONQ", "BLDP", "PLUG", "JOBY", "TECN.MI", "NEXI.MI"]

st.sidebar.header("⚙️ Parametri Algoritmo")
tickers_input = st.sidebar.text_area("Ticker da analizzare (separati da virgola):", ",".join(TICKERS_DEFAULT))
ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# Pesi dell'algoritmo
w_growth = st.sidebar.slider("Peso Spinta di Prezzo (%)", 0, 100, 50) / 100
w_momentum = st.sidebar.slider("Peso Momentum Tecnico (RSI) (%)", 0, 100, 50) / 100

# Funzione per recuperare i dati in modo nativo e sicuro
def fetch_stock_data(symbol):
    try:
        # Pulisci il formato ticker per API globale
        clean_symbol = symbol.replace('.MI', '')
        
        # Endpoint API finanziaria aperta a tolleranza elevata
        url = f"https://query2.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=3m"
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
            
        data = response.json()
        result = data.get('chart', {}).get('result', [])
        
        if not result:
            return None
            
        quote = result[0].get('indicators', {}).get('quote', [{}])[0]
        closes = quote.get('close', [])
        
        # Rimuovi valori None
        clean_closes = [c for c in closes if c is not None]
        
        if len(clean_closes) < 15:
            return None
            
        price = clean_closes[-1]
        price_1m_ago = clean_closes[-20] if len(clean_closes) >= 20 else clean_closes[0]
        
        # Calcolo Performance a 1 Mese
        perf_1m = ((price - price_1m_ago) / price_1m_ago) * 100
        
        # Calcolo RSI (14 giorni)
        df_close = pd.Series(clean_closes)
        delta = df_close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
        
        # Calcolo Medie Mobili
        sma20 = float(df_close.rolling(20).mean().iloc[-1])
        sma50 = float(df_close.rolling(50).mean().iloc[-1]) if len(df_close) >= 50 else sma20
        
        # Scoring
        mom_score = 50
        if price > sma20: mom_score += 25
        if price > sma50: mom_score += 25
        
        growth_score = min(max((perf_1m + 20) * 2, 0), 100)
        total_score = round((growth_score * w_growth) + (mom_score * w_momentum), 1)
        
        meta = result[0].get('meta', {})
        currency = meta.get('currency', '$')
        
        return {
            "Ticker": symbol,
            "Prezzo": f"{round(price, 2)} {currency}",
            "Perf. 1 Mese (%)": round(perf_1m, 1),
            "RSI (14d)": round(rsi, 1),
            "Sopra SMA20": "Sì" if price > sma20 else "No",
            "Score Totale": total_score
        }
    except Exception as e:
        return None

# --- ESECUZIONE ANALISI ---
if st.button("🔄 Avvia Analisi e Genera Classifica"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, t in enumerate(ticker_list):
        status_text.text(f"Analisi in corso per {t}...")
        data = fetch_stock_data(t)
        if data:
            results.append(data)
        progress_bar.progress((idx + 1) / len(ticker_list))
        
    status_text.empty()
    
    if results:
        df = pd.DataFrame(results)
        df = df.sort_values(by="Score Totale", ascending=False).reset_index(drop=True)
        df.index += 1
        
        st.subheader("🏆 Classifica Top Titoli")
        st.dataframe(
            df[["Ticker", "Prezzo", "Perf. 1 Mese (%)", "RSI (14d)", "Sopra SMA20", "Score Totale"]],
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("🔍 Scheda Dettagliata (Seleziona un titolo)")
        
        selected_ticker = st.selectbox("Seleziona il titolo per i dettagli:", df["Ticker"].tolist())
        stock_detail = df[df["Ticker"] == selected_ticker].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Score Totale", f"{stock_detail['Score Totale']} / 100")
        col2.metric("Performance 1 Mese", f"{stock_detail['Perf. 1 Mese (%)']}%")
        col3.metric("RSI (Momentum)", f"{stock_detail['RSI (14d)']}")

        st.markdown(f"### Dettaglio Analisi: **{stock_detail['Ticker']}**")
        st.write(f"- **Tendenza di Breve:** Variazione del **{stock_detail['Perf. 1 Mese (%)']}%** nell'ultimo mese.")
        st.write(f"- **Forza Relativa (RSI):** Valore **{stock_detail['RSI (14d)']}**.")
        st.write(f"- **Posizione Tecnico/Medie:** Sopra la media a 20 giorni: **{stock_detail['Sopra SMA20']}**.")
    else:
        st.error("Nessun dato recuperato. Prova a verificare i ticker o riavvia tra pochi istanti.")
        
