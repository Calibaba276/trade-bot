import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  ColorType,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type Time,
} from "lightweight-charts";
import { useReplayStore } from "../../store/replayStore";

interface Props {
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export function TradeReplayChart({ containerRef }: Props) {
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  const { selectedTimeframe, currentTime, priceData } = useReplayStore();

  // Initialise chart once
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart = createChart(el, {
      layout: {
        background: { type: ColorType.Solid, color: "#0f1419" },
        textColor: "#9ca3af",
      },
      grid: {
        vertLines: { color: "#1e2530" },
        horzLines: { color: "#1e2530" },
      },
      crosshair: {
        vertLine: { color: "#2a3040", labelBackgroundColor: "#1e2530" },
        horzLine: { color: "#2a3040", labelBackgroundColor: "#1e2530" },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "#1e2530",
      },
      rightPriceScale: { borderColor: "#1e2530" },
      width: el.clientWidth,
      height: el.clientHeight,
    });

    // v5 API: addSeries(SeriesType, options)
    const series = chart.addSeries(CandlestickSeries, {
      upColor: "#34d399",
      downColor: "#f87171",
      borderUpColor: "#34d399",
      borderDownColor: "#f87171",
      wickUpColor: "#34d399",
      wickDownColor: "#f87171",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (el) chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
    });
    ro.observe(el);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [containerRef]);

  // Update candles whenever currentTime or timeframe changes
  useEffect(() => {
    const series = seriesRef.current;
    if (!series) return;

    const candles = (priceData[selectedTimeframe] ?? [])
      .filter((c) => c.time <= currentTime)
      .map(
        (c): CandlestickData => ({
          time: Math.floor(c.time / 1000) as Time,
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        })
      );

    series.setData(candles);
    if (candles.length > 0) chartRef.current?.timeScale().fitContent();
  }, [currentTime, selectedTimeframe, priceData]);

  return null;
}
