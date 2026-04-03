
import math
from itertools import product
from typing import Dict, List

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="Channel Allocation Decision Engine",
    page_icon="📦",
    layout="wide",
)


# -----------------------------
# Helpers
# -----------------------------
def clamp_nonnegative(value: float) -> float:
    return max(0.0, float(value))


def money(value: float) -> str:
    return f"${value:,.0f}"


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def demand_triplet(min_v: float, exp_v: float, max_v: float) -> List[float]:
    ordered = sorted([clamp_nonnegative(min_v), clamp_nonnegative(exp_v), clamp_nonnegative(max_v)])
    return ordered


def build_scenarios(
    dtc_min: float,
    dtc_exp: float,
    dtc_max: float,
    wh_min: float,
    wh_exp: float,
    wh_max: float,
) -> List[Dict]:
    dtc_levels = demand_triplet(dtc_min, dtc_exp, dtc_max)
    wh_levels = demand_triplet(wh_min, wh_exp, wh_max)

    level_names = ["Low", "Expected", "High"]
    weights = {
        (0, 0): 0.08,
        (0, 1): 0.10,
        (0, 2): 0.07,
        (1, 0): 0.10,
        (1, 1): 0.30,
        (1, 2): 0.10,
        (2, 0): 0.07,
        (2, 1): 0.10,
        (2, 2): 0.08,
    }

    scenarios = []
    for i, j in product(range(3), range(3)):
        scenarios.append(
            {
                "name": f"DTC {level_names[i]} / Wholesale {level_names[j]}",
                "dtc_demand": dtc_levels[i],
                "wholesale_demand": wh_levels[j],
                "probability": weights[(i, j)],
            }
        )
    return scenarios


def evaluate_allocation(
    total_inventory: int,
    dtc_share: float,
    dtc_price: float,
    wholesale_price: float,
    unit_cost: float,
    wholesale_commitment: int,
    scenarios: List[Dict],
) -> Dict:
    total_inventory = max(0, int(total_inventory))
    dtc_inventory = int(round(total_inventory * dtc_share))
    wholesale_inventory = total_inventory - dtc_inventory

    commitment_gap = max(0, wholesale_commitment - wholesale_inventory)
    commitment_met = commitment_gap == 0

    weighted_profit = 0.0
    weighted_revenue = 0.0
    weighted_leftover = 0.0
    weighted_unmet_dtc = 0.0
    weighted_unmet_wh = 0.0
    weighted_stockout_flag = 0.0
    profits = []
    scenario_rows = []

    for sc in scenarios:
        dtc_sales = min(dtc_inventory, sc["dtc_demand"])
        wholesale_sales = min(wholesale_inventory, sc["wholesale_demand"])
        units_sold = dtc_sales + wholesale_sales

        revenue = dtc_sales * dtc_price + wholesale_sales * wholesale_price
        cogs = units_sold * unit_cost
        profit = revenue - cogs

        unmet_dtc = max(0.0, sc["dtc_demand"] - dtc_inventory)
        unmet_wh = max(0.0, sc["wholesale_demand"] - wholesale_inventory)
        leftover = max(0.0, total_inventory - units_sold)
        stockout_flag = 1.0 if (unmet_dtc > 0 or unmet_wh > 0) else 0.0

        weight = sc["probability"]
        weighted_profit += profit * weight
        weighted_revenue += revenue * weight
        weighted_leftover += leftover * weight
        weighted_unmet_dtc += unmet_dtc * weight
        weighted_unmet_wh += unmet_wh * weight
        weighted_stockout_flag += stockout_flag * weight
        profits.append(profit)

        scenario_rows.append(
            {
                "Scenario": sc["name"],
                "Probability": sc["probability"],
                "DTC Demand": sc["dtc_demand"],
                "Wholesale Demand": sc["wholesale_demand"],
                "DTC Sales": dtc_sales,
                "Wholesale Sales": wholesale_sales,
                "Revenue": revenue,
                "Profit": profit,
                "Leftover Units": leftover,
                "Unmet DTC": unmet_dtc,
                "Unmet Wholesale": unmet_wh,
            }
        )

    downside_profit = min(profits) if profits else 0.0
    upside_profit = max(profits) if profits else 0.0

    return {
        "dtc_share": dtc_share,
        "wholesale_share": 1 - dtc_share,
        "dtc_inventory": dtc_inventory,
        "wholesale_inventory": wholesale_inventory,
        "expected_profit": weighted_profit,
        "expected_revenue": weighted_revenue,
        "expected_leftover": weighted_leftover,
        "expected_unmet_dtc": weighted_unmet_dtc,
        "expected_unmet_wholesale": weighted_unmet_wh,
        "stockout_risk": weighted_stockout_flag,
        "downside_profit": downside_profit,
        "upside_profit": upside_profit,
        "commitment_gap": commitment_gap,
        "commitment_met": commitment_met,
        "scenario_rows": scenario_rows,
    }


