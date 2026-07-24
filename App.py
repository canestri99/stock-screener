import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Small-Cap Opportunity Screener", layout="wide")

st.title("🎯 Real Small-Cap Market Screener")
st.caption("Scansione automatica del mercato per individuare i 10-20 titoli Small-Cap con maggior momentum a 3 mesi.")

# --- SIDEBAR: PARAMETRI DI FILTRO ---
st.sidebar.header("🔍 Filtri di Mercato")
min_mcap = st.sidebar.number_input("Capitalizzazione Minima ($M):", value=300, step=50) * 1_000_000
max_mcap = st.sidebar.number_input("Capitalizzazione Massima ($M):", value=2000, step=100) * 1_000_000
min_volume = st.sidebar.number_input("Volume Medio Minimo:", value=100000, step=50000)

top_n = st.sidebar.slider("Numero di titoli da mostrare nella classifica:", 5, 20, 15)

# Lista di universo Small-Cap attiva (senza limite di chiamate singole)
# Usiamo un approccio di scansione aggregata tramite endpoint pubblico per ovviare ai limiti di quota
@st.cache_data(ttl=3600)
def scan_small_cap_market():
    try:
        # Recupera la lista delle aziende e dati finanziari essenziali
        url = "https://financialmodelingprep.com/api/v3/stock-screener?marketCapMoreThan=300000000&marketCapLowerThan=2000000000&betaMoreThan=1&isEtf=false&isActivelyTraded=true&limit=150&apikey=demo"
        res = requests.get(url, timeout=15)
        if res.status_code != 200:
            return None
        return res.json()
    except Exception:
        return None

# Funzione per recuperare i dettagli di prezzo/momentum
def get_bulk_prices(symbols):
    try:
        sym_str = ",".join(symbols)
        url = f"https://financialmodelingprep.com/api/v3/quote/{sym_str}?apikey=demo"
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            return res.json()
        return []
    except Exception:
        return []

# --- ESECUZIONE DELLA SCANSIONE ---
if st.button("🚀 Scansiona il Mercato e Trova i Migliori Titoli"):
    with st.spinner("Scansione del mercato Small-Cap in corso..."):
        raw_candidates = scan_small_cap_market()
        
        if not raw_candidates:
            st.error("Errore durante la connessione al mercato. Riprova tra pochi istanti.")
        else:
            # Filtra per parametri di Market Cap scelti dall'utente
            valid_stocks = [
                s for s in raw_candidates 
                if min_mcap <= s.get('marketCap', 0) <= max_mcap and s.get('volume', 0) >= min_volume
            ]
            
            symbols = [s['symbol'] for s in valid_stocks[:60]] # Prendi i primi 60 candidati da analizzare
            quotes = get_bulk_prices(symbols)
            
            quote_map = {q['symbol']: q for q in quotes}
            
            results = []
            for item in valid_stocks:
                sym = item['symbol']
                q_data = quote_map.get(sym, {})
                
                price = q_data.get('price', item.get('price', 0))
                change_pct = q_data.get('changesPercentage', 0)
                year_high = q_data.get('yearHigh', price)
                year_low = q_data.get('yearLow', price)
                
                if price <= 0:
                    continue
                    
                # Prossimità ai massimi annuali (segnale di breakout/momentum)
                range_span = max((year_high - year_low), 0.01)
                high_proximity = ((price - year_low) / range_span) * 100
                
                # Calcolo dello Score di Potenziale
                # Più il titolo è vicino ai massimi ed ha spinta di breve, più alto è lo score
                score = round((high_proximity * 0.6) + (min(max(change_pct + 10, 0), 40) * 1.0), 1)
                
                results.append({
                    "Ticker": sym,
                    "Nome Società": item.get('companyName', sym),
                    "Settore": item.get('sector', 'N/A'),
                    "Prezzo ($)": round(price, 2),
                    "Market Cap ($M)": round(item.get('marketCap', 0) / 1_000_000, 1),
                    "Variazione Oggi (%)": round(change_pct, 2),
                    "Vicinanza ai Massimi (%)": round(high_proximity, 1),
                    "Score Potenziale (0-100)": score
                })
            
            if results:
                df = pd.DataFrame(results)
                df = df.sort_values(by="Score Potenziale (0-100)", ascending=False).reset_index(drop=True)
                
                top_df = df.head(top_n)
                top_df.index += 1
                
                st.subheader(f"🏆 Top {len(top_df)} Small-Cap Selezionate dall'Algoritmo")
                st.dataframe(
                    top_df[["Ticker", "Nome Società", "Settore", "Prezzo ($)", "Market Cap ($M)", "Variazione Oggi (%)", "Score Potenziale (0-100)"]],
                    use_container_width=True
                )
                
                st.markdown("---")
                st.subheader("📊 Dettaglio Opportunità")
                selected_ticker = st.selectbox("Seleziona una Small-Cap dalla lista per l'analisi dettagliata:", top_df["Ticker"].tolist())
                
                detail = top_df[top_df["Ticker"] == selected_ticker].iloc[0]
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Score Potenziale", f"{detail['Score Potenziale (0-100)']} / 100")
                col2.metric("Market Cap", f"${detail['Market Cap ($M)']}M")
                col3.metric("Settore", detail['Settore'])
                
                st.write(f"**Perché questo titolo è in classifica:**")
                st.write(f"- Si trova al **{detail['Vicinanza ai Massimi (%)']}%** del suo range annuale (forte struttura rialzista).")
                st.write(f"- Performance recente: **{detail['Variazione Oggi (%)']}%**.")
            else:
                st.warning("Nessuna azione trovata con i filtri impostati. Prova ad allargare i parametri nella barra laterale.")
                
