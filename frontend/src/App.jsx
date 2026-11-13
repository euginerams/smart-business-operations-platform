import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Activity, AlertTriangle, BarChart3, Boxes, CalendarDays, CheckCircle2,
    CircleDollarSign, LayoutDashboard, Moon, Package, Plus, RefreshCw, ShoppingCart,
  Sun, Users, X
} from 'lucide-react';
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis
} from 'recharts';

const API = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');
const url = (path) => `${API}${path}`;

const asList = (data) => {
  if (Array.isArray(data)) return data;
  if (!data || typeof data !== 'object') return [];
  for (const key of ['items', 'results', 'data', 'products', 'customers', 'sales', 'transactions']) {
    if (Array.isArray(data[key])) return data[key];
    if (data[key] && typeof data[key] === 'object') {
      for (const nestedKey of ['items', 'results']) {
        if (Array.isArray(data[key][nestedKey])) return data[key][nestedKey];
      }
    }
  }
  return [];
};

const money = (value) =>
  new Intl.NumberFormat('en-ZA', { style: 'currency', currency: 'ZAR' }).format(Number(value ?? 0));

const fmt = (value) => new Intl.NumberFormat('en-ZA').format(Number(value ?? 0));

const today = () => {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
};

const errorMessage = (error) => {
  if (typeof error === 'string') return error;
  const detail = error?.detail ?? error?.message;
  if (Array.isArray(detail)) return detail.map((item) => item.msg || JSON.stringify(item)).join('; ');
  if (detail && typeof detail === 'object') return JSON.stringify(detail);
  return detail || 'An unexpected error occurred. Please try again.';
};

async function request(path, options = {}) {
  let response;
  try {
    const requestOptions = { ...options };
    if (options.body) {
      requestOptions.headers = {
        'Content-Type': 'application/json',
        ...options.headers
      };
    } else if (!options.headers) {
      delete requestOptions.headers;
    }

    response = Object.keys(requestOptions).length
      ? await fetch(url(path), requestOptions)
      : await fetch(url(path));
  } catch {
    throw new Error('Could not connect to the API. Check that the backend is running and try again.');
  }

  const data = response.status === 204
    ? null
    : await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(errorMessage(data) || `Request failed (${response.status})`);
  }
  return data;
}

function Field({ label, children }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function Modal({ title, onClose, children }) {
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => {
      if (event.target === event.currentTarget) onClose();
    }}>
      <section className="modal" role="dialog" aria-modal="true" aria-label={title}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Close">
            <X size={19} />
          </button>
        </div>
        {children}
      </section>
    </div>
  );
}

function HealthBar({ healthy = 0, low = 0 }) {
  const total = Number(healthy) + Number(low);
  const percent = total ? Math.round((Number(healthy) / total) * 100) : 0;
  return (
    <div className="health-bar">
      <div className="health-bar-track" role="img"
        aria-label={`${percent}% of active products are healthy`}>
        <div className="health-bar-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="health-bar-legend">
        <span>{fmt(healthy)} healthy</span><span>{fmt(low)} low stock</span>
      </div>
    </div>
  );
}

function DataTable({ headers, rows, empty }) {
  return (
    <div className="table-scroll">
      <table>
        <thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead>
        <tbody>{rows.length ? rows : empty}</tbody>
      </table>
    </div>
  );
}

