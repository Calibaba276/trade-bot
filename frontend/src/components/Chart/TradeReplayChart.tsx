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
import { renderPatterns } from "../../utils/patternRenderer";

interface Props {
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export function TradeReplayChart({ containerRef }: Props) {
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawRef = useRef<(() => void) | null>(null);

  const { selectedTimeframe, currentTime, priceData, events } = useReplayStore();

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

    // Reads store directly so scroll/zoom handler never holds stale data
    const draw = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const { events: ev, currentTime: ct, selectedTimeframe: tf } =
        useReplayStore.getState();
      renderPatterns(canvas, chart, series, ev, ct, tf);
    };
    drawRef.current = draw;

    const syncCanvas = () => {
      const canvas = canvasRef.current;
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = el.clientWidth * dpr;
      canvas.height = el.clientHeight * dpr;
    };

    const ro = new ResizeObserver(() => {
      if (!el) return;
      chart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
      syncCanvas();
      draw();
    });
    ro.observe(el);

    // Sync canvas on initial mount
    syncCanvas();

    // Redraw overlays when the user scrolls or zooms the chart
    const scrollHandler = () => draw();
    chart.timeScale().subscribeVisibleTimeRangeChange(scrollHandler);

    return () => {
      ro.disconnect();
      chart.timeScale().unsubscribeVisibleTimeRangeChange(scrollHandler);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      drawRef.current = null;
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
        }),
      );

    series.setData(candles);
    if (candles.length > 0) chartRef.current?.timeScale().fitContent();

    // Redraw overlays after candle data changes
    drawRef.current?.();
  }, [currentTime, selectedTimeframe, priceData]);

  // Redraw overlays when event list changes (new live events arriving)
  useEffect(() => {
    drawRef.current?.();
  }, [events]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    />
  );
}
