import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="error-state" style={{ flexDirection: "column", gap: 12, padding: 32 }}>
          <div style={{ fontSize: 16, fontWeight: 700 }}>페이지 로드 실패</div>
          <div className="subtle" style={{ fontSize: 13, maxWidth: 400, textAlign: "center" }}>
            {this.state.error?.message || "알 수 없는 오류가 발생했습니다."}
          </div>
          <button
            onClick={this.handleRetry}
            style={{
              marginTop: 8,
              padding: "8px 20px",
              borderRadius: 8,
              border: "1px solid rgba(255,255,255,0.15)",
              background: "rgba(255,255,255,0.06)",
              color: "var(--text-primary)",
              cursor: "pointer",
              fontWeight: 600,
              fontSize: 13,
            }}
          >
            다시 시도
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
