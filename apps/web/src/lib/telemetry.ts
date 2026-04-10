import { ApplicationInsights } from "@microsoft/applicationinsights-web";

let appInsightsInstance: ApplicationInsights | null = null;

function createTraceId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `trace-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export function getRequestTraceId(): string {
  return createTraceId();
}

export function initTelemetry(): ApplicationInsights | null {
  if (appInsightsInstance !== null) {
    return appInsightsInstance;
  }

  const connectionString = import.meta.env.VITE_APPINSIGHTS_CONNECTION_STRING?.trim();
  if (!connectionString) {
    appInsightsInstance = null;
    return appInsightsInstance;
  }

  appInsightsInstance = new ApplicationInsights({
    config: {
      connectionString,
      enableAutoRouteTracking: true,
      disableFetchTracking: false,
      distributedTracingMode: 1,
    },
  });
  appInsightsInstance.loadAppInsights();
  appInsightsInstance.trackPageView();
  return appInsightsInstance;
}

export function trackApiError(message: string, properties?: Record<string, string>) {
  appInsightsInstance?.trackException({
    exception: new Error(message),
    properties,
  });
}
