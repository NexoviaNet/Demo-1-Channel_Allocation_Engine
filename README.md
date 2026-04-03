
# Channel Allocation Decision Engine

This repo includes a Streamlit MVP for one connected decision:

**How should limited inventory be split across DTC and wholesale before you commit it?**

## Important note on the sample input

The earlier sample values were intentionally placeholder-style demo values.
This zip now includes a more realistic built-in sample dataset in `sample_input.csv` so the app has:
- actual SKU-like examples
- channel-specific demand ranges
- prices and costs
- inventory and commitment assumptions

It is still demo data, not your real merchant data.

## Files

- `app.py` — Streamlit app
- `sample_input.csv` — built-in sample SKUs
- `requirements.txt` — dependencies
- `README.md` — run notes and framing

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Input modes

The app supports:
1. **Use sample SKU** — loads one of the included sample rows
2. **Manual entry** — lets you type your own assumptions

## What the demo presents

- the recommended split
- three viable paths
- what could go wrong
- one key takeaway
- the best next step
- a tradeoff curve across allocation choices

## Website framing

**Headline:**  
Decide where your inventory should go — before you commit it.

**Subhead:**  
Test DTC vs wholesale allocation with visible tradeoffs, risks, and next-step guidance.
