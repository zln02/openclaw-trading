import { useEffect, useRef, memo } from "react";
import PropTypes from "prop-types";

/**
 * TradingView 위젯 범용 컴포넌트.
 *
 * widgetType: TradingView 스크립트명 접미사
 *   - "advanced-chart"        → Advanced Chart (풀 차트)
 *   - "market-overview"       → Market Overview (지수/종목 목록)
 *   - "mini-symbol-overview"  → Mini Chart (소형 심볼 차트)
 *   - "ticker-tape"           → Ticker Tape (상단 띠)
 *
 * config: TradingView 위젯 JSON 설정 객체 (autosize 자동 추가)
 * height: 컨테이너 높이(px), 기본 420
 */
const TvWidget = memo(function TvWidget({ widgetType, config, height = 420 }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    // 이전 인스턴스 제거
    container.innerHTML = "";

    // TradingView 위젯은 스크립트 innerHTML로 JSON config를 읽음
    const script = document.createElement("script");
    script.src = `https://s3.tradingview.com/external-embedding/embed-widget-${widgetType}.js`;
    script.async = true;
    script.innerHTML = JSON.stringify({ autosize: true, ...config });
    container.appendChild(script);

    // cleanup — 탭 이동 시 이전 위젯 제거
    return () => {
      if (container) container.innerHTML = "";
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Mount once: TradingView 위젯이 자체 생명주기를 관리

  return (
    <div
      ref={containerRef}
      className="tradingview-widget-container w-full overflow-hidden"
      style={{ height: `${height}px` }}
    />
  );
});

TvWidget.propTypes = {
  widgetType: PropTypes.string.isRequired,
  config: PropTypes.object.isRequired,
  height: PropTypes.number,
};

export default TvWidget;
