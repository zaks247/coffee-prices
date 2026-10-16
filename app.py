import streamlit as st
import yfinance as yf
import requests
from datetime import datetime, timedelta
import pandas as pd
import json
import os
import re

st.set_page_config(
    page_title="Cijene kave",
    page_icon="☕",
    layout="centered",
    initial_sidebar_state="collapsed"
)

CACHE_FILE = "robusta_cache.json"

def load_robusta_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"price": 3400.0, "updated": "", "source": "default"}

def save_robusta_cache(price, source="manual"):
    data = {
        "price": float(price),
        "updated": datetime.now().strftime("%d. %b %Y. %H:%M"),
        "source": source
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)
    return data

def get_usd_eur():
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=8)
        return round(r.json()["rates"]["EUR"], 4)
    except:
        return 0.892

def get_arabica():
    try:
        ticker = yf.Ticker("KC=F")
        hist = ticker.history(period="1mo")
        if hist.empty:
            return None
        current = float(hist["Close"].iloc[-1])
        month_start = float(hist["Close"].iloc[0])
        change_pct = ((current - month_start) / month_start) * 100
        return {
            "price_cents": round(current, 2),
            "price_usd": round(current / 100, 4),
            "change_pct": round(change_pct, 2),
            "history": hist["Close"].tail(10)
        }
    except Exception:
        return None

def try_fetch_robusta():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    urls = [
        "https://www.investing.com/commodities/london-coffee",
        "https://hk.investing.com/commodities/london-coffee",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code == 200:
                match = re.search(r'3,[0-9]{3}\.[0-9]{2}', r.text)
                if match:
                    return float(match.group(0).replace(",", ""))
        except:
            continue
    return None

st.markdown("""
<style>
    .big-number { font-size: 2.4rem; font-weight: 700; margin: 4px 0; }
    .sub-number { font-size: 1.5rem; color: #1e293b; margin: 2px 0; }
    .positive { color: #16a34a; font-weight: 600; }
    .negative { color: #dc2626; font-weight: 600; }
    .card {
        background: #ffffff;
        border-radius: 16px;
        padding: 18px 16px;
        margin-bottom: 14px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    }
    .header { text-align: center; margin-bottom: 4px; }
    .stButton>button { width: 100%; border-radius: 12px; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='header'>☕ Cijene kave</h1>", unsafe_allow_html=True)
st.caption("Brza provjera za klijente · Arabica automatski · Robusta pokušaj automatskog osvježavanja · EUR / kg / tona")

usd_eur = get_usd_eur()
arabica = get_arabica()
cache = load_robusta_cache()

should_refresh = True
if cache.get("updated"):
    try:
        last = datetime.strptime(cache["updated"], "%d. %b %Y. %H:%M")
        if datetime.now() - last < timedelta(hours=8):
            should_refresh = False
    except:
        pass

if should_refresh:
    with st.spinner("Ažuriram cijenu Robuste..."):
        new_price = try_fetch_robusta()
        if new_price:
            cache = save_robusta_cache(new_price, source="auto")
            st.toast(f"Robusta ažurirana: {new_price:,.0f} $/t")
        else:
            st.caption("Automatsko ažuriranje trenutno nije dostupno — koristim zadnju spremljenu cijenu")

robusta_price = float(cache["price"])

with st.expander("Ručna izmjena cijene Robuste (samo ako treba)"):
    manual = st.number_input(
        "Nova cijena Robuste (USD/tona)",
        min_value=2000.0,
        max_value=6000.0,
        value=robusta_price,
        step=1.0
    )
    if st.button("Spremi ručnu cijenu"):
        cache = save_robusta_cache(manual, source="ručno")
        robusta_price = manual
        st.success("Ručna cijena spremljena")
        st.rerun()

col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("**Arabica (New York)**")
    if arabica:
        cents = arabica["price_cents"]
        usd_lb = arabica["price_usd"]
        eur_lb = usd_lb * usd_eur
        eur_kg = eur_lb * 2.20462
        eur_tonne = eur_kg * 1000

        st.markdown(f"<p class='big-number'>{cents:.2f} ¢/lb</p>", unsafe_allow_html=True)
        change = arabica["change_pct"]
        color_class = "positive" if change >= 0 else "negative"
        st.markdown(f"<p class='{color_class}'>{change:+.2f}% ovaj mjesec</p>", unsafe_allow_html=True)
        st.markdown(f"<p class='sub-number'>€{eur_kg:.2f} / kg</p>", unsafe_allow_html=True)
        st.markdown(f"<p class='sub-number'>€{eur_tonne:,.0f} / t</p>", unsafe_allow_html=True)
    else:
        st.info("Arabica trenutno nije dostupna")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("**Robusta (London)**")
    eur_t = robusta_price * usd_eur
    eur_kg_r = eur_t / 1000
    st.markdown(f"<p class='big-number'>{robusta_price:,.0f} $/t</p>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-number'>€{eur_kg_r:.2f} / kg</p>", unsafe_allow_html=True)
    st.markdown(f"<p class='sub-number'>€{eur_t:,.0f} / t</p>", unsafe_allow_html=True)
    source = cache.get("source", "")
    updated = cache.get("updated", "")
    if updated:
        st.caption(f"Zadnje ažuriranje: {updated} ({source})")
    st.markdown("</div>", unsafe_allow_html=True)

st.divider()

if arabica and "history" in arabica:
    st.subheader("Arabica – zadnje cijene")
    hist = arabica["history"]
    df = pd.DataFrame({"¢/lb": hist})
    st.line_chart(df, height=220, use_container_width=True)

st.caption(f"USD/EUR ≈ {usd_eur} · Učitano {datetime.now().strftime('%d. %b %Y. %H:%M')} (Zagreb)")
st.caption("Arabica: Yahoo Finance · Robusta: pokušaj automatskog osvježavanja (ako ne uspije, koristi zadnju cijenu)")

if st.button("🔄 Osvježi", use_container_width=True):
    st.rerun()
