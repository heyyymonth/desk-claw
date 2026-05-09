import { Server } from 'lucide-react';
import type { HealthStatus } from '../types';

export function StatusIndicator({
  health,
  isLoading,
  error,
}: {
  health?: HealthStatus;
  isLoading: boolean;
  error: unknown;
}) {
  const modelState = health?.model_status ?? health?.ollama ?? 'unknown';
  const isHealthy = !error && !isLoading;

  return (
    <div className="flex items-center gap-2 rounded-md border border-line bg-white px-3 py-2 text-sm">
      <Server size={16} aria-hidden="true" />
      <span className={isHealthy ? 'font-semibold text-greenRisk' : 'font-semibold text-amberRisk'}>
        Backend {isLoading ? 'checking' : error ? 'unavailable' : 'online'}
      </span>
      <span className="text-steel">Ollama: {String(modelState)}</span>
    </div>
  );
}
