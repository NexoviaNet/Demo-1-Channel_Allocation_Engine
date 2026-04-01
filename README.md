# Channel Allocation Decision Engine MVP

A Streamlit demo app for testing one connected decision:

**How should limited inventory be allocated across DTC and wholesale channels?**

## Files

- `app.py` — Streamlit application
- `requirements.txt` — Python dependencies
- `sample_inputs.csv` — example values for quick testing

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## What the app does

- accepts basic unit economics, inventory, and demand ranges
- simulates DTC / wholesale allocation splits
- returns three strategies: Conservative, Balanced, Aggressive
- highlights likely breakage points
- shows scenario-based profit ranges

## Intended use

This is a **demoable MVP**, not a full production system.
It is meant to prove the decision-engine concept before adding:

- CSV upload flows
- multiple SKUs
- saved decision history
- Shopify / channel integrations
