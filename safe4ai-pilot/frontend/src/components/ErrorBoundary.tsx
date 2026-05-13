import type { ErrorInfo, ReactNode } from "react";
import { Component } from "react";
import Button from "./Button";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error", error, info);
  }

  render() {
    if (!this.state.hasError) return this.props.children;

    return (
      <div className="flex min-h-screen items-center justify-center bg-paper px-4">
        <div className="max-w-sm rounded-2xl border border-line bg-surface p-6 text-center shadow-sm">
          <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-danger">Interface error</p>
          <h1 className="mt-3 font-serif text-[24px] tracking-tight text-ink">Something went wrong</h1>
          <p className="mt-2 text-[13px] leading-6 text-text-3">
            The workspace hit an unexpected UI error. Refreshing gives the app a clean state.
          </p>
          <Button className="mt-5" variant="primary" onClick={() => window.location.reload()}>
            Refresh workspace
          </Button>
        </div>
      </div>
    );
  }
}
