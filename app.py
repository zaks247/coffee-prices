import streamlit as st
import yfinance as yf
import requests
from datetime import datetime, timedelta
import pandas as pd
import json
import os
import re
try:
    from curl_cffi import requests as cffi_requests  # zaobilazi blokadu (TLS otisak preglednika)
except Exception:
    cffi_requests = None

def http_get(url, headers=None, timeout=12):
    if cffi_requests is not None:
        try:
            r = cffi_requests.get(url, headers=headers, impersonate="chrome", timeout=timeout)
            if r.status_code == 200:
                return r
        except Exception:
            pass
    return requests.get(url, headers=headers, timeout=timeout)

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

@st.cache_data(ttl=12*60*60, show_spinner=False)
def get_fetch_time():
    return datetime.now().strftime("%d. %b %Y. %H:%M")

@st.cache_data(ttl=12*60*60, show_spinner=False)
def get_usd_eur():
    try:
        r = requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=8)
        return round(r.json()["rates"]["EUR"], 4)
    except:
        return 0.892

@st.cache_data(ttl=12*60*60, show_spinner=False)
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

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

@st.cache_data(ttl=12*60*60, show_spinner=False)
def get_robusta_live():
    """ICE London Robusta (USD/t) s investing.com JSON API-ja (instrument 8911)."""
    try:
        r = http_get(
            "https://api.investing.com/api/financialdata/8911/historical/chart/?interval=P1D&pointscount=60",
            headers={"domain-id": "www", "Accept": "application/json"}, timeout=12)
        if r.status_code == 200:
            rows = r.json().get("data") or []
            s = pd.Series(
                [float(x[4]) for x in rows],
                index=pd.to_datetime([x[0] for x in rows], unit="ms").normalize())
            s = s[~s.index.duplicated(keep="last")]
            if len(s) and 1000 < s.iloc[-1] < 10000:
                month = s[s.index >= s.index[-1] - pd.Timedelta(days=30)]
                change = (s.iloc[-1] - month.iloc[0]) / month.iloc[0] * 100
                return {"price": float(s.iloc[-1]), "change_pct": round(float(change), 2),
                        "history": s.tail(10), "source": "auto",
                        "fetched": datetime.now().strftime("%d. %b %Y. %H:%M")}
    except Exception:
        pass
    p = try_fetch_robusta()
    if p:
        return {"price": p, "change_pct": None, "history": None, "source": "auto (web)",
                "fetched": datetime.now().strftime("%d. %b %Y. %H:%M")}
    return None

def try_fetch_robusta():
    urls = [
        "https://www.investing.com/commodities/london-coffee",
        "https://hk.investing.com/commodities/london-coffee",
    ]
    for url in urls:
        try:
            r = http_get(url)
            if r.status_code == 200:
                m = re.search(r'instrument-price-last"[^>]*>([0-9][0-9,]*\.?[0-9]*)<', r.text)
                if m:
                    v = float(m.group(1).replace(",", ""))
                    if 1000 < v < 10000:
                        return v
        except Exception:
            continue
    return None

st.markdown("""
<style>
    .big-number { font-size: 2.4rem; font-weight: 700; margin: 4px 0; }
    .sub-number { font-size: 1.5rem; margin: 2px 0; }
    .positive { color: #16a34a; font-weight: 600; }
    .negative { color: #dc2626; font-weight: 600; }
    .header { text-align: center; margin-bottom: 4px; }
    .stButton>button { width: 100%; border-radius: 12px; }
    header, [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
    [data-testid="stStatusWidget"], [data-testid="stAppDeployButton"], #MainMenu, footer,
    a[href*="streamlit.io"], div[class*="viewerBadge"], [class*="profileContainer"] { display: none !important; visibility: hidden !important; }
    .block-container { padding-top: 1.5rem; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='header'>☕ Cijene kave</h1>", unsafe_allow_html=True)
st.caption("Brza provjera za klijente · Arabica automatski · Robusta pokušaj automatskog osvježavanja · EUR / kg / tona")

usd_eur = get_usd_eur()
arabica = get_arabica()
cache = load_robusta_cache()

robusta_live = None
manual_recent = cache.get("source") == "ručno"

if not manual_recent:
    with st.spinner("Ažuriram cijenu Robuste..."):
        robusta_live = get_robusta_live()
    if robusta_live:
        cache = {"price": robusta_live["price"], "updated": robusta_live["fetched"], "source": robusta_live["source"]}
        if load_robusta_cache().get("price") != robusta_live["price"]:
            save_robusta_cache(robusta_live["price"], source=robusta_live["source"])
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
    if manual_recent and st.button("Vrati automatsku cijenu"):
        save_robusta_cache(robusta_price, source="auto")
        st.cache_data.clear()
        st.rerun()
        st.rerun()

col1, col2 = st.columns(2)

with col1:
    with st.container(border=True):
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

with col2:
    with st.container(border=True):
        st.markdown("**Robusta (London)**")
        eur_t = robusta_price * usd_eur
        eur_kg_r = eur_t / 1000
        st.markdown(f"<p class='big-number'>{robusta_price:,.0f} $/t</p>", unsafe_allow_html=True)
        if robusta_live and robusta_live.get("change_pct") is not None:
            rc = robusta_live["change_pct"]
            st.markdown(f"<p class='{'positive' if rc >= 0 else 'negative'}'>{rc:+.2f}% ovaj mjesec</p>", unsafe_allow_html=True)
        st.markdown(f"<p class='sub-number'>€{eur_kg_r:.2f} / kg</p>", unsafe_allow_html=True)
        st.markdown(f"<p class='sub-number'>€{eur_t:,.0f} / t</p>", unsafe_allow_html=True)
        source = cache.get("source", "")
        updated = cache.get("updated", "")
        if updated:
            st.caption(f"Zadnje ažuriranje: {updated} ({source})")

st.divider()

if arabica and "history" in arabica:
    st.subheader("Arabica – zadnje cijene")
    hist = arabica["history"]
    hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
    df = pd.DataFrame({"¢/lb": hist.astype(float)})
    st.line_chart(df, height=220, width="stretch")

if robusta_live and robusta_live.get("history") is not None:
    st.subheader("Robusta – zadnje cijene")
    st.line_chart(pd.DataFrame({"$/t": robusta_live["history"]}), height=220, width="stretch")

st.caption(f"USD/EUR ≈ {usd_eur} · Zadnje ažuriranje cijena: {get_fetch_time()} · automatski svakih 12 h")
st.caption("Arabica: Yahoo Finance · Robusta: Investing.com (ICE London, automatski; ako ne uspije, koristi zadnju cijenu)")

if st.button("🔄 Osvježi", width="stretch"):
    st.cache_data.clear()
    st.rerun()
