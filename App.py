import streamlit as st
import pandas as pd
import numpy as np
from pandas_datareader import data as pdr
from datetime import datetime, timedelta

# Configurazione Pagina
st.set_page_config(page_title="Small Cap Screener", layout="wide")

st.title("🚀 Global Small-Cap Screener (3 Mesi)")
st.caption("Analisi automatizzata multifattoriale su azioni a piccola capitalizzazione tramite provider Stooq.")

# --- LISTA SIMBOLI DA ANALIZZARE ---
TICKERS_DEFAULT = ["TECN.MI", "SOUN", "IONQ", "NEXI.MI", "BLDP", "PLUG", "JOBY"]

st.sidebar.header("⚙️ Parametri Algoritmo")
tickers_input = st.sidebar.text_area("Ticker da analizzare (separati da virgola):", ",".join(TICKERS_DEFAULT))
ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# Pesi dell'algoritmo
w_growth = st.sidebar.slider("Peso Spinta di Prezzo (%)", 0, 100, 50) / 100
w_momentum = st.sidebar.slider("Peso Momentum Tecnico (RSI) (%)", 0, 100, 50) / 100

# Funzione per recuperare i dati da Stooq
def get_stooq_data(ticker):
    try:
        # Definizione intervallo temporale (6 mesi)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        
        # Scarica dati storici
        df = pdr.DataReader(ticker, 'stooq', start=start_date, end=end_date)
        
        if df.empty or len(df) < 20:
            return None
            
        # Stooq restituisce i dati in ordine decrescente, li invertiamo
        df = df.sort_index(ascending=True)
        
        closes = df['Close']
        price = float(closes.iloc[-1])
        price_1m_ago = float(closes.iloc[-20]) if len(closes) >= 20 else float(closes.iloc[0])
        
        # Calcolo Performance a 1 Mese
        perf_1m = ((price - price_1m_ago) / price_1m_ago) * 100
        
        # Calcolo RSI (14 giorni)
        delta = closes.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
        
        # Calcolo Medie Mobili
        sma20 = float(closes.rolling(20).mean().iloc[-1])
        sma50 = float(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else sma20
        
        # Scoring
        mom_score = 50
        if price > sma20: mom_score += 25
        if price > sma50: mom_score += 25
        
        growth_score = min(max((perf_1m + 20) * 2, 0), 100)
        
        total_score = round((growth_score * w_growth) + (mom_score * w_momentum), 1)
        
        return {
            "Ticker": ticker,
            "Prezzo ($/€)": round(price, 2),
            "Perf. 1 Mese (%)": round(perf_1m, 1),
            "RSI (14d)": round(rsi, 1),
            "Sopra SMA20": "Sì" if price > sma20 else "No",
            "Score Totale": total_score
        }
    except Exception:
        return None

# --- ESECUZIONE ANALISI ---
if st.button("🔄 Avvia Analisi e Genera Classifica"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, t in enumerate(ticker_list):
        status_text.text(f"Scaricamento dati per {t} da Stooq...")
        data = get_stooq_data(t)
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
            df[["Ticker", "Prezzo ($/€)", "Perf. 1 Mese (%)", "RSI (14d)", "Sopra SMA20", "Score Totale"]],
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
        st.write(f"- **Tendenza di Breve:** Il titolo ha registrato una variazione del **{stock_detail['Perf. 1 Mese (%)']}%** nell'ultimo mese.")
        st.write(f"- **Forza Relativa (RSI):** Il valore attuale è **{stock_detail['RSI (14d)']}** (valori tra 50 e 65 indicano spinta rialzista senza ipercomprato).")
        st.write(f"- **Posizione Tecnico/Medie:** Il prezzo è attualmente sopra la media a 20 giorni: **{stock_detail['Sopra SMA20']}**.")
    else:
        st.error("Nessun dato trovato. Assicurati che il file requirements.txt contenga 'pandas-datareader'.")
        
