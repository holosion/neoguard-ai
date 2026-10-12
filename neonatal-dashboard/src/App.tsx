import { lazy, Suspense, useState } from "react"
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  ArrowLeft,
  Baby,
  Check,
  ChevronRight,
  CircleAlert,
  Cloud,
  Database,
  HeartPulse,
  Info,
  LoaderCircle,
  Menu,
  Moon,
  Router,
  ShieldAlert,
  Sun,
  Thermometer,
  TrendingDown,
  Wifi,
  WifiOff,
  X,
} from "lucide-react"

const VitalChart = lazy(() => import("./VitalChart"))

type Screen = "ward" | "patient" | "alerts" | "devices"
type WardState = "live" | "loading" | "empty"
type Severity = "urgent" | "watch" | "normal"

const patients = [
  {
    id: "NEO-042",
    hr: 175,
    spo2: 89,
    temp: 35.4,
    trend: "Falling",
    risk: 84,
    state: "urgent" as Severity,
    updated: "8 sec ago",
  },
  {
    id: "NEO-019",
    hr: 148,
    spo2: 93,
    temp: 36.1,
    trend: "Drift down",
    risk: 58,
    state: "watch" as Severity,
    updated: "12 sec ago",
  },
  {
    id: "NEO-033",
    hr: 132,
    spo2: 97,
    temp: 36.8,
    trend: "Stable",
    risk: 12,
    state: "normal" as Severity,
    updated: "4 sec ago",
  },
]

const initialAlerts = [
  {
    id: 1,
    patient: "NEO-042",
    type: "local_threshold",
    detail: "SpO₂ below 90%",
    severity: "urgent" as Severity,
    time: "Today, 14:31",
    ack: false,
  },
  {
    id: 2,
    patient: "NEO-042",
    type: "ai_composite",
    detail: "Composite risk crossed 80%",
    severity: "urgent" as Severity,
    time: "Today, 14:29",
    ack: false,
  },
  {
    id: 3,
    patient: "NEO-019",
    type: "ai_trend",
    detail: "Temperature drifting downward",
    severity: "watch" as Severity,
    time: "Today, 14:18",
    ack: true,
  },
  {
    id: 4,
    patient: "NEO-033",
    type: "local_threshold",
    detail: "Transient tachycardia",
    severity: "watch" as Severity,
    time: "Today, 13:42",
    ack: true,
  },
]

const devices = [
  {
    id: "ESP32-A4",
    patient: "NEO-042",
    online: false,
    last: "14:28",
    buffered: 36,
    signal: "—",
  },
  {
    id: "ESP32-B7",
    patient: "NEO-019",
    online: true,
    last: "12 sec ago",
    buffered: 0,
    signal: "Good",
  },
  {
    id: "ESP32-C2",
    patient: "NEO-033",
    online: true,
    last: "4 sec ago",
    buffered: 0,
    signal: "Strong",
  },
  {
    id: "ESP32-D1",
    patient: "Unassigned",
    online: true,
    last: "6 sec ago",
    buffered: 0,
    signal: "Good",
  },
]

const transitions = [
  {
    device: "ESP32-A4",
    state: "Offline",
    time: "Today, 14:28",
    note: "WiFi connection lost",
  },
  {
    device: "ESP32-A4",
    state: "Online",
    time: "Today, 14:12",
    note: "144 buffered readings synced",
  },
  {
    device: "ESP32-B7",
    state: "Online",
    time: "Today, 13:56",
    note: "Connection restored",
  },
]

function IconButton({
  label,
  children,
  onClick,
}: {
  label: string
  children: React.ReactNode
  onClick?: () => void
}) {
  return (
    <button className="icon-button" aria-label={label} onClick={onClick}>
      {children}
    </button>
  )
}

function SeverityBadge({
  severity,
  risk,
}: {
  severity: Severity
  risk?: number
}) {
  const Icon =
    severity === "urgent"
      ? CircleAlert
      : severity === "watch"
        ? AlertTriangle
        : Check
  return (
    <span className={`severity-badge ${severity}`}>
      <Icon size={15} strokeWidth={2.5} />
      <span>{severity.toUpperCase()}</span>
      {risk !== undefined && <strong>{risk}%</strong>}
    </span>
  )
}

