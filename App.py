import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import io

st.set_page_config(page_title="Dynamic Small-Cap Screener", layout="wide")

st.title("🛰️ Dynamic Market Small-Cap Screener")
st.caption("Scansione automatica dell'intero universo Small-Cap reale (S&P 600) per individuare i titoli a più alto potenziale.")

# --- SIDEBAR: PARAMETRI ---
st.sidebar.header("⚙️ Parametri Screening")
top_n = st.sidebar.slider("Numero di opportunità da trovare:", 5, 20, 15)
min_price = st.sidebar.number_input("Prezzo Minimo ($):", value=2.0, step=0.5)
max_price = st.sidebar.number_input("Prezzo Massimo ($):", value=50.0, step=5.0)

w_perf = st.sidebar.slider("Peso Momentum 1 Mese (%)", 0, 100, 50) / 100
w_high = st.sidebar.slider("Peso Prossimità Massimi (%)", 0, 100, 50) / 100

# --- FUNZIONE 1: RECUPERO DINAMICO UNIVERSO MERCATO ---
@st.cache_data(ttl=86400) # Aggiorna la lista dell'indice ogni 24 ore
def get_live_smallcap_universe():
    """Scansiona la composizione reale dell'S&P SmallCap 600 live da Wikipedia"""
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_SmallCap_600_companies"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'}
        response = requests.get(url, headers=headers, timeout=12)
        
        if response.status_code != 200:
            return []
            
        # Uso di io.StringIO per evitare l'errore di pathing HTML
        html_buffer = io.StringIO(response.text)
        tables = pd.read_html(html_buffer)
        
        df_symbols = tables[0]
        if 'Symbol' in df_symbols.columns:
            tickers = df_symbols['Symbol'].tolist()
        elif 'Ticker' in df_symbols.columns:
            tickers = df_symbols['Ticker'].tolist()
        else:
            tickers = []
            
        # Pulisci i ticker (es. sostituisci punti con trattini per Yahoo Finance)
        tickers = [str(t).strip().replace('.', '-') for t in tickers if isinstance(t, str)]
        return tickers
    except Exception as e:
        st.error(f"Errore durante l'estrazione della lista: {e}")
        return []

# --- FUNZIONE 2: SCANSIONE E ANALISI BATCH ---
@st.cache_data(ttl=1800)
def process_market_screening(ticker_list, min_p, max_p, weight_p, weight_h):
    """Scarica ed elabora i dati di mercato per l'intera lista in un unico blocco"""
    if not ticker_list:
        return pd.DataFrame()
        
    # Scarica i dati di tutto il listino in un unico download batch rapido
    data = yf.download(ticker_list, period="3m", interval="1d", group_by='ticker', progress=False)
    
    results = []
    
    for ticker in ticker_list:
        try:
            if len(ticker_list) > 1:
                if ticker not in data.columns.levels[0]:
                    continue
                df_t = data[ticker].dropna()
            else:
                df_t = data.dropna()
                
            if len(df_t) < 20:
                continue
                
            closes = df_t['Close']
            price = float(closes.iloc[-1])
            
            # Filtro sulla fascia di prezzo impostata dall'utente
            if price < min_p or price > max_p:
                continue
                
            price_1m_ago = float(closes.iloc[-20])
            high_3m = float(closes.max())
            low_3m = float(closes.min())
            
            # Performance 1 Mese
            perf_1m = ((price - price_1m_ago) / price_1m_ago) * 100
            
            # Vicinanza ai massimi a 3 mesi (struttura rialzista)
            range_span = max((high_3m - low_3m), 0.01)
            high_proximity = ((price - low_3m) / range_span) * 100
            
            # RSI (14 giorni)
            delta = closes.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / (loss + 1e-9)
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])
            
            # Algoritmo di Scoring
            score_perf = min(max((perf_1m + 20) * 2, 0), 100)
            total_score = round((score_perf * weight_p) + (high_proximity * weight_h), 1)
            
            results.append({
                "Ticker": ticker,
                "Prezzo ($)": round(price, 2),
                "Perf. 1 Mese (%)": round(perf_1m, 1),
                "RSI (14d)": round(rsi, 1),
                "Vicinanza ai Massimi (%)": round(high_proximity, 1),
                "Score Potenziale": total_score
            })
        except Exception:
            continue
            
    return pd.DataFrame(results)

# --- BOTTONE ED ESECUZIONE ---
if st.button("🔍 Scansiona Mercato Reale Ora"):
    with st.spinner("1/2 Recupero componenti aggiornati dell'indice S&P SmallCap 600..."):
        universe = get_live_smallcap_universe()
        
    if universe:
        st.success(f"Trovate {len(universe)} aziende Small-Cap attive sul mercato! Inizio analisi quantitativa...")
        
        with st.spinner(f"2/2 Analisi in corso su {len(universe)} titoli... (attendi circa 5-10 secondi)"):
            df_results = process_market_screening(universe, min_price, max_price, w_perf, w_high)
            
        if not df_results.empty:
            df_sorted = df_results.sort_values(by="Score Potenziale", ascending=False).reset_index(drop=True)
            top_df = df_sorted.head(top_n)
            top_df.index += 1
            
            st.markdown("---")
            st.subheader(f"🏆 Top {len(top_df)} Opportunità Small-Cap Selezionate dall'Algoritmo")
            st.dataframe(
                top_df[["Ticker", "Prezzo ($)", "Perf. 1 Mese (%)", "RSI (14d)", "Vicinanza ai Massimi (%)", "Score Potenziale"]],
                use_container_width=True
            )
            
            st.markdown("---")
            st.subheader("📊 Dettaglio Scheda Titolo")
            selected = st.selectbox("Seleziona una delle aziende trovate per analizzarla:", top_df["Ticker"].tolist())
            stock = top_df[top_df["Ticker"] == selected].iloc[0]
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Score Potenziale", f"{stock['Score Potenziale']} / 100")
            c2.metric("Spinta a 1 Mese", f"{stock['Perf. 1 Mese (%)']}%")
            c3.metric("RSI Tecnico", f"{stock['RSI (14d)']}")
            
            st.write(f"**Analisi per {stock['Ticker']}:**")
            st.write(f"- Il titolo quota a **${stock['Prezzo ($)']}** ed è posizionato al **{stock['Vicinanza ai Massimi (%)']}%** del range di prezzo degli ultimi 3 mesi.")
            st.write(f"- Ha mostrato un momentum del **{stock['Perf. 1 Mese (%)']}%** nell'ultimo mese.")
        else:
            st.warning("Nessun titolo rispetta i filtri impostati. Prova ad allargare i range di prezzo nella barra laterale.")
    else:
        st.error("Impossibile scaricare la lista dell'indice dal mercato. Riprova tra pochi istanti.")
        