def classify_allocations(results: List[Dict]) -> Dict[str, Dict]:
    valid = [r for r in results if r["commitment_met"]]
    if not valid:
        valid = results

    balanced = max(valid, key=lambda x: x["expected_profit"])
    conservative = max(
        valid,
        key=lambda x: (x["downside_profit"], -x["stockout_risk"], x["expected_profit"]),
    )
    aggressive = max(
        valid,
        key=lambda x: (x["upside_profit"], x["expected_profit"]),
    )

    return {
        "Conservative": conservative,
        "Balanced": balanced,
        "Aggressive": aggressive,
    }


def build_frontier_table(all_results: List[Dict]) -> pd.DataFrame:
    rows = []
    for result in all_results:
        rows.append(
            {
                "DTC Allocation %": int(round(result["dtc_share"] * 100)),
                "Wholesale Allocation %": int(round(result["wholesale_share"] * 100)),
                "Expected Profit": result["expected_profit"],
                "Downside Profit": result["downside_profit"],
                "Upside Profit": result["upside_profit"],
                "Stockout Risk": result["stockout_risk"],
                "Expected Leftover": result["expected_leftover"],
                "Expected Unmet DTC": result["expected_unmet_dtc"],
                "Expected Unmet Wholesale": result["expected_unmet_wholesale"],
                "Commitment Met": result["commitment_met"],
            }
        )
    return pd.DataFrame(rows)


def build_strategy_summary(strategy_map: Dict[str, Dict]) -> pd.DataFrame:
    rows = []
    for name, result in strategy_map.items():
        rows.append(
            {
                "Strategy": name,
                "Allocation": f"{int(round(result['dtc_share'] * 100))}% DTC / {int(round(result['wholesale_share'] * 100))}% Wholesale",
                "Expected Profit": money(result["expected_profit"]),
                "Downside": money(result["downside_profit"]),
                "Upside": money(result["upside_profit"]),
                "Stockout Risk": percent(result["stockout_risk"]),
            }
        )
    return pd.DataFrame(rows)


def strategy_narrative(name: str, strategy: Dict, balanced: Dict) -> List[str]:
    notes = []
    if name == "Conservative":
        notes.append(f"This protects downside first. Worst-case profit lands at {money(strategy['downside_profit'])}.")
    elif name == "Balanced":
        notes.append(f"This maximizes expected profit at {money(strategy['expected_profit'])} across the tested demand range.")
    else:
        notes.append(f"This leans into upside. Best-case profit reaches {money(strategy['upside_profit'])}, but the plan is less forgiving.")

    if strategy["stockout_risk"] > 0.50:
        notes.append("At least one channel is likely to run short across several scenarios.")
    elif strategy["stockout_risk"] > 0.20:
        notes.append("Stockout risk is meaningful. This plan works best only if demand stays near expectation.")
    else:
        notes.append("Stockout risk is relatively contained in the tested scenarios.")

    if strategy["expected_leftover"] > 0.20 * (strategy["dtc_inventory"] + strategy["wholesale_inventory"]):
        notes.append("You are protecting flexibility, but you are also carrying more leftover inventory on average.")

    if not strategy["commitment_met"]:
        notes.append(f"This misses the wholesale commitment by {strategy['commitment_gap']} units.")

    if name != "Balanced":
        dtc_diff = strategy["dtc_share"] - balanced["dtc_share"]
        if abs(dtc_diff) >= 0.10:
            direction = "more" if dtc_diff > 0 else "less"
            notes.append(f"Compared with the balanced plan, this sends {abs(int(round(dtc_diff * 100)))} percentage points {direction} inventory to DTC.")

    return notes


def what_could_go_wrong(best: Dict, dtc_price: float, wholesale_price: float, total_inventory: int) -> List[str]:
    issues = []

    if best["stockout_risk"] > 0.50:
        issues.append("Your inventory is too tight for the demand range you entered. Stockout risk is the main issue.")
    elif best["stockout_risk"] > 0.25:
        issues.append("You are operating with limited slack. A stronger-than-expected week will create channel tension.")

    if best["expected_unmet_dtc"] > best["expected_unmet_wholesale"] * 1.5:
        issues.append("The likely breakage is missed upside in DTC, not wholesale underdelivery.")
    elif best["expected_unmet_wholesale"] > best["expected_unmet_dtc"] * 1.5:
        issues.append("The likely breakage is wholesale underdelivery. Your current setup does not comfortably support account commitments.")

    if wholesale_price >= dtc_price:
        issues.append("Your channel pricing is compressed. DTC is not earning enough premium over wholesale to justify risk.")

    if best["expected_leftover"] > 0.25 * total_inventory:
        issues.append("You are likely holding too much inventory relative to the demand assumptions entered.")

    if not best["commitment_met"]:
        issues.append("The wholesale commitment entered is not feasible under the tested balanced allocation.")

    if not issues:
        issues.append("No severe structural conflict showed up. The next thing to challenge is whether your demand ranges are realistic enough.")

    return issues


