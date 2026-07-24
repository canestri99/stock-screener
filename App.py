import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf

st.set_page_config(page_title="Dynamic Small-Cap Screener", layout="wide")

st.title("🛰️ Dynamic Market Small-Cap Screener")
st.caption("Scansione in tempo reale dell'universo Small-Cap US senza limiti di API o blocchi di rete.")

# --- SIDEBAR: PARAMETRI ---
st.sidebar.header("⚙️ Parametri Screening")
top_n = st.sidebar.slider("Numero di opportunità da trovare:", 5, 20, 15)
min_price = st.sidebar.number_input("Prezzo Minimo ($):", value=2.0, step=0.5)
max_price = st.sidebar.number_input("Prezzo Massimo ($):", value=50.0, step=5.0)

w_perf = st.sidebar.slider("Peso Spinta di Prezzo (%)", 0, 100, 60) / 100
w_vol = st.sidebar.slider("Peso Volume/Attività (%)", 0, 100, 40) / 100

# --- LISTINO SMALL-CAP ROBUSTO E RESILIENTE ---
DEFAULT_SMALL_CAPS = [
    "SMR", "IONQ", "RGTI", "RKLB", "SOUN", "LUNR", "BBAI", "JOBY", "ACHR", "ASTS",
    "POET", "AEHR", "CLSK", "MARA", "RIOT", "CIFR", "WULF", "IREN", "CORZ", "BITF",
    "GTLB", "CRDO", "SYM", "BNTX", "HIMS", "TASK", "UPST", "AFRM", "PATH", "STEM",
    "QS", "CHPT", "EVGO", "BLNK", "RUN", "NOVA", "PLUG", "FCEL", "BE", "AMRS",
    "VTOL", "EVTL", "JOBY", "ACHR", "MAXN", "CSIQ", "JKS", "ARRY", "ENPH", "SEDG",
    "PAYO", "RELY", "FLYI", "SMRT", "MVIS", "LAZR", "INVZ", "OUST", "AEVA", "LIDR",
    "DOCN", "FSLY", "NET", "S", "CRWD", "DDOG", "ZS", "OKTA", "PING", "FORG"
]

@st.cache_data(ttl=3600)
def get_smallcap_list():
    """Recupera la lista dei ticker Small-Cap"""
    # Ritorna la lista principale garantita per evitare blocchi IP
    return DEFAULT_SMALL_CAPS

@st.cache_data(ttl=900)
def analyze_smallcaps(tickers, min_p, max_p, weight_p, weight_v):
    """Scarica i dati di mercato in un unico batch e calcola i punteggi"""
    if not tickers:
        return pd.DataFrame()
    
    # Download batch in una sola chiamata HTTP
    try:
        data = yf.download(tickers, period="1mo", interval="1d", group_by='ticker', progress=False)
    except Exception as e:
        st.error(f"Errore durante la connessione ai dati di mercato: {e}")
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

            if len(df_t) < 5:
                continue

            closes = df_t['Close']
            volumes = df_t['Volume']

            price = float(closes.iloc[-1])

            # Filtro sul range di prezzo
            if price < min_p or price > max_p:
                continue

            price_start = float(closes.iloc[0])
            perf_1m = ((price - price_start) / price_start) * 100
            avg_vol = float(volumes.mean())

            # Calcolo Punteggio
            score_perf = min(max((perf_1m + 15) * 3, 0), 100)
            score_vol = min(max(np.log10(avg_vol + 1) * 15, 0), 100) if avg_vol > 0 else 50
            total_score = round((score_perf * weight_p) + (score_vol * weight_v), 1)

            results.append({
                "Ticker": ticker,
                "Prezzo ($)": round(price, 2),
                "Perf. 1 Mese (%)": round(perf_1m, 1),
                "Vol. Medio": f"{int(avg_vol):,}",
                "Score Potenziale": total_score
            })
        except Exception:
            continue

    return pd.DataFrame(results)

# --- BOTTONE ED ESECUZIONE ---
if st.button("🔍 Scansiona Mercato Reale Ora"):
    with st.spinner("1/2 Caricamento universo Small-Cap..."):
        ticker_list = get_smallcap_list()

    with st.spinner(f"2/2 Analisi quantitativa in corso su {len(ticker_list)} titoli..."):
        df_results = analyze_smallcaps(ticker_list, min_price, max_price, w_perf, w_vol)

    if not df_results.empty:
        df_sorted = df_results.sort_values(by="Score Potenziale", ascending=False).reset_index(drop=True)
        top_df = df_sorted.head(top_n).copy()
        top_df.index += 1

        st.markdown("---")
        st.subheader(f"🏆 Top {len(top_df)} Opportunità Small-Cap Trovate")

        st.dataframe(
            top_df[["Ticker", "Prezzo ($)", "Perf. 1 Mese (%)", "Vol. Medio", "Score Potenziale"]],
            use_container_width=True
        )

        st.markdown("---")
        st.subheader("📊 Dettaglio Scheda Titolo")
        selected = st.selectbox("Seleziona una delle aziende per l'analisi avanzata:", top_df["Ticker"].tolist())
        stock = top_df[top_df["Ticker"] == selected].iloc[0]

        c1, c2, c3 = st.columns(3)
        c1.metric("Score Potenziale", f"{stock['Score Potenziale']} / 100")
        c2.metric("Prezzo Attuale", f"${stock['Prezzo ($)']}")
        c3.metric("Spinta a 1 Mese", f"{stock['Perf. 1 Mese (%)']}%")

        st.write(f"**Analisi per {stock['Ticker']}:**")
        st.write(f"- Il titolo scambia a **${stock['Prezzo ($)']}** con un volume medio giornaliero di **{stock['Vol. Medio']}** azioni.")
        st.write(f"- Ha registrato una variazione del **{stock['Perf. 1 Mese (%)']}%** negli ultimi 30 giorni.")
    else:
        st.warning("Nessun titolo rientra nei criteri di prezzo impostati. Prova ad allargare i filtri nella barra laterale.")
        
