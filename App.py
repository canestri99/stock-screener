import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Advanced Small-Cap Screener", layout="wide")

st.title("🚀 Advanced Multifactor Small-Cap Screener")
st.caption("Analisi quantitativa avanzata: Momentum, Volume, RSI, Medie Mobili e Breakout.")

# --- SIDEBAR: PARAMETRI E PESI DELL'ALGORITMO ---
st.sidebar.header("⚙️ Filtri Base")
top_n = st.sidebar.slider("Numero di risultati da mostrare:", 5, 20, 15)
min_price = st.sidebar.number_input("Prezzo Minimo ($):", value=2.0, step=0.5)
max_price = st.sidebar.number_input("Prezzo Massimo ($):", value=50.0, step=5.0)

st.sidebar.header("⚖️ Pesi dell'Algoritmo (%)")
w_perf = st.sidebar.slider("Spinta Momentum (1 Mese)", 0, 100, 30) / 100
w_vol = st.sidebar.slider("Liquidità e Volume", 0, 100, 20) / 100
w_trend = st.sidebar.slider("Trend Medie Mobili (SMA20/50)", 0, 100, 25) / 100
w_high = st.sidebar.slider("Vicinanza ai Massimi", 0, 100, 25) / 100

st.sidebar.header("🛡️ Protezione Ipercomprato")
max_rsi_allowed = st.sidebar.slider("RSI Massimo Tollerato (Soglia Ipercomprato):", 65, 90, 80)

# --- LISTINO SMALL-CAP ROBUSTO ---
DEFAULT_SMALL_CAPS = [
    "SMR", "IONQ", "RGTI", "RKLB", "SOUN", "LUNR", "BBAI", "JOBY", "ACHR", "ASTS",
    "POET", "AEHR", "CLSK", "MARA", "RIOT", "CIFR", "WULF", "IREN", "CORZ", "BITF",
    "GTLB", "CRDO", "SYM", "BNTX", "HIMS", "TASK", "UPST", "AFRM", "PATH", "STEM",
    "QS", "CHPT", "EVGO", "BLNK", "RUN", "NOVA", "PLUG", "FCEL", "BE", "FSLY",
    "S", "VTOL", "EVTL", "MAXN", "CSIQ", "JKS", "ARRY", "ENPH", "SEDG", "PAYO",
    "DOCN", "NET", "CRWD", "DDOG", "ZS", "OKTA"
]
DEFAULT_SMALL_CAPS = list(dict.fromkeys(DEFAULT_SMALL_CAPS))

# --- FUNZIONE DI CALCOLO AVANZATO ---
@st.cache_data(ttl=900)
def analyze_advanced_smallcaps(tickers, min_p, max_p, w_p, w_v, w_t, w_h, rsi_limit):
    if not tickers:
        return pd.DataFrame()
    
    try:
        # Scarichiamo 6 mesi di dati per calcolare accuratamente SMA50 e RSI
        data = yf.download(tickers, period="6mo", interval="1d", group_by='ticker', progress=False)
    except Exception as e:
        st.error(f"Errore durante il recupero dei dati: {e}")
        return pd.DataFrame()

    results = []

    for ticker in tickers:
        try:
            if len(tickers) > 1:
                if ticker not in data.columns.levels[0]:
                    continue
                df_t = data[ticker].dropna()
            else:
                df_t = data.dropna()

            if len(df_t) < 50: # Servono almeno 50 candele per la media mobile SMA50
                continue

            closes = df_t['Close']
            volumes = df_t['Volume']
            price = float(closes.iloc[-1])

            # 1. Filtro Prezzo Base
            if price < min_p or price > max_p:
                continue

            # 2. Performance a 1 Mese (~20 giorni lavorativi)
            price_1m_ago = float(closes.iloc[-20])
            perf_1m = ((price - price_1m_ago) / price_1m_ago) * 100

            # 3. Volume Medio (30 giorni)
            avg_vol = float(volumes.iloc[-20:].mean())

            # 4. Calcolo RSI a 14 giorni
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])

            # Filtro o Penalizzazione se in Ipercomprato Estremo
            if rsi > rsi_limit:
                continue

            # 5. Medie Mobili (SMA 20 e SMA 50)
            sma20 = float(closes.rolling(20).mean().iloc[-1])
            sma50 = float(closes.rolling(50).mean().iloc[-1])
            
            # Score Trend (100 se sopra sia a SMA20 che SMA50, 50 se sopra solo una, 0 se sotto entrambe)
            trend_score = 0
            if price > sma20: trend_score += 50
            if price > sma50: trend_score += 50

            # 6. Vicinanza ai Massimi del periodo (Prossimità al Breakout)
            high_period = float(closes.max())
            low_period = float(closes.min())
            range_span = max((high_period - low_period), 0.01)
            high_proximity = ((price - low_period) / range_span) * 100

            # --- ALGORITMO DI SCORING MULTIFATTORIALE ---
            score_perf = min(max((perf_1m + 15) * 3, 0), 100)
            score_vol = min(max(np.log10(avg_vol + 1) * 15, 0), 100) if avg_vol > 0 else 50
            
            # Punteggio Globale
            total_score = (
                (score_perf * w_p) + 
                (score_vol * w_v) + 
                (trend_score * w_t) + 
                (high_proximity * w_h)
            )
            
            # Penalizzazione RSI sfavorevole (sotto 40 = poco momentum)
            if rsi < 40:
                total_score *= 0.8

            results.append({
                "Ticker": ticker,
                "Prezzo ($)": round(price, 2),
                "Perf. 1 Mese (%)": round(perf_1m, 1),
                "RSI (14d)": round(rsi, 1),
                "Sopra SMA20": "Sì" if price > sma20 else "No",
                "Sopra SMA50": "Sì" if price > sma50 else "No",
                "Vicinanza Massimi (%)": round(high_proximity, 1),
                "Vol. Medio": f"{int(avg_vol):,}",
                "Score Totale": round(total_score, 1)
            })
        except Exception:
            continue

    return pd.DataFrame(results)

