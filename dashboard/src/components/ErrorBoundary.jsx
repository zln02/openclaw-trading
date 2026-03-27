import React from "react";

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error("Dashboard error boundary caught an error", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="mx-auto flex min-h-screen max-w-3xl flex-col items-center justify-center gap-4 px-6 text-center">
          <h1 className="text-2xl font-semibold">문제가 발생했습니다. 페이지를 새로고침해주세요.</h1>
          <p className="max-w-2xl break-words text-sm opacity-80">
            {this.state.error?.message || "알 수 없는 오류"}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-full border border-white/20 px-5 py-2 text-sm"
          >
            새로고침
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
