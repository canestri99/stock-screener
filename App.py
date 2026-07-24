import streamlit as st
import pandas as pd
import numpy as np
from yahooquery import Ticker

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

# --- ESECUZIONE ANALISI ---
if st.button("🔄 Avvia Analisi e Genera Classifica"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    status_text.text("Connessione ai dati finanziari in corso...")
    
    try:
        # Inizializza Ticker tramite yahooquery (gestisce i blocchi IP)
        t = Ticker(ticker_list, asynchronous=False)
        
        # Recupero Storico Prezzi (6 mesi)
        hist_df = t.history(period="6m")
        summary_detail = t.summary_detail
        price_dict = t.price
        financial_data = t.financial_data
        
        for idx, symbol in enumerate(ticker_list):
            status_text.text(f"Elaborazione {symbol}...")
            
            try:
                # Estrazione Prezzi Storici del singolo simbolo
                if isinstance(hist_df, pd.DataFrame) and symbol in hist_df.index:
                    df_sym = hist_df.loc[symbol].dropna(subset=['close'])
                else:
                    continue
                    
                if len(df_sym) < 20:
                    continue
                    
                closes = df_sym['close']
                price = float(closes.iloc[-1])
                
                # Dati Target & Informazioni Società
                p_info = price_dict.get(symbol, {}) if isinstance(price_dict, dict) else {}
                f_info = financial_data.get(symbol, {}) if isinstance(financial_data, dict) else {}
                
                short_name = p_info.get('shortName', symbol) if isinstance(p_info, dict) else symbol
                mcap = p_info.get('marketCap', 0) if isinstance(p_info, dict) else 0
                mcap_val = (mcap / 1e6) if mcap else 0
                
                target_price = f_info.get('targetMeanPrice', price) if isinstance(f_info, dict) else price
                if not target_price or np.isnan(target_price):
                    target_price = price
                    
                growth_upside = ((target_price - price) / price) * 100 if target_price > 0 else 0
                
                # Calcolo Indicatori Tecnici (RSI e Medie Mobili)
                delta = closes.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / (loss + 1e-9)
                rsi_series = 100 - (100 / (1 + rs))
                rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
                
                sma20 = float(closes.rolling(20).mean().iloc[-1])
                sma50 = float(closes.rolling(50).mean().iloc[-1]) if len(closes) >= 50 else sma20
                
                # Score Momentum
                mom_score = 50
                if price > sma20: mom_score += 25
                if price > sma50: mom_score += 25
                
                # Score Growth
                growth_score = min(max(growth_upside * 2, 0), 100)
                health_score = 50
                
                total_score = round((growth_score * w_growth) + (mom_score * w_momentum) + (health_score * w_health), 1)
                
                results.append({
                    "Ticker": symbol,
                    "Nome": short_name,
                    "Prezzo ($)": round(price, 2),
                    "Target Analisti ($)": round(target_price, 2),
                    "Upside Stimato (%)": round(growth_upside, 1),
                    "Score Totale": total_score,
                    "RSI (14d)": round(rsi, 1),
                    "MCap (M$)": round(mcap_val, 1)
                })
            except Exception as e:
                continue
                
            progress_bar.progress((idx + 1) / len(ticker_list))
            
    except Exception as global_e:
        st.error(f"Errore durante il recupero globale: {global_e}")
        
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
        st.error("Impossibile scaricare i dati al momento. Verifica di aver aggiornato il file requirements.txt con 'yahooquery'.")
        
