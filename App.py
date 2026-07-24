import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

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

# --- FUNZIONE DI CALCOLO E ANALISI ---
def analyze_stock(ticker_symbol):
    try:
        stock = yf.Ticker(ticker_symbol)
        
        # Scarica lo storico dati (ultimi 6 mesi)
        hist = stock.history(period="6m")
        if hist.empty or len(hist) < 20:
            return None

        # Ottieni prezzo attuale dal grafico
        price = float(hist['Close'].iloc[-1])
        
        # Tenta il recupero informazioni fondamentali
        info = {}
        try:
            info = stock.info
        except Exception:
            pass

        target_price = info.get("targetMeanPrice", price)
        if target_price is None:
            target_price = price

        mcap = info.get("marketCap", 0)
        mcap_val = (mcap / 1e6) if mcap else 0
        
        growth_upside = ((target_price - price) / price) * 100 if target_price > 0 else 0

        # Calcolo RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / (loss + 1e-9)
        rsi_series = 100 - (100 / (1 + rs))
        rsi = float(rsi_series.iloc[-1]) if not rsi_series.empty else 50.0
        
        # Medie Mobili
        sma20 = float(hist['Close'].rolling(20).mean().iloc[-1])
        sma50 = float(hist['Close'].rolling(50).mean().iloc[-1]) if len(hist) >= 50 else sma20
        
        # Score Momentum
        mom_score = 50
        if price > sma20: mom_score += 25
        if price > sma50: mom_score += 25
        
        # Score Growth
        growth_score = min(max(growth_upside * 2, 0), 100)
        
        # Score Salute
        debt_to_equity = info.get("debtToEquity", 100)
        if debt_to_equity is None: debt_to_equity = 100
        health_score = 100 if debt_to_equity < 50 else (50 if debt_to_equity < 150 else 20)

        # Total Score
        total_score = round((growth_score * w_growth) + (mom_score * w_momentum) + (health_score * w_health), 1)

        return {
            "Ticker": ticker_symbol,
            "Nome": info.get("shortName", ticker_symbol),
            "Settore": info.get("sector", "N/D"),
            "Prezzo ($)": round(price, 2),
            "Target Analisti ($)": round(target_price, 2),
            "Upside Stimato (%)": round(growth_upside, 1),
            "Score Totale": total_score,
            "RSI (14d)": round(rsi, 1),
            "Debito/Equity": debt_to_equity,
            "MCap (M$)": round(mcap_val, 1)
        }
    except Exception as e:
        return None

# --- ESECUZIONE ANALISI ---
if st.button("🔄 Avvia Analisi e Genera Classifica"):
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for idx, t in enumerate(ticker_list):
        status_text.text(f"Analizzando {t}...")
        data = analyze_stock(t)
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
            df[["Ticker", "Nome", "Settore", "Prezzo ($)", "Upside Stimato (%)", "Score Totale"]],
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
        st.write(f"- **Momentum (RSI):** {stock_detail['RSI (14d)']}.")
        st.write(f"- **Rapporto Debito/Capitale:** {stock_detail['Debito/Equity']}.")
    else:
        st.error("Nessun dato recuperato per i ticker inseriti. Riprova tra poco o verifica i simboli dei titoli.")
        
