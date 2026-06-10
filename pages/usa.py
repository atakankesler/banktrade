import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import date, timedelta

US_TECH_STOCKS = {
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "NVIDIA": "NVDA",
    "Amazon": "AMZN",
    "Alphabet (Google)": "GOOGL",
    "Meta": "META",
    "Tesla": "TSLA",
    "Netflix": "NFLX",
}

INDICES = {
    "S&P 500": "^GSPC",
    "NASDAQ Composite": "^IXIC",
}

OTHER_ASSETS = {
    "Dow Jones": "^DJI",
    "Altın (USD)": "GC=F",
    "Ham Petrol (USD)": "CL=F",
    "Bitcoin (USD)": "BTC-USD",
    "Ethereum (USD)": "ETH-USD",
    "USD / EUR": "EURUSD=X",
    "VIX (Volatilite)": "^VIX",
    "Gümüş (USD)": "SI=F",
}

st.title("💻 US Tech Stocks Artış Oranları")
st.markdown("Yahoo Finance verilerini kullanarak seçilen tarih aralığındaki hisse performansını gösterir.")

with st.sidebar:
    st.header("⚙️ Ayarlar")

    selected_stocks = st.multiselect(
        "Teknoloji Şirketleri",
        options=list(US_TECH_STOCKS.keys()),
        default=list(US_TECH_STOCKS.keys())[:5],
    )

    st.markdown("**Endeksler**")
    show_sp500 = st.checkbox("S&P 500", value=True)
    show_nasdaq = st.checkbox("NASDAQ Composite", value=True)

    st.markdown("**Karşılaştırma**")
    show_halkb = st.checkbox("Halkbank (HALKB.IS)", value=True)

    st.markdown("**Diğer Varlıklar**")
    selected_others = st.multiselect(
        "Varlık Seç",
        options=list(OTHER_ASSETS.keys()),
        default=[],
        label_visibility="collapsed",
    )

    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Başlangıç Tarihi",
            value=date.today() - timedelta(days=365),
            max_value=date.today() - timedelta(days=1),
        )
    with col2:
        end_date = st.date_input(
            "Bitiş Tarihi",
            value=date.today(),
            max_value=date.today(),
        )

    chart_type = st.radio(
        "Grafik Türü",
        ["Çizgi Grafik", "Bar Grafik"],
    )

    fetch_btn = st.button("📊 Verileri Getir", width="stretch", type="primary")

selected_indices = {}
if show_sp500:
    selected_indices["S&P 500"] = INDICES["S&P 500"]
if show_nasdaq:
    selected_indices["NASDAQ Composite"] = INDICES["NASDAQ Composite"]

selected_other_assets = {k: OTHER_ASSETS[k] for k in selected_others}

if not selected_stocks and not selected_indices and not selected_other_assets:
    st.warning("Lütfen en az bir hisse veya endeks seçin.")
    st.stop()

if start_date >= end_date:
    st.error("Başlangıç tarihi, bitiş tarihinden önce olmalıdır.")
    st.stop()

if show_halkb:
    selected_other_assets["Halkbank"] = "HALKB.IS"

if fetch_btn or "tech_df_results" not in st.session_state:
    all_items = {**{s: US_TECH_STOCKS[s] for s in selected_stocks}, **selected_indices, **selected_other_assets}
    tickers = list(all_items.values())

    with st.spinner("Veriler Yahoo Finance'den çekiliyor..."):
        try:
            raw = yf.download(
                tickers,
                start=start_date,
                end=end_date + timedelta(days=1),
                progress=False,
                auto_adjust=True,
            )

            if raw.empty:
                st.error("Seçilen tarih aralığında veri bulunamadı.")
                st.stop()

            close = raw["Close"] if len(tickers) > 1 else raw[["Close"]]
            if len(tickers) == 1:
                close.columns = tickers

            results = []
            price_data = {}

            for name, ticker in all_items.items():
                if ticker not in close.columns:
                    continue
                series = close[ticker].dropna()
                if len(series) < 2:
                    continue

                start_price = series.iloc[0]
                end_price = series.iloc[-1]
                change_pct = ((end_price - start_price) / start_price) * 100
                is_index = name in selected_indices or name in selected_other_assets
                max_price = series.max()
                max_date = series.idxmax().strftime("%d.%m.%Y")

                results.append({
                    "Ad": name,
                    "Sembol": ticker,
                    "Tür": "Endeks/Varlık" if is_index else "Hisse",
                    "Başlangıç Değeri ($)": round(start_price, 2),
                    "Bitiş Değeri ($)": round(end_price, 2),
                    "Artış / Düşüş (%)": round(change_pct, 2),
                    "En Yüksek ($)": round(max_price, 2),
                    "En Yüksek Tarih": max_date,
                })

                normalized = (series / series.iloc[0] - 1) * 100
                price_data[name] = (normalized, is_index)

            st.session_state["tech_df_results"] = pd.DataFrame(results)
            st.session_state["tech_price_data"] = price_data

        except Exception as e:
            st.error(f"Veri çekilirken hata oluştu: {e}")
            st.stop()

df = st.session_state.get("tech_df_results", pd.DataFrame())
price_data = st.session_state.get("tech_price_data", {})

if df.empty:
    st.info("Sol panelden tarih aralığı ve hisse seçip 'Verileri Getir' butonuna basın.")
    st.stop()

