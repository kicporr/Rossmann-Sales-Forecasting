"""Econometric analysis of Rossmann daily sales.

Contents
--------
* ADF stationarity tests on the chain series and on Store 1.
* Weekly seasonal decomposition of Store 1.
* ACF / PACF of levels and first differences.
* OLS regression with robust (HC3) standard errors and coefficient
  interpretation for Store 1.
* SARIMAX(1,0,1)(1,1,1,7) with promotion/holiday/day-of-week exogenous
  regressors, trained up to 2015-06-14 and evaluated on the untouched holdout.
* Residual diagnostics: Ljung-Box, Jarque-Bera, Durbin-Watson, Breusch-Pagan.

The SARIMAX model is deliberately fitted to a single store: fitting 1,115
independent seasonal models would be computationally wasteful and would ignore
the cross-store signal that the global gradient-boosted model exploits.  The
comparison therefore documents *where* classical time-series models remain
useful (interpretability, single-series monitoring) and where they do not.
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
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from statsmodels.stats.diagnostic import acorr_ljungbox, het_breuschpagan
from statsmodels.stats.stattools import durbin_watson, jarque_bera
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.stattools import adfuller

from src.config import ensure_directories, load_config
from src.data_preparation import load_processed
from src.eda import GOLD, GREY, LIGHT, NAVY, ORANGE, TEAL, THOUSANDS, _save
from src.evaluation import evaluate_predictions, mae, rmspe

LOGGER = logging.getLogger(__name__)


def adf_report(series: pd.Series, label: str) -> dict[str, Any]:
    """Augmented Dickey-Fuller test with a readable verdict."""
    clean = series.dropna().astype("float64")
    result = adfuller(clean, autolag="AIC", result_object=False)
    return {
        "series": label,
        "n": int(len(clean)),
        "adf_statistic": float(result[0]),
        "p_value": float(result[1]),
        "used_lags": int(result[2]),
        "critical_values": {key: float(value) for key, value in result[4].items()},
        "stationary_at_5pct": bool(result[1] < 0.05),
    }


def build_store_series(train: pd.DataFrame, store_id: int) -> pd.DataFrame:
    """Complete daily series for one store (closed days explicitly zero)."""
    frame = train[train["Store"] == store_id].sort_values("Date").set_index("Date")
    full_index = pd.date_range(frame.index.min(), frame.index.max(), freq="D")
    frame = frame.reindex(full_index)
    frame["Sales"] = frame["Sales"].fillna(0)
    frame["Customers"] = frame["Customers"].fillna(0)
    frame["Open"] = frame["Open"].fillna(0)
    frame["Promo"] = frame["Promo"].fillna(0)
    frame["SchoolHoliday"] = frame["SchoolHoliday"].fillna(0)
    for code in ("a", "b", "c"):
        frame[f"StateHoliday_{code}"] = frame[f"StateHoliday_{code}"].fillna(0)
    frame["DayOfWeek"] = frame.index.dayofweek + 1
    frame.index.name = "Date"
    return frame


def sarimax_exog(frame: pd.DataFrame) -> pd.DataFrame:
    """Fixed exogenous design shared by train and forecast frames."""
    out = pd.DataFrame(index=frame.index)
    out["Promo"] = frame["Promo"].astype(float)
    out["SchoolHoliday"] = frame["SchoolHoliday"].astype(float)
    for code in ("a", "b", "c"):
        out[f"holiday_{code}"] = frame[f"StateHoliday_{code}"].astype(float)
    for day in range(2, 8):
        out[f"dow_{day}"] = (frame["DayOfWeek"] == day).astype(float)
    return out


def fit_ols(frame: pd.DataFrame) -> Any:
    """OLS of log sales on promotions, weekday, holidays and a linear trend."""
    data = frame[frame["Open"] == 1].copy()
    data["log_sales"] = np.log(data["Sales"].where(data["Sales"] > 0))
    data = data.dropna(subset=["log_sales"])
    data["trend_days"] = (data.index - data.index.min()).days
    # Build the design dynamically: a store that never opens on Sunday (or
    # never experiences a given holiday type) would otherwise create a
    # perfectly collinear dummy and a rank-deficient matrix.
    terms = ["Promo", "SchoolHoliday", "trend_days"]
    days = sorted(int(day) for day in data["DayOfWeek"].unique())
    if len(days) > 1:
        terms.append(f"C(DayOfWeek, levels={days})")
    for code in ("a", "b", "c"):
        column = f"StateHoliday_{code}"
        if data[column].sum() > 0 and data[column].nunique() > 1:
            terms.append(column)
    formula = "log_sales ~ " + " + ".join(terms)
    model = smf.ols(formula, data=data).fit(cov_type="HC3")
    rank = np.linalg.matrix_rank(model.model.exog)
    if rank != model.model.exog.shape[1]:
        raise ValueError(f"OLS design is rank deficient: rank {rank} of {model.model.exog.shape[1]}")
    LOGGER.info("OLS formula: %s", formula)
    return model


def coefficient_table(model: Any) -> pd.DataFrame:
    """OLS coefficients translated into approximate percentage effects."""
    frame = pd.DataFrame(
        {
            "coefficient": model.params,
            "std_error": model.bse,
            "p_value": model.pvalues,
            "ci_low": model.conf_int()[0],
            "ci_high": model.conf_int()[1],
        }
    )
    frame["pct_effect"] = (np.exp(frame["coefficient"]) - 1) * 100
    return frame.round(4)


def make_series_figure(series: pd.DataFrame, store_id: int, figures: Path) -> None:
    decomposition = seasonal_decompose(series["Sales"], model="additive", period=7)
    fig, axes = plt.subplots(4, 1, figsize=(12, 9), sharex=True)
    components = [
        (series["Sales"], "Observed daily sales", NAVY),
        (decomposition.trend, "Weekly-centred trend (7-day moving average)", TEAL),
        (decomposition.seasonal, "Weekly seasonal component", GOLD),
        (decomposition.resid, "Residual", GREY),
    ]
    for ax, (values, title, color) in zip(axes, components, strict=True):
        ax.plot(values.index, values, color=color, linewidth=1.2)
        ax.set_title(title, fontsize=10.5, loc="left", color=NAVY, fontweight="bold")
        ax.yaxis.set_major_formatter(THOUSANDS)
        ax.grid(alpha=0.25)
    fig.suptitle(f"Additive decomposition of daily sales - Store {store_id}", fontsize=14, fontweight="bold", color=NAVY)
    axes[-1].set_xlabel("Date")
    _save(fig, figures / "fig15_ts_decomposition.png")


def make_acf_figure(series: pd.Series, figures: Path) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12.5, 7.5))
    plot_acf(series, lags=35, ax=axes[0, 0], color=NAVY, zero=False)
    axes[0, 0].set_title("ACF - sales level")
    plot_pacf(series, lags=35, ax=axes[0, 1], color=NAVY, method="ywm", zero=False)
    axes[0, 1].set_title("PACF - sales level")
    plot_acf(series.diff().dropna(), lags=35, ax=axes[1, 0], color=ORANGE, zero=False)
    axes[1, 0].set_title("ACF - first difference")
    plot_pacf(series.diff().dropna(), lags=35, ax=axes[1, 1], color=ORANGE, method="ywm", zero=False)
    axes[1, 1].set_title("PACF - first difference")
    for ax in axes.ravel():
        ax.grid(alpha=0.25)
        ax.set_xlabel("Lag (days)")
    fig.suptitle("Autocorrelation structure: strong 7-day seasonality", fontsize=14, fontweight="bold", color=NAVY)
    _save(fig, figures / "fig16_acf_pacf.png")


def make_diagnostics_figure(model: Any, figures: Path) -> None:
    fitted = model.fittedvalues
    residuals = model.resid
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.6))
    axes[0].scatter(fitted, residuals, s=8, alpha=0.4, color=NAVY)
    axes[0].axhline(0, color=ORANGE, linewidth=1.2)
    axes[0].set_title("Residuals vs fitted")
    axes[0].set_xlabel("Fitted log sales")
    axes[0].set_ylabel("Residual")
    stats.probplot(residuals, dist="norm", plot=axes[1])
    axes[1].set_title("Normal Q-Q plot")
    axes[2].hist(residuals, bins=45, color=TEAL, edgecolor="white")
    axes[2].set_title("Residual distribution")
    axes[2].set_xlabel("Residual")
    axes[2].set_ylabel("Count")
    fig.suptitle("OLS residual diagnostics", fontsize=14, fontweight="bold", color=NAVY)
    _save(fig, figures / "fig17_regression_diagnostics.png")


def make_sarimax_figure(history: pd.Series, actual: pd.Series, forecast: pd.Series, figures: Path, store_id: int) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 6))
    tail = history.iloc[-120:]
    ax.plot(tail.index, tail, color=NAVY, linewidth=1.2, label="Actual (history tail)")
    ax.plot(actual.index, actual, color=TEAL, linewidth=1.4, label="Actual (holdout)")
    ax.plot(forecast.index, forecast, color=ORANGE, linewidth=1.6, linestyle="--", label="SARIMAX forecast")
    ax.axvline(actual.index.min(), color=GREY, linestyle=":", linewidth=1.2)
    ax.set_title(f"SARIMAX forecast vs actual sales - Store {store_id}")
    ax.set_ylabel("Sales (PLN)")
    ax.set_xlabel("Date")
    ax.yaxis.set_major_formatter(THOUSANDS)
    ax.legend(loc="upper left", ncol=3)
    _save(fig, figures / "fig18_sarimax_forecast.png")


def make_residual_acf(residuals: pd.Series, figures: Path, lb_pvalue: float) -> None:
    fig, ax = plt.subplots(figsize=(10, 4.8))
    plot_acf(residuals.dropna(), lags=35, ax=ax, color=TEAL, zero=False)
    ax.set_title(f"SARIMAX residual autocorrelation (Ljung-Box p = {lb_pvalue:.3f})")
    ax.set_xlabel("Lag (days)")
    ax.grid(alpha=0.25)
    _save(fig, figures / "fig19_sarimax_residual_acf.png")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    cfg = load_config()
    ensure_directories(cfg)
    data = load_processed(cfg)
    train = data["train"]
    store_id = int(cfg["models"]["sarimax"]["store_id"])
    figures = Path(cfg["paths"]["figures"])
    metrics_dir = Path(cfg["paths"]["metrics"])

    chain = train.groupby("Date", observed=True).agg(sales=("Sales", "sum"), open_stores=("Open", "sum")).reset_index()
    chain_daily = chain.set_index("Date")["sales"]
    chain_weekly = chain.set_index("Date")["sales"].resample("W-MON").sum()

    stationarity = [
        adf_report(chain_daily, "Chain daily sales"),
        adf_report(chain_daily.diff(), "Chain daily sales - first difference"),
        adf_report(chain_weekly, "Chain weekly sales"),
        adf_report(chain_weekly.diff(), "Chain weekly sales - first difference"),
    ]

    series = build_store_series(train, store_id)
    stationarity.append(adf_report(series["Sales"], f"Store {store_id} daily sales"))
    stationarity.append(adf_report(series["Sales"].diff(), f"Store {store_id} daily sales - first difference"))

    decomposition = seasonal_decompose(series["Sales"], model="additive", period=7)
    remainder = (decomposition.seasonal + decomposition.resid).dropna()
    seasonal_strength = max(0.0, 1.0 - float(np.var(decomposition.resid.dropna()) / np.var(remainder)))
    make_series_figure(series, store_id, figures)
    make_acf_figure(series["Sales"], figures)

    ols = fit_ols(series)
    coefficients = coefficient_table(ols)
    coefficients.to_csv(metrics_dir / "ols_coefficients.csv")
    make_diagnostics_figure(ols, figures)
    bp = het_breuschpagan(ols.resid, ols.model.exog)
    jb = jarque_bera(ols.resid)
    ols_diagnostics = {
        "r_squared": float(ols.rsquared),
        "adj_r_squared": float(ols.rsquared_adj),
        "f_statistic": float(ols.fvalue),
        "f_pvalue": float(ols.f_pvalue),
        "n_obs": int(ols.nobs),
        "durbin_watson": float(durbin_watson(ols.resid)),
        "jarque_bera_p": float(jb[1]),
        "breusch_pagan_p": float(bp[1]),
        "residual_std": float(np.std(ols.resid, ddof=1)),
    }

    holdout = cfg["split"]["holdout"]
    train_end = pd.Timestamp(holdout["train_end"])
    val_start = pd.Timestamp(holdout["val_start"])
    val_end = pd.Timestamp(holdout["val_end"])

    history = series.loc[:train_end]
    future = series.loc[val_start:val_end]
    train_exog = sarimax_exog(history)
    future_exog = sarimax_exog(future)
    order = tuple(cfg["models"]["sarimax"]["order"])
    seasonal_order = tuple(cfg["models"]["sarimax"]["seasonal_order"])

    sarimax = SARIMAX(
        history["Sales"].astype("float64"),
        exog=train_exog,
        order=order,
        seasonal_order=seasonal_order,
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = sarimax.fit(disp=False, maxiter=200)
    forecast = fitted.get_forecast(steps=len(future), exog=future_exog)
    mean_forecast = np.clip(np.asarray(forecast.predicted_mean), 0, None)
    forecast_series = pd.Series(mean_forecast, index=future.index).where(future["Open"] == 1, 0.0)

    evaluation_frame = pd.DataFrame(
        {
            "Store": store_id,
            "Date": future.index,
            "Open": future["Open"].to_numpy(),
            "Sales": future["Sales"].to_numpy(),
            "Prediction": forecast_series.to_numpy(),
        }
    )
    sarimax_metrics = evaluate_predictions(evaluation_frame, label="sarimax")

    make_sarimax_figure(history["Sales"], future["Sales"].where(future["Open"] == 1, np.nan), forecast_series.where(future["Open"] == 1, np.nan), figures, store_id)

    residuals = pd.Series(fitted.resid, index=history.index).dropna()
    lb = acorr_ljungbox(residuals, lags=[7, 14, 21], return_df=True)
    lb_pvalue = float(lb["lb_pvalue"].iloc[0])
    make_residual_acf(residuals, figures, lb_pvalue)
    sarimax_diagnostics = {
        "aic": float(fitted.aic),
        "bic": float(fitted.bic),
        "ljung_box_lag7_p": lb_pvalue,
        "ljung_box_lag14_p": float(lb["lb_pvalue"].iloc[1]),
        "jarque_bera_p": float(jarque_bera(residuals)[1]),
        "residual_std": float(np.std(residuals, ddof=1)),
        "converged": bool(fitted.mle_retvals.get("converged", True)),
        "order": list(order),
        "seasonal_order": list(seasonal_order),
    }

    comparison_rows = [
        {"model": "sarimax", "rmspe": sarimax_metrics["rmspe"], "mae": sarimax_metrics["mae"], "n": sarimax_metrics["n_rows_scored"]}
    ]
    forecast_path = Path(cfg["paths"]["predictions"]) / "validation_predictions.parquet"
    if forecast_path.exists():
        fold_predictions = pd.read_parquet(forecast_path)
        for model_name in ("seasonal_naive", "historical_average", "linear_regression", "random_forest", "xgboost"):
            subset = fold_predictions[
                (fold_predictions["fold"] == "holdout")
                & (fold_predictions["model"] == model_name)
                & (fold_predictions["Store"] == store_id)
            ]
            if subset.empty:
                continue
            comparison_rows.append(
                {
                    "model": model_name,
                    "rmspe": rmspe(subset["Sales"], subset["Prediction"]),
                    "mae": mae(subset["Sales"], subset["Prediction"]),
                    "n": int((subset["Sales"] > 0).sum()),
                }
            )
    comparison = pd.DataFrame(comparison_rows).sort_values("rmspe").round(4)
    comparison.to_csv(metrics_dir / "store1_model_comparison.csv", index=False)

    payload = {
        "store_id": store_id,
        "stationarity": stationarity,
        "decomposition": {
            "period_days": 7,
            "seasonal_strength": float(seasonal_strength),
        },
        "ols": ols_diagnostics,
        "ols_coefficients": coefficients.reset_index().rename(columns={"index": "term"}).to_dict("records"),
        "sarimax": sarimax_diagnostics,
        "sarimax_holdout": sarimax_metrics,
        "store1_comparison": comparison.to_dict("records"),
    }
    (metrics_dir / "econometrics_summary.json").write_text(json.dumps(payload, indent=2, default=float), encoding="utf-8")
    print(json.dumps({"stationarity": stationarity, "ols": ols_diagnostics, "sarimax": sarimax_diagnostics, "holdout": sarimax_metrics}, indent=2, default=float))
    print(comparison.to_string(index=False))


if __name__ == "__main__":
    main()
