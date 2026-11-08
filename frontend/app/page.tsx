"use client";
import { useCallback, useEffect, useState, FormEvent } from "react";
import {
  Activity,
  ArrowUpRight,
  BarChart3,
  Database,
  FileDown,
  FolderOpen,
  LayoutDashboard,
  LogOut,
  Moon,
  Plus,
  Search,
  ShieldCheck,
  Sun,
  UploadCloud,
  Workflow,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  LineChart,
  Line,
} from "recharts";

type User = { name: string; email: string };
type Workspace = { id: string; name: string };
type Column = {
  name: string;
  type: string;
  suggested_role: string;
  missing: number;
  unique: number;
  stats: Record<string, number>;
};
type Dataset = {
  id: string;
  name: string;
  created: number;
  meanings: Record<string, string>;
  profile: {
    rows: number;
    columns: Column[];
    missing_cells: number;
    duplicate_rows: number;
    sheets: string[];
    selected_sheet: string | null;
    preview: Record<string, unknown>[];
    limitations: string[];
  };
};
type Definition = {
  dimension: string;
  measure: string | null;
  operation: string;
};
type Analysis = {
  id: string;
  name: string;
  dataset_id: string;
  definition: Definition;
};
type ChartData = {
  points: { label: string; value: number | null }[];
  source_rows: number;
  groups: number;
  limitations: string[];
};
type Source = {
  id: string;
  provider: string;
  property_id: string | null;
  last_sync: number | null;
  totals?: Record<string, number | null>;
  daily?: Record<string, string | number>[];
  jobs?: {
    id: string;
    status: string;
    records: number;
    error: string | null;
  }[];
};

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("x-ek-request", "1");
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const response = await fetch(`/api${path}`, {
    ...init,
    headers,
    credentials: "same-origin",
    signal: init.signal || AbortSignal.timeout(125000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string"
        ? body.detail
        : "Please check your input and try again.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}
const number = (value: number | null | undefined) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("en", { maximumFractionDigits: 2 }).format(value);
const yesterday = new Date(Date.now() - 86400000).toISOString().slice(0, 10);
const weekAgo = new Date(Date.now() - 8 * 86400000).toISOString().slice(0, 10);

export default function Home() {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);
  const [register, setRegister] = useState(false);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspace, setWorkspace] = useState("");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [analyses, setAnalyses] = useState<Analysis[]>([]);
  const [tab, setTab] = useState("Overview");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [dark, setDark] = useState(false);
  const [definition, setDefinition] = useState<Definition>({
    dimension: "",
    measure: "",
    operation: "sum",
  });
  const [chart, setChart] = useState<ChartData | null>(null);
  const [chartType, setChartType] = useState("bar");
  const [analysisName, setAnalysisName] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [sheet, setSheet] = useState("");
  const [sources, setSources] = useState<Source[]>([]);
  const [properties, setProperties] = useState<
    Record<string, { id: string; name: string }[]>
  >({});
  const [googleReady, setGoogleReady] = useState(false);
  const [start, setStart] = useState(weekAgo);
  const [end, setEnd] = useState(yesterday);
  const [marketingLimitations, setMarketingLimitations] = useState<string[]>(
    [],
  );

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }
  const loadWorkspaces = useCallback(async () => {
    const ws = await api<Workspace[]>("/workspaces");
    setWorkspaces(ws);
    setWorkspace(ws[0]?.id || "");
  }, []);
  useEffect(() => {
    api<User>("/auth/me", { signal: AbortSignal.timeout(8000) })
      .then(async (u) => {
        setUser(u);
        await loadWorkspaces();
      })
      .catch(() => {})
      .finally(() => setInitializing(false));
    setDark(localStorage.getItem("ek-theme") === "dark");
  }, [loadWorkspaces]);
  const loadData = useCallback(async () => {
    if (!workspace) return;
    const [ds, saved, connected, status] = await Promise.all([
      api<Dataset[]>(`/workspaces/${workspace}/datasets`),
      api<Analysis[]>(`/workspaces/${workspace}/analyses`),
      api<Source[]>(`/workspaces/${workspace}/connections`),
      api<{ google_configured: boolean }>("/integrations/status"),
    ]);
    setDatasets(ds);
    setAnalyses(saved);
    setSources(connected);
    setGoogleReady(status.google_configured);
  }, [workspace]);
  useEffect(() => {
    setDataset(null);
    setChart(null);
    setSources([]);
    setProperties({});
    loadData().catch((e) => setError(e.message));
  }, [loadData]);

  function chooseDataset(ds: Dataset, def?: Definition) {
    setDataset(ds);
    setChart(null);
    setTab("Business Intelligence");
    const dim = ds.profile.columns.find((c) =>
      ["dimension", "date"].includes(ds.meanings[c.name]),
    );
    const measure = ds.profile.columns.find(
      (c) => ds.meanings[c.name] === "measure",
    );
    setDefinition(
      def || {
        dimension: dim?.name || "",
        measure: measure?.name || null,
        operation: measure ? "sum" : "count",
      },
    );
    setAnalysisName(ds.name.replace(/\.[^.]+$/, "") + " analysis");
  }
  async function auth(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    await act(async () => {
      setUser(
        await api<User>(`/auth/${register ? "register" : "login"}`, {
          method: "POST",
          body: JSON.stringify(values),
        }),
      );
      await loadWorkspaces();
    });
  }
  async function upload(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (!sheet) data.delete("sheet");
    await act(async () => {
      const ds = await api<Dataset>(`/workspaces/${workspace}/datasets`, {
        method: "POST",
        body: data,
      });
      await loadData();
      chooseDataset(ds);
      setNotice(
        "Upload complete. Review column roles, then generate your chart.",
      );
    });
  }
  async function generate() {
    if (!dataset) return;
    const query = new URLSearchParams({
      dimension: definition.dimension,
      operation: definition.operation,
    });
    if (definition.measure) query.set("measure", definition.measure);
    setChart(await api<ChartData>(`/datasets/${dataset.id}/chart?${query}`));
  }
  async function loadMarketing() {
    const data = await api<{ sources: Source[]; limitations: string[] }>(
      `/workspaces/${workspace}/marketing?start=${start}&end=${end}`,
    );
    setSources(data.sources);
    setMarketingLimitations(data.limitations);
  }
  const selectedWorkspace = workspaces.find((w) => w.id === workspace);
  const totalRows = datasets.reduce((n, ds) => n + ds.profile.rows, 0);

  if (initializing)
    return (
      <main className="auth-shell">
        <div className="loading">Opening your workspace…</div>
      </main>
    );
  if (!user)
    return (
      <main className="auth-shell">
        <section className="auth-story">
          <div className="wordmark">
            <span className="brand-icon">EK</span> EK-Logic
          </div>
          <div>
            <span className="eyebrow">
              BUSINESS INTELLIGENCE, MADE PRACTICAL
            </span>
            <h1>
              Every dataset has
              <br />a story.
              <br />
              <em>Find yours.</em>
            </h1>
            <p>
              Bring your business and marketing data together.
              <br />
              Explore the patterns. Make your next decision with evidence.
            </p>
          </div>
          <div className="trust">
            <ShieldCheck size={18} /> Private workspaces · Data you control
          </div>
        </section>
        <section className="auth-panel">
          <div className="auth-card">
            <span className="eyebrow">TURN DATA INTO DECISIONS</span>
            <h2>{register ? "Create your workspace" : "Welcome back"}</h2>
            <p>
              {register
                ? "Start with your data. Build clarity from there."
                : "Sign in to continue your analysis."}
            </p>
            <form onSubmit={auth}>
              {register && (
                <>
                  <label>
                    Your name
                    <input
                      name="name"
                      required
                      maxLength={120}
                      autoComplete="name"
                    />
                  </label>
                  <label>
                    Organization
                    <input
                      name="organization"
                      required
                      maxLength={120}
                      autoComplete="organization"
                    />
                  </label>
                </>
              )}
              <label>
                Email address
                <input
                  name="email"
                  type="email"
                  required
                  maxLength={254}
                  autoComplete="email"
                />
              </label>
              <label>
                Password
                <input
                  name="password"
                  type="password"
                  required
                  minLength={12}
                  maxLength={128}
                  autoComplete={register ? "new-password" : "current-password"}
                />
                <small>At least 12 characters</small>
              </label>
              {error && (
                <p role="alert" className="error">
                  {error}
                </p>
              )}
              <button className="primary full" disabled={busy}>
                {busy
                  ? "Please wait…"
                  : register
                    ? "Create account"
                    : "Sign in"}
                <ArrowUpRight size={17} />
              </button>
            </form>
            <button
              className="text-button"
              onClick={() => {
                setRegister(!register);
                setError("");
              }}
            >
              {register
                ? "Already have an account? Sign in"
                : "New to EK-Logic? Create an account"}
            </button>
            <p className="fine">
              Early release. Email verification and password recovery are not
              yet available.
            </p>
          </div>
        </section>
      </main>
    );

  return (
    <div className={`app ${dark ? "dark" : ""}`}>
      <aside className="sidebar">
        <a className="wordmark" href="/">
          <span className="brand-icon">EK</span>EK-Logic
          <span className="beta">BETA</span>
        </a>
        <div className="workspace-picker">
          <span className="eyebrow">YOUR WORKSPACE</span>
          <label className="sr-only" htmlFor="workspace">
            Workspace
          </label>
          <select
            id="workspace"
            value={workspace}
            onChange={(e) => {
              setWorkspace(e.target.value);
              setChart(null);
            }}
          >
            {workspaces.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>
        <span className="nav-label">INTELLIGENCE</span>
        <nav>
          {[
            ["Overview", LayoutDashboard],
            ["Business Intelligence", BarChart3],
            ["Marketing Intelligence", Activity],
            ["Upload Data", UploadCloud],
            ["Saved Reports", FolderOpen],
            ["Data Pipelines", Workflow],
            ["Workspaces", Database],
          ].map(([name, Icon]) => {
            const Label = Icon as typeof Activity;
            return (
              <button
                key={name as string}
                className={tab === name ? "active" : ""}
                onClick={() => {
                  setTab(name as string);
                  setError("");
                }}
              >
                <Label size={18} />
                {name as string}
                {name === "Upload Data" && (
                  <Plus size={14} className="nav-plus" />
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="release-note">
            <span className="status-dot" /> Your data. Your decisions.
            <p>Only uploaded or connected data appears here.</p>
          </div>
          <div className="user-row">
            <span className="avatar">{user.name[0]?.toUpperCase()}</span>
            <div>
              <strong>{user.name}</strong>
              <small>{user.email}</small>
            </div>
            <button
              aria-label="Sign out"
              onClick={() =>
                act(async () => {
                  await api("/auth/logout", { method: "POST" });
                  setUser(null);
                  setDataset(null);
                  setDatasets([]);
                  setChart(null);
                })
              }
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>
            <span className="muted">Workspace / </span>
            {tab}
          </span>
          <div className="topbar-right">
            <span className="private-tag">
              <ShieldCheck size={14} /> Private workspace
            </span>
            <button
              aria-label="Toggle color theme"
              onClick={() => {
                setDark(!dark);
                localStorage.setItem("ek-theme", !dark ? "dark" : "light");
              }}
            >
              {dark ? <Sun size={18} /> : <Moon size={18} />}
            </button>
            <span className="avatar small">{user.name[0]?.toUpperCase()}</span>
          </div>
        </header>
        <main className="content">
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                {selectedWorkspace?.name || "YOUR WORKSPACE"}
              </span>
              <h1>
                {tab === "Overview" ? "A clearer view of your business." : tab}
              </h1>
              <p>
                {tab === "Overview"
                  ? "Your data, analysis, and next steps — all in one place."
                  : "Explore real data. Build decisions on evidence."}
              </p>
            </div>
            <button className="primary" onClick={() => setTab("Upload Data")}>
              <Plus size={17} /> Add dataset
            </button>
          </div>
          {error && (
            <div className="banner error" role="alert">
              {error}
              <button onClick={() => setError("")}>Dismiss</button>
            </div>
          )}
          {notice && (
            <div className="banner success" role="status">
              {notice}
              <button onClick={() => setNotice("")}>Dismiss</button>
            </div>
          )}
          {busy && (
            <div className="busy" role="status">
              Working…
            </div>
          )}
          {tab === "Overview" && (
            <>
              <div className="kpi-grid">
                <Kpi
                  title="Datasets"
                  value={number(datasets.length)}
                  note="Uploaded to this workspace"
                  icon={<Database />}
                />
                <Kpi
                  title="Rows available"
                  value={number(totalRows)}
                  note="Across your uploaded datasets"
                  icon={<BarChart3 />}
                />
                <Kpi
                  title="Saved analyses"
                  value={number(analyses.length)}
                  note="Ready to revisit and export"
                  icon={<FolderOpen />}
                />
                <Kpi
                  title="Google sources"
                  value={number(sources.length)}
                  note="Authorized connections"
                  icon={<Activity />}
                />
              </div>
              <div className="overview-grid">
                <section className="card">
                  <div className="card-title">
                    <div>
                      <span className="eyebrow">FROM DATA TO DIRECTION</span>
                      <h2>Make your first discovery.</h2>
                    </div>
                    <span className="pill">Business intelligence</span>
                  </div>
                  <p className="muted">
                    Upload a spreadsheet, review its quality, and explore the
                    measures that matter to you.
                  </p>
                  <div className="steps">
                    <div>
                      <span>01</span>
                      <strong>Bring your data</strong>
                      <p>CSV or Excel, up to 10 MB.</p>
                    </div>
                    <div>
                      <span>02</span>
                      <strong>Understand the quality</strong>
                      <p>Review missing values and column roles.</p>
                    </div>
                    <div>
                      <span>03</span>
                      <strong>Turn it into insight</strong>
                      <p>Visualize, save, and export your analysis.</p>
                    </div>
                  </div>
                  <button
                    className="primary"
                    onClick={() => setTab("Upload Data")}
                  >
                    Upload a dataset <ArrowUpRight size={16} />
                  </button>
                </section>
                <section className="card navy-card">
                  <span className="eyebrow">CONNECTED INTELLIGENCE</span>
                  <Activity size={42} />
                  <h2>
                    Your marketing.
                    <br />
                    In perspective.
                  </h2>
                  <p>
                    Bring authorized Search Console and GA4 daily metrics into
                    your workspace.
                  </p>
                  <button
                    className="light-button"
                    onClick={() => setTab("Marketing Intelligence")}
                  >
                    Manage Google sources <ArrowUpRight size={16} />
                  </button>
                </section>
              </div>
              <DatasetList datasets={datasets} onSelect={chooseDataset} />
            </>
          )}
          {tab === "Upload Data" && (
            <section className="card upload-card">
              <UploadCloud size={42} />
              <h2>Start with the data you have.</h2>
              <p className="muted">
                Upload CSV or XLSX. Your original file is preserved. No rows are
                silently cleaned or removed.
              </p>
              <form onSubmit={upload}>
                <label>
                  Choose file
                  <input name="file" type="file" accept=".csv,.xlsx" required />
                </label>
                <label>
                  Excel worksheet <span className="muted">(optional)</span>
                  <input
                    name="sheet"
                    value={sheet}
                    onChange={(e) => setSheet(e.target.value)}
                    placeholder="Leave blank to use the first worksheet"
                  />
                </label>
                <small>
                  Limits: 10 MB · 100,000 rows · 100 columns · UTF-8 CSV · No
                  macros
                </small>
                <button className="primary" disabled={busy || !workspace}>
                  <UploadCloud size={17} /> Upload and profile
                </button>
              </form>
              <p className="fine">
                Try the clearly labeled synthetic dataset in the repository’s
                examples folder. No sample business performance is loaded
                automatically.
              </p>
            </section>
          )}
          {tab === "Business Intelligence" && (
            <>
              {!dataset ? (
                <DatasetList datasets={datasets} onSelect={chooseDataset} />
              ) : (
                <>
                  <div className="dataset-header">
                    <div>
                      <span className="pill">UPLOADED DATA</span>
                      <h2>{dataset.name}</h2>
                      <p className="muted">
                        {dataset.profile.selected_sheet &&
                          `Worksheet: ${dataset.profile.selected_sheet} · `}
                        {number(dataset.profile.rows)} rows ·{" "}
                        {dataset.profile.columns.length} columns
                      </p>
                    </div>
                    <button
                      className="secondary"
                      onClick={() => {
                        setDataset(null);
                        setChart(null);
                      }}
                    >
                      Change dataset
                    </button>
                  </div>
                  <div className="kpi-grid compact">
                    <Kpi
                      title="Rows"
                      value={number(dataset.profile.rows)}
                      note="Original source rows"
                    />
                    <Kpi
                      title="Missing cells"
                      value={number(dataset.profile.missing_cells)}
                      note="No values have been imputed"
                    />
                    <Kpi
                      title="Duplicate rows"
                      value={number(dataset.profile.duplicate_rows)}
                      note="Duplicates remain in the analysis"
                    />
                    <Kpi
                      title="Column mappings"
                      value={number(Object.keys(dataset.meanings).length)}
                      note="Review inferred roles below"
                    />
                  </div>
                  <section className="card">
                    <div className="card-title">
                      <div>
                        <h2>Know your data</h2>
                        <p className="muted">
                          Confirm each column’s role before analysis. These are
                          suggestions, not verified meanings.
                        </p>
                      </div>
                      <button
                        className="secondary"
                        disabled={busy}
                        onClick={() =>
                          act(async () => {
                            const ds = await api<Dataset>(
                              `/datasets/${dataset.id}/meanings`,
                              {
                                method: "PUT",
                                body: JSON.stringify({
                                  meanings: dataset.meanings,
                                }),
                              },
                            );
                            setDataset(ds);
                            await loadData();
                            setNotice("Column roles saved.");
                          })
                        }
                      >
                        Save column roles
                      </button>
                    </div>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Column</th>
                            <th>Detected type</th>
                            <th>Missing</th>
                            <th>Distinct</th>
                            <th>Role</th>
                            <th>Numeric range</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dataset.profile.columns.map((c) => (
                            <tr key={c.name}>
                              <td>
                                <strong>{c.name}</strong>
                              </td>
                              <td>{c.type}</td>
                              <td>{number(c.missing)}</td>
                              <td>{number(c.unique)}</td>
                              <td>
                                <select
                                  aria-label={`Role for ${c.name}`}
                                  value={dataset.meanings[c.name]}
                                  onChange={(e) => {
                                    setDataset({
                                      ...dataset,
                                      meanings: {
                                        ...dataset.meanings,
                                        [c.name]: e.target.value,
                                      },
                                    });
                                    setChart(null);
                                  }}
                                >
                                  {[
                                    "dimension",
                                    "date",
                                    "measure",
                                    "ignore",
                                  ].map((r) => (
                                    <option key={r}>{r}</option>
                                  ))}
                                </select>
                              </td>
                              <td>
                                {c.stats.min != null
                                  ? `${number(c.stats.min)} – ${number(c.stats.max)}`
                                  : "—"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                  <section className="card">
                    <div className="card-title">
                      <div>
                        <h2>Explore a question</h2>
                        <p className="muted">
                          Choose how to group and summarize your data.
                        </p>
                      </div>
                      <select
                        aria-label="Chart type"
                        value={chartType}
                        onChange={(e) => setChartType(e.target.value)}
                      >
                        <option value="bar">Bar chart</option>
                        <option value="line">Line chart</option>
                      </select>
                    </div>
                    <div className="chart-controls">
                      <label>
                        Group by
                        <select
                          value={definition.dimension}
                          onChange={(e) => {
                            setDefinition({
                              ...definition,
                              dimension: e.target.value,
                            });
                            setChart(null);
                          }}
                        >
                          <option value="">Choose column</option>
                          {dataset.profile.columns
                            .filter((c) =>
                              ["dimension", "date"].includes(
                                dataset.meanings[c.name],
                              ),
                            )
                            .map((c) => (
                              <option key={c.name}>{c.name}</option>
                            ))}
                        </select>
                      </label>
                      <label>
                        Calculation
                        <select
                          value={definition.operation}
                          onChange={(e) => {
                            setDefinition({
                              ...definition,
                              operation: e.target.value,
                            });
                            setChart(null);
                          }}
                        >
                          {["sum", "mean", "count", "min", "max"].map((o) => (
                            <option key={o}>{o}</option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Measure
                        <select
                          value={definition.measure || ""}
                          disabled={definition.operation === "count"}
                          onChange={(e) => {
                            setDefinition({
                              ...definition,
                              measure: e.target.value,
                            });
                            setChart(null);
                          }}
                        >
                          <option value="">Choose column</option>
                          {dataset.profile.columns
                            .filter(
                              (c) => dataset.meanings[c.name] === "measure",
                            )
                            .map((c) => (
                              <option key={c.name}>{c.name}</option>
                            ))}
                        </select>
                      </label>
                      <button
                        className="primary"
                        disabled={busy || !definition.dimension}
                        onClick={() =>
                          act(async () => {
                            await api(`/datasets/${dataset.id}/meanings`, {
                              method: "PUT",
                              body: JSON.stringify({
                                meanings: dataset.meanings,
                              }),
                            });
                            await generate();
                          })
                        }
                      >
                        Generate chart
                      </button>
                    </div>
                    {chart ? (
                      <>
                        <div
                          className="chart-area"
                          role="img"
                          aria-label={`${definition.operation} by ${definition.dimension}`}
                        >
                          <ResponsiveContainer width="100%" height={320}>
                            {chartType === "bar" ? (
                              <BarChart data={chart.points}>
                                <CartesianGrid
                                  strokeDasharray="3 3"
                                  vertical={false}
                                />
                                <XAxis
                                  dataKey="label"
                                  tick={{ fontSize: 11 }}
                                />
                                <YAxis tick={{ fontSize: 11 }} />
                                <Tooltip />
                                <Bar
                                  dataKey="value"
                                  fill="#2563eb"
                                  radius={[5, 5, 0, 0]}
                                />
                              </BarChart>
                            ) : (
                              <LineChart data={chart.points}>
                                <CartesianGrid
                                  strokeDasharray="3 3"
                                  vertical={false}
                                />
                                <XAxis
                                  dataKey="label"
                                  tick={{ fontSize: 11 }}
                                />
                                <YAxis tick={{ fontSize: 11 }} />
                                <Tooltip />
                                <Line
                                  type="linear"
                                  dataKey="value"
                                  stroke="#0d9488"
                                  strokeWidth={3}
                                  connectNulls={false}
                                />
                              </LineChart>
                            )}
                          </ResponsiveContainer>
                        </div>
                        <p className="fine">
                          {chart.source_rows.toLocaleString()} source rows ·{" "}
                          {chart.groups} groups.{" "}
                          {chartType === "line" &&
                            "Groups are sorted by label; use ISO-formatted dates for chronological order."}
                        </p>
                        <details>
                          <summary>View accessible chart data</summary>
                          <div className="table-scroll">
                            <table>
                              <thead>
                                <tr>
                                  <th>{definition.dimension}</th>
                                  <th>{definition.operation}</th>
                                </tr>
                              </thead>
                              <tbody>
                                {chart.points.map((p) => (
                                  <tr key={p.label}>
                                    <td>{p.label}</td>
                                    <td>{number(p.value)}</td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </details>
                        <div className="save-row">
                          <label>
                            Analysis name
                            <input
                              value={analysisName}
                              maxLength={120}
                              onChange={(e) => setAnalysisName(e.target.value)}
                            />
                          </label>
                          <button
                            className="primary"
                            disabled={busy || !analysisName.trim()}
                            onClick={() =>
                              act(async () => {
                                await api(`/datasets/${dataset.id}/analyses`, {
                                  method: "POST",
                                  body: JSON.stringify({
                                    name: analysisName,
                                    ...definition,
                                  }),
                                });
                                await loadData();
                                setNotice(
                                  "Analysis saved. Open Saved Reports to download it.",
                                );
                              })
                            }
                          >
                            Save analysis
                          </button>
                        </div>
                        <p className="fine">{chart.limitations.join(" ")}</p>
                      </>
                    ) : (
                      <div className="empty chart-empty">
                        <BarChart3 size={30} />
                        <h3>Your next insight starts here.</h3>
                        <p>
                          Select your columns and generate a chart from the
                          uploaded data.
                        </p>
                      </div>
                    )}
                  </section>
                  <section className="card">
                    <h2>Source preview</h2>
                    <p className="muted">
                      First {dataset.profile.preview.length} rows. Missing cells
                      appear as —.
                    </p>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            {dataset.profile.columns.map((c) => (
                              <th key={c.name}>{c.name}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {dataset.profile.preview.map((r, i) => (
                            <tr key={i}>
                              {dataset.profile.columns.map((c) => (
                                <td key={c.name}>
                                  {r[c.name] == null ? "—" : String(r[c.name])}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </section>
                </>
              )}
            </>
          )}
          {tab === "Saved Reports" && (
            <section className="card">
              <div className="card-title">
                <div>
                  <h2>Your saved analyses</h2>
                  <p className="muted">
                    Exports include the exact aggregation saved in each
                    analysis.
                  </p>
                </div>
                <span className="pill">{analyses.length} saved</span>
              </div>
              {!analyses.length ? (
                <Empty
                  title="No saved reports yet"
                  text="Upload a dataset, generate a chart, and save your analysis."
                />
              ) : (
                <div className="report-list">
                  {analyses.map((a) => (
                    <div key={a.id}>
                      <div>
                        <h3>{a.name}</h3>
                        <p className="muted">
                          {a.definition.operation} by {a.definition.dimension}
                        </p>
                      </div>
                      <div className="actions">
                        <button
                          className="secondary"
                          onClick={() => {
                            const ds = datasets.find(
                              (d) => d.id === a.dataset_id,
                            );
                            if (ds) chooseDataset(ds, a.definition);
                          }}
                        >
                          Open
                        </button>
                        {["csv", "xlsx", "pdf"].map((f) => (
                          <a
                            className="export-link"
                            key={f}
                            href={`/api/analyses/${a.id}/export?format=${f}`}
                          >
                            <FileDown size={15} />
                            {f.toUpperCase()}
                          </a>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </section>
          )}
          {tab === "Marketing Intelligence" && (
            <>
              <section className="card">
                <div className="card-title">
                  <div>
                    <h2>Connect your marketing data</h2>
                    <p className="muted">
                      Read-only access. Metrics come from the Google account you
                      authorize.
                    </p>
                  </div>
                  <span className={`pill ${googleReady ? "green" : ""}`}>
                    {googleReady
                      ? "OAuth configured"
                      : "Configuration required"}
                  </span>
                </div>
                {!googleReady && (
                  <p className="callout">
                    The server needs a Google OAuth client, redirect URI, and
                    encryption key. Follow docs/deployment.md. Live data will
                    appear after authorization and synchronization.
                  </p>
                )}
                <div className="actions">
                  {["gsc", "ga4"].map((provider) => (
                    <button
                      key={provider}
                      className="secondary"
                      disabled={busy || !googleReady}
                      onClick={() =>
                        act(async () => {
                          const result = await api<{ url: string }>(
                            `/workspaces/${workspace}/google/${provider}/authorize`,
                            { method: "POST" },
                          );
                          window.location.assign(result.url);
                        })
                      }
                    >
                      <Plus size={16} />
                      {sources.some((s) => s.provider === provider)
                        ? "Reconnect"
                        : "Connect"}{" "}
                      {provider === "gsc"
                        ? "Search Console"
                        : "Google Analytics 4"}
                    </button>
                  ))}
                </div>
              </section>
              <section className="card">
                <div className="card-title">
                  <div>
                    <h2>Performance, with context</h2>
                    <p className="muted">
                      Load previously synchronized records or synchronize up to
                      31 completed days.
                    </p>
                  </div>
                </div>
                <div className="chart-controls">
                  <label>
                    Start date
                    <input
                      type="date"
                      value={start}
                      max={yesterday}
                      onChange={(e) => setStart(e.target.value)}
                    />
                  </label>
                  <label>
                    End date
                    <input
                      type="date"
                      value={end}
                      max={yesterday}
                      onChange={(e) => setEnd(e.target.value)}
                    />
                  </label>
                  <button
                    className="primary"
                    disabled={busy}
                    onClick={() => act(loadMarketing)}
                  >
                    Load metrics
                  </button>
                </div>
                {!sources.length && (
                  <Empty
                    title="No Google sources connected"
                    text="Connect an authorized property to begin. No metrics are simulated."
                  />
                )}
                {sources.map((s) => (
                  <div className="source-block" key={s.id}>
                    <div className="card-title">
                      <div>
                        <span className="eyebrow">
                          {s.provider.toUpperCase()}
                        </span>
                        <h3>{s.property_id || "Select a property"}</h3>
                        <p className="fine">
                          Last sync:{" "}
                          {s.last_sync
                            ? new Date(s.last_sync * 1000).toLocaleString()
                            : "Never"}
                        </p>
                      </div>
                      <div className="actions">
                        <button
                          className="secondary"
                          disabled={busy}
                          onClick={() =>
                            act(async () => {
                              setProperties({
                                ...properties,
                                [s.id]: await api(
                                  `/connections/${s.id}/properties`,
                                ),
                              });
                            })
                          }
                        >
                          Choose property
                        </button>
                        <button
                          className="primary"
                          disabled={busy || !s.property_id}
                          onClick={() =>
                            act(async () => {
                              await api(`/connections/${s.id}/sync`, {
                                method: "POST",
                                body: JSON.stringify({ start, end }),
                              });
                              await loadMarketing();
                              setNotice(
                                "Synchronization finished. Review freshness and coverage before interpreting results.",
                              );
                            })
                          }
                        >
                          Sync selected dates
                        </button>
                      </div>
                    </div>
                    {properties[s.id] && (
                      <label>
                        Authorized property
                        <select
                          value={s.property_id || ""}
                          onChange={(e) => {
                            const property_id = e.target.value;
                            if (property_id)
                              act(async () => {
                                await api(`/connections/${s.id}/property`, {
                                  method: "PUT",
                                  body: JSON.stringify({ property_id }),
                                });
                                await loadData();
                              });
                          }}
                        >
                          <option value="">Select property</option>
                          {properties[s.id].map((p) => (
                            <option key={p.id} value={p.id}>
                              {p.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    )}
                    {s.totals && Object.keys(s.totals).length > 0 ? (
                      <>
                        <div className="kpi-grid compact">
                          {Object.entries(s.totals).map(([k, v]) => (
                            <Kpi
                              key={k}
                              title={k.replaceAll("_", " ")}
                              value={
                                k === "ctr" && v != null
                                  ? `${number(v * 100)}%`
                                  : number(v)
                              }
                              note="Selected synchronized dates"
                            />
                          ))}
                        </div>
                        <div className="chart-area">
                          <ResponsiveContainer width="100%" height={240}>
                            <LineChart data={s.daily}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
                              <YAxis />
                              <Tooltip />
                              <Line
                                type="linear"
                                dataKey={
                                  s.provider === "gsc" ? "clicks" : "sessions"
                                }
                                stroke="#2563eb"
                                strokeWidth={2}
                              />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      </>
                    ) : (
                      <p className="muted">
                        No loaded metrics for this source. Select a property,
                        synchronize dates, then load metrics.
                      </p>
                    )}
                  </div>
                ))}
                {marketingLimitations.map((t) => (
                  <p className="fine" key={t}>
                    {t}
                  </p>
                ))}
              </section>
            </>
          )}
          {tab === "Data Pipelines" && (
            <section className="card">
              <div className="card-title">
                <div>
                  <h2>Source health and sync history</h2>
                  <p className="muted">
                    Manual Google synchronization. Automatic scheduling is a
                    later milestone.
                  </p>
                </div>
                <button
                  className="secondary"
                  disabled={busy}
                  onClick={() => act(loadMarketing)}
                >
                  Refresh status
                </button>
              </div>
              {!sources.length && (
                <Empty
                  title="No pipelines yet"
                  text="Connect Google sources from Marketing Intelligence."
                />
              )}
              {sources.map((s) => (
                <div className="source-block" key={s.id}>
                  <h3>
                    {s.provider.toUpperCase()} ·{" "}
                    {s.property_id || "No property selected"}
                  </h3>
                  <p className="muted">
                    Last successful sync:{" "}
                    {s.last_sync
                      ? new Date(s.last_sync * 1000).toLocaleString()
                      : "Never"}
                  </p>
                  {s.jobs?.map((j) => (
                    <div key={j.id} className="job">
                      <span
                        className={`pill ${j.status === "success" ? "green" : ""}`}
                      >
                        {j.status}
                      </span>
                      <span>{j.records} daily records</span>
                      <span>{j.error}</span>
                    </div>
                  ))}
                </div>
              ))}
            </section>
          )}
          {tab === "Workspaces" && (
            <section className="card">
              <h2>A place for every business</h2>
              <p className="muted">
                Workspaces belong to your organization. All organization users
                can access its workspaces in this release.
              </p>
              <form
                className="save-row"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () => {
                    const ws = await api<Workspace>("/workspaces", {
                      method: "POST",
                      body: JSON.stringify({ name: workspaceName }),
                    });
                    setWorkspaces([...workspaces, ws]);
                    setWorkspace(ws.id);
                    setWorkspaceName("");
                    setNotice("Workspace created.");
                  });
                }}
              >
                <label>
                  Workspace name
                  <input
                    value={workspaceName}
                    maxLength={120}
                    required
                    onChange={(e) => setWorkspaceName(e.target.value)}
                  />
                </label>
                <button className="primary" disabled={busy}>
                  Create workspace
                </button>
              </form>
              <div className="report-list">
                {workspaces.map((w) => (
                  <div key={w.id}>
                    <strong>{w.name}</strong>
                    <button
                      className="secondary"
                      onClick={() => {
                        setWorkspace(w.id);
                        setTab("Overview");
                      }}
                    >
                      Open workspace
                    </button>
                  </div>
                ))}
              </div>
            </section>
          )}
          <footer>
            EK-Logic <span>Turn Data Into Decisions.</span>
            <span>Phase 1 · Early release</span>
          </footer>
        </main>
      </div>
    </div>
  );
}
function Kpi({
  title,
  value,
  note,
  icon,
}: {
  title: string;
  value: string;
  note: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="kpi">
      <div>
        <span>{title}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <small>{note}</small>
    </div>
  );
}
function Empty({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty">
      <Database size={28} />
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
function DatasetList({
  datasets,
  onSelect,
}: {
  datasets: Dataset[];
  onSelect: (d: Dataset) => void;
}) {
  return (
    <section className="card">
      <div className="card-title">
        <div>
          <h2>Your datasets</h2>
          <p className="muted">A starting point for your next analysis.</p>
        </div>
        <span className="pill">{datasets.length} datasets</span>
      </div>
      {!datasets.length ? (
        <Empty
          title="Your workspace is ready"
          text="Upload a CSV or Excel file to see your data here."
        />
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Dataset</th>
                <th>Rows</th>
                <th>Columns</th>
                <th>Uploaded</th>
                <th>Explore</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((ds) => (
                <tr key={ds.id}>
                  <td>
                    <strong>{ds.name}</strong>
                  </td>
                  <td>{number(ds.profile.rows)}</td>
                  <td>{ds.profile.columns.length}</td>
                  <td>{new Date(ds.created * 1000).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="text-button"
                      onClick={() => onSelect(ds)}
                    >
                      Open analysis <ArrowUpRight size={15} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