function App() {
  const [page, setPage] = useState('overview');
  const [summary, setSummary] = useState(null);
  const [top, setTop] = useState([]);
  const [low, setLow] = useState([]);
  const [health, setHealth] = useState(null);
  const [products, setProducts] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [sales, setSales] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [threshold, setThreshold] = useState('5');
  const [from, setFrom] = useState(`${today().slice(0, 7)}-01`);
  const [to, setTo] = useState(today());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [modal, setModal] = useState('');
  const [editing, setEditing] = useState(null);
  const [search, setSearch] = useState('');
    const [listErrors, setListErrors] = useState({});
  const [theme, setTheme] = useState(() =>
    document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');

  const toggleTheme = () => {
    const next = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('theme', next); } catch { /* storage unavailable */ }
    setTheme(next);
  };

  const [productForm, setProductForm] = useState({
    sku: '', name: '', description: '', category: '', price: '', stock_quantity: '0'
  });
  const [customerForm, setCustomerForm] = useState({
    full_name: '', email: '', phone: '', company: '', notes: ''
  });
  const [stockForm, setStockForm] = useState({
    product_id: '', movement_type: 'stock_in', quantity: '1', reason: 'Restock',
    adjustment_direction: 'increase'
  });
  const [saleForm, setSaleForm] = useState({ customer_id: '', product_id: '', quantity: '1' });

  const refreshDashboard = useCallback(async () => {
    const query = new URLSearchParams();
    if (from) query.set('start_date', from);
    if (to) query.set('end_date', to);
    const suffix = query.toString() ? `?${query}` : '';

    const results = await Promise.allSettled([
      request(`/reports/summary${suffix}`),
      request(`/reports/top-products${suffix}${suffix ? '&' : '?'}limit=10`),
      request(`/reports/low-stock?threshold=${encodeURIComponent(threshold)}`),
      request(`/reports/inventory-health?threshold=${encodeURIComponent(threshold)}`)
    ]);

    const messages = [];
    if (results[0].status === 'fulfilled') setSummary(results[0].value);
    else messages.push(`Summary: ${errorMessage(results[0].reason)}`);
    if (results[1].status === 'fulfilled') setTop(asList(results[1].value));
    else messages.push(`Top products: ${errorMessage(results[1].reason)}`);
    if (results[2].status === 'fulfilled') setLow(asList(results[2].value));
    else messages.push(`Low stock: ${errorMessage(results[2].reason)}`);
    if (results[3].status === 'fulfilled') setHealth(results[3].value);
    else messages.push(`Inventory health: ${errorMessage(results[3].reason)}`);

    if (results.every((result) => result.status === 'rejected')) {
      return ['Unable to load dashboard data'];
    }
    return messages;
  }, [from, to, threshold]);

  const refreshLists = useCallback(async () => {
    const endpoints = [
      ['products', '/products/?limit=100', setProducts],
      ['customers', '/customers/?limit=100', setCustomers],
      ['sales', '/sales/?limit=100', setSales]
    ];
    const results = await Promise.allSettled(endpoints.map(([, path]) => request(path)));
    const messages = {};
    results.forEach((result, index) => {
      const [name, , setter] = endpoints[index];
      if (result.status === 'fulfilled') setter(asList(result.value));
      else messages[name] = errorMessage(result.reason);
    });
    setListErrors(messages);
    return Object.values(messages);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const [dashboardErrors, listErrorsFound] = await Promise.all([
      refreshDashboard(),
      refreshLists()
    ]);
    const messages = [...dashboardErrors, ...listErrorsFound];
    setError(messages.length ? messages.join(' | ') : '');
    setLoading(false);
  }, [refreshDashboard, refreshLists]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (saleForm.product_id && !products.some((product) =>
      String(product.id) === String(saleForm.product_id) && Number(product.stock_quantity) > 0
    )) {
      setSaleForm((current) => ({ ...current, product_id: '' }));
    }
  }, [products, saleForm.product_id]);

  const navigate = (next) => {
    setPage(next);
    setError('');
    setNotice('');
    setSearch('');
  };

  const run = async (operation, success) => {
    setError('');
    setNotice('');
    try {
      await operation();
      setNotice(success);
      const [dashboardErrors, listErrorsFound] = await Promise.all([
        refreshDashboard(), refreshLists()
      ]);
      const messages = [...dashboardErrors, ...listErrorsFound];
      if (messages.length) setError(messages.join(' | '));
      setModal('');
      setEditing(null);
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const openProduct = (product = null) => {
    setEditing(product);
    setProductForm(product ? {
      sku: product.sku ?? '',
      name: product.name ?? '',
      description: product.description ?? '',
      category: product.category ?? '',
      price: String(product.price ?? ''),
      stock_quantity: String(product.stock_quantity ?? 0)
    } : {
      sku: '', name: '', description: '', category: '', price: '', stock_quantity: '0'
    });
    setModal('product');
  };

  const saveProduct = (event) => {
    event.preventDefault();
    const body = { ...productForm, price: Number(productForm.price) };
    if (!editing) body.stock_quantity = Number(productForm.stock_quantity);
    else delete body.stock_quantity;
    run(() => request(editing ? `/products/${editing.id}` : '/products/', {
      method: editing ? 'PATCH' : 'POST', body: JSON.stringify(body)
    }), editing ? 'Product updated.' : 'Product created.');
  };

  const openCustomer = (customer = null) => {
    setEditing(customer);
    setCustomerForm(customer ? {
      full_name: customer.full_name ?? '', email: customer.email ?? '',
      phone: customer.phone ?? '', company: customer.company ?? '', notes: customer.notes ?? ''
    } : { full_name: '', email: '', phone: '', company: '', notes: '' });
    setModal('customer');
  };

  const saveCustomer = (event) => {
    event.preventDefault();
    const body = Object.fromEntries(Object.entries(customerForm).map(([key, value]) => [
      key, value.trim() || null
    ]));
    run(() => request(editing ? `/customers/${editing.id}` : '/customers/', {
      method: editing ? 'PATCH' : 'POST', body: JSON.stringify(body)
    }), editing ? 'Customer updated.' : 'Customer created.');
  };

  const openStock = (product = null) => {
    setStockForm({
      product_id: String(product?.id ?? products[0]?.id ?? ''),
      movement_type: 'stock_in', quantity: '1', reason: 'Restock',
      adjustment_direction: 'increase'
    });
    setModal('stock');
  };

  const saveStock = (event) => {
    event.preventDefault();
    const body = {
      product_id: Number(stockForm.product_id),
      movement_type: stockForm.movement_type,
      quantity: Number(stockForm.quantity),
      reason: stockForm.reason.trim()
    };
    if (body.movement_type === 'adjustment') {
      body.adjustment_direction = stockForm.adjustment_direction || 'increase';
    }
    run(() => request('/inventory/transactions', {
      method: 'POST', body: JSON.stringify(body)
    }), 'Inventory movement recorded.');
  };

  const saveSale = (event) => {
    event.preventDefault();
    if (!saleForm.product_id) {
      setError('Please select a product with available stock.');
      return;
    }
    const selectedProduct = products.find((product) =>
      String(product.id) === String(saleForm.product_id)
    );
    const quantity = Number(saleForm.quantity);
    if (!selectedProduct || quantity < 1 || quantity > Number(selectedProduct.stock_quantity)) {
      setError('Please enter a valid quantity that does not exceed the available stock.');
      return;
    }
    const body = {
      customer_id: saleForm.customer_id ? Number(saleForm.customer_id) : null,
      items: [{ product_id: Number(saleForm.product_id), quantity }]
    };
    run(() => request('/sales/', { method: 'POST', body: JSON.stringify(body) }),
      'Sale recorded and stock deducted.');
  };

  const showTransactions = async (product) => {
    setError('');
    try {
      const rows = await request(`/inventory/products/${product.id}/transactions?limit=50`);
      setTransactions(asList(rows).map((row) => ({ ...row, product_name: product.name })));
      setModal('history');
    } catch (e) {
      setError(errorMessage(e));
    }
  };

  const deactivate = (type, item) => {
    const label = type === 'product' ? item.name : item.full_name;
    if (!window.confirm(`Deactivate ${type} “${label}”?`)) return;
    run(() => request(`/${type === 'product' ? 'products' : 'customers'}/${item.id}`, {
      method: 'DELETE'
    }), `${type === 'product' ? 'Product' : 'Customer'} deactivated.`);
  };

  const nav = [
    ['overview', 'Overview', LayoutDashboard],
    ['sales', 'Sales analytics', BarChart3],
    ['products', 'Products', Package],
    ['inventory', 'Inventory', Boxes],
    ['customers', 'Customers', Users],
    ['record-sale', 'Record a sale', ShoppingCart]
  ];
  const pageTitle = nav.find((item) => item[0] === page)?.[1] || 'Overview';

  const filteredProducts = useMemo(() => products.filter((product) =>
    `${product.name ?? ''} ${product.sku ?? ''} ${product.category ?? ''}`
      .toLowerCase().includes(search.toLowerCase())
  ), [products, search]);

  const filteredCustomers = useMemo(() => customers.filter((customer) =>
    `${customer.full_name ?? ''} ${customer.email ?? ''} ${customer.company ?? ''}`
      .toLowerCase().includes(search.toLowerCase())
  ), [customers, search]);

  const availableProducts = useMemo(() => products.filter((product) =>
    Number(product.stock_quantity) > 0
  ), [products]);

  const stat = (label, value, description, Icon) => (
    <article className="stat-card">
      <div className="stat-top"><span>{label}</span><Icon size={20} /></div>
      <strong>{value}</strong><small>{description}</small>
    </article>
  );

  const tableEmpty = (columns, message) => (
    <tr><td colSpan={columns} className="empty">{message}</td></tr>
  );

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark"><Boxes /></span>
          <div><b>SmartBusiness</b><small>OPERATIONS PLATFORM</small></div>
        </div>
        <div className="sidebar-label">WORKSPACE</div>
        <nav className="side-nav">
          {nav.map(([id, label, Icon]) => (
                        <button key={id} className={`nav-link ${page === id ? 'active' : ''}`}
              aria-current={page === id ? 'page' : undefined}
              onClick={() => navigate(id)}>
              <Icon size={19} /><span>{label}</span>
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom"><span className="status-dot" />API-connected workspace</div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div className="breadcrumb">Workspace <span>/</span> <b>{pageTitle}</b></div>
          <div className="topbar-right">
                        <span className="environment-label">LIVE BUSINESS DATA</span>
            <button type="button" className="icon-button" onClick={toggleTheme}
              aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
              title={theme === 'dark' ? 'Light mode' : 'Dark mode'}>
              {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <button className="button secondary small" onClick={load} disabled={loading}>
              <RefreshCw size={15} />Refresh
            </button>
          </div>
        </header>

        <div className="dashboard-content">
          <div className="welcome-section">
            <div>
              <div className="eyebrow"><Activity size={15} />BUSINESS OPERATIONS</div>
              <h1>{page === 'overview' ? 'Business overview' : pageTitle}</h1>
              <p className="page-subtitle">
                {page === 'overview'
                  ? 'Monitor sales, track inventory, and understand business performance.'
                  : `Manage and review your business ${pageTitle.toLowerCase()}.`}
              </p>
            </div>
            {['products', 'customers', 'inventory', 'record-sale'].includes(page) && (
              <button className="button primary" onClick={() =>
                page === 'products' ? openProduct()
                  : page === 'customers' ? openCustomer()
                    : page === 'inventory' ? openStock() : navigate('record-sale')}>
                <Plus size={16} />
                {page === 'products' ? 'Add product' : page === 'customers' ? 'Add customer'
                  : page === 'inventory' ? 'Record movement' : 'New sale'}
              </button>
            )}
          </div>

          {error && <div className="alert error" role="alert">
            <AlertTriangle size={18} /><span>
              <b>{error.includes('Unable to load dashboard data')
                ? 'Unable to load dashboard data'
                : 'Some data could not be loaded or saved'}</b>
              <small>{error}</small>
            </span>
          </div>}
          {notice && <div className="alert success"><CheckCircle2 size={18} />{notice}</div>}
                    {loading && <div className="loading-bar" role="status" aria-label="Loading business data" />}

          {/* OVERVIEW */}
          {page === 'overview' && <>
            <section className="filter-bar">
              <div><b><CalendarDays size={17} />Reporting period</b><small>Choose dates for sales reports</small></div>
              <div className="controls">
                <Field label="From"><input type="date" value={from} max={to}
                  onChange={(event) => setFrom(event.target.value)} /></Field>
                <Field label="To"><input type="date" value={to} min={from} max={today()}
                  onChange={(event) => setTo(event.target.value)} /></Field>
                <button className="button secondary" onClick={load}>Apply dates</button>
              </div>
            </section>

            <section className="stats-grid">
              {stat('Total revenue', money(summary?.total_revenue), 'Recorded sales revenue', CircleDollarSign)}
              {stat('Total sales', fmt(summary?.total_sales), 'Completed sales', ShoppingCart)}
              {stat('Units sold', fmt(summary?.units_sold), 'Items sold in period', Boxes)}
              {stat('Active products', fmt(summary?.active_products), 'Current active products', Package)}
              {stat('Active customers', fmt(summary?.active_customers), 'Current active customers', Users)}
              {stat('Inventory value', money(health?.inventory_value ?? summary?.inventory_value),
                'Current stock at listed prices', BarChart3)}
            </section>

            <section className="filter-bar">
              <div><b><AlertTriangle size={17} />Inventory alert threshold</b>
                <small>Products at or below this quantity are flagged</small></div>
              <div className="controls">
                <Field label="Low-stock threshold">
                  <select value={threshold} onChange={(event) => setThreshold(event.target.value)}>
                    {[0, 3, 5, 10, 20].map((value) =>
                      <option key={value} value={value}>{value} units</option>)}
                  </select>
                </Field>
                <button className="button secondary" onClick={load}>Apply threshold</button>
              </div>
            </section>

            <div className="two-col">
              <section className="panel">
                <h2>Top-selling products</h2>
                <p className="muted">Ranked by units sold in the selected period</p>
                <div className="chart-container">
                  {top.length ? <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={top}><CartesianGrid strokeDasharray="3 3" vertical={false} />
                      <XAxis dataKey="sku" /><YAxis allowDecimals={false} /><Tooltip />
                      <Bar dataKey="units_sold" fill="#7456e8" radius={[5, 5, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer> : <p className="empty">No sales in this period.</p>}
                </div>
              </section>
              <section className="panel">
                <h2>Inventory health</h2>
                <p className="muted">{fmt(low.length)} active product(s) have {threshold} or fewer units.</p>
                <div className="health-numbers">
                  <strong>{fmt(health?.total_stock_units)}<small>Total stock units</small></strong>
                                    <strong>{money(health?.inventory_value)}<small>Inventory value</small></strong>
                </div>
                <HealthBar healthy={health?.healthy_stock_products} low={health?.low_stock_products} />
              </section>
            </div>

            <section className="panel">
              <h2>Inventory requiring attention</h2>
              <p className="muted">Low-stock and out-of-stock products</p>
              <DataTable headers={['Product', 'SKU', 'Category', 'Stock', 'Unit price', 'Status']}
                rows={low.map((product) => <tr key={product.product_id}>
                  <td>{product.name}</td><td>{product.sku}</td><td>{product.category || '—'}</td>
                  <td>{product.stock_quantity}</td><td>{money(product.unit_price)}</td>
                  <td><span className={`pill ${Number(product.stock_quantity) === 0 ? 'danger' : 'warning'}`}>{Number(product.stock_quantity) === 0 ? 'Out of stock' : 'Low stock'}</span></td>
                </tr>)} empty={tableEmpty(6, 'No products need attention.')} />
            </section>
          </>}

          {/* SALES ANALYTICS */}
          {page === 'sales' && <>
            <section className="filter-bar">
              <div><b><CalendarDays size={17} />Sales reporting period</b>
                <small>Filter sales metrics and rankings</small></div>
              <div className="controls">
                <Field label="From"><input type="date" value={from} max={to}
                  onChange={(event) => setFrom(event.target.value)} /></Field>
                <Field label="To"><input type="date" value={to} min={from} max={today()}
                  onChange={(event) => setTo(event.target.value)} /></Field>
                <button className="button secondary" onClick={load}>Apply dates</button>
              </div>
            </section>
            <section className="stats-grid">
              {stat('Revenue', money(summary?.total_revenue), 'For selected period', CircleDollarSign)}
              {stat('Sales', fmt(summary?.total_sales), 'Completed transactions', ShoppingCart)}
              {stat('Units sold', fmt(summary?.units_sold), 'Total items sold', Boxes)}
            </section>
            <section className="panel">
              <h2>Top-selling products</h2><p className="muted">Units sold and revenue by product</p>
              <div className="chart-container tall">
                {top.length ? <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={top} margin={{ bottom: 35 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="product_name" angle={-15} textAnchor="end" interval={0} />
                    <YAxis allowDecimals={false} /><Tooltip />
                    <Bar dataKey="units_sold" fill="#7456e8" />
                  </BarChart>
                </ResponsiveContainer> : <p className="empty">No sales recorded for this period.</p>}
              </div>
              <DataTable headers={['Product', 'SKU', 'Units sold', 'Revenue']}
                rows={top.map((product) => <tr key={product.product_id}>
                  <td>{product.product_name}</td><td>{product.sku}</td>
                  <td>{fmt(product.units_sold)}</td><td>{money(product.revenue)}</td>
                </tr>)} empty={tableEmpty(4, 'No sales to report.')} />
            </section>
            <section className="panel">
              <div className="panel-title-row"><h2>Recent sales</h2>
                <button className="button primary" onClick={() => navigate('record-sale')}>
                  <Plus size={15} />Record sale</button></div>
              <DataTable headers={['Sale #', 'Date', 'Items', 'Total']}
                rows={sales.map((sale) => <tr key={sale.id}>
                  <td>#{sale.id}</td>
                  <td>{sale.created_at ? new Date(sale.created_at).toLocaleString('en-ZA') : '—'}</td>
                  <td>{asList(sale.items).map((item) =>
                    `${item.product_name || 'Product'} × ${item.quantity}`).join(', ') || '—'}</td>
                  <td>{money(sale.total_amount)}</td>
                </tr>)} empty={tableEmpty(4, listErrors.sales
                  ? 'Sales could not be loaded. Check the API error above.' : 'No sales recorded yet.')} />
            </section>
          </>}

          {/* PRODUCTS */}
          {page === 'products' && <section className="panel">
            <div className="panel-title-row"><div><h2>Product catalogue</h2>
              <p className="muted">Create, update and deactivate products.</p></div>
              <input className="search" placeholder="Search products…" value={search}
                onChange={(event) => setSearch(event.target.value)} /></div>
            <DataTable headers={['Product', 'SKU', 'Category', 'Price', 'Stock', 'Actions']}
              rows={filteredProducts.map((product) => <tr key={product.id}>
                <td><b>{product.name}</b><small className="cell-sub">{product.description}</small></td>
                <td>{product.sku}</td><td>{product.category || '—'}</td>
                <td>{money(product.price)}</td><td>{product.stock_quantity}</td>
                <td className="actions">
                  <button className="text-button" onClick={() => openProduct(product)}>Edit</button>
                  <button className="text-button" onClick={() => openStock(product)}>Stock</button>
                  <button className="text-button danger-text" onClick={() => deactivate('product', product)}>Deactivate</button>
                </td>
              </tr>)} empty={tableEmpty(6, listErrors.products
                ? 'Products could not be loaded. Check the API error above.'
                : search ? 'No products match your search.' : 'No products found.')} />
          </section>}

          {/* INVENTORY */}
          {page === 'inventory' && <>
            <section className="stats-grid">
              {stat('Active products', fmt(products.length), 'Products available', Package)}
              {stat('Low-stock items', fmt(low.length), 'At current threshold', AlertTriangle)}
              {stat('Total stock units', fmt(health?.total_stock_units), 'Across active products', Boxes)}
              {stat('Inventory value', money(health?.inventory_value), 'Current stock value', CircleDollarSign)}
            </section>
            <section className="panel">
              <div className="panel-title-row"><div><h2>Stock levels</h2>
                <p className="muted">Record stock movements or inspect a product's history.</p></div>
                <button className="button primary" onClick={() => openStock()}><Plus size={15} />Record movement</button>
              </div>
              <DataTable headers={['Product', 'SKU', 'Current stock', 'Unit price', 'Status', 'Actions']}
                rows={products.map((product) => <tr key={product.id}>
                  <td>{product.name}</td><td>{product.sku}</td><td>{product.stock_quantity}</td>
                  <td>{money(product.price)}</td>
                  <td><span className={`pill ${Number(product.stock_quantity) <= Number(threshold) ? 'warning' : 'good'}`}>
                    {Number(product.stock_quantity) <= Number(threshold) ? 'Low stock' : 'Healthy'}</span></td>
                  <td className="actions">
                    <button className="text-button" onClick={() => openStock(product)}>Adjust stock</button>
                    <button className="text-button" onClick={() => showTransactions(product)}>History</button>
                  </td>
                </tr>)} empty={tableEmpty(6, listErrors.products
                  ? 'Inventory could not be loaded. Check the API error above.' : 'No active products.')} />
            </section>
          </>}

          {/* CUSTOMERS */}
          {page === 'customers' && <section className="panel">
            <div className="panel-title-row"><div><h2>Customer directory</h2>
              <p className="muted">Manage customer details and status.</p></div>
              <input className="search" placeholder="Search customers…" value={search}
                onChange={(event) => setSearch(event.target.value)} /></div>
            <DataTable headers={['Customer', 'Email', 'Phone', 'Company', 'Actions']}
              rows={filteredCustomers.map((customer) => <tr key={customer.id}>
                <td><b>{customer.full_name}</b></td><td>{customer.email || '—'}</td>
                <td>{customer.phone || '—'}</td><td>{customer.company || '—'}</td>
                <td className="actions">
                  <button className="text-button" onClick={() => openCustomer(customer)}>Edit</button>
                  <button className="text-button danger-text" onClick={() => deactivate('customer', customer)}>Deactivate</button>
                </td>
              </tr>)} empty={tableEmpty(5, listErrors.customers
                ? 'Customers could not be loaded. Check the API error above.'
                : search ? 'No customers match your search.' : 'No customers found.')} />
          </section>}

          {/* RECORD SALE */}
          {page === 'record-sale' && <section className="panel form-panel">
            <h2>Record a sale</h2>
            <p className="muted">A successful sale automatically deducts stock and records an inventory movement.</p>
            <form onSubmit={saveSale} className="form-grid">
              <Field label="Customer (optional)">
                <select value={saleForm.customer_id} onChange={(event) =>
                  setSaleForm((current) => ({ ...current, customer_id: event.target.value }))}>
                  <option value="">Walk-in customer</option>
                  {customers.map((customer) => <option key={customer.id} value={customer.id}>
                    {customer.full_name}{customer.company ? ` — ${customer.company}` : ''}
                  </option>)}
                </select>
                {listErrors.customers && <small className="muted">Customer list unavailable: {listErrors.customers}</small>}
              </Field>
              <Field label="Product">
                <select required value={saleForm.product_id} onChange={(event) =>
                  setSaleForm((current) => ({ ...current, product_id: event.target.value }))}>
                  <option value="">Select a product</option>
                  {availableProducts.map((product) => <option key={product.id} value={product.id}>
                    {product.name} ({product.sku}) — {product.stock_quantity} available
                  </option>)}
                </select>
                {!availableProducts.length && <small className="muted">
                  {listErrors.products ? 'Products could not be loaded. Refresh after checking the API.' : 'No products currently have stock available.'}
                </small>}
              </Field>
              <Field label="Quantity">
                <input type="number" min="1" max={products.find((p) =>
                  String(p.id) === String(saleForm.product_id))?.stock_quantity ?? undefined}
                  required value={saleForm.quantity} onChange={(event) =>
                    setSaleForm((current) => ({ ...current, quantity: event.target.value }))} />
                {saleForm.product_id && <small className="muted">
                  Available stock: {products.find((p) => String(p.id) === String(saleForm.product_id))?.stock_quantity ?? 0}
                </small>}
              </Field>
              <button className="button primary" type="submit"
                disabled={!availableProducts.length || !saleForm.product_id}>Complete sale</button>
            </form>
          </section>}

          <footer className="dashboard-footer">Smart Business Operations Platform
            <span>{loading ? 'Updating…' : 'Connected to business API'}</span>
          </footer>
        </div>
      </main>

      {/* PRODUCT MODAL */}
      {modal === 'product' && <Modal title={editing ? 'Edit product' : 'Add product'} onClose={() => setModal('')}>
        <form className="form-grid" onSubmit={saveProduct}>
          <Field label="SKU"><input required minLength="2" maxLength="50" value={productForm.sku}
            onChange={(event) => setProductForm((current) => ({ ...current, sku: event.target.value }))} /></Field>
          <Field label="Product name"><input required minLength="2" value={productForm.name}
            onChange={(event) => setProductForm((current) => ({ ...current, name: event.target.value }))} /></Field>
          <Field label="Category"><input value={productForm.category}
            onChange={(event) => setProductForm((current) => ({ ...current, category: event.target.value }))} /></Field>
          <Field label="Unit price (ZAR)"><input type="number" min="0" step="0.01" required value={productForm.price}
            onChange={(event) => setProductForm((current) => ({ ...current, price: event.target.value }))} /></Field>
          {!editing && <Field label="Opening stock"><input type="number" min="0" step="1"
            value={productForm.stock_quantity} onChange={(event) =>
              setProductForm((current) => ({ ...current, stock_quantity: event.target.value }))} /></Field>}
          <Field label="Description"><textarea value={productForm.description}
            onChange={(event) => setProductForm((current) => ({ ...current, description: event.target.value }))} /></Field>
          <div className="form-actions">
            <button type="button" className="button secondary" onClick={() => setModal('')}>Cancel</button>
            <button className="button primary">{editing ? 'Save changes' : 'Create product'}</button>
          </div>
        </form>
      </Modal>}

      {/* CUSTOMER MODAL */}
      {modal === 'customer' && <Modal title={editing ? 'Edit customer' : 'Add customer'} onClose={() => setModal('')}>
        <form className="form-grid" onSubmit={saveCustomer}>
          <Field label="Full name"><input required minLength="2" value={customerForm.full_name}
            onChange={(event) => setCustomerForm((current) => ({ ...current, full_name: event.target.value }))} /></Field>
          <Field label="Email"><input type="email" value={customerForm.email}
            onChange={(event) => setCustomerForm((current) => ({ ...current, email: event.target.value }))} /></Field>
          <Field label="Phone"><input value={customerForm.phone}
            onChange={(event) => setCustomerForm((current) => ({ ...current, phone: event.target.value }))} /></Field>
          <Field label="Company"><input value={customerForm.company}
            onChange={(event) => setCustomerForm((current) => ({ ...current, company: event.target.value }))} /></Field>
          <Field label="Notes"><textarea value={customerForm.notes}
            onChange={(event) => setCustomerForm((current) => ({ ...current, notes: event.target.value }))} /></Field>
          <div className="form-actions">
            <button type="button" className="button secondary" onClick={() => setModal('')}>Cancel</button>
            <button className="button primary">{editing ? 'Save changes' : 'Create customer'}</button>
          </div>
        </form>
      </Modal>}

      {/* INVENTORY MODAL */}
      {modal === 'stock' && <Modal title="Record inventory movement" onClose={() => setModal('')}>
        <form className="form-grid" onSubmit={saveStock}>
          <Field label="Product"><select required value={stockForm.product_id}
            onChange={(event) => setStockForm((current) => ({ ...current, product_id: event.target.value }))}>
            <option value="">Select a product</option>
            {products.map((product) => <option key={product.id} value={product.id}>
              {product.name} ({product.stock_quantity} available)</option>)}
          </select></Field>
          <Field label="Movement type"><select value={stockForm.movement_type}
            onChange={(event) => setStockForm((current) => ({ ...current, movement_type: event.target.value }))}>
            <option value="stock_in">Stock in</option><option value="stock_out">Stock out</option>
            <option value="adjustment">Adjustment</option>
          </select></Field>
          {stockForm.movement_type === 'adjustment' && <Field label="Adjustment direction">
            <select value={stockForm.adjustment_direction} onChange={(event) =>
              setStockForm((current) => ({ ...current, adjustment_direction: event.target.value }))}>
              <option value="increase">Increase</option><option value="decrease">Decrease</option>
            </select>
          </Field>}
          <Field label="Quantity"><input type="number" min="1" step="1" required value={stockForm.quantity}
            onChange={(event) => setStockForm((current) => ({ ...current, quantity: event.target.value }))} /></Field>
          <Field label="Reason"><input required minLength="3" maxLength="255" value={stockForm.reason}
            onChange={(event) => setStockForm((current) => ({ ...current, reason: event.target.value }))} /></Field>
          <div className="form-actions">
            <button type="button" className="button secondary" onClick={() => setModal('')}>Cancel</button>
            <button className="button primary" disabled={!products.length}>Save movement</button>
          </div>
        </form>
      </Modal>}

      {/* INVENTORY HISTORY MODAL */}
      {modal === 'history' && <Modal title="Inventory movement history" onClose={() => setModal('')}>
        <DataTable headers={['Date', 'Movement', 'Quantity change', 'Reason']}
          rows={transactions.map((transaction) => <tr key={transaction.id}>
            <td>{transaction.created_at ? new Date(transaction.created_at).toLocaleString('en-ZA') : '—'}</td>
            <td>{String(transaction.movement_type || '').replaceAll('_', ' ') || '—'}</td>
            <td>{Number(transaction.quantity_change) > 0 ? '+' : ''}{transaction.quantity_change}</td>
            <td>{transaction.reason || '—'}</td>
          </tr>)} empty={tableEmpty(4, 'No movements recorded for this product.')} />
      </Modal>}
    </div>
  );
}

export default App;