# --- BOTTONE ED ESECUZIONE ---
if st.button("🚀 Avvia Scansione Multifattoriale"):
    with st.spinner("Analisi quantitativa avanzata in corso (Momentum, RSI, SMA20/50, Breakout)..."):
        df_results = analyze_advanced_smallcaps(
            DEFAULT_SMALL_CAPS, min_price, max_price, 
            w_perf, w_vol, w_trend, w_high, max_rsi_allowed
        )

    if not df_results.empty:
        df_sorted = df_results.sort_values(by="Score Totale", ascending=False).reset_index(drop=True)
        top_df = df_sorted.head(top_n).copy()
        top_df.index += 1

        st.markdown("---")
        st.subheader(f"🏆 Classifica Top {len(top_df)} Small-Cap Selezionate")

        # Tabella Risultati Avanzata
        st.dataframe(
            top_df[[
                "Ticker", "Prezzo ($)", "Perf. 1 Mese (%)", "RSI (14d)", 
                "Sopra SMA20", "Sopra SMA50", "Vicinanza Massimi (%)", "Score Totale"
            ]],
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("📊 Analisi Tecnica Dettagliata Titolo")
        selected = st.selectbox("Seleziona una delle aziende trovate per analizzare la scheda:", top_df["Ticker"].tolist())
        stock = top_df[top_df["Ticker"] == selected].iloc[0]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Score Totale", f"{stock['Score Totale']} / 100")
        c2.metric("Performance 1 Mese", f"{stock['Perf. 1 Mese (%)']}%")
        c3.metric("RSI (14 giorni)", f"{stock['RSI (14d)']}")
        c4.metric("Prossimità Massimi", f"{stock['Vicinanza Massimi (%)']}%")

        st.markdown(f"### Report Tecnico per **{stock['Ticker']}**")
        st.write(f"- **Trend delle Medie Mobili:** Il titolo si trova sopra la media a 20 giorni: **{stock['Sopra SMA20']}** | Sopra la media a 50 giorni: **{stock['Sopra SMA50']}**.")
        st.write(f"- **Forza Relativa (RSI):** Un valore di **{stock['RSI (14d)']}** indica un momentum sano senza essere in ipercomprato estremo.")
        st.write(f"- **Struttura di Prezzo:** È posizionato al **{stock['Vicinanza Massimi (%)']}%** rispetto al massimo recente (segnale di potenziale breakout).")
    else:
        st.warning("Nessun titolo rispetta i filtri impostati o la soglia RSI. Prova ad allargare i parametri nella barra laterale.")
        
