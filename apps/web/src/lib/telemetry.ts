function createTraceId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `trace-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function getRequestTraceId(): string {
  return createTraceId();
}

export function initTelemetry(): void {
  // Telemetry is currently disabled to keep the frontend startup path stable.
}

export function trackApiError(_message: string, _properties?: Record<string, string>): void {
  // No-op while telemetry is disabled.
}
