import pandas as pd
import streamlit as st
from itertools import product
from typing import Dict, List

st.set_page_config(
    page_title="Channel Allocation Decision Engine",
    page_icon="📦",
    layout="wide",
)


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

    scenario_rows = []
    weighted_profit = 0.0
    weighted_revenue = 0.0
    weighted_units_sold = 0.0
    weighted_leftover = 0.0
    weighted_unmet_dtc = 0.0
    weighted_unmet_wh = 0.0
    weighted_stockout_flag = 0.0

    profits = []

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
        weighted_units_sold += units_sold * weight
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
        "expected_units_sold": weighted_units_sold,
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


def build_summary_table(strategy_map: Dict[str, Dict]) -> pd.DataFrame:
    rows = []
    for name, result in strategy_map.items():
        rows.append(
            {
                "Strategy": name,
                "DTC Allocation": percent(result["dtc_share"]),
                "Wholesale Allocation": percent(result["wholesale_share"]),
                "DTC Units": int(result["dtc_inventory"]),
                "Wholesale Units": int(result["wholesale_inventory"]),
                "Expected Revenue": money(result["expected_revenue"]),
                "Expected Profit": money(result["expected_profit"]),
                "Downside Profit": money(result["downside_profit"]),
                "Upside Profit": money(result["upside_profit"]),
                "Stockout Risk": percent(result["stockout_risk"]),
                "Expected Leftover": f"{result['expected_leftover']:.1f}",
            }
        )
    return pd.DataFrame(rows)


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
                "Commitment Met": result["commitment_met"],
            }
        )
    return pd.DataFrame(rows)


def explain_strategy(name: str, strategy: Dict, balanced: Dict) -> List[str]:
    notes = []

    if name == "Conservative":
        notes.append(
            f"This option protects downside first. Worst-case profit lands at {money(strategy['downside_profit'])}."
        )
    elif name == "Balanced":
        notes.append(
            f"This option maximizes expected profit at {money(strategy['expected_profit'])} while keeping channel exposure visible."
        )
    else:
        notes.append(
            f"This option leans into upside. Best-case profit reaches {money(strategy['upside_profit'])}, but volatility is higher."
        )

    if strategy["stockout_risk"] > 0.50:
        notes.append("Stockout risk is high. At least one channel is likely to be short under multiple scenarios.")
    elif strategy["stockout_risk"] > 0.20:
        notes.append("Stockout risk is moderate. This plan works, but only if demand stays near expected levels.")
    else:
        notes.append("Stockout risk is relatively contained under the tested scenarios.")

    if strategy["expected_leftover"] > 0.20 * (strategy["dtc_inventory"] + strategy["wholesale_inventory"]):
        notes.append("This plan leaves a meaningful amount of inventory uncommitted on average. That protects flexibility but may slow cash conversion.")

    if not strategy["commitment_met"]:
        notes.append(
            f"This allocation misses the wholesale minimum commitment by {strategy['commitment_gap']} units."
        )

    dtc_diff = strategy["dtc_share"] - balanced["dtc_share"]
    if abs(dtc_diff) >= 0.10 and name != "Balanced":
        direction = "more" if dtc_diff > 0 else "less"
        notes.append(
            f"Compared with the balanced plan, this sends {abs(int(round(dtc_diff * 100)))} percentage points {direction} inventory to DTC."
        )

    return notes


def conflict_flags(best: Dict, dtc_price: float, wholesale_price: float) -> List[str]:
    flags = []

    if best["stockout_risk"] > 0.50:
        flags.append("Your current inventory position is too tight for the demand range you entered.")

    if best["expected_unmet_dtc"] > best["expected_unmet_wholesale"] * 1.5:
        flags.append("DTC demand is the main pressure point. Your likely breakage is missed upside in the direct channel.")
    elif best["expected_unmet_wholesale"] > best["expected_unmet_dtc"] * 1.5:
        flags.append("Wholesale demand is the main pressure point. Current allocation likely undermines account commitments.")

    if dtc_price <= wholesale_price:
        flags.append("Wholesale pricing is too close to DTC pricing. Channel economics are compressed.")

    if best["expected_leftover"] > 0.25 * (best["dtc_inventory"] + best["wholesale_inventory"]):
        flags.append("You are carrying excess inventory under the current demand assumptions.")

    if not best["commitment_met"]:
        flags.append("Your tested inventory level does not support the wholesale commitment you entered.")

    if not flags:
        flags.append("No severe structural conflict detected under the current assumptions. The bigger question is whether your demand ranges are realistic.")

    return flags


st.title("Channel Allocation Decision Engine")
st.caption("Model one decision: how limited inventory should be allocated across DTC and wholesale channels.")