def one_thing_to_take(best: Dict, total_inventory: int) -> str:
    if best["stockout_risk"] > 0.50:
        return "Your biggest risk is stockout under demand uncertainty, not overstock."
    if best["expected_unmet_wholesale"] > best["expected_unmet_dtc"] * 1.5:
        return "Your biggest risk is breaking wholesale commitments, not missing DTC upside."
    if best["expected_unmet_dtc"] > best["expected_unmet_wholesale"] * 1.5:
        return "Your biggest risk is underallocating to DTC and leaving revenue on the table."
    if best["expected_leftover"] > 0.25 * total_inventory:
        return "Your biggest risk is excess inventory drag, not shortage."
    return "Your current decision is reasonably balanced; the next improvement should come from tightening assumptions, not adding complexity."


def next_step_suggestion(best: Dict) -> str:
    if best["stockout_risk"] > 0.50:
        return "Tighten demand assumptions and test whether a higher inventory position or lower wholesale promise is feasible."
    if best["expected_unmet_wholesale"] > best["expected_unmet_dtc"]:
        return "Revisit wholesale commitment size before promising more volume."
    if best["expected_unmet_dtc"] > best["expected_unmet_wholesale"]:
        return "Test whether shifting more inventory to DTC increases profit without unacceptable stockout risk."
    return "Run this on three real SKUs and look for repeated channel bias before changing policy broadly."


@st.cache_data
def load_sample_input() -> pd.DataFrame:
    return pd.read_csv("sample_input.csv")


# -----------------------------
# Sidebar inputs
# -----------------------------
st.title("Channel Allocation Decision Engine")
st.caption("One decision: how limited inventory should be split across DTC and wholesale before you commit it.")

sample_df = load_sample_input()
sample_names = sample_df["sku_name"].tolist()

with st.sidebar:
    st.header("Decision Inputs")
    mode = st.radio("Input mode", ["Use sample SKU", "Manual entry"], index=0)

    if mode == "Use sample SKU":
        selected = st.selectbox("Choose sample SKU", sample_names, index=0)
        row = sample_df.loc[sample_df["sku_name"] == selected].iloc[0].to_dict()
    else:
        row = {
            "sku_name": "",
            "unit_cost": 10.0,
            "dtc_price": 20.0,
            "wholesale_price": 12.0,
            "current_inventory": 0,
            "incoming_inventory": 0,
            "dtc_min": 0,
            "dtc_exp": 0,
            "dtc_max": 0,
            "wh_min": 0,
            "wh_exp": 0,
            "wh_max": 0,
            "wholesale_commitment": 0,
        }

    sku_name = st.text_input("SKU / product name", value=row["sku_name"])

    st.subheader("Core economics")
    unit_cost = st.number_input("Unit cost", min_value=0.0, value=float(row["unit_cost"]), step=1.0)
    dtc_price = st.number_input("DTC price", min_value=0.0, value=float(row["dtc_price"]), step=1.0)
    wholesale_price = st.number_input("Wholesale price", min_value=0.0, value=float(row["wholesale_price"]), step=1.0)

    st.subheader("Inventory in play")
    current_inventory = st.number_input("Current inventory", min_value=0, value=int(row["current_inventory"]), step=10)

    st.subheader("Demand ranges")
    st.caption("Enter low / expected / high demand for each channel.")
    dtc_min = st.number_input("DTC low", min_value=0.0, value=float(row["dtc_min"]), step=10.0)
    dtc_exp = st.number_input("DTC expected", min_value=0.0, value=float(row["dtc_exp"]), step=10.0)
    dtc_max = st.number_input("DTC high", min_value=0.0, value=float(row["dtc_max"]), step=10.0)
    wh_min = st.number_input("Wholesale low", min_value=0.0, value=float(row["wh_min"]), step=10.0)
    wh_exp = st.number_input("Wholesale expected", min_value=0.0, value=float(row["wh_exp"]), step=10.0)
    wh_max = st.number_input("Wholesale high", min_value=0.0, value=float(row["wh_max"]), step=10.0)

    with st.expander("Advanced inputs", expanded=False):
        incoming_inventory = st.number_input("Incoming inventory", min_value=0, value=int(row["incoming_inventory"]), step=10)
        wholesale_commitment = st.number_input(
            "Minimum wholesale commitment",
            min_value=0,
            value=int(row["wholesale_commitment"]),
            step=10,
            help="Optional. Enter only if you have effectively promised a buyer a minimum number of units.",
        )


