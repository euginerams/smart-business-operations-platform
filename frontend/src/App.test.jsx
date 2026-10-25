// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
} from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import App from "./App";

vi.mock("recharts", () => {
  const MockChart = ({ children }) => (
    <div data-testid="mock-chart">{children}</div>
  );

  const MockShape = ({ children }) => <div>{children}</div>;

  return {
    ResponsiveContainer: MockChart,
    BarChart: MockChart,
    PieChart: MockChart,
    Bar: MockShape,
    CartesianGrid: MockShape,
    Cell: MockShape,
    Pie: MockShape,
    Tooltip: MockShape,
    XAxis: MockShape,
    YAxis: MockShape,
  };
});

function mockResponse(data, ok = true, status = 200) {
  return Promise.resolve({
    ok,
    status,
    json: () => Promise.resolve(data),
  });
}

function setupSuccessfulFetch() {
  const summary = {
    total_revenue: "1500.00",
    total_sales: 3,
    units_sold: 8,
    active_products: 2,
    active_customers: 4,
    inventory_value: "2500.00",
  };

  const topProducts = [
    {
      product_name: "Business Laptop",
      sku: "LAP-001",
      units_sold: 5,
      revenue: "1000.00",
    },
  ];

  const lowStock = [
    {
      product_id: 1,
      name: "Business Laptop",
      sku: "LAP-001",
      category: "Computers",
      stock_quantity: 3,
      unit_price: "200.00",
      inventory_value: "600.00",
    },
  ];

  const inventoryHealth = {
    threshold: 5,
    active_products: 2,
    total_stock_units: 13,
    low_stock_units: 3,
    healthy_stock_units: 10,
    low_stock_products: 1,
    healthy_stock_products: 1,
    inventory_value: "2500.00",
  };

  global.fetch = vi.fn((url) => {
    if (url.startsWith("/reports/summary")) {
      return mockResponse(summary);
    }

    if (url.startsWith("/reports/top-products")) {
      return mockResponse(topProducts);
    }

    if (url.startsWith("/reports/low-stock")) {
      return mockResponse(lowStock);
    }

    if (url.startsWith("/reports/inventory-health")) {
      return mockResponse(inventoryHealth);
    }

    return mockResponse({ detail: "Not found" }, false, 404);
  });
}

describe("Smart Business Operations dashboard", () => {
  beforeEach(() => {
    setupSuccessfulFetch();
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("loads business figures and inventory insights", async () => {
    render(<App />);

    expect(
      await screen.findByText("Business overview"),
    ).toBeInTheDocument();

    expect(
      await screen.findByText(
        /1 active product\(s\) have 5 or fewer units/i,
      ),
    ).toBeInTheDocument();

    // en-ZA formats R1,500 as approximately "R 1 500,00".
    // The whitespace matcher also handles non-breaking spaces.
    expect(
      await screen.findByText(/1\s*500,00/),
    ).toBeInTheDocument();

    expect(global.fetch).toHaveBeenCalledWith(
      "/reports/inventory-health?threshold=5",
    );
  });

  it("requests updated inventory reports when the threshold changes", async () => {
    render(<App />);

    await screen.findByText("Business overview");

    const thresholdSelect = screen.getByLabelText(
      "Low-stock threshold",
    );

    fireEvent.change(thresholdSelect, {
      target: { value: "10" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Apply threshold" }),
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        "/reports/inventory-health?threshold=10",
      );

      expect(global.fetch).toHaveBeenCalledWith(
        "/reports/low-stock?threshold=10",
      );
    });
  });

  it("shows an error when the backend returns a failed response", async () => {
    global.fetch = vi.fn(() =>
      mockResponse({ detail: "Server error" }, false, 500),
    );

    render(<App />);

    expect(
      await screen.findByText("Unable to load dashboard data"),
    ).toBeInTheDocument();

    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("sends the selected reporting dates to the sales reports", async () => {
    render(<App />);

    await screen.findByText("Business overview");

    const dateInputs = screen.getAllByDisplayValue(
      /^\d{4}-\d{2}-\d{2}$/,
    );

    expect(dateInputs.length).toBeGreaterThanOrEqual(2);

    fireEvent.change(dateInputs[0], {
      target: { value: "2026-10-01" },
    });

    fireEvent.change(dateInputs[1], {
      target: { value: "2026-10-20" },
    });

    fireEvent.click(
      screen.getByRole("button", { name: "Apply dates" }),
    );

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("start_date=2026-10-01"),
      );

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("end_date=2026-10-20"),
      );
    });
  });
});