with st.sidebar:
    st.header("Decision Inputs")

    use_example = st.checkbox("Load example values", value=True)

    defaults = {
        "sku_name": "Core Product / SKU A",
        "unit_cost": 18.0,
        "dtc_price": 48.0,
        "wholesale_price": 30.0,
        "current_inventory": 600,
        "incoming_inventory": 100,
        "dtc_min": 180,
        "dtc_exp": 260,
        "dtc_max": 360,
        "wh_min": 140,
        "wh_exp": 240,
        "wh_max": 340,
        "wholesale_commitment": 180,
    }

    if not use_example:
        defaults = {
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

    sku_name = st.text_input("SKU / product name", value=defaults["sku_name"])

    st.subheader("Unit economics")
    unit_cost = st.number_input("Unit cost", min_value=0.0, value=float(defaults["unit_cost"]), step=1.0)
    dtc_price = st.number_input("DTC selling price", min_value=0.0, value=float(defaults["dtc_price"]), step=1.0)
    wholesale_price = st.number_input("Wholesale price", min_value=0.0, value=float(defaults["wholesale_price"]), step=1.0)

    st.subheader("Inventory")
    current_inventory = st.number_input("Current inventory", min_value=0, value=int(defaults["current_inventory"]), step=10)
    incoming_inventory = st.number_input("Incoming inventory", min_value=0, value=int(defaults["incoming_inventory"]), step=10)

    st.subheader("DTC demand range")
    dtc_min = st.number_input("DTC demand — low", min_value=0.0, value=float(defaults["dtc_min"]), step=10.0)
    dtc_exp = st.number_input("DTC demand — expected", min_value=0.0, value=float(defaults["dtc_exp"]), step=10.0)
    dtc_max = st.number_input("DTC demand — high", min_value=0.0, value=float(defaults["dtc_max"]), step=10.0)

    st.subheader("Wholesale demand range")
    wh_min = st.number_input("Wholesale demand — low", min_value=0.0, value=float(defaults["wh_min"]), step=10.0)
    wh_exp = st.number_input("Wholesale demand — expected", min_value=0.0, value=float(defaults["wh_exp"]), step=10.0)
    wh_max = st.number_input("Wholesale demand — high", min_value=0.0, value=float(defaults["wh_max"]), step=10.0)

    st.subheader("Constraints")
    wholesale_commitment = st.number_input(
        "Minimum wholesale commitment",
        min_value=0,
        value=int(defaults["wholesale_commitment"]),
        step=10,
        help="Optional. If you promised a buyer a minimum number of units, enter it here.",
    )

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
summary_df = build_summary_table(strategy_map)
frontier_df = build_frontier_table(all_results)
balanced = strategy_map["Balanced"]
flags = conflict_flags(balanced, dtc_price, wholesale_price)

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Total inventory in play", f"{total_inventory:,} units")
with col_b:
    st.metric("Balanced expected profit", money(balanced["expected_profit"]))
with col_c:
    st.metric("Balanced stockout risk", percent(balanced["stockout_risk"]))

st.divider()

left, right = st.columns([1.15, 0.85])

with left:
    st.subheader(f"Recommended strategy set — {sku_name or 'Unnamed SKU'}")
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    st.subheader("Allocation frontier")
    chart_df = frontier_df.copy().sort_values("DTC Allocation %")
    st.line_chart(chart_df.set_index("DTC Allocation %")[["Expected Profit", "Downside Profit", "Upside Profit"]])
    st.caption("This chart shows how profit changes as you shift more inventory toward DTC.")

    st.subheader("All tested allocation splits")
    formatted_frontier = frontier_df.copy()
    formatted_frontier["Expected Profit"] = formatted_frontier["Expected Profit"].map(money)
    formatted_frontier["Downside Profit"] = formatted_frontier["Downside Profit"].map(money)
    formatted_frontier["Upside Profit"] = formatted_frontier["Upside Profit"].map(money)
    formatted_frontier["Stockout Risk"] = formatted_frontier["Stockout Risk"].map(percent)
    formatted_frontier["Expected Leftover"] = formatted_frontier["Expected Leftover"].map(lambda x: f"{x:.1f}")
    st.dataframe(formatted_frontier, use_container_width=True, hide_index=True)

with right:
    st.subheader("What appears to be breaking")
    for flag in flags:
        st.warning(flag)

    st.subheader("Strategy explanations")
    for strategy_name in ["Conservative", "Balanced", "Aggressive"]:
        strategy = strategy_map[strategy_name]
        with st.expander(strategy_name, expanded=(strategy_name == "Balanced")):
            st.markdown(
                f"**Allocation:** {percent(strategy['dtc_share'])} to DTC / {percent(strategy['wholesale_share'])} to Wholesale"
            )
            st.markdown(
                f"**Expected profit:** {money(strategy['expected_profit'])}  \\n**Downside profit:** {money(strategy['downside_profit'])}  \\n**Upside profit:** {money(strategy['upside_profit'])}"
            )
            notes = explain_strategy(strategy_name, strategy, balanced)
            for note in notes:
                st.write(f"- {note}")

    st.subheader("Balanced plan — scenario details")
    scenario_df = pd.DataFrame(balanced["scenario_rows"])
    scenario_df["Probability"] = scenario_df["Probability"].map(percent)
    scenario_df["Revenue"] = scenario_df["Revenue"].map(money)
    scenario_df["Profit"] = scenario_df["Profit"].map(money)
    st.dataframe(scenario_df, use_container_width=True, hide_index=True)

st.divider()

st.subheader("How to use this demo")
st.markdown(
    """
This MVP does one thing on purpose: it structures **one connected operating decision**.

Use it when you need to decide how much inventory should go to:
- DTC / Shopify-like direct sales
- Wholesale / B2B channel commitments

It does **not** replace ERP, forecasting infrastructure, or ad platforms.
It exposes the tradeoff around inventory, demand range, channel economics, and commitment risk in one place.
"""
)

st.subheader("Suggested next steps")
for item in [
    "Test three real SKUs and compare whether the same channel bias shows up repeatedly.",
    "Tighten the demand ranges. Most early breakage comes from unrealistic assumptions, not model math.",
    "If this becomes a weekly decision, the next version should add CSV upload and decision history tracking.",
]:
    st.write(f"- {item}")
