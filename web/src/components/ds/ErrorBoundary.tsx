import { Component, type ErrorInfo, type ReactNode } from "react";
import { ErrorState } from "./ErrorState";

interface Props {
  children: ReactNode;
  /** Custom fallback — overrides the default ErrorState rendering. */
  fallback?: ReactNode;
}

interface State {
  error: Error | null;
}

/**
 * Class-based error boundary that catches render errors in its subtree
 * and displays the ds `ErrorState` with a "Reload" action.
 *
 * Mount once around the route area in App.tsx:
 *   <ErrorBoundary><Suspense ...><Routes /></Suspense></ErrorBoundary>
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary] Caught render error:", error, info.componentStack);
  }

  private handleRetry = () => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="flex min-h-[40vh] items-center justify-center p-6">
          <ErrorState
            title="Something went wrong"
            error={this.state.error}
            onRetry={this.handleRetry}
            retryLabel="Try again"
          />
        </div>
      );
    }
    return this.props.children;
  }
}
