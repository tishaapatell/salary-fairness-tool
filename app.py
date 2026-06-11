"""
Is This Salary Fair?  —  a pay-transparency tool built on official US BLS wage data.

Lets anyone pick a job title + state and see the REAL salary range (median + percentiles)
from the Bureau of Labor Statistics OEWS dataset, compare their own offer against it,
and view how the role pays across all 50 states on a map.

Data: BLS Occupational Employment and Wage Statistics (OEWS), state file.
      https://www.bls.gov/oes/tables.htm   (download the latest "State" cross-industry file)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import os
from dotenv import load_dotenv




# 1. CONFIG

st.set_page_config(page_title="Is This Salary Fair?", page_icon="💵", layout="wide")

load_dotenv()
try:
    import anthropic
    AI_KEY = os.getenv("ANTHROPIC_API_KEY")
    ai_client = anthropic.Anthropic(api_key=AI_KEY) if AI_KEY else None
except ImportError:
    ai_client = None


st.markdown("""
<style>
.block-container {
    padding-top: 1rem;
    padding-bottom: 1rem;
}
</style>
""", unsafe_allow_html=True)

DATA_FILE = "oews_slim.csv"   

# Full state name -> 2-letter code, needed for the US map
STATE_ABBREV = {
    'Alabama':'AL','Alaska':'AK','Arizona':'AZ','Arkansas':'AR','California':'CA',
    'Colorado':'CO','Connecticut':'CT','Delaware':'DE','District of Columbia':'DC',
    'Florida':'FL','Georgia':'GA','Hawaii':'HI','Idaho':'ID','Illinois':'IL',
    'Indiana':'IN','Iowa':'IA','Kansas':'KS','Kentucky':'KY','Louisiana':'LA',
    'Maine':'ME','Maryland':'MD','Massachusetts':'MA','Michigan':'MI','Minnesota':'MN',
    'Mississippi':'MS','Missouri':'MO','Montana':'MT','Nebraska':'NE','Nevada':'NV',
    'New Hampshire':'NH','New Jersey':'NJ','New Mexico':'NM','New York':'NY',
    'North Carolina':'NC','North Dakota':'ND','Ohio':'OH','Oklahoma':'OK','Oregon':'OR',
    'Pennsylvania':'PA','Rhode Island':'RI','South Carolina':'SC','South Dakota':'SD',
    'Tennessee':'TN','Texas':'TX','Utah':'UT','Vermont':'VT','Virginia':'VA',
    'Washington':'WA','West Virginia':'WV','Wisconsin':'WI','Wyoming':'WY'
}

WAGE_COLS = ['A_PCT10', 'A_PCT25', 'A_MEDIAN', 'A_PCT75', 'A_PCT90', 'A_MEAN']

# 2. LOAD + CLEAN DATA  (cached so it loads once, not on every click)

@st.cache_data
def load_data():
    df = pd.read_csv(DATA_FILE)
    df.columns = [c.strip().upper() for c in df.columns]   # normalize headers
    
    # Keep only detailed occupations (drop aggregate/summary rows)
    group_col = 'O_GROUP' if 'O_GROUP' in df.columns else 'OCC_GROUP'
    if group_col in df.columns:
        df = df[df[group_col].astype(str).str.lower() == 'detailed']

    # Wage columns contain '*' (not released) and '#' (capped). Force to numbers.
    for c in WAGE_COLS:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce')

    # Keep only the 50 states + DC (drop national/territory rows)
    df = df[df['AREA_TITLE'].isin(STATE_ABBREV.keys())]
    return df

@st.cache_data
def load_bea():
    """Load BEA Regional Price Parities (cost of living, US avg = 100).
    Expects a CSV named bea_rpp.csv with two columns: State, RPP.
    Optional — if the file is missing, the cost-of-living feature is skipped."""
    try:
        b = pd.read_csv("bea_rpp.csv")
    except FileNotFoundError:
        return None
    b.columns = [c.strip() for c in b.columns]
    b = b.rename(columns={'State': 'AREA_TITLE'})
    b['RPP'] = pd.to_numeric(b['RPP'], errors='coerce')
    return b[['AREA_TITLE', 'RPP']].dropna()

try:
    df = load_data()
except FileNotFoundError:
    st.error(f"Couldn't find '{DATA_FILE}'. Download the BLS OEWS state file, "
             f"rename it to '{DATA_FILE}', and put it in this folder.")
    st.stop()

bea = load_bea()   # None if bea_rpp.csv is absent


# 3. HEADER

st.title("💵 Is This Salary Fair?")
st.markdown(
    "See the **real** salary range for any job in any US state, using official "
    "**Bureau of Labor Statistics** wage data — and check how an offer stacks up."
)


# 4. USER INPUTS

col1, col2 = st.columns(2)
with col1:
    state = st.selectbox("Select a state", sorted(df['AREA_TITLE'].unique()))
with col2:
    occs = sorted(df[df['AREA_TITLE'] == state]['OCC_TITLE'].unique())
    occupation = st.selectbox("Select a job title", occs)

offer = st.number_input("Optional: enter a salary offer to compare ($/year)",
                        min_value=0, value=0, step=1000)


# 5. PULL THE ROW FOR THIS STATE + OCCUPATION

row = df[(df['AREA_TITLE'] == state) & (df['OCC_TITLE'] == occupation)]

if row.empty or row['A_MEDIAN'].isna().all():
    st.warning("BLS hasn't released wage data for this job in this state. Try another.")
    st.stop()

row = row.iloc[0]

# 6. SHOW THE KEY NUMBERS


st.subheader(f"{occupation} — {state}")

# --- Cost of living adjustment ---
real_median = None
rpp = None

if bea is not None:
    rpp_row = bea[bea['AREA_TITLE'] == state]
    if not rpp_row.empty:
        rpp = float(rpp_row['RPP'].iloc[0])
        real_median = row['A_MEDIAN'] / (rpp / 100)

# --- Single aligned row for ALL KPIs ---
m1, m2, m3, m4, m5 = st.columns(5)

m1.metric("Median (50th pct)", f"${row['A_MEDIAN']:,.0f}")
m2.metric("Entry level (10th pct)", f"${row['A_PCT10']:,.0f}")
m3.metric("Top earners (90th pct)", f"${row['A_PCT90']:,.0f}")

# show placeholders if BEA missing
if rpp is not None:
    m4.metric("Cost of living index", f"{rpp:.0f}",
              help="US average = 100. Above = more expensive")
else:
    m4.metric("Cost of living index", "N/A")

if real_median is not None:
    m5.metric(
        "Real (cost-adjusted) median",
        f"${real_median:,.0f}",
        delta=f"{real_median - row['A_MEDIAN']:,.0f}"
    )
else:
    m5.metric("Real (cost-adjusted) median", "N/A")


# 7. PERCENTILE BAR CHART

pct_df = pd.DataFrame({
    "Percentile": ["10th", "25th", "Median", "75th", "90th"],
    "Annual Wage": [row['A_PCT10'], row['A_PCT25'], row['A_MEDIAN'],
                    row['A_PCT75'], row['A_PCT90']]
})
fig_bar = px.bar(pct_df, x="Percentile", y="Annual Wage",
                 title="Salary distribution", text_auto=".2s")
st.plotly_chart(fig_bar, use_container_width=True)


# 8. OFFER COMPARISON

if offer > 0:
    anchors_pct = [10, 25, 50, 75, 90]
    anchors_val = [row['A_PCT10'], row['A_PCT25'], row['A_MEDIAN'],
                   row['A_PCT75'], row['A_PCT90']]
    est_pct = float(np.interp(offer, anchors_val, anchors_pct))  # rough percentile rank

    if offer < row['A_MEDIAN']:
        st.error(f"An offer of ${offer:,.0f} is **below the median** "
                 f"(~{est_pct:.0f}th percentile) for this role in {state}.")
    else:
        st.success(f"An offer of ${offer:,.0f} is **at or above the median** "
                   f"(~{est_pct:.0f}th percentile) for this role in {state}.")

# 8b. AI PLAIN-ENGLISH EXPLANATION  (optional — only runs if an API key is set)

if ai_client and st.button("🤖 Explain this in plain English"):
    facts = (
        f"Occupation: {occupation}. State: {state}. "
        f"Median annual wage: ${row['A_MEDIAN']:,.0f}. "
        f"10th percentile: ${row['A_PCT10']:,.0f}. "
        f"90th percentile: ${row['A_PCT90']:,.0f}. "
        + (f"User's offer: ${offer:,.0f}. " if offer > 0 else "")
    )
    prompt = (
        "You are a helpful career advisor. Using ONLY the official BLS wage facts "
        "below, write 2-3 short, plain-English sentences for a non-technical person "
        "explaining what these numbers mean and (if an offer is given) how it compares. "
        "Do not invent any numbers beyond those provided.\n\n" + facts
    )
    with st.spinner("Asking the AI..."):
        try:
            resp = ai_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=250,
                messages=[{"role": "user", "content": prompt}],
            )
            st.write(resp.content[0].text.replace("$", "\\$"))
        except Exception as e:
            st.warning(f"AI explanation unavailable right now: {e}")
elif not ai_client:
    st.caption("💡 Tip: add an ANTHROPIC_API_KEY to enable a plain-English AI explanation.")



# 8c. AI NEGOTIATION TALKING POINTS  (uses ONLY the real BLS numbers)

if ai_client and offer > 0 and st.button("💬 Generate negotiation talking points"):
    facts = (
        f"Job title: {occupation}. State: {state}. "
        f"Candidate's current offer: ${offer:,.0f}. "
        f"BLS median wage: ${row['A_MEDIAN']:,.0f}. "
        f"25th percentile: ${row['A_PCT25']:,.0f}. "
        f"75th percentile: ${row['A_PCT75']:,.0f}. "
        f"90th percentile: ${row['A_PCT90']:,.0f}."
    )
    prompt = (
        "You are a professional career coach helping someone prepare for a salary "
        "negotiation. Using ONLY the official BLS wage facts below, write 2-3 concise, "
        "professional talking points the candidate could use in a negotiation. "
        "Reference the market benchmarks specifically. Be measured and realistic - do "
        "NOT invent any numbers beyond those provided, and do not over-promise. If the "
        "offer is already at or above the median, acknowledge it's competitive.\n\n"
        + facts
    )
    with st.spinner("Drafting talking points..."):
        try:
            resp = ai_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=350,
                messages=[{"role": "user", "content": prompt}],
            )
            st.markdown("#### 💬 Your negotiation talking points")
            st.write(resp.content[0].text.replace("$", "\\$"))
            st.caption("Generated from official BLS benchmarks. Review before using; "
                       "this is informational, not professional negotiation advice.")
        except Exception as e:
            st.warning(f"Couldn't generate talking points right now: {e}")
elif ai_client and offer == 0:
    st.caption("💡 Enter an offer above to generate AI negotiation talking points.")


# 9. US MAP — how this occupation pays across all states

st.subheader(f"How {occupation} pays across the US (median wage)")
occ_map = df[df['OCC_TITLE'] == occupation].copy()
occ_map['code'] = occ_map['AREA_TITLE'].map(STATE_ABBREV)
occ_map = occ_map.dropna(subset=['A_MEDIAN', 'code'])

fig_map = px.choropleth(occ_map, locations='code', locationmode="USA-states",
                        color='A_MEDIAN', scope="usa",
                        color_continuous_scale="Blues",
                        labels={'A_MEDIAN': 'Median wage ($)'})
st.plotly_chart(fig_map, use_container_width=True)


# 9b. BEST STATES BY REAL (COST-ADJUSTED) PAY  — the analytical headline

if bea is not None:
    st.subheader(f"💡 Best states for {occupation} (adjusted for cost of living)")
    rank = (df[df['OCC_TITLE'] == occupation][['AREA_TITLE', 'A_MEDIAN']]
            .merge(bea, on='AREA_TITLE', how='inner')
            .dropna(subset=['A_MEDIAN', 'RPP']))
    rank['Real Median'] = (rank['A_MEDIAN'] / (rank['RPP'] / 100)).round(0)
    rank = rank.rename(columns={'AREA_TITLE': 'State', 'A_MEDIAN': 'Nominal Median',
                                'RPP': 'Cost of Living'})
    rank = rank.sort_values('Real Median', ascending=False).reset_index(drop=True)
    rank.index += 1  # rank starting at 1

    st.caption("Same paycheck buys more in cheaper states. 'Real Median' = nominal wage "
               "adjusted for each state's cost of living (US avg = 100).")
    st.dataframe(rank.style.format({'Nominal Median': '${:,.0f}',
                                    'Cost of Living': '{:.0f}',
                                    'Real Median': '${:,.0f}'}),
                 use_container_width=True)

    best = rank.iloc[0]
    st.success(f"🏆 For real purchasing power, **{best['State']}** ranks #1 for this role: "
               f"a nominal ${best['Nominal Median']:,.0f} is worth "
               f"~${best['Real Median']:,.0f} after cost of living.")


# 10. HONEST DISCLAIMER  (the trust signal)

st.caption(
    "Sources: U.S. Bureau of Labor Statistics (OEWS) for wages; U.S. Bureau of "
    "Economic Analysis (Regional Price Parities) for cost of living. Figures are "
    "official state-level benchmarks, not guarantees for any individual role. "
    "Cost-of-living adjustment is statewide, not city-specific. '*' / missing values "
    "mean the agency did not release an estimate for that cell."
)