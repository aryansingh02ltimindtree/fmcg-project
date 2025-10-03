# backend/forecasting_api.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import List, Optional, Literal
import pandas as pd

router = APIRouter()  # no prefix → exposes POST /forecast

# ---------- Schemas ----------
class SeriesPoint(BaseModel):
    date: str            # e.g., "2024-01-01" or "Jan 2024" (we'll parse)
    value: float

class ForecastReq(BaseModel):
    model: Literal["ARIMA", "SARIMA", "Prophet"] = "SARIMA"
    horizon: int = 6
    series: List[SeriesPoint]
    measure: Optional[str] = None
    filters: Optional[dict] = None

    @field_validator("horizon")
    @classmethod
    def _validate_horizon(cls, v):
        if not (1 <= v <= 36):
            raise ValueError("horizon must be between 1 and 36 months")
        return v

# ---------- Helpers ----------
def _to_monthly_series(points: List[SeriesPoint]) -> pd.Series:
    """
    Build a clean monthly-start DatetimeIndex series with one value per month.
    - Parses many date formats.
    - Collapses duplicates per month.
    - Reindexes to a complete monthly range.
    """
    if not points:
        return pd.Series(dtype=float)

    # Parse dates robustly
    idx = []
    vals = []
    for p in points:
        d = pd.to_datetime(p.date, errors="coerce")
        if pd.isna(d):
            # try "Jan 2024" style
            d = pd.to_datetime(p.date, format="%b %Y", errors="coerce")
        if pd.isna(d):
            # try forcing day
            d = pd.to_datetime("01 " + str(p.date), errors="coerce")
        if not pd.isna(d):
            idx.append(d)
            vals.append(float(p.value))

    if not idx:
        return pd.Series(dtype=float)

    s = pd.Series(vals, index=pd.DatetimeIndex(idx, name="month_date")).sort_index()

    # Normalize to month start safely (NO 'MS' with Period)
    s.index = s.index.to_period("M").to_timestamp(how="start")

    # Collapse duplicates per month
    s = s.groupby(level=0).sum(min_count=1)

    # Complete monthly range
    full_idx = pd.date_range(s.index.min(), s.index.max(), freq="MS")
    s = s.reindex(full_idx).astype(float)

    return s

def _sarima_forecast(s: pd.Series, horizon: int):
    from statsmodels.tsa.statespace.sarimax import SARIMAX
    model = SARIMAX(
        s, order=(1, 1, 1), seasonal_order=(1, 1, 1, 12),
        enforce_stationarity=False, enforce_invertibility=False
    )
    res = model.fit(disp=False)
    fc = res.get_forecast(steps=horizon)
    ci = fc.conf_int()
    idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    out = pd.DataFrame({
        "month_date": idx,
        "yhat": fc.predicted_mean.values,
        "yhat_lo": ci.iloc[:, 0].values,
        "yhat_hi": ci.iloc[:, 1].values
    })

    # quick backtest (last 12)
    hist = s.dropna().iloc[-12:]
    mape = None
    if len(hist) >= 3:
        bt = res.get_prediction(start=hist.index[0], end=hist.index[-1]).predicted_mean
        mape = float((abs((hist - bt) / hist)).replace([float("inf")], pd.NA).dropna().mean())
    return out, mape

def _arima_forecast(s: pd.Series, horizon: int):
    from statsmodels.tsa.arima.model import ARIMA
    res = ARIMA(s, order=(1, 1, 1)).fit()
    fc = res.get_forecast(steps=horizon)
    idx = pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=horizon, freq="MS")
    out = pd.DataFrame({
        "month_date": idx,
        "yhat": fc.predicted_mean.values
    })
    return out, None

def _prophet_forecast(s: pd.Series, horizon: int):
    try:
        from prophet import Prophet  # pip install prophet
    except Exception as e:
        raise HTTPException(status_code=501, detail=f"Prophet not available: {e}")

    df = s.reset_index()
    df.columns = ["ds", "y"]
    m = Prophet(seasonality_mode="multiplicative")
    m.fit(df)
    future = m.make_future_dataframe(periods=horizon, freq="MS")
    pred = m.predict(future).tail(horizon)[["ds", "yhat", "yhat_lower", "yhat_upper"]]
    pred.columns = ["month_date", "yhat", "yhat_lo", "yhat_hi"]
    return pred, None

# ---------- Route ----------
@router.post("/forecast")
def forecast(req: ForecastReq):
    s = _to_monthly_series(req.series)
    if s.empty or s.dropna().empty:
        raise HTTPException(status_code=400, detail="Empty or invalid series for forecasting.")

    model = req.model.upper()
    if model == "SARIMA":
        out, mape = _sarima_forecast(s, req.horizon)
    elif model == "ARIMA":
        out, mape = _arima_forecast(s, req.horizon)
    elif model == "PROPHET":
        out, mape = _prophet_forecast(s, req.horizon)
    else:
        raise HTTPException(status_code=400, detail="Unknown model")

    # Match your frontend expectations (simple JSON)
    return {
        "fcst": out.assign(month=lambda x: x["month_date"].dt.strftime("%b %Y"))
                  .drop(columns=["month_date"]).to_dict(orient="records"),
        "mape": mape
    }
