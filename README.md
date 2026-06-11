
# Is This Salary Fair? — US Pay Transparency Tool

A web app that turns official US government data into honest salary benchmarks.
Pick any job + state to see real wage percentiles (BLS), a cost-of-living-adjusted
"best states" ranking (BEA), a US wage map, and AI-generated plain-English
explanations and negotiation talking points — all grounded in official data.

**Live demo:** https://salary-fairness-tool-5pe5skm3q5coigdmcta4ht.streamlit.app

**Tools:** Python, Streamlit, Plotly, pandas, Anthropic API
**Data:** US Bureau of Labor Statistics (OEWS) + Bureau of Economic Analysis (RPP)

## Run locally
1. pip install -r requirements.txt
2. Add BLS OEWS state data as oews_slim.csv and BEA data as bea_rpp.csv
3. (Optional AI) Add a .env file with ANTHROPIC_API_KEY=your_key
4. streamlit run app.py