# --- Özet Kartlar ---
st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 0.875rem !important; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)
st.subheader("📈 Özet")
cols = st.columns(len(df))
for i, row in df.iterrows():
    with cols[i]:
        st.metric(
            label=row["Ad"],
            value=f"${row['Bitiş Değeri ($)']:.2f}",
            delta=f"{row['Artış / Düşüş (%)']:+.2f}%",
        )
        dist_from_high = ((row['Bitiş Değeri ($)'] - row['En Yüksek ($)']) / row['En Yüksek ($)']) * 100
        st.markdown(
            f"<p style='font-size:0.875rem; color:#888; margin-top:-12px; line-height:1.7;'>"
            f"Başlangıç: ${row['Başlangıç Değeri ($)']:.2f}<br>"
            f"En Yüksek: ${row['En Yüksek ($)']:.2f}<br>"
            f"Tarih: {row['En Yüksek Tarih']}<br>"
            f"Zirveden Uzaklık: {dist_from_high:+.2f}%"
            f"</p>",
            unsafe_allow_html=True,
        )

st.divider()

# --- Grafik ---
st.subheader("📊 Normalize Fiyat Değişimi (%)")

if chart_type == "Çizgi Grafik":
    fig = go.Figure()
    for name, (series, is_index) in price_data.items():
        fig.add_trace(go.Scatter(
            x=series.index,
            y=series.values,
            name=name,
            mode="lines",
            line=dict(width=3 if is_index else 1.5, dash="dash" if is_index else "solid"),
        ))
    fig.update_layout(
        xaxis_title="Tarih",
        yaxis_title="Değişim (%)",
        hovermode="x unified",
        height=450,
        yaxis=dict(ticksuffix="%"),
    )
else:
    bar_df = df.sort_values("Artış / Düşüş (%)", ascending=True)
    colors = ["#ef4444" if v < 0 else "#22c55e" for v in bar_df["Artış / Düşüş (%)"]]
    fig = go.Figure(go.Bar(
        x=bar_df["Artış / Düşüş (%)"],
        y=bar_df["Ad"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in bar_df["Artış / Düşüş (%)"]],
        textposition="outside",
    ))
    fig.update_layout(
        xaxis_title="Artış / Düşüş (%)",
        xaxis=dict(ticksuffix="%"),
        height=400,
    )

st.plotly_chart(fig, width="stretch")

# --- NVIDIA vs HALKB Açıklık Tablosu ---
_gap_candidates = {
    "NVIDIA": "NVIDIA",
    "HALKB": "Halkbank",
}

def _to_naive(s):
    if getattr(s.index, "tz", None) is not None:
        s = s.copy()
        s.index = s.index.tz_convert(None)
    return s

_named = {
    col: _to_naive(price_data[key][0]).rename(col)
    for col, key in _gap_candidates.items()
    if key in price_data
}

if "NVIDIA" in _named and "HALKB" in _named:
    combined = pd.concat(_named.values(), axis=1, join="inner")
    combined["HALKB-NVIDIA"] = combined["HALKB"] - combined["NVIDIA"]

    n_days = (combined.index[-1] - combined.index[0]).days
    if n_days <= 30:
        tbl = combined.copy()
        freq_label = "Günlük"
    elif n_days <= 180:
        tbl = combined.resample("W").last()
        freq_label = "Haftalık"
    else:
        tbl = combined.resample("ME").last()
        freq_label = "Aylık"

    tbl = tbl.dropna(how="all")

    st.divider()
    st.subheader(f"📐 NVIDIA & HALKB Normalize Açıklık ({freq_label})")

    cur = float(combined["HALKB-NVIDIA"].iloc[-1])
    avg = float(combined["HALKB-NVIDIA"].mean())
    mx = float(combined["HALKB-NVIDIA"].max())
    mn = float(combined["HALKB-NVIDIA"].min())

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Güncel Açıklık", f"{cur:+.2f}%")
    with m2:
        st.metric("Ort. Açıklık", f"{avg:+.2f}%")
    with m3:
        st.metric("Maks. Açıklık", f"{mx:+.2f}%")
    with m4:
        st.metric("Min. Açıklık", f"{mn:+.2f}%")

    gap_df = pd.DataFrame({
        "Tarih": tbl.index.strftime("%d.%m.%Y"),
        "NVIDIA (%)": tbl["NVIDIA"].round(2).values,
        "HALKB (%)": tbl["HALKB"].round(2).values,
        "HALKB-NVIDIA (%)": tbl["HALKB-NVIDIA"].round(2).values,
    })

    st.dataframe(
        gap_df,
        hide_index=True,
        width="stretch",
        column_config={
            "NVIDIA (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "HALKB (%)": st.column_config.NumberColumn(format="%.2f%%"),
            "HALKB-NVIDIA (%)": st.column_config.NumberColumn(format="%.2f%%"),
        },
    )

st.divider()

# --- Tablo ---
st.subheader("📋 Detaylı Tablo")
styled = df.copy()
st.dataframe(
    styled,
    hide_index=True,
    width="stretch",
    column_config={
        "Artış / Düşüş (%)": st.column_config.NumberColumn(format="%.2f%%"),
        "Başlangıç Değeri ($)": st.column_config.NumberColumn(format="$%.2f"),
        "Bitiş Değeri ($)": st.column_config.NumberColumn(format="$%.2f"),
        "En Yüksek ($)": st.column_config.NumberColumn(format="$%.2f"),
    },
)
