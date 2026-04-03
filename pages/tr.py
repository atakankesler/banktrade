import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta
from streamlit_autorefresh import st_autorefresh

st_autorefresh(interval=60_000, key="autorefresh")


def zone_signal(series):
    """RSI + Bollinger Bands + MACD hesaplar, gösterge değerleri ve yorum döndürür."""
    if len(series) < 35:
        return None, ""

    # RSI (14)
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi_val = float(100 - (100 / (1 + gain / loss)).iloc[-1])

    # Bollinger Bands (20, 2σ)
    sma = series.rolling(20).mean()
    std = series.rolling(20).std()
    upper_bb = float((sma + 2 * std).iloc[-1])
    lower_bb = float((sma - 2 * std).iloc[-1])
    current = float(series.iloc[-1])
    bb_pct = (current - lower_bb) / (upper_bb - lower_bb) * 100  # 0=alt, 100=üst

    # MACD (12, 26, 9)
    ema12 = series.ewm(span=12, adjust=False).mean()
    ema26 = series.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9, adjust=False).mean()
    macd_bull = macd.iloc[-1] > signal_line.iloc[-1]

    # Skorlama
    score = 0
    if rsi_val < 35: score += 1
    elif rsi_val > 65: score -= 1
    if bb_pct < 20: score += 1
    elif bb_pct > 80: score -= 1
    if macd_bull: score += 1
    else: score -= 1

    # Yorum
    rsi_str = f"RSI {rsi_val:.0f} ({'aşırı satım' if rsi_val < 35 else 'aşırı alım' if rsi_val > 65 else 'nötr'})"
    bb_str = f"BB %{bb_pct:.0f} ({'alt bant' if bb_pct < 20 else 'üst bant' if bb_pct > 80 else 'orta'})"
    macd_str = f"MACD {'yukarı' if macd_bull else 'aşağı'}"

    if score >= 2:
        zone = "buy"
        yorum = f"Alım bölgesi: {rsi_str}, {bb_str}, {macd_str}."
    elif score <= -2:
        zone = "sell"
        yorum = f"Satım bölgesi: {rsi_str}, {bb_str}, {macd_str}."
    else:
        zone = None
        yorum = f"Nötr: {rsi_str}, {bb_str}, {macd_str}."

    return zone, yorum


def find_support_resistance(series, window=10, num_levels=3, tolerance=0.02):
    resistance_pts, support_pts = [], []
    for i in range(window, len(series) - window):
        sl = series.iloc[i - window: i + window + 1]
        if series.iloc[i] == sl.max():
            resistance_pts.append(float(series.iloc[i]))
        if series.iloc[i] == sl.min():
            support_pts.append(float(series.iloc[i]))

    def cluster(levels):
        if not levels:
            return []
        levels = sorted(levels)
        clusters, group = [], [levels[0]]
        for lv in levels[1:]:
            if (lv - group[0]) / group[0] < tolerance:
                group.append(lv)
            else:
                clusters.append(sum(group) / len(group))
                group = [lv]
        clusters.append(sum(group) / len(group))
        return clusters

    current = float(series.iloc[-1])
    res_levels = sorted([r for r in cluster(resistance_pts) if r > current * 0.98])[:num_levels]
    sup_levels = sorted([s for s in cluster(support_pts) if s < current * 1.02], reverse=True)[:num_levels]
    return sup_levels, res_levels


TURKISH_BANKS = {
    "Garanti BBVA": "GARAN.IS",
    "Akbank": "AKBNK.IS",
    "İş Bankası": "ISCTR.IS",
    "Yapı Kredi": "YKBNK.IS",
    "Halkbank": "HALKB.IS",
    "Vakıfbank": "VAKBN.IS",
    "TSKB": "TSKB.IS",
    "Albaraka Türk": "ALBRK.IS",
    "QNB Finansbank": "QNBFB.IS",
    "Şekerbank": "SKBNK.IS",
}

INDICES = {
    "Bankacılık Endeksi (XBANK)": "XBANK.IS",
    "BIST 100 (XU100)": "XU100.IS",
}

OTHER_ASSETS = {
    "Altın (USD)": "GC=F",
    "Gümüş (USD)": "SI=F",
    "NASDAQ": "^IXIC",
    "Dolar / TL": "USDTRY=X",
    "Euro / TL": "EURTRY=X",
}

st.title("🏦 Türk Bankaları Hisse Artış Oranları")
st.markdown("Yahoo Finance verilerini kullanarak seçilen tarih aralığındaki hisse performansını gösterir.")

with st.sidebar:
    st.header("⚙️ Ayarlar")

    selected_banks = st.multiselect(
        "Bankalar",
        options=list(TURKISH_BANKS.keys()),
        default=list(TURKISH_BANKS.keys())[:5],
    )

    st.markdown("**Endeksler**")
    show_xbank = st.checkbox("Bankacılık Endeksi (XBANK)", value=True)
    show_xu100 = st.checkbox("BIST 100 (XU100)", value=True)

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

    fetch_btn = st.button("📊 Verileri Getir", use_container_width=True, type="primary")

