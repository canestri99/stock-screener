import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Dynamic Small-Cap Screener", layout="wide")

st.title("🛰️ Dynamic Market Small-Cap Screener")
st.caption("Scansione automatica e diretta del mercato Small-Cap senza limiti di API.")

# --- SIDEBAR: PARAMETRI ---
st.sidebar.header("⚙️ Parametri Screening")
top_n = st.sidebar.slider("Numero di opportunità da trovare:", 5, 20, 15)
min_price = st.sidebar.number_input("Prezzo Minimo ($):", value=2.0, step=0.5)
max_price = st.sidebar.number_input("Prezzo Massimo ($):", value=50.0, step=5.0)

w_perf = st.sidebar.slider("Peso Spinta di Prezzo (%)", 0, 100, 60) / 100
w_vol = st.sidebar.slider("Peso Volume/Attività (%)", 0, 100, 40) / 100

# --- FUNZIONE D'ESTRAZIONE DIRECT API ---
@st.cache_data(ttl=900)
def fetch_yahoo_smallcaps(min_p, max_p):
    """Richiesta diretta allo screener JSON pubblico"""
    url = "https://query2.finance.yahoo.com/v1/finance/screener"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # Payload per filtrare Small Cap US
    payload = {
        "offset": 0,
        "size": 100,
        "sortField": "percentchange",
        "sortType": "DESC",
        "quoteType": "EQUITY",
        "query": {
            "operator": "AND",
            "operands": [
                {"operator": "eq", "operands": ["region", "us"]},
                {"operator": "gte", "operands": ["intradaymarketcap", 300000000]},
                {"operator": "lte", "operands": ["intradaymarketcap", 2000000000]},
                {"operator": "gte", "operands": ["intradayprice", min_p]},
                {"operator": "lte", "operands": ["intradayprice", max_p]}
            ]
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            quotes = data.get("finance", {}).get("result", [{}])[0].get("quotes", [])
            return quotes
    except Exception as e:
        st.error(f"Errore nella chiamata di mercato: {e}")
    return []

# --- ESECUZIONE SCANNER ---
if st.button("🔍 Scansiona Mercato Reale Ora"):
    with st.spinner("Scansione in tempo reale dell'universo Small-Cap US in corso..."):
        raw_quotes = fetch_yahoo_smallcaps(min_price, max_price)

    if raw_quotes:
        results = []
        for q in raw_quotes:
            sym = q.get("symbol")
            name = q.get("shortName", sym)
            price = q.get("regularMarketPrice", 0.0)
            change = q.get("regularMarketChangePercent", 0.0)
            mcap = q.get("marketCap", 0)
            vol = q.get("regularMarketVolume", 0)

            if price <= 0:
                continue

            # Calcolo Score di Momentum/Attività
            score_change = min(max((change + 15) * 3, 0), 100)
            score_vol = min(max(np.log10(vol + 1) * 15, 0), 100) if vol > 0 else 50
            
            total_score = round((score_change * w_perf) + (score_vol * w_vol), 1)

            results.append({
                "Ticker": sym,
                "Nome Azienda": name,
                "Prezzo ($)": round(price, 2),
                "Perf. Oggi (%)": round(change, 2),
                "Market Cap ($M)": round(mcap / 1_000_000, 1),
                "Volume": f"{vol:,}",
                "Score Potenziale": total_score
            })

        if results:
            df = pd.DataFrame(results)
            df = df.sort_values(by="Score Potenziale", ascending=False).reset_index(drop=True)
            top_df = df.head(top_n).copy()
            top_df.index += 1

            st.markdown("---")
            st.subheader(f"🏆 Top {len(top_df)} Small-Cap Trovate in Tempo Reale")

            st.dataframe(
                top_df[["Ticker", "Nome Azienda", "Prezzo ($)", "Perf. Oggi (%)", "Market Cap ($M)", "Score Potenziale"]],
                use_container_width=True
            )

            st.markdown("---")
            st.subheader("📊 Dettaglio Scheda Titolo")
            selected = st.selectbox("Seleziona un'azienda per i dettagli:", top_df["Ticker"].tolist())
            stock = top_df[top_df["Ticker"] == selected].iloc[0]

            c1, c2, c3 = st.columns(3)
            c1.metric("Score Potenziale", f"{stock['Score Potenziale']} / 100")
            c2.metric("Prezzo Attuale", f"${stock['Prezzo ($)']}")
            c3.metric("Spinta Recente", f"{stock['Perf. Oggi (%)']}%")

            st.write(f"**Analisi per {stock['Nome Azienda']} ({stock['Ticker']}):**")
            st.write(f"- Capitalizzazione di Mercato: **${stock['Market Cap ($M)']} Milioni**")
            st.write(f"- Volume di scambio: **{stock['Volume']}** azioni")
        else:
            st.warning("Nessun titolo trovato per la fascia di prezzo selezionata. Prova ad allargare i filtri nella barra laterale.")
    else:
        st.error("Nessun dato restituito dal mercato. Riprova tra qualche istante.")
            
