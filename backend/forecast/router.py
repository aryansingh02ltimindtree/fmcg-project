# FastAPI router sketch — adapt to your project
from fastapi import APIRouter
from pydantic import BaseModel
import pandas as pd

router = APIRouter(prefix="/forecast")

class SeriesPoint(BaseModel):
    date: str
    value: float

class ForecastReq(BaseModel):
    model: str  # "ARIMA" | "SARIMA" | "Prophet"
    horizon: int = 6
    series: list[SeriesPoint]
    measure: str | None = None
    filters: dict | None = None

@router.post("")
def forecast(req: ForecastReq):
    s = pd.Series({pd.to_datetime(p.date): p.value for p in req.series})
    s = s.asfreq("MS")  # safe, we built a regular monthly index in the UI already
    model = req.model.upper()

    if model == "PROPHET":
        from prophet import Prophet
        df = s.reset_index()
        df.columns = ["ds","y"]
        m = Prophet(seasonality_mode="multiplicative")
        m.fit(df)
        future = m.make_future_dataframe(periods=req.horizon, freq="MS")
        fc = m.predict(future).tail(req.horizon)[["ds","yhat","yhat_lower","yhat_upper"]]
        return {"fcst": fc.to_dict(orient="records")}
    elif model == "SARIMA":
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        res = SARIMAX(s, order=(1,1,1), seasonal_order=(1,1,1,12),
                      enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)
        f = res.get_forecast(steps=req.horizon)
        ci = f.conf_int()
        out = pd.DataFrame({
            "month_date": pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=req.horizon, freq="MS"),
            "yhat": f.predicted_mean.values,
            "yhat_lo": ci.iloc[:,0].values,
            "yhat_hi": ci.iloc[:,1].values
        })
        return {"fcst": out.to_dict(orient="records")}
    else:  # ARIMA
        from statsmodels.tsa.arima.model import ARIMA
        res = ARIMA(s, order=(1,1,1)).fit()
        f = res.get_forecast(steps=req.horizon)
        out = pd.DataFrame({
            "month_date": pd.date_range(s.index[-1] + pd.offsets.MonthBegin(1), periods=req.horizon, freq="MS"),
            "yhat": f.predicted_mean.values
        })
        return {"fcst": out.to_dict(orient="records")}
