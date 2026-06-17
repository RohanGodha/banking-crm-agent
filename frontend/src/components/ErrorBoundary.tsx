import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';

interface Props {
  children: ReactNode;
  label?: string;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error boundary caught:', error, info);
  }

  reset = () => this.setState({ error: null });

  render() {
    if (this.state.error) {
      return (
        <div className="h-full flex items-center justify-center p-6">
          <div className="card max-w-md w-full p-5 space-y-3">
            <div className="flex items-center gap-2 text-danger">
              <AlertTriangle size={16} />
              <span className="text-sm font-semibold">
                Something went wrong{this.props.label ? ` in ${this.props.label}` : ''}
              </span>
            </div>
            <p className="text-xs text-text-muted break-words font-mono">
              {this.state.error.message}
            </p>
            <button onClick={this.reset} className="btn-outline text-xs">
              Try again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
