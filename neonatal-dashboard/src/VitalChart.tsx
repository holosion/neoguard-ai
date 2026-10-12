import { useMemo } from "react"
import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  type ChartOptions,
  type Plugin,
} from "chart.js"
import { Line } from "react-chartjs-2"

ChartJS.register(
  CategoryScale,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
  Legend,
  Filler,
)

const labels = ["14:15", "14:18", "14:21", "14:24", "14:27", "14:30"]

const bandPlugin: Plugin<"line"> = {
  id: "clinicalBands",
  beforeDraw(chart, _args, options) {
    const { ctx, chartArea, scales } = chart
    if (!chartArea || !scales.y) return
    const bands =
      (options as {
        bands?: { from: number to: number color: string }[]
      }).bands ?? []

    ctx.save()
    bands.forEach(({ from, to, color }) => {
      const y1 = scales.y.getPixelForValue(to)
      const y2 = scales.y.getPixelForValue(from)
      ctx.fillStyle = color
      ctx.fillRect(
        chartArea.left,
        y1,
        chartArea.right - chartArea.left,
        y2 - y1,
      )
    })
    ctx.restore()
  },
}

ChartJS.register(bandPlugin)

type VitalChartProps = {
  title: string
  value: string
  unit: string
  color: string
  values: number[]
  min: number
  max: number
  bands: { from: number to: number color: string }[]
}

export default function VitalChart({
  title,
  value,
  unit,
  color,
  values,
  min,
  max,
  bands,
}: VitalChartProps) {
  const options = useMemo<ChartOptions<"line">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      interaction: { intersect: false, mode: "index" },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#101923",
          titleColor: "#fff",
          bodyColor: "#fff",
          padding: 10,
          cornerRadius: 8,
        },
        clinicalBands: { bands },
      } as ChartOptions<"line">["plugins"],
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: "#8290a3", maxRotation: 0, font: { size: 10 } },
          border: { display: false },
        },
        y: {
          min,
          max,
          grid: { color: "rgba(130,144,163,.13)" },
          ticks: { color: "#8290a3", font: { size: 10 }, maxTicksLimit: 5 },
          border: { display: false },
        },
      },
    }),
    [bands, max, min],
  )
  const data = {
    labels,
    datasets: [
      {
        data: values,
        borderColor: color,
        backgroundColor: color,
        borderWidth: 2.5,
        pointRadius: values.map((reading) =>
          reading <= min + (max - min) * 0.2 ? 4 : 0,
        ),
        pointBackgroundColor: "#ff6678",
        pointBorderColor: "#fff",
        pointBorderWidth: 2,
        tension: 0.32,
        fill: false,
      },
    ],
  }

  return (
    <div className="chart-card">
      <div className="chart-title">
        <div>
          <h3>{title}</h3>
          <p>Last 15 minutes</p>
        </div>
        <div className="chart-value">
          {value}
          <span>{unit}</span>
        </div>
      </div>
      <div className="chart-canvas">
        <Line options={options} data={data} />
      </div>
      <div className="chart-legend">
        <span>
          <i className="legend-line" style={{ background: color }} />
          Reading
        </span>
        <span>
          <i className="legend-band" />
          Threshold band
        </span>
        <span>
          <i className="legend-breach" />
          Breach
        </span>
      </div>
    </div>
  )
}