function Sidebar({
  screen,
  onNavigate,
  open,
  onClose,
}: {
  screen: Screen
  onNavigate: (s: Screen) => void
  open: boolean
  onClose: () => void
}) {
  const links: { id: Screen label: string icon: React.ReactNode }[] = [
    { id: "ward", label: "Ward overview", icon: <Activity size={19} /> },
    { id: "alerts", label: "Alerts log", icon: <ShieldAlert size={19} /> },
    { id: "devices", label: "Devices", icon: <Router size={19} /> },
  ]
  return (
    <>
      {open && (
        <button
          className="mobile-scrim"
          aria-label="Close navigation"
          onClick={onClose}
        />
      )}
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <HeartPulse size={22} />
          </div>
          <div>
            <strong>NeoWatch</strong>
            <span>Ward monitor</span>
          </div>
          <IconButton label="Close navigation" onClick={onClose}>
            <X size={20} />
          </IconButton>
        </div>
        <nav aria-label="Primary navigation">
          {links.map((link) => (
            <button
              key={link.id}
              className={
                screen === link.id ||
                (screen === "patient" && link.id === "ward")
                  ? "active"
                  : ""
              }
              onClick={() => {
                onNavigate(link.id)
                onClose()
              }}
            >
              {link.icon}
              <span>{link.label}</span>
              {link.id === "alerts" && <em>2</em>}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <Info size={18} />
          <p>
            <strong>Decision support</strong>
            <span>Bedside devices continue local alarms independently.</span>
          </p>
        </div>
        <div className="facility">
          <div className="facility-icon">HC</div>
          <p>
            <strong>Kisoro Health Centre IV</strong>
            <span>Neonatal ward</span>
          </p>
        </div>
      </aside>
    </>
  )
}

function Header({
  title,
  subtitle,
  theme,
  setTheme,
  onMenu,
}: {
  title: string
  subtitle: string
  theme: string
  setTheme: (t: string) => void
  onMenu: () => void
}) {
  return (
    <header className="page-header">
      <div className="title-wrap">
        <IconButton label="Open navigation" onClick={onMenu}>
          <Menu size={21} />
        </IconButton>
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
      </div>
      <div className="header-actions">
        <div className="sync-pill">
          <Wifi size={16} />
          <span>
            <strong>Connected</strong> · polling every 5s
          </span>
        </div>
        <span className="last-sync">
          Last sync <strong>14:32:08</strong>
        </span>
        <IconButton
          label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
          onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
        >
          {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
        </IconButton>
      </div>
    </header>
  )
}

function WardOverview({ onPatient }: { onPatient: () => void }) {
  const [wardState, setWardState] = useState<WardState>("live")
  return (
    <div className="page-content">
      <section className="metrics-grid" aria-label="Ward status">
        <div className="metric-card">
          <div className="metric-icon blue">
            <Baby size={20} />
          </div>
          <p>
            <span>Active sessions</span>
            <strong>3</strong>
            <small>of 8 cots occupied</small>
          </p>
        </div>
        <div className="metric-card critical">
          <div className="metric-icon red">
            <ShieldAlert size={20} />
          </div>
          <p>
            <span>Critical alerts</span>
            <strong>2</strong>
            <small>1 patient needs attention</small>
          </p>
        </div>
        <div className="metric-card">
          <div className="metric-icon green">
            <Cloud size={20} />
          </div>
          <p>
            <span>Sync status</span>
            <strong className="word">Online</strong>
            <small>Backend responding normally</small>
          </p>
        </div>
      </section>

      <section className="panel patient-panel">
        <div className="panel-heading">
          <div>
            <h2>Active patients</h2>
            <p>Automatically prioritised by composite risk score</p>
          </div>
          <div className="view-state" aria-label="Preview ward states">
            {(["live", "loading", "empty"] as WardState[]).map((state) => (
              <button
                key={state}
                className={wardState === state ? "active" : ""}
                onClick={() => setWardState(state)}
              >
                {state === "live" ? "Live" : state}
              </button>
            ))}
          </div>
        </div>

        {wardState === "loading" && (
          <div className="state-card">
            <LoaderCircle className="spin" size={28} />
            <h3>Updating ward data</h3>
            <p>Checking active sessions and recent readings…</p>
          </div>
        )}
        {wardState === "empty" && (
          <div className="state-card">
            <Baby size={30} />
            <h3>No active sessions</h3>
            <p>Connect and assign a bedside device to begin monitoring.</p>
            <button
              className="primary-button"
              onClick={() => setWardState("live")}
            >
              View sample sessions
            </button>
          </div>
        )}
        {wardState === "live" && (
          <div className="patient-table-wrap">
            <table className="patient-table">
              <thead>
                <tr>
                  <th>Priority / patient</th>
                  <th>
                    HR <span>bpm</span>
                  </th>
                  <th>
                    SpO₂ <span>%</span>
                  </th>
                  <th>
                    Temp <span>°C</span>
                  </th>
                  <th>Trend</th>
                  <th>Triage state</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {patients.map((patient, index) => (
                  <tr
                    key={patient.id}
                    className={patient.state === "urgent" ? "critical-row" : ""}
                    tabIndex={0}
                    onClick={onPatient}
                    onKeyDown={(e) => e.key === "Enter" && onPatient()}
                  >
                    <td>
                      <div className={`priority-number ${patient.state}`}>
                        {index + 1}
                      </div>
                      <div>
                        <strong>{patient.id}</strong>
                        <small>Updated {patient.updated}</small>
                      </div>
                    </td>
                    <td className="vital">
                      {patient.hr}
                      <small>{patient.hr > 160 ? "High" : "In range"}</small>
                    </td>
                    <td
                      className={`vital ${
                        patient.spo2 < 90
                          ? "danger-text"
                          : patient.spo2 < 95
                            ? "warn-text"
                            : ""
                      }`}
                    >
                      {patient.spo2}
                      <small>
                        {patient.spo2 < 90
                          ? "Below limit"
                          : patient.spo2 < 95
                            ? "Low"
                            : "In range"}
                      </small>
                    </td>
                    <td
                      className={`vital ${
                        patient.temp < 35.5
                          ? "danger-text"
                          : patient.temp < 36.5
                            ? "warn-text"
                            : ""
                      }`}
                    >
                      {patient.temp}
                      <small>
                        {patient.temp < 35.5
                          ? "Critical low"
                          : patient.temp < 36.5
                            ? "Below range"
                            : "In range"}
                      </small>
                    </td>
                    <td>
                      <span
                        className={`trend ${
                          patient.trend === "Stable" ? "stable" : ""
                        }`}
                      >
                        {patient.trend === "Stable" ? (
                          <Activity size={17} />
                        ) : (
                          <TrendingDown size={17} />
                        )}
                        {patient.trend}
                      </span>
                    </td>
                    <td>
                      <SeverityBadge
                        severity={patient.state}
                        risk={patient.risk}
                      />
                    </td>
                    <td>
                      <ChevronRight size={20} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="table-note">
          <Info size={15} /> Risk ranking is decision support only. Always
          respond to bedside alarms and clinical judgement.
        </div>
      </section>
    </div>
  )
}

function PatientDetail({ onBack }: { onBack: () => void }) {
  return (
    <div className="page-content detail-page">
      <button className="back-button" onClick={onBack}>
        <ArrowLeft size={17} /> Back to ward overview
      </button>
      <div className="patient-hero">
        <div>
          <div className="eyebrow">PATIENT SESSION</div>
          <h2>NEO-042</h2>
          <p>Cot 04 · Device ESP32-A4 · Started today at 11:47</p>
        </div>
        <SeverityBadge severity="urgent" risk={84} />
      </div>
      <div className="offline-banner">
        <WifiOff size={23} />
        <div>
          <strong>Device offline. Bedside alarm still active.</strong>
          <span>
            Showing last known data from 14:28. Readings will sync automatically
            when connectivity returns.
          </span>
        </div>
      </div>

      <div className="detail-layout">
        <div className="charts-column">
          <Suspense
            fallback={
              <div className="chart-card chart-loading">
                <LoaderCircle className="spin" size={25} />
                <span>Loading trend charts…</span>
              </div>
            }
          >
            <VitalChart
              title="Skin temperature"
              value="35.4"
              unit="°C"
              color="#4fa9ff"
              values={[36.1, 36.0, 35.9, 35.7, 35.6, 35.4]}
              min={35}
              max={37.5}
              bands={[
                { from: 35, to: 35.5, color: "rgba(255,82,102,.12)" },
                { from: 36, to: 36.4, color: "rgba(245,177,67,.10)" },
              ]}
            />
            <VitalChart
              title="Oxygen saturation"
              value="89"
              unit="%"
              color="#9d7cff"
              values={[94, 93, 94, 92, 91, 89]}
              min={85}
              max={100}
              bands={[{ from: 85, to: 90, color: "rgba(255,82,102,.12)" }]}
            />
            <VitalChart
              title="Heart rate"
              value="175"
              unit="bpm"
              color="#ff7184"
              values={[148, 152, 155, 161, 168, 175]}
              min={110}
              max={190}
              bands={[{ from: 170, to: 190, color: "rgba(255,82,102,.10)" }]}
            />
          </Suspense>
        </div>
        <aside className="detail-sidebar">
          <section className="risk-card">
            <div className="risk-heading">
              <div>
                <span>Why this risk score</span>
                <h3>ELEVATED</h3>
              </div>
              <strong>78%</strong>
            </div>
            <p className="risk-intro">
              The model found three factors increasing this session’s predicted
              risk.
            </p>
            <div className="factor">
              <span>
                <Thermometer size={17} />
                Downward temperature trend
              </span>
              <p>
                −0.4°C over 15 min <strong>+2.14</strong>
              </p>
            </div>
            <div className="factor">
              <span>
                <ArrowDown size={17} />
                Low oxygen saturation
              </span>
              <p>
                SpO₂ 91% <strong>+1.65</strong>
              </p>
            </div>
            <div className="factor">
              <span>
                <HeartPulse size={17} />
                Tachycardia trend
              </span>
              <p>
                Heart rate increasing <strong>+1.12</strong>
              </p>
            </div>
            <div className="suggested-action">
              <AlertTriangle size={20} />
              <p>
                <span>Suggested action</span>
                <strong>
                  Priority bedside inspection and thermal intervention advised.
                </strong>
              </p>
            </div>
            <div className="decision-note">
              <Info size={15} /> Decision support only, not a diagnosis.
            </div>
          </section>
          <section className="info-card">
            <div className="card-heading">
              <h3>Session information</h3>
              <Database size={18} />
            </div>
            <dl>
              <div>
                <dt>Device ID</dt>
                <dd>ESP32-A4</dd>
              </div>
              <div>
                <dt>Session started</dt>
                <dd>Today, 11:47</dd>
              </div>
              <div>
                <dt>Last sync</dt>
                <dd>12 seconds ago</dd>
              </div>
              <div>
                <dt>Recovered</dt>
                <dd>144 buffered readings</dd>
              </div>
            </dl>
          </section>
          <section className="info-card">
            <div className="card-heading">
              <h3>Clinical risk context</h3>
              <span>Clinician entered</span>
            </div>
            <dl>
              <div>
                <dt>Birth weight</dt>
                <dd>2.1 kg</dd>
              </div>
              <div>
                <dt>Place of birth</dt>
                <dd>Health facility</dd>
              </div>
              <div>
                <dt>Delayed breastfeeding</dt>
                <dd>Yes · 4 hours</dd>
              </div>
            </dl>
            <button className="secondary-button">Edit clinical context</button>
          </section>
        </aside>
      </div>
    </div>
  )
}

function AlertsLog() {
  const [alerts, setAlerts] = useState(initialAlerts)
  return (
    <div className="page-content">
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Alert history</h2>
            <p>Local device and decision-support events from active sessions</p>
          </div>
          <span className="outline-badge">2 unacknowledged</span>
        </div>
        <div className="data-table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Patient</th>
                <th>Alert type</th>
                <th>Details</th>
                <th>Severity</th>
                <th>Timestamp</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map((alert) => (
                <tr key={alert.id}>
                  <td>
                    <strong>{alert.patient}</strong>
                  </td>
                  <td>
                    <code>{alert.type}</code>
                  </td>
                  <td>{alert.detail}</td>
                  <td>
                    <SeverityBadge severity={alert.severity} />
                  </td>
                  <td>{alert.time}</td>
                  <td>
                    {alert.ack ? (
                      <span className="acknowledged">
                        <Check size={15} /> Acknowledged
                      </span>
                    ) : (
                      <button
                        className="ack-button"
                        onClick={() =>
                          setAlerts((items) =>
                            items.map((item) =>
                              item.id === alert.id
                                ? { ...item, ack: true }
                                : item,
                            ),
                          )
                        }
                      >
                        Acknowledge
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

function DevicesView() {
  return (
    <div className="page-content">
      <section className="metrics-grid device-metrics">
        <div className="metric-card">
          <div className="metric-icon green">
            <Wifi size={20} />
          </div>
          <p>
            <span>Online devices</span>
            <strong>3</strong>
            <small>of 4 registered</small>
          </p>
        </div>
        <div className="metric-card">
          <div className="metric-icon red">
            <WifiOff size={20} />
          </div>
          <p>
            <span>Offline devices</span>
            <strong>1</strong>
            <small>Bedside alarm remains active</small>
          </p>
        </div>
        <div className="metric-card">
          <div className="metric-icon amber">
            <Database size={20} />
          </div>
          <p>
            <span>Waiting to sync</span>
            <strong>36</strong>
            <small>buffered readings</small>
          </p>
        </div>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>Bedside devices</h2>
            <p>Connectivity status and local reading buffers</p>
          </div>
        </div>
        <div className="device-grid">
          {devices.map((device) => (
            <article
              className={`device-card ${device.online ? "" : "offline"}`}
              key={device.id}
            >
              <div className="device-top">
                <div
                  className={`device-icon ${
                    device.online ? "online" : "offline"
                  }`}
                >
                  <Router size={21} />
                </div>
                <span
                  className={`connection ${
                    device.online ? "online" : "offline"
                  }`}
                >
                  {device.online ? <Wifi size={14} /> : <WifiOff size={14} />}
                  {device.online ? "ONLINE" : "OFFLINE"}
                </span>
              </div>
              <h3>{device.id}</h3>
              <p>
                Assigned to <strong>{device.patient}</strong>
              </p>
              <dl>
                <div>
                  <dt>Last seen online</dt>
                  <dd>{device.last}</dd>
                </div>
                <div>
                  <dt>WiFi signal</dt>
                  <dd>{device.signal}</dd>
                </div>
                <div>
                  <dt>Buffered readings</dt>
                  <dd className={device.buffered ? "warn-text" : ""}>
                    {device.buffered}
                  </dd>
                </div>
              </dl>
              {!device.online && (
                <div className="local-alarm-note">
                  <ShieldAlert size={16} /> Local alarm is still active
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
      <section className="panel transition-panel">
        <div className="panel-heading">
          <div>
            <h2>Connectivity transition log</h2>
            <p>Latest online and offline events</p>
          </div>
        </div>
        <div className="timeline">
          {transitions.map((item, i) => (
            <div className="timeline-item" key={`${item.device}-${item.time}`}>
              <div className={`timeline-dot ${item.state.toLowerCase()}`}>
                {item.state === "Online" ? (
                  <Wifi size={14} />
                ) : (
                  <WifiOff size={14} />
                )}
              </div>
              <div>
                <strong>
                  {item.device} went {item.state.toLowerCase()}
                </strong>
                <span>{item.note}</span>
              </div>
              <time>{item.time}</time>
              {i < transitions.length - 1 && <i />}
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("ward")
  const [theme, setTheme] = useState("dark")
  const [menuOpen, setMenuOpen] = useState(false)
  const titles: Record<Screen, [string, string]> = {
    ward: ["Ward overview", "Prioritised neonatal monitoring"],
    patient: ["Patient detail", "NEO-042 · Live session"],
    alerts: ["Alerts log", "Review and acknowledge ward events"],
    devices: ["Devices & connectivity", "Bedside monitor status"],
  }
  return (
    <div className="app-shell" data-theme={theme}>
      <Sidebar
        screen={screen}
        onNavigate={setScreen}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
      />
      <main className="main-area">
        <Header
          title={titles[screen][0]}
          subtitle={titles[screen][1]}
          theme={theme}
          setTheme={setTheme}
          onMenu={() => setMenuOpen(true)}
        />
        {screen === "ward" && (
          <WardOverview onPatient={() => setScreen("patient")} />
        )}
        {screen === "patient" && (
          <PatientDetail onBack={() => setScreen("ward")} />
        )}
        {screen === "alerts" && <AlertsLog />}
        {screen === "devices" && <DevicesView />}
      </main>
    </div>
  )
}