# -----------------------------
# Model execution
# -----------------------------
total_inventory = int(current_inventory + incoming_inventory)
scenarios = build_scenarios(dtc_min, dtc_exp, dtc_max, wh_min, wh_exp, wh_max)

all_results = []
for split_pct in range(0, 101, 5):
    share = split_pct / 100.0
    result = evaluate_allocation(
        total_inventory=total_inventory,
        dtc_share=share,
        dtc_price=dtc_price,
        wholesale_price=wholesale_price,
        unit_cost=unit_cost,
        wholesale_commitment=wholesale_commitment,
        scenarios=scenarios,
    )
    all_results.append(result)

strategy_map = classify_allocations(all_results)
balanced = strategy_map["Balanced"]
frontier_df = build_frontier_table(all_results).sort_values("DTC Allocation %")
summary_df = build_strategy_summary(strategy_map)
issue_list = what_could_go_wrong(balanced, dtc_price, wholesale_price, total_inventory)
headline_takeaway = one_thing_to_take(balanced, total_inventory)
next_step = next_step_suggestion(balanced)

# -----------------------------
# Layout
# -----------------------------
hero_left, hero_mid, hero_right = st.columns([1.1, 1.0, 0.9])
with hero_left:
    st.metric("Product", sku_name or "Unnamed SKU")
with hero_mid:
    st.metric("Total inventory in play", f"{total_inventory:,} units")
with hero_right:
    st.metric("Recommended split", f"{int(round(balanced['dtc_share'] * 100))}% DTC / {int(round(balanced['wholesale_share'] * 100))}% Wholesale")

st.divider()

col_left, col_right = st.columns([1.35, 0.95])

with col_left:
    st.subheader("The decision")
    st.markdown(f"### Recommended: **{int(round(balanced['dtc_share'] * 100))}% to DTC / {int(round(balanced['wholesale_share'] * 100))}% to Wholesale**")
    st.markdown(f"Expected profit: **{money(balanced['expected_profit'])}** · Stockout risk: **{percent(balanced['stockout_risk'])}** · Expected leftover: **{balanced['expected_leftover']:.1f} units**")

    st.subheader("Three viable paths")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    strategy_tabs = st.tabs(["Conservative", "Balanced", "Aggressive"])
    for tab, name in zip(strategy_tabs, ["Conservative", "Balanced", "Aggressive"]):
        strategy = strategy_map[name]
        with tab:
            st.markdown(f"**Allocation:** {int(round(strategy['dtc_share'] * 100))}% DTC / {int(round(strategy['wholesale_share'] * 100))}% Wholesale")
            for note in strategy_narrative(name, strategy, balanced):
                st.write(f"- {note}")

    st.subheader("Tradeoff curve")
    chart_df = frontier_df[["DTC Allocation %", "Expected Profit", "Downside Profit", "Upside Profit"]].set_index("DTC Allocation %")
    st.line_chart(chart_df)
    st.caption("As you push more inventory to DTC, profit potential rises or falls depending on your channel economics and demand ranges.")

with col_right:
    st.subheader("What could go wrong")
    for issue in issue_list:
        st.warning(issue)

    st.subheader("If you only take one thing")
    st.info(headline_takeaway)

    st.subheader("Best next step")
    st.success(next_step)

    st.subheader("Balanced plan details")
    st.markdown(
        f"- **DTC units:** {balanced['dtc_inventory']}  \n- **Wholesale units:** {balanced['wholesale_inventory']}  \n- **Expected unmet DTC:** {balanced['expected_unmet_dtc']:.1f}  \n- **Expected unmet wholesale:** {balanced['expected_unmet_wholesale']:.1f}"
    )

st.divider()

with st.expander("See scenario detail behind the balanced recommendation", expanded=False):
    scenario_df = pd.DataFrame(balanced["scenario_rows"])
    scenario_df["Probability"] = scenario_df["Probability"].map(percent)
    scenario_df["Revenue"] = scenario_df["Revenue"].map(money)
    scenario_df["Profit"] = scenario_df["Profit"].map(money)
    st.dataframe(scenario_df, use_container_width=True, hide_index=True)

st.subheader("What this demo is showing")
st.markdown(
    '''
This demo is intentionally narrow. It helps you decide how limited inventory should be split across:
- direct sales
- wholesale / B2B commitments

It does **not** try to replace ERP, ad tools, or full forecasting infrastructure.
It is a decision surface for one connected call: where inventory should go before cost compounds.
'''
)

st.subheader("Where to go next")
st.markdown(
    '''
Use this for one SKU or one product family first. Then compare patterns across multiple runs.
If you want to test how broader policy choices behave under uncertainty, the next demo should be the **Policy Stress Test**.
'''
)
