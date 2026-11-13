import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  BarChart3,
  Boxes,
  CalendarDays,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  LayoutDashboard,
  Package,
  RefreshCw,
  ShoppingCart,
  Users,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const money = new Intl.NumberFormat("en-ZA", {
  style: "currency",
  currency: "ZAR",
  maximumFractionDigits: 2,
});

const number = new Intl.NumberFormat("en-ZA");

function formatMoney(value) {
  return money.format(Number(value ?? 0));
}

function formatNumber(value) {
  return number.format(Number(value ?? 0));
}

function formatDate(date) {
  // Use local calendar components; toISOString() converts to UTC and can
  // shift the selected calendar date in time zones such as South Africa.
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function StatCard({ title, value, description, icon: Icon, accent }) {
  return (
    <article className="stat-card">
      <div className="stat-top">
        <span className="stat-label">{title}</span>
        <span className={`stat-icon ${accent}`}>
          <Icon size={19} />
        </span>
      </div>
      <div className="stat-value">{value}</div>
      <div className="stat-description">{description}</div>
    </article>
  );
}

function Panel({ title, subtitle, action, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <div className="panel-heading">
        <div>
          <h2>{title}</h2>
          {subtitle && <p>{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

function LoadingState() {
  return (
    <div className="loading-state">
      <span className="spinner" />
      <span>Loading business data...</span>
    </div>
  );
}

function App() {
  const today = new Date();
  const firstDay = new Date(today.getFullYear(), today.getMonth(), 1);

  const [startDate, setStartDate] = useState(formatDate(firstDay));
  const [endDate, setEndDate] = useState(formatDate(today));
  const [appliedStartDate, setAppliedStartDate] = useState(formatDate(firstDay));
  const [appliedEndDate, setAppliedEndDate] = useState(formatDate(today));
  const [threshold, setThreshold] = useState("5");
  const [appliedThreshold, setAppliedThreshold] = useState("5");
  const latestRequestId = useRef(0);

  const [summary, setSummary] = useState(null);
  const [topProducts, setTopProducts] = useState([]);
  const [lowStock, setLowStock] = useState([]);
  const [inventoryHealth, setInventoryHealth] = useState(null);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState(null);

  const loadDashboard = useCallback(
    async (showLoading = true) => {
      if (appliedStartDate && appliedEndDate && appliedStartDate > appliedEndDate) {
        setError("The start date cannot be later than the end date.");
        return;
      }

      const requestId = ++latestRequestId.current;

      if (showLoading) {
        setLoading(true);
      } else {
        setRefreshing(true);
      }

      setError("");

      const dateParams = new URLSearchParams();

      if (appliedStartDate) dateParams.set("start_date", appliedStartDate);
      if (appliedEndDate) dateParams.set("end_date", appliedEndDate);

      const query = dateParams.toString();
      const summaryUrl = `/reports/summary${query ? `?${query}` : ""}`;
      const productsUrl =
        `/reports/top-products?${query ? `${query}&` : ""}limit=8`;

      try {
        const [
          summaryResponse,
          productsResponse,
          stockResponse,
          healthResponse,
        ] = await Promise.all([
          fetch(summaryUrl),
          fetch(productsUrl),
          fetch(`/reports/low-stock?threshold=${appliedThreshold}`),
          fetch(`/reports/inventory-health?threshold=${appliedThreshold}`),
        ]);

        const responses = [
          ["Summary", summaryResponse],
          ["Top products", productsResponse],
          ["Low-stock report", stockResponse],
          ["Inventory health", healthResponse],
        ];

        for (const [label, response] of responses) {
          if (!response.ok) {
            throw new Error(`${label} request failed (${response.status}).`);
          }
        }

        const [
          summaryData,
          productsData,
          stockData,
          healthData,
        ] = await Promise.all([
          summaryResponse.json(),
          productsResponse.json(),
          stockResponse.json(),
          healthResponse.json(),
        ]);

        // Ignore older requests that finish after a more recent filter request.
        if (requestId !== latestRequestId.current) return;

        setSummary(summaryData);
        setTopProducts(productsData);
        setLowStock(stockData);
        setInventoryHealth(healthData);
        setLastUpdated(new Date());
      } catch (requestError) {
        if (requestId !== latestRequestId.current) return;
        setError(
          `${requestError.message} Check that the FastAPI backend is running.`,
        );
      } finally {
        if (requestId === latestRequestId.current) {
          setLoading(false);
          setRefreshing(false);
        }
      }
    },
    [appliedStartDate, appliedEndDate, appliedThreshold],
  );

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  const chartData = topProducts.map((product) => ({
    name:
      product.product_name.length > 18
        ? `${product.product_name.slice(0, 18)}…`
        : product.product_name,
    units: Number(product.units_sold),
  }));

  const stockChartData = [
    {
      name: "Healthy stock",
      value: Number(inventoryHealth?.healthy_stock_units ?? 0),
    },
    {
      name: "Low stock",
      value: Number(inventoryHealth?.low_stock_units ?? 0),
    },
  ];

  const hasStockData = stockChartData.some((item) => item.value > 0);
  const lowStockProducts = Number(inventoryHealth?.low_stock_products ?? 0);
  const totalStockUnits = Number(inventoryHealth?.total_stock_units ?? 0);

  let inventoryInsight = "Inventory data is not available yet.";

  if (inventoryHealth) {
    if (Number(inventoryHealth.active_products) === 0) {
      inventoryInsight =
        "There are no active products. Add products to start monitoring inventory.";
    } else if (lowStockProducts === 0) {
      inventoryInsight =
        `All active products are above the ${appliedThreshold}-unit low-stock threshold.`;
    } else {
      inventoryInsight =
        `${formatNumber(lowStockProducts)} active product(s) have ${appliedThreshold} or fewer units. Review the alerts below and plan replenishment.`;
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Boxes size={23} />
          </div>
          <div className="brand-text">
            <strong>SmartBusiness</strong>
            <span>OPERATIONS PLATFORM</span>
          </div>
        </div>

        <div className="sidebar-label">WORKSPACE</div>

        <nav className="side-nav" aria-label="Main navigation">
          <a className="nav-link active" href="#overview">
            <LayoutDashboard size={19} />
            <span>Overview</span>
          </a>
          <a className="nav-link" href="#sales">
            <BarChart3 size={19} />
            <span>Sales analytics</span>
          </a>
          <a className="nav-link" href="#inventory">
            <Package size={19} />
            <span>Inventory</span>
          </a>
        </nav>

        <div className="sidebar-bottom">
          <div className="system-status">
            <span className="status-dot" />
            <div>
              <strong>Dashboard status</strong>
              <span>{error ? "Check connection" : "Connected when data loads"}</span>
            </div>
          </div>
          <div className="sidebar-footer">
            Smart Business Operations Platform
            <br />
            Portfolio project · Local development
          </div>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">
            <span>Workspace</span>
            <span className="breadcrumb-divider">/</span>
            <strong>Overview</strong>
          </div>
          <div className="topbar-right">
            <span className="environment-label">
              <span className="status-dot" />
              LOCAL ENVIRONMENT
            </span>
            <div className="avatar">SB</div>
          </div>
        </header>

        <div className="dashboard-content" id="overview">
          <section className="welcome-section">
            <div>
              <div className="eyebrow">
                <Activity size={15} />
                BUSINESS INTELLIGENCE
              </div>
              <h1>Business overview</h1>
              <p className="page-subtitle">
                Monitor sales, track inventory, and understand business
                performance.
              </p>
            </div>

            <button
              className="button button-primary"
              onClick={() => loadDashboard(false)}
              disabled={loading || refreshing}
              type="button"
            >
              <RefreshCw size={16} />
              {refreshing ? "Refreshing..." : "Refresh data"}
            </button>
          </section>

          <section className="filter-bar">
            <div className="filter-title">
              <CalendarDays size={18} />
              <div>
                <strong>Reporting period</strong>
                <span>Choose the dates for your sales reports</span>
              </div>
            </div>

            <div className="date-controls">
              <label>
                <span>From</span>
                <input
                  type="date"
                  value={startDate}
                  max={endDate || undefined}
                  onChange={(event) => setStartDate(event.target.value)}
                />
              </label>
              <label>
                <span>To</span>
                <input
                  type="date"
                  value={endDate}
                  min={startDate || undefined}
                  max={formatDate(today)}
                  onChange={(event) => setEndDate(event.target.value)}
                />
              </label>
              <button
                className="button button-secondary"
                onClick={() => {
                  if (startDate && endDate && startDate > endDate) {
                    setError("The start date cannot be later than the end date.");
                    return;
                  }
                  setAppliedStartDate(startDate);
                  setAppliedEndDate(endDate);
                }}
                disabled={loading || refreshing}
                type="button"
              >
                Apply dates
              </button>
            </div>
          </section>

          <section className="filter-bar">
            <div className="filter-title">
              <AlertTriangle size={18} />
              <div>
                <strong>Inventory alert threshold</strong>
                <span>
                  Products at or below this quantity will be flagged
                </span>
              </div>
            </div>

            <div className="date-controls">
              <label>
                <span>Low-stock threshold</span>
                <select
                  value={threshold}
                  onChange={(event) => setThreshold(event.target.value)}
                >
                  <option value="0">0 units (out of stock only)</option>
                  <option value="3">3 units</option>
                  <option value="5">5 units</option>
                  <option value="10">10 units</option>
                  <option value="20">20 units</option>
                </select>
              </label>
              <button
                className="button button-secondary"
                onClick={() => setAppliedThreshold(threshold)}
                disabled={loading || refreshing}
                type="button"
              >
                Apply threshold
              </button>
            </div>
          </section>

          {error && (
            <div className="error-banner" role="alert">
              <AlertTriangle size={20} />
              <div>
                <strong>Unable to load dashboard data</strong>
                <p>{error}</p>
              </div>
              <button
                type="button"
                className="error-retry"
                onClick={() => loadDashboard()}
              >
                Try again
              </button>
            </div>
          )}

          <section className="section-block">
            <div className="section-heading">
              <div>
                <h2>Performance at a glance</h2>
                <p>
                  Sales metrics use the selected period; product, customer and
                  inventory figures reflect current active records.
                </p>
              </div>
              <span className="period-tag">
                <Clock3 size={14} />
                {appliedStartDate && appliedEndDate
                  ? `${appliedStartDate} – ${appliedEndDate}`
                  : "All available dates"}
              </span>
            </div>

            {loading && !summary ? (
              <LoadingState />
            ) : (
              <div className="stats-grid">
                <StatCard
                  title="Total revenue"
                  value={formatMoney(summary?.total_revenue)}
                  description="Recorded sales revenue"
                  icon={CircleDollarSign}
                  accent="purple"
                />
                <StatCard
                  title="Total sales"
                  value={formatNumber(summary?.total_sales)}
                  description="Completed sales records"
                  icon={ShoppingCart}
                  accent="blue"
                />
                <StatCard
                  title="Units sold"
                  value={formatNumber(summary?.units_sold)}
                  description="Items sold in this period"
                  icon={Boxes}
                  accent="orange"
                />
                <StatCard
                  title="Active products"
                  value={formatNumber(summary?.active_products)}
                  description="Products currently active"
                  icon={Package}
                  accent="green"
                />
                <StatCard
                  title="Active customers"
                  value={formatNumber(summary?.active_customers)}
                  description="Customers currently active"
                  icon={Users}
                  accent="pink"
                />
                <StatCard
                  title="Inventory value"
                  value={formatMoney(inventoryHealth?.inventory_value ?? summary?.inventory_value)}
                  description="Current active stock at listed prices"
                  icon={BarChart3}
                  accent="teal"
                />
              </div>
            )}
          </section>

          <section className="section-block">
            <Panel
              title="Business insight"
              subtitle="A quick interpretation of your current inventory"
              action={
                <span className="panel-badge">
                  <Activity size={14} />
                  Inventory analysis
                </span>
              }
            >
              {loading && !inventoryHealth ? (
                <LoadingState />
              ) : (
                <div className="success-state">
                  {lowStockProducts > 0 ? (
                    <AlertTriangle size={24} />
                  ) : (
                    <CheckCircle2 size={24} />
                  )}
                  <div>
                    <strong>{inventoryInsight}</strong>
                    <p>
                      {formatNumber(totalStockUnits)} units across{" "}
                      {formatNumber(inventoryHealth?.active_products)} active
                      products. Inventory value:{" "}
                      {formatMoney(inventoryHealth?.inventory_value)}.
                    </p>
                  </div>
                </div>
              )}
            </Panel>
          </section>

          <section className="analytics-grid" id="sales">
            <Panel
              title="Top-selling products"
              subtitle="Products ranked by units sold in the selected period"
              className="sales-panel"
              action={<span className="panel-badge">By units sold</span>}
            >
              {loading && topProducts.length === 0 ? (
                <LoadingState />
              ) : chartData.length === 0 ? (
                <div className="empty-state">
                  No sales recorded for this period. Record sales to see your
                  best-performing products here.
                </div>
              ) : (
                <>
                  <div className="chart-container">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={chartData}
                        margin={{ top: 10, right: 8, left: -18, bottom: 4 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          vertical={false}
                          stroke="#e9edf4"
                        />
                        <XAxis
                          dataKey="name"
                          tick={{ fill: "#737b8c", fontSize: 11 }}
                          axisLine={false}
                          tickLine={false}
                          interval={0}
                          angle={-18}
                          textAnchor="end"
                          height={65}
                        />
                        <YAxis
                          allowDecimals={false}
                          tick={{ fill: "#737b8c", fontSize: 12 }}
                          axisLine={false}
                          tickLine={false}
                        />
                        <Tooltip
                          formatter={(value) => [
                            formatNumber(value),
                            "Units sold",
                          ]}
                        />
                        <Bar
                          dataKey="units"
                          name="Units sold"
                          fill="#7456e8"
                          radius={[5, 5, 0, 0]}
                          maxBarSize={48}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="product-ranking">
                    {topProducts.slice(0, 5).map((product, index) => (
                      <div
                        className="ranking-row"
                        key={`${product.sku}-${index}`}
                      >
                        <span className="rank-number">{index + 1}</span>
                        <div className="ranking-product">
                          <strong>{product.product_name}</strong>
                          <span>SKU: {product.sku}</span>
                        </div>
                        <div className="ranking-result">
                          <strong>{formatNumber(product.units_sold)}</strong>
                          <span>units</span>
                        </div>
                        <div className="ranking-revenue">
                          {formatMoney(product.revenue)}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </Panel>

            <Panel
              title="Inventory health"
              subtitle={`Stock units grouped using the ${appliedThreshold}-unit threshold`}
              className="inventory-panel"
              action={
                <span className="panel-badge warning-badge">
                  <AlertTriangle size={14} />
                  {formatNumber(lowStockProducts)} low-stock products
                </span>
              }
            >
              {loading && !inventoryHealth ? (
                <LoadingState />
              ) : (
                <>
                  <div className="inventory-summary">
                    <div>
                      <span className="inventory-number">
                        {formatNumber(totalStockUnits)}
                      </span>
                      <span className="inventory-caption">Total stock units</span>
                    </div>
                    <div className="inventory-legend">
                      <span>
                        <i className="legend-dot in-stock" />
                        Healthy units
                      </span>
                      <span>
                        <i className="legend-dot low-stock" />
                        Low-stock units
                      </span>
                    </div>
                  </div>

                  <div className="donut-container">
                    {hasStockData ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={stockChartData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={67}
                            outerRadius={92}
                            paddingAngle={4}
                            stroke="none"
                          >
                            {stockChartData.map((entry, index) => (
                              <Cell
                                key={entry.name}
                                fill={index === 0 ? "#36b58a" : "#f1a44b"}
                              />
                            ))}
                          </Pie>
                          <Tooltip
                            formatter={(value) => [
                              formatNumber(value),
                              "Stock units",
                            ]}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="empty-state">
                        No stock units to display.
                      </div>
                    )}
                  </div>

                  <div className="inventory-footnote">
                    <CheckCircle2 size={16} />
                    Stock units are grouped according to each product's
                    quantity, not the number of products.
                  </div>
                </>
              )}
            </Panel>
          </section>

          <section className="section-block" id="inventory">
            <div className="section-heading">
              <div>
                <h2>Low-stock alerts</h2>
                <p>
                  Active products with {threshold} or fewer units remaining
                </p>
              </div>
              <span className="alert-count">
                <AlertTriangle size={15} />
                {lowStock.length} items need attention
              </span>
            </div>

            <Panel
              title="Inventory requiring attention"
              subtitle="Review these products and plan replenishment"
              className="stock-table-panel"
              action={
                <span className="threshold-tag">
                  Threshold: {threshold} units
                </span>
              }
            >
              {loading && lowStock.length === 0 ? (
                <LoadingState />
              ) : lowStock.length === 0 ? (
                <div className="success-state">
                  <CheckCircle2 size={24} />
                  <div>
                    <strong>No low-stock alerts</strong>
                    <p>
                      No active products are at or below the selected
                      threshold.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="table-scroll">
                  <table className="stock-table">
                    <thead>
                      <tr>
                        <th>Product</th>
                        <th>SKU</th>
                        <th>Category</th>
                        <th>Quantity remaining</th>
                        <th>Unit price</th>
                        <th>Stock value</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {lowStock.map((product) => (
                        <tr key={product.product_id}>
                          <td>
                            <div className="table-product">
                              <span className="table-product-icon">
                                <Package size={17} />
                              </span>
                              <strong>{product.name}</strong>
                            </div>
                          </td>
                          <td className="sku-cell">{product.sku}</td>
                          <td>{product.category || "Uncategorised"}</td>
                          <td>
                            <strong
                              className={
                                product.stock_quantity === 0
                                  ? "stock-zero"
                                  : "stock-low"
                              }
                            >
                              {formatNumber(product.stock_quantity)}
                            </strong>
                          </td>
                          <td>{formatMoney(product.unit_price)}</td>
                          <td>{formatMoney(product.inventory_value)}</td>
                          <td>
                            <span
                              className={`stock-status ${
                                product.stock_quantity === 0
                                  ? "out-of-stock"
                                  : "low-status"
                              }`}
                            >
                              {product.stock_quantity === 0 ? (
                                <ArrowDownRight size={13} />
                              ) : (
                                <AlertTriangle size={13} />
                              )}
                              {product.stock_quantity === 0
                                ? "Out of stock"
                                : "Low stock"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </Panel>
          </section>

          <footer className="dashboard-footer">
            <span>Smart Business Operations Platform</span>
            <span>
              {lastUpdated
                ? `Last updated at ${lastUpdated.toLocaleTimeString("en-ZA", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}`
                : "Waiting for data"}
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}

export default App;