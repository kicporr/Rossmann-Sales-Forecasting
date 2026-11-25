"""Exploratory data analysis for the Rossmann dataset.

The script produces every figure referenced in ``reports/eda_report.md`` and
writes the underlying statistics to ``outputs/metrics/eda_summary.json``.
Figures use a consistent visual language: title, variable description in the
subtitle, annotated values and a source note.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter
from scipy import stats

from src.config import ensure_directories, load_config
from src.data_preparation import load_processed

LOGGER = logging.getLogger(__name__)

NAVY = "#1f3a5f"
TEAL = "#2a9d8f"
ORANGE = "#e76f51"
GOLD = "#e9c46a"
GREY = "#6b7280"
LIGHT = "#dbe4ee"

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.family": "DejaVu Sans",
        "font.size": 10.5,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlecolor": NAVY,
        "axes.labelsize": 10.5,
        "axes.labelcolor": "#374151",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.edgecolor": "#cbd5e1",
        "axes.grid": True,
        "grid.color": "#e5e7eb",
        "grid.linewidth": 0.8,
        "xtick.color": "#4b5563",
        "ytick.color": "#4b5563",
        "legend.frameon": False,
    }
)

THOUSANDS = FuncFormatter(lambda value, _: f"{value / 1000:,.0f}k" if value >= 1000 else f"{value:,.0f}")


def _save(fig: plt.Figure, path: Path, caption: str = "Source: Rossmann Store Sales, train.csv (2013-01-01 - 2015-07-31)") -> None:
    fig.text(0.01, 0.005, caption, fontsize=7.5, color=GREY)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    LOGGER.info("Saved figure %s", path.name)


def _annotate_bars(ax: plt.Axes, values: np.ndarray, fmt: str = "{:,.0f}", offset: float = 0.01) -> None:
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    for index, value in enumerate(values):
        ax.text(index, value + span * offset, fmt.format(value), ha="center", va="bottom", fontsize=8.5, color="#374151")


def _store_stats(train: pd.DataFrame) -> pd.DataFrame:
    open_days = train[train["Open"] == 1]
    stats_frame = (
        open_days.groupby("Store", observed=True)
        .agg(
            mean_sales=("Sales", "mean"),
            std_sales=("Sales", "std"),
            mean_customers=("Customers", "mean"),
            open_days=("Sales", "size"),
            total_sales=("Sales", "sum"),
        )
        .reset_index()
    )
    stats_frame["cv"] = stats_frame["std_sales"] / stats_frame["mean_sales"]
    attrs = train[["Store", "StoreType", "Assortment", "CompetitionDistance"]].drop_duplicates("Store")
    return stats_frame.merge(attrs, on="Store", how="left")


def build_summary(train: pd.DataFrame, store_stats: pd.DataFrame) -> dict[str, Any]:
    open_df = train[train["Open"] == 1]
    positive = open_df[open_df["Sales"] > 0]
    weekday = (
        open_df.groupby("DayOfWeek", observed=True)
        .agg(avg_sales=("Sales", "mean"), avg_customers=("Customers", "mean"), days=("Sales", "size"))
        .reset_index()
    )
    weekday["avg_basket"] = weekday["avg_sales"] / weekday["avg_customers"]
    promo = (
        open_df.groupby("Promo", observed=True)
        .agg(
            avg_sales=("Sales", "mean"),
            avg_customers=("Customers", "mean"),
            days=("Sales", "size"),
        )
        .reset_index()
    )
    promo["avg_basket"] = promo["avg_sales"] / promo["avg_customers"]
    store_type = (
        open_df.groupby("StoreType", observed=True)
        .agg(avg_sales=("Sales", "mean"), avg_customers=("Customers", "mean"), days=("Sales", "size"))
        .reset_index()
    )
    store_type["avg_basket"] = store_type["avg_sales"] / store_type["avg_customers"]
    assortment = (
        open_df.groupby("Assortment", observed=True)
        .agg(avg_sales=("Sales", "mean"), days=("Sales", "size"))
        .reset_index()
    )
    holiday = (
        open_df.groupby("StateHoliday", observed=True)
        .agg(avg_sales=("Sales", "mean"), avg_customers=("Customers", "mean"), days=("Sales", "size"))
        .reset_index()
    )
    monthly = (
        open_df.assign(month=open_df["Date"].dt.to_period("M").astype(str))
        .groupby("month", observed=True)
        .agg(avg_sales=("Sales", "mean"), total_sales=("Sales", "sum"), days=("Sales", "size"))
        .reset_index()
    )
    yearly = (
        open_df.assign(year=open_df["Date"].dt.year)
        .groupby("year", observed=True)
        .agg(avg_sales=("Sales", "mean"), total_sales=("Sales", "sum"), days=("Sales", "size"))
        .reset_index()
    )
    distance_bins = pd.cut(
        store_stats["CompetitionDistance"],
        bins=[-np.inf, 500, 1000, 2500, 5000, np.inf],
        labels=["<500 m", "500-999 m", "1-2.5 km", "2.5-5 km", ">=5 km"],
    )
    distance = (
        store_stats.assign(bucket=distance_bins)
        .groupby("bucket", observed=True)
        .agg(stores=("Store", "size"), avg_sales=("mean_sales", "mean"))
        .reset_index()
    )

    promo_paired = (
        open_df.groupby(["Store", "Promo"], observed=True)["Sales"].mean().unstack().dropna()
    )
    promo_paired.columns = ["no_promo", "promo"]
    paired_diff = promo_paired["promo"] - promo_paired["no_promo"]
    paired_test = stats.ttest_rel(promo_paired["promo"], promo_paired["no_promo"])

    weekday_groups = [group["Sales"].to_numpy() for _, group in open_df.groupby("DayOfWeek", observed=True)]
    weekday_test = stats.kruskal(*weekday_groups)
    type_groups = [group["Sales"].to_numpy() for _, group in open_df.groupby("StoreType", observed=True)]
    type_test = stats.kruskal(*type_groups)
    holiday_groups = [group["Sales"].to_numpy() for _, group in open_df.groupby("StateHoliday", observed=True)]
    holiday_test = stats.kruskal(*holiday_groups)
    distance_test = stats.spearmanr(store_stats["CompetitionDistance"], store_stats["mean_sales"], nan_policy="omit")

    summary = {
        "overview": {
            "date_min": str(train["Date"].min().date()),
            "date_max": str(train["Date"].max().date()),
            "rows": int(len(train)),
            "stores": int(train["Store"].nunique()),
            "total_sales": float(train["Sales"].sum()),
            "total_customers": float(train["Customers"].sum()),
            "avg_daily_sales_open": float(open_df["Sales"].mean()),
            "median_daily_sales_open": float(open_df["Sales"].median()),
            "avg_daily_sales_all_rows": float(train["Sales"].mean()),
            "avg_customers_open": float(open_df["Customers"].mean()),
            "avg_basket": float(positive["Sales"].sum() / positive["Customers"].sum()),
            "open_rate": float((train["Open"] == 1).mean()),
            "closed_rows": int((train["Open"] == 0).sum()),
            "zero_sales_open": int(((train["Sales"] == 0) & (train["Open"] == 1)).sum()),
            "zero_sales_share_of_open": float(((train["Sales"] == 0) & (train["Open"] == 1)).mean()),
            "sales_share_top10pct_stores": float(
                store_stats.nlargest(max(1, int(len(store_stats) * 0.1)), "total_sales")["total_sales"].sum()
                / store_stats["total_sales"].sum()
            ),
        },
        "weekday": weekday.round(3).to_dict("records"),
        "promo": promo.round(3).to_dict("records"),
        "store_type": store_type.round(3).to_dict("records"),
        "assortment": assortment.round(3).to_dict("records"),
        "holiday": holiday.round(3).to_dict("records"),
        "monthly": monthly.round(3).to_dict("records"),
        "yearly": yearly.round(3).to_dict("records"),
        "distance": distance.round(3).to_dict("records"),
        "stores": {
            "avg_sales_mean": float(store_stats["mean_sales"].mean()),
            "avg_sales_min": float(store_stats["mean_sales"].min()),
            "avg_sales_max": float(store_stats["mean_sales"].max()),
            "cv_median": float(store_stats["cv"].median()),
            "cv_p90": float(store_stats["cv"].quantile(0.9)),
            "n_high_volatility": int((store_stats["cv"] > store_stats["cv"].quantile(0.9)).sum()),
            "top5": store_stats.nlargest(5, "mean_sales")[["Store", "mean_sales", "cv", "StoreType"]]
            .round(3)
            .to_dict("records"),
            "bottom5": store_stats.nsmallest(5, "mean_sales")[["Store", "mean_sales", "cv", "StoreType"]]
            .round(3)
            .to_dict("records"),
        },
        "tests": {
            "promo_paired_t": {
                "statistic": float(paired_test.statistic),
                "p_value": float(paired_test.pvalue),
                "mean_uplift": float(paired_diff.mean()),
                "median_uplift": float(paired_diff.median()),
                "n_stores": int(len(paired_diff)),
                "pct_stores_positive": float((paired_diff > 0).mean()),
                "cohens_dz": float(paired_diff.mean() / paired_diff.std(ddof=1)),
            },
            "weekday_kruskal": {"statistic": float(weekday_test.statistic), "p_value": float(weekday_test.pvalue)},
            "store_type_kruskal": {"statistic": float(type_test.statistic), "p_value": float(type_test.pvalue)},
            "holiday_kruskal": {"statistic": float(holiday_test.statistic), "p_value": float(holiday_test.pvalue)},
            "competition_spearman": {
                "rho": float(distance_test.statistic),
                "p_value": float(distance_test.pvalue),
                "n_stores": int(store_stats["CompetitionDistance"].notna().sum()),
            },
        },
    }
    return summary


def make_figures(train: pd.DataFrame, store_stats: pd.DataFrame, figures: Path) -> None:
    """Create every EDA figure as a separate PNG."""
    open_df = train[train["Open"] == 1]
    daily = train.groupby("Date", observed=True)["Sales"].sum().reset_index()
    daily["rolling_28"] = daily["Sales"].rolling(28, min_periods=7).mean()

    # 1. Chain sales trend
    fig, ax = plt.subplots(figsize=(12.5, 6))
    ax.plot(daily["Date"], daily["Sales"], color=LIGHT, linewidth=0.8, label="Daily chain sales")
    ax.plot(daily["Date"], daily["rolling_28"], color=NAVY, linewidth=2.2, label="28-day rolling mean")
    ax.set_title("Daily chain revenue, 2013-2015")
    ax.set_ylabel("Sales (PLN)")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(THOUSANDS)
    ax.legend(loc="upper left")
    ax.text(
        0.99,
        0.03,
        "Weekly saw-tooth = Sunday closures + Monday peaks; rolling mean shows the underlying trend.",
        transform=ax.transAxes,
        ha="right",
        fontsize=8.5,
        color=GREY,
    )
    _save(fig, figures / "fig01_daily_sales_trend.png")

    # 2. Weekday seasonality
    weekday = (
        open_df.groupby("DayOfWeek", observed=True)
        .agg(avg_sales=("Sales", "mean"), avg_customers=("Customers", "mean"), days=("Sales", "size"))
        .reset_index()
    )
    labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4))
    axes[0].bar(labels, weekday["avg_sales"], color=NAVY, width=0.65)
    axes[0].set_title("Average sales by weekday")
    axes[0].set_ylabel("Average sales (PLN)")
    axes[0].yaxis.set_major_formatter(THOUSANDS)
    _annotate_bars(axes[0], weekday["avg_sales"].to_numpy())
    axes[0].set_ylim(0, weekday["avg_sales"].max() * 1.12)
    axes[1].bar(labels, weekday["avg_customers"], color=TEAL, width=0.65)
    axes[1].set_title("Average customer count by weekday")
    axes[1].set_ylabel("Customers per open day")
    _annotate_bars(axes[1], weekday["avg_customers"].to_numpy())
    axes[1].set_ylim(0, weekday["avg_customers"].max() * 1.12)
    fig.suptitle("Weekly seasonality: Monday and Sunday are the strongest trading days", fontsize=14, fontweight="bold", color=NAVY)
    _save(fig, figures / "fig02_weekday_seasonality.png")

    # 3. Monthly heatmap
    monthly_pivot = (
        open_df.assign(year=open_df["Date"].dt.year, month=open_df["Date"].dt.month)
        .groupby(["year", "month"], observed=True)["Sales"]
        .mean()
        .unstack()
    )
    fig, ax = plt.subplots(figsize=(11, 4.6))
    image = ax.imshow(monthly_pivot.to_numpy(), aspect="auto", cmap="YlGnBu")
    ax.set_xticks(range(12), labels=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set_yticks(range(len(monthly_pivot.index)), labels=monthly_pivot.index)
    ax.set_title("Average daily sales by year and month")
    ax.set_xlabel("Month")
    ax.set_ylabel("Year")
    for row in range(monthly_pivot.shape[0]):
        for column in range(monthly_pivot.shape[1]):
            value = monthly_pivot.iloc[row, column]
            if pd.notna(value):
                ax.text(column, row, f"{value / 1000:.1f}k", ha="center", va="center", fontsize=8, color="white" if value > 7200 else "#1f2937")
    ax.grid(False)
    fig.colorbar(image, ax=ax, label="Average sales (PLN)", shrink=0.8)
    _save(fig, figures / "fig03_monthly_heatmap.png")

    # 4. Sales distribution
    sample = positive_sample(open_df, 200_000)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    axes[0].hist(sample["Sales"], bins=60, color=TEAL, edgecolor="white")
    axes[0].set_title("Distribution of daily sales (open days)")
    axes[0].set_xlabel("Sales (PLN)")
    axes[0].set_ylabel("Store-days")
    axes[0].xaxis.set_major_formatter(THOUSANDS)
    axes[1].hist(np.log1p(sample["Sales"]), bins=60, color=NAVY, edgecolor="white")
    axes[1].set_title("Same distribution on a log scale")
    axes[1].set_xlabel("log(Sales + 1)")
    axes[1].set_ylabel("Store-days")
    fig.suptitle("Sales are right-skewed; the log transform stabilises the variance", fontsize=14, fontweight="bold", color=NAVY)
    _save(fig, figures / "fig04_sales_distribution.png")

    # 5. Store ranking
    ranked = store_stats.sort_values("mean_sales", ascending=False)
    top = ranked.head(12).iloc[::-1]
    bottom = ranked.tail(12)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.2), sharex=True)
    axes[0].barh(top["Store"].astype(str), top["mean_sales"], color=TEAL)
    axes[0].set_title("Top 12 stores by average daily sales")
    axes[0].set_xlabel("Average sales on open days (PLN)")
    axes[0].xaxis.set_major_formatter(THOUSANDS)
    axes[1].barh(bottom["Store"].astype(str), bottom["mean_sales"], color=ORANGE)
    axes[1].set_title("Bottom 12 stores by average daily sales")
    axes[1].set_xlabel("Average sales on open days (PLN)")
    axes[1].xaxis.set_major_formatter(THOUSANDS)
    fig.suptitle("Store performance is highly dispersed", fontsize=14, fontweight="bold", color=NAVY)
    _save(fig, figures / "fig05_store_ranking.png")

    # 6. Store volatility
    fig, ax = plt.subplots(figsize=(11, 6))
    colors = {"a": NAVY, "b": ORANGE, "c": TEAL, "d": GOLD}
    for store_type, group in store_stats.groupby("StoreType", observed=True):
        ax.scatter(group["mean_sales"], group["cv"], s=18, alpha=0.65, label=f"Type {store_type}", color=colors.get(store_type, GREY))
    threshold = store_stats["cv"].quantile(0.9)
    ax.axhline(threshold, color=ORANGE, linestyle="--", linewidth=1.2, label=f"90th percentile CV = {threshold:.2f}")
    ax.set_title("Store average sales vs coefficient of variation")
    ax.set_xlabel("Average daily sales (PLN)")
    ax.set_ylabel("Coefficient of variation (std / mean)")
    ax.xaxis.set_major_formatter(THOUSANDS)
    ax.legend(loc="upper right", ncol=2)
    _save(fig, figures / "fig06_store_volatility.png")

    # 7. Promo effect
    promo = (
        open_df.groupby("Promo", observed=True)
        .agg(avg_sales=("Sales", "mean"), avg_customers=("Customers", "mean"))
        .reset_index()
    )
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4))
    labels = ["No promotion", "Promotion"]
    axes[0].bar(labels, promo["avg_sales"], color=[GREY, TEAL], width=0.55)
    axes[0].set_title("Average sales per open day")
    axes[0].set_ylabel("Sales (PLN)")
    axes[0].yaxis.set_major_formatter(THOUSANDS)
    _annotate_bars(axes[0], promo["avg_sales"].to_numpy())
    axes[0].set_ylim(0, promo["avg_sales"].max() * 1.12)
    axes[1].bar(labels, promo["avg_customers"], color=[GREY, TEAL], width=0.55)
    axes[1].set_title("Average customers per open day")
    axes[1].set_ylabel("Customers")
    _annotate_bars(axes[1], promo["avg_customers"].to_numpy())
    axes[1].set_ylim(0, promo["avg_customers"].max() * 1.12)
    fig.suptitle("Promotions coincide with more traffic and higher sales", fontsize=14, fontweight="bold", color=NAVY)
    _save(fig, figures / "fig07_promo_effect.png")

    # 8. Promo uplift by store type
    pivot = open_df.groupby(["StoreType", "Promo"], observed=True)["Sales"].mean().unstack()
    uplift = (pivot[1] / pivot[0] - 1).sort_values()
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(uplift.index, uplift.to_numpy() * 100, color=[TEAL if value > 0 else ORANGE for value in uplift])
    ax.set_title("Promotion uplift by store type")
    ax.set_ylabel("Uplift vs non-promo days (%)")
    ax.set_xlabel("Store type")
    for bar, value in zip(bars, uplift * 100, strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.6, f"{value:.1f}%", ha="center", fontsize=9)
    ax.set_ylim(0, (uplift.max() * 100) * 1.15)
    _save(fig, figures / "fig08_promo_uplift_by_type.png")

    # 9. Store type / assortment
    sample = positive_sample(open_df, 120_000)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.4))
    type_order = sample.groupby("StoreType", observed=True)["Sales"].median().sort_values().index
    data = [sample.loc[sample["StoreType"] == code, "Sales"].to_numpy() for code in type_order]
    axes[0].boxplot(data, tick_labels=[f"Type {code}" for code in type_order], showfliers=False, patch_artist=True,
                    boxprops={"facecolor": LIGHT, "edgecolor": NAVY}, medianprops={"color": ORANGE, "linewidth": 2})
    axes[0].set_title("Daily sales by store type")
    axes[0].set_ylabel("Sales (PLN)")
    axes[0].yaxis.set_major_formatter(THOUSANDS)
    assortment_order = sample.groupby("Assortment", observed=True)["Sales"].median().sort_values().index
    data = [sample.loc[sample["Assortment"] == code, "Sales"].to_numpy() for code in assortment_order]
    axes[1].boxplot(data, tick_labels=[f"Assortment {code}" for code in assortment_order], showfliers=False, patch_artist=True,
                    boxprops={"facecolor": "#f6e7d7", "edgecolor": ORANGE}, medianprops={"color": NAVY, "linewidth": 2})
    axes[1].set_title("Daily sales by assortment")
    axes[1].set_ylabel("Sales (PLN)")
    axes[1].yaxis.set_major_formatter(THOUSANDS)
    fig.suptitle("Store formats differ in level and dispersion", fontsize=14, fontweight="bold", color=NAVY)
    _save(fig, figures / "fig09_store_type_assortment.png")

    # 10. Holiday effect
    holiday = (
        open_df.groupby("StateHoliday", observed=True)
        .agg(avg_sales=("Sales", "mean"), days=("Sales", "size"))
        .reset_index()
    )
    names = {"0": "Regular day", "a": "Public holiday", "b": "Easter", "c": "Christmas"}
    labels = [names.get(code, code) for code in holiday["StateHoliday"]]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    bars = ax.bar(labels, holiday["avg_sales"], color=[GREY, ORANGE, ORANGE, ORANGE], width=0.6)
    ax.set_title("Average sales on state holidays vs regular days")
    ax.set_ylabel("Average sales per open day (PLN)")
    ax.yaxis.set_major_formatter(THOUSANDS)
    for bar, value, days in zip(bars, holiday["avg_sales"], holiday["days"], strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 80, f"{value:,.0f}\n(n={days:,})", ha="center", fontsize=8.5)
    ax.set_ylim(0, holiday["avg_sales"].max() * 1.18)
    _save(fig, figures / "fig10_holiday_effect.png")

    # 11. Competition distance
    distance_bins = pd.cut(
        store_stats["CompetitionDistance"],
        bins=[-np.inf, 500, 1000, 2500, 5000, np.inf],
        labels=["<500 m", "500-999 m", "1-2.5 km", "2.5-5 km", ">=5 km"],
    )
    distance = store_stats.assign(bucket=distance_bins).groupby("bucket", observed=True).agg(
        stores=("Store", "size"), avg_sales=("mean_sales", "mean"), se=("mean_sales", "sem")
    ).reset_index()
    fig, ax = plt.subplots(figsize=(10.5, 5.4))
    bars = ax.bar(distance["bucket"].astype(str), distance["avg_sales"], yerr=distance["se"] * 1.96, capsize=5,
                  color=NAVY, width=0.6, error_kw={"ecolor": ORANGE, "linewidth": 1.4})
    ax.set_title("Average store sales by distance to nearest competitor")
    ax.set_ylabel("Average daily sales (PLN)")
    ax.set_xlabel("Competition distance bucket")
    ax.yaxis.set_major_formatter(THOUSANDS)
    for bar, value, stores in zip(bars, distance["avg_sales"], distance["stores"], strict=True):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 120, f"{value:,.0f}\n{stores} stores", ha="center", fontsize=8.5)
    ax.set_ylim(0, distance["avg_sales"].max() * 1.18)
    _save(fig, figures / "fig11_competition_distance.png")

    # 12. Customers vs sales
    sample = positive_sample(open_df, 150_000)
    fig, ax = plt.subplots(figsize=(10.5, 6.2))
    hexbin = ax.hexbin(sample["Customers"], sample["Sales"], gridsize=55, cmap="YlGnBu", mincnt=1, bins="log")
    rho = stats.spearmanr(sample["Customers"], sample["Sales"]).statistic
    ax.set_title("Customers vs sales on open days")
    ax.set_xlabel("Customers per day")
    ax.set_ylabel("Sales (PLN)")
    ax.yaxis.set_major_formatter(THOUSANDS)
    fig.colorbar(hexbin, ax=ax, label="Store-days (log scale)")
    ax.text(0.02, 0.95, f"Spearman rho = {rho:.2f}", transform=ax.transAxes, fontsize=10, color=NAVY)
    _save(fig, figures / "fig12_customers_vs_sales.png")

    # 13. Correlation matrix
    numeric = open_df[["Sales", "Customers", "Promo", "SchoolHoliday", "DayOfWeek", "IsStateHoliday", "CompetitionDistance"]].copy()
    numeric["DayOfWeek"] = numeric["DayOfWeek"]
    correlation = numeric.corr(method="spearman")
    fig, ax = plt.subplots(figsize=(8.6, 7))
    image = ax.imshow(correlation.to_numpy(), cmap="RdYlBu", vmin=-1, vmax=1)
    ax.set_xticks(range(len(correlation)), labels=correlation.columns, rotation=35, ha="right")
    ax.set_yticks(range(len(correlation)), labels=correlation.columns)
    ax.grid(False)
    for row in range(len(correlation)):
        for column in range(len(correlation)):
            value = correlation.iloc[row, column]
            ax.text(column, row, f"{value:.2f}", ha="center", va="center", fontsize=8.5,
                    color="white" if abs(value) > 0.55 else "#1f2937")
    ax.set_title("Spearman correlation matrix (open days)")
    fig.colorbar(image, ax=ax, shrink=0.8)
    _save(fig, figures / "fig13_correlation_matrix.png")

    # 14. Opening pattern
    pattern = train.assign(closed=(train["Open"] == 0)).groupby("DayOfWeek", observed=True)["closed"].mean() * 100
    day_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    ax.bar(day_labels, pattern.reindex(range(1, 8)).to_numpy(), color=ORANGE, width=0.6)
    ax.set_title("Share of closed store-days by weekday")
    ax.set_ylabel("Closed store-days (%)")
    ax.set_xlabel("Weekday")
    for index, value in enumerate(pattern.reindex(range(1, 8)).to_numpy()):
        ax.text(index, value + 0.4, f"{value:.1f}%", ha="center", fontsize=9)
    ax.set_ylim(0, max(pattern.max() * 1.15, 5))
    _save(fig, figures / "fig14_opening_pattern.png")


def positive_sample(frame: pd.DataFrame, size: int, seed: int = 42) -> pd.DataFrame:
    if len(frame) <= size:
        return frame
    return frame.sample(size, random_state=seed)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    cfg = load_config()
    ensure_directories(cfg)
    data = load_processed(cfg)
    train = data["train"]
    store_stats = _store_stats(train)
    summary = build_summary(train, store_stats)
    figures = Path(cfg["paths"]["figures"])
    figures.mkdir(parents=True, exist_ok=True)
    make_figures(train, store_stats, figures)
    metrics = Path(cfg["paths"]["metrics"])
    (metrics / "eda_summary.json").write_text(json.dumps(summary, indent=2, default=float), encoding="utf-8")
    print(json.dumps(summary["overview"], indent=2))
    print("EDA figures and summary written.")


if __name__ == "__main__":
    main()
