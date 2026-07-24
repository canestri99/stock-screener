import streamlit as st
import pandas as pd
import numpy as np
import requests
import json

# Configurazione Pagina
st.set_page_config(page_title="Small Cap Screener", layout="wide")

st.title("🚀 Global Small-Cap Screener (3 Mesi)")
st.caption("Analisi automatizzata multifattoriale su azioni a piccola capitalizzazione.")

# --- LISTA SIMBOLI DA ANALIZZARE ---
TICKERS_DEFAULT = ["TECN.MI", "SOUN", "IONQ", "NEXI.MI", "BLDP", "PLUG", "JOBY"]

st.sidebar.header("⚙️ Parametri Algoritmo")
tickers_input = st.sidebar.text_area("Ticker da analizzare (separati da virgola):", ",".join(TICKERS_DEFAULT))
ticker_list = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

# Pesi dell'algoritmo
w_growth = st.sidebar.slider("Peso Valutazione/Target (%)", 0, 100, 40) / 100
w_momentum = st.sidebar.slider("Peso Momentum Tecnico (%)", 0, 100, 40) / 100
w_health = st.sidebar.slider("Peso Salute Finanziaria (%)", 0, 100, 20) / 100

# --- FUNZIONE D'ESTRAZIONE CON USER-AGENT ---
def get_yahoo_data(symbol):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    # 1. Recupero Storico Prezzi (per RSI e Medie Mobili)
    chart_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=6m"
    res_chart = requests.get(chart_url, headers=headers, timeout=10)
    if res_chart.status_code != 200:
        return None
        
    data_chart = res_chart.json()
    result = data_chart.get('chart', {}).get('result', [])
    if not result:
        return None
        
    timestamps = result[0].get('timestamp', [])
    quote = result[0].get('indicators', {}).get('quote', [{}])[0]
    closes = quote.get('close', [])
    
    # Rimuovi valori Noni
    clean_closes = [c for c in closes if c is not None]
    if len(clean_closes) < 20:
        return None
        
    price = clean_closes[-1]
    
    # 2. Recupero Dati Fondamentali e Target
    target_price = price
    debt_to_equity = 100
    mcap_val = 0
    short_name = symbol
    sector = "N/D"
    
    try:
        quote_url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}"
        res_quote = requests.get(quote_url, headers=headers, timeout=10)
        if res_quote.status_code == 200:
            q_data = res_quote.json().get('quoteResponse', {}).get('result', [])
            if q_data:
                item = q_data[0]
                target_price = item.get('targetPriceMean', price)
                short_name = item.get('shortName', symbol)
                mcap_val = item.get('marketCap', 0) / 1e6
    except Exception:
        pass

    # Calcolo indicatori tecnici (RSI, Medie Mobili)
    df_close = pd.Series(clean_closes)
    delta = df_close.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    rsi_series = 100 - (100 / (1 + rs))
    rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
    
    sma20 = float(df_close.rolling(20).mean().iloc[-1])
    sma50 = float(df_close.rolling(50).mean().iloc[-1]) if len(df_close) >= 50 else sma20
    
    # Score Momentum
    mom_score = 50
    if price > sma20: mom_score += 25
    if price > sma50: mom_score += 25
    
    # Upside & Growth Score
    growth_upside = ((target_price - price) / price) * 100 if target_price > 0 else 0
    growth_score = min(max(growth_upside * 2, 0), 100)
    
    # Score Salute
    health_score = 50
    
    # Total Score
    total_score = round((growth_score * w_growth) + (mom_score * w_momentum) + (health_score * w_health), 1)

    return {
        "Ticker": symbol,
        "Nome": short_name,
        "Settore": sector,
        "Prezzo ($)": round(price, 2),
        "Target Analisti ($)": round(target_price, 2),
        "Upside Stimato (%)": round(growth_upside, 1),
        "Score Totale": total_score,
        "RSI (14d)": round(rsi, 1),
        "MCap (M$)": round(mcap_val, 1)
    }

# --- ESECUZIONE ANALISI ---
if st.button("🔄 Avvia Analisi e Genera Classifica"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, t in enumerate(ticker_list):
        status_text.text(f"Analizzando {t}...")
        data = get_yahoo_data(t)
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
            df[["Ticker", "Nome", "Prezzo ($)", "Target Analisti ($)", "Upside Stimato (%)", "Score Totale"]],
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("🔍 Scheda Dettagliata (Clicca su un titolo)")
        
        selected_ticker = st.selectbox("Seleziona il titolo per vedere le motivazioni:", df["Ticker"].tolist())
        stock_detail = df[df["Ticker"] == selected_ticker].iloc[0]

        col1, col2, col3 = st.columns(3)
        col1.metric("Score Totale", f"{stock_detail['Score Totale']} / 100")
        col2.metric("Upside Stimato", f"+{stock_detail['Upside Stimato (%)']}%")
        col3.metric("RSI (Momentum)", f"{stock_detail['RSI (14d)']}")

        st.markdown(f"### Dettaglio Analisi: **{stock_detail['Nome']}**")
        st.write(f"- **Target Analisti:** Prezzo attuale **${stock_detail['Prezzo ($)']}**, Target **${stock_detail['Target Analisti ($)']}** (Upside +{stock_detail['Upside Stimato (%)']}%).")
        st.write(f"- **Momentum (RSI):** Valore RSI a 14 giorni pari a **{stock_detail['RSI (14d)']}**.")
    else:
        st.error("Errore di connessione o ticker errati. Assicurati che i simboli siano corretti (es. 'IONQ', 'SOUN', 'TECN.MI').")
        
