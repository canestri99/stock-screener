import streamlit as st
import pandas as pd
import numpy as np
import requests

# Configurazione Pagina
st.set_page_config(page_title="Small Cap Screener", layout="wide")

st.title("🚀 Global Small-Cap Screener (3 Mesi)")
st.caption("Analisi automatizzata multifattoriale tramite Alpha Vantage API.")

# --- CHIAVE API INTEGRATA ---
API_KEY = "L7VMWM3OAU94RNBG"

# --- BARRA LATERALE ---
st.sidebar.header("⚙️ Parametri Algoritmo")
TICKERS_DEFAULT = ["SOUN", "IONQ", "BLDP", "PLUG", "JOBY"]
tickers_input = st.sidebar.text_area("Ticker da analizzare (separati da virgola):", ",".join(TICKERS_DEFAULT))
ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

w_growth = st.sidebar.slider("Peso Spinta di Prezzo (%)", 0, 100, 50) / 100
w_momentum = st.sidebar.slider("Peso Momentum Tecnico (%)", 0, 100, 50) / 100

# --- FUNZIONE D'ESTRAZIONE API ---
def fetch_stock_alpha_vantage(symbol):
    try:
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={API_KEY}"
        res = requests.get(url, timeout=12)
        
        if res.status_code != 200:
            return None
            
        data = res.json()
        time_series = data.get("Time Series (Daily)", {})
        
        if not time_series:
            return None
            
        # Estrai le date ordinate e i prezzi di chiusura
        dates = sorted(time_series.keys())
        closes = [float(time_series[d]["4. close"]) for d in dates]
        
        if len(closes) < 20:
            return None

        price = closes[-1]
        price_1m_ago = closes[-20] if len(closes) >= 20 else closes[0]
        
        # Performance a 1 Mese
        perf_1m = ((price - price_1m_ago) / price_1m_ago) * 100
        
        # Calcolo RSI (14d)
        df_close = pd.Series(closes)
        delta = df_close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
        
        # Medie Mobili
        sma20 = float(df_close.rolling(20).mean().iloc[-1])
        sma50 = float(df_close.rolling(50).mean().iloc[-1]) if len(df_close) >= 50 else sma20
        
        # Scoring
        mom_score = 50
        if price > sma20: mom_score += 25
        if price > sma50: mom_score += 25
        
        growth_score = min(max((perf_1m + 20) * 2, 0), 100)
        total_score = round((growth_score * w_growth) + (mom_score * w_momentum), 1)
        
        return {
            "Ticker": symbol,
            "Prezzo ($)": round(price, 2),
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
        status_text.text(f"Download dati Alpha Vantage per {t}...")
        data = fetch_stock_alpha_vantage(t)
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
            df[["Ticker", "Prezzo ($)", "Perf. 1 Mese (%)", "RSI (14d)", "Sopra SMA20", "Score Totale"]],
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
        st.error("Nessun dato recuperato. Nota: le API gratuite di Alpha Vantage permettono fino a 5 chiamate al minuto. Attendi 30 secondi e riprova.")
        