selected_indices = {}
if show_xbank:
    selected_indices["Bankacılık Endeksi (XBANK)"] = INDICES["Bankacılık Endeksi (XBANK)"]
if show_xu100:
    selected_indices["BIST 100 (XU100)"] = INDICES["BIST 100 (XU100)"]

selected_other_assets = {k: OTHER_ASSETS[k] for k in selected_others}

if not selected_banks and not selected_indices and not selected_other_assets:
    st.warning("Lütfen en az bir banka veya endeks seçin.")
    st.stop()

if start_date >= end_date:
    st.error("Başlangıç tarihi, bitiş tarihinden önce olmalıdır.")
    st.stop()

if fetch_btn or "df_results" not in st.session_state:
    all_items = {**{b: TURKISH_BANKS[b] for b in selected_banks}, **selected_indices, **selected_other_assets}
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
            raw_close_data = {}

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
                    "Tür": "Endeks" if is_index else "Hisse",
                    "Başlangıç Değeri (₺)": round(start_price, 2),
                    "Bitiş Değeri (₺)": round(end_price, 2),
                    "Artış / Düşüş (%)": round(change_pct, 2),
                    "En Yüksek (₺)": round(max_price, 2),
                    "En Yüksek Tarih": max_date,
                })

                normalized = (series / series.iloc[0] - 1) * 100
                price_data[name] = (normalized, is_index)
                raw_close_data[name] = (series, is_index)

            st.session_state["df_results"] = pd.DataFrame(results)
            st.session_state["price_data"] = price_data
            st.session_state["raw_close"] = raw_close_data

        except Exception as e:
            st.error(f"Veri çekilirken hata oluştu: {e}")
            st.stop()

df = st.session_state.get("df_results", pd.DataFrame())
price_data = st.session_state.get("price_data", {})
raw_close = st.session_state.get("raw_close", {})

if df.empty:
    st.info("Sol panelden tarih aralığı ve banka seçip 'Verileri Getir' butonuna basın.")
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
        dist_from_high = ((row['Bitiş Değeri (₺)'] - row['En Yüksek (₺)']) / row['En Yüksek (₺)']) * 100
        name = row["Ad"]
        sup_str, res_str = "—", "—"
        zone, yorum = None, ""

        if name in raw_close:
            series, _ = raw_close[name]
            if len(series) >= 25:
                sup_levels, res_levels = find_support_resistance(series)
                if sup_levels:
                    sup_str = " / ".join(f"₺{v:.2f}" for v in sup_levels[:2])
                if res_levels:
                    res_str = " / ".join(f"₺{v:.2f}" for v in res_levels[:2])
            if len(series) >= 35:
                zone, yorum = zone_signal(series)

        delta_val = row['Artış / Düşüş (%)']
        delta_color = "#22c55e" if delta_val >= 0 else "#ef4444"
        delta_sign = "+" if delta_val >= 0 else ""

        if zone == "buy":
            border = "2px solid #22c55e"
            badge = "<span style='background:#22c55e;color:#fff;padding:1px 6px;border-radius:4px;font-size:0.75rem;'>Alım Bölgesi</span><br>"
        elif zone == "sell":
            border = "2px solid #ef4444"
            badge = "<span style='background:#ef4444;color:#fff;padding:1px 6px;border-radius:4px;font-size:0.75rem;'>Satım Bölgesi</span><br>"
        else:
            border = "1px solid #333"
            badge = ""

        st.markdown(
            f"<div style='border:{border};border-radius:10px;padding:12px 14px;margin-bottom:4px;'>"
            f"<div style='font-size:0.8rem;color:#aaa;margin-bottom:2px;'>{name}</div>"
            f"<div style='font-size:1.35rem;font-weight:700;'>₺{row['Bitiş Değeri (₺)']:.2f}</div>"
            f"<div style='color:{delta_color};font-size:0.9rem;font-weight:600;margin-bottom:6px;'>{delta_sign}{delta_val:.2f}%</div>"
            f"<div style='font-size:0.8rem;color:#888;line-height:1.8;'>"
            f"Başlangıç: ₺{row['Başlangıç Değeri (₺)']:.2f}<br>"
            f"En Yüksek: ₺{row['En Yüksek (₺)']:.2f} ({row['En Yüksek Tarih']})<br>"
            f"Zirveden: {dist_from_high:+.2f}%<br>"
            f"<span style='color:#ef4444;'>{res_str}</span><br>"
            f"<span style='color:#22c55e;'>{sup_str}</span><br>"
            f"{badge}"
            f"<span style='font-size:0.72rem;color:#666;'>{yorum}</span>"
            f"</div></div>",
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

st.plotly_chart(fig, use_container_width=True)

st.divider()

# --- Tablo ---
st.subheader("📋 Detaylı Tablo")
styled = df.copy()
st.dataframe(
    styled,
    hide_index=True,
    use_container_width=True,
    column_config={
        "Artış / Düşüş (%)": st.column_config.NumberColumn(format="%.2f%%"),
        "Başlangıç Değeri (₺)": st.column_config.NumberColumn(format="₺%.2f"),
        "Bitiş Değeri (₺)": st.column_config.NumberColumn(format="₺%.2f"),
    },
)