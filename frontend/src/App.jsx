import { useEffect, useState } from "react";
import "./App.css";

const API = "http://127.0.0.1:8000";

const format = (value, digits = 2) =>
  Number(value).toLocaleString("en-IN", {
    maximumFractionDigits: digits,
  });

async function getData(path, signal) {
  const response = await fetch(`${API}${path}`, { signal });

  if (!response.ok) {
    throw new Error(`${path} returned HTTP ${response.status}`);
  }

  return response.json();
}

function InventoryPanel({ scenario }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const controller = new AbortController();

    getData(`/inventory?scenario=${scenario}`, controller.signal)
      .then(setRows)
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });

    return () => controller.abort();
  }, [scenario]);

  if (error) return <p role="alert">{error}</p>;
  if (!rows) return <p role="status">Loading scenario…</p>;
  if (!rows.length) return <p>No results for this scenario.</p>;

  return (
    <>
      <p className="muted">
        Lead time: {rows[0].lead_time_days} days · Buffer:{" "}
        {rows[0].buffer_days} days
      </p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Drug class</th>
              <th>Daily average</th>
              <th>Lead-time demand</th>
              <th>Safety stock</th>
              <th>Reorder point</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.drug_class}>
                <td>{row.drug_class}</td>
                <td>{format(row.average_daily_sales)}</td>
                <td>{format(row.lead_time_demand)}</td>
                <td>{format(row.safety_stock)}</td>
                <td><strong>{format(row.reorder_point)}</strong></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [scenario, setScenario] = useState("standard_delivery");

  useEffect(() => {
    const controller = new AbortController();

    Promise.all(
      [
        "/kpis",
        "/classes",
        "/forecast",
        "/quality",
        "/patterns/weekday",
      ].map((path) => getData(path, controller.signal))
    )
      .then(([kpis, classes, forecast, quality, weekdays]) => {
        setData({ kpis, classes, forecast, quality, weekdays });
      })
      .catch((err) => {
        if (err.name !== "AbortError") setError(err.message);
      });

    return () => controller.abort();
  }, []);

  if (error) {
    return (
      <main>
        <h1>Could not load dashboard</h1>
        <p role="alert">{error}</p>
        <p>Check that FastAPI is running on port 8000.</p>
        <button onClick={() => window.location.reload()}>Retry</button>
      </main>
    );
  }

  if (!data) {
    return <main><p role="status">Loading sales intelligence…</p></main>;
  }

  const { kpis, classes, forecast, quality, weekdays } = data;
  const selected = forecast.metrics.find((row) => row.selected);
  const baseline = forecast.metrics.find(
    (row) => row.model === "seasonal_naive"
  );

  return (
    <main>
      <header>
        <div>
          <p className="eyebrow">PHARMACEUTICAL DEMAND INTELLIGENCE</p>
          <h1>Demand & supply planning</h1>
          <p className="muted">
            Historical analysis · {kpis.start_date.slice(0, 10)} to{" "}
            {kpis.end_date.slice(0, 10)}
          </p>
        </div>
        <span className="badge">Historical demo</span>
      </header>

      <section className="kpi-grid" aria-label="Key metrics">
        {[
          ["Recorded sales volume", format(kpis.total_sales)],
          ["Drug classes", kpis.drug_classes],
          ["Complete days", format(kpis.complete_days, 0)],
          ["Top three share", `${format(kpis.top_three_share_pct)}%`],
        ].map(([label, value]) => (
          <article className="card" key={label}>
            <p className="muted">{label}</p>
            <strong className="kpi-value">{value}</strong>
          </article>
        ))}
      </section>

      <div className="two-column">
        <section className="card">
          <h2>Sales concentration</h2>
          <p className="muted">Share of total recorded volume</p>

          {classes.map((row) => (
            <div className="bar-row" key={row.drug_class}>
              <span>{row.drug_class}</span>
              <div className="bar-track" aria-hidden="true">
                <div style={{ width: `${row.share_pct}%` }} />
              </div>
              <strong>{format(row.share_pct)}%</strong>
            </div>
          ))}
        </section>

        <section className="card">
          <h2>Weekday patterns</h2>
          <p className="muted">Average total daily sales</p>
          <div className="table-wrap">
            <table>
              <thead>
                <tr><th>Weekday</th><th>Average sales</th></tr>
              </thead>
              <tbody>
                {weekdays.map((row) => (
                  <tr key={row.weekday}>
                    <td>{row.weekday}</td>
                    <td>{format(row.average_daily_sales)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <section className="card">
        <h2>Forecast evaluation</h2>
        <p className="muted">
          Three 28-day validation windows, followed by a separate
          28-day holdout. Lower WAPE is better.
        </p>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Model</th>
                <th>Validation WAPE</th>
                <th>Holdout WAPE</th>
                <th>Selected by validation</th>
              </tr>
            </thead>
            <tbody>
              {forecast.metrics.map((row) => (
                <tr key={row.model}>
                  <td>{row.model.replaceAll("_", " ")}</td>
                  <td>{format(row.validation_wape_pct)}%</td>
                  <td>{format(row.holdout_wape_pct)}%</td>
                  <td>{row.selected ? "Yes" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selected && baseline &&
          selected.holdout_wape_pct > baseline.holdout_wape_pct && (
            <p className="notice">
              The selected model performed worse than the baseline on
              the final holdout. Forecast improvement is not established.
            </p>
          )}

        <details>
          <summary>View the 28-day historical forecast</summary>
          <p className="muted">
            Forecasts begin after the October 2019 training cutoff,
            not from today.
          </p>
          <div className="table-wrap">
            <table>
              <thead><tr><th>Date</th><th>Forecast volume</th></tr></thead>
              <tbody>
                {forecast.future.map((row) => (
                  <tr key={row.timestamp}>
                    <td>{row.timestamp.slice(0, 10)}</td>
                    <td>{format(row.forecast)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      </section>

      <section className="card">
        <div className="section-heading">
          <h2>Inventory scenarios</h2>
          <label>
            Delivery scenario{" "}
            <select
              value={scenario}
              onChange={(event) => setScenario(event.target.value)}
            >
              <option value="short_delivery">Short delivery</option>
              <option value="standard_delivery">Standard delivery</option>
              <option value="delayed_delivery">Delayed delivery</option>
            </select>
          </label>
        </div>

        <InventoryPanel key={scenario} scenario={scenario} />

        <p className="muted">
          Class forecasts use constant shares from the last 90 days.
          Safety stock equals recent daily average × buffer days.
          Reorder points are scenario thresholds, not order quantities.
        </p>
      </section>

      <section className="card">
        <h2>Data quality</h2>
        <p>
          <strong>{format(quality.matching_pairs, 0)}</strong> of{" "}
          <strong>{format(quality.checked_pairs, 0)}</strong>{" "}
          hourly-to-daily pairs matched within tolerance.
        </p>
        <p className="muted">
          Issues: {quality.issue_pairs} · Incomplete boundary days:{" "}
          {quality.incomplete_days}, excluded from daily analysis.
        </p>
      </section>

      <footer>
        Sales are a proxy for demand. Values use the source dataset’s
        sales units, not revenue. Class-level scenarios require
        product-level inventory and supplier data before operational use.
      </footer>
    </main>
  );
}
