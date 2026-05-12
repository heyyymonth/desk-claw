import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "../../src/App";

const rules = {
  executive_name: "Executive",
  timezone: "America/Los_Angeles",
  working_hours: { start: "09:00", end: "17:00" },
  protected_blocks: [],
  preferences: ["Avoid protected blocks."]
};

const meetingRequest = {
  raw_text: "Important customer meeting from Alex for 30 minutes next week",
  intent: {
    title: "Customer meeting",
    requester: "Alex",
    duration_minutes: 30,
    priority: "high",
    attendees: [],
    preferred_windows: [],
    constraints: ["Requested for next week"],
    missing_fields: []
  }
};

const recommendation = {
  decision: "schedule",
  confidence: 0.84,
  rationale: ["Found a safe slot."],
  risks: [],
  proposed_slots: [{ start: "2026-05-11T11:00:00-07:00", end: "2026-05-11T11:30:00-07:00", reason: "Open" }],
  model_status: "not_configured"
};

const draft = {
  subject: "Re: Customer meeting",
  body: "Please confirm whether that works on your side.",
  tone: "warm",
  model_status: "not_configured"
};

const aiMetrics = {
  total_events: 2,
  success_rate: 1,
  adk_coverage: 1,
  tool_call_coverage: 1,
  avg_latency_ms: 25,
  p95_latency_ms: 30,
  model_status_counts: { used: 2 },
  operation_metrics: [
    {
      operation: "generate_recommendation",
      total: 2,
      success_rate: 1,
      adk_coverage: 1,
      avg_latency_ms: 25,
      tool_calls_avg: 4,
      model_status_counts: { used: 2 },
    },
  ],
  tool_metrics: [
    {
      tool_name: "inspect_calendar_conflicts",
      calls: 2,
      failure_count: 0,
      success_rate: 1,
      avg_latency_ms: 25,
      failure_reasons: {},
    },
  ],
  insights: [
    {
      severity: "info",
      title: "AI telemetry window is healthy",
      detail: "No unavailable models were detected.",
      reason: "healthy_window",
    },
  ],
  slowest_events: [],
  recent_failures: [],
};

describe("App", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith("/api/health")) return Promise.resolve(jsonResponse({ status: "ok", model_status: "not_configured" }));
      if (url.endsWith("/api/rules/default")) return Promise.resolve(jsonResponse(rules));
      if (url.endsWith("/api/calendar/mock")) return Promise.resolve(jsonResponse({ blocks: [] }));
      if (url.endsWith("/api/requests/parse")) return Promise.resolve(jsonResponse(meetingRequest));
      if (url.endsWith("/api/recommendations/generate")) return Promise.resolve(jsonResponse(recommendation));
      if (url.endsWith("/api/drafts/generate")) return Promise.resolve(jsonResponse(draft));
      if (url.endsWith("/api/telemetry/ai/dashboard")) return Promise.resolve(jsonResponse(aiMetrics));
      if (url.endsWith("/api/decisions") && init?.method === "POST") {
        return Promise.resolve(jsonResponse({ id: "1", created_at: "2026-05-09T00:00:00Z", meeting_request: meetingRequest, recommendation, final_decision: "accepted", notes: "" }));
      }
      if (url.endsWith("/api/decisions")) return Promise.resolve(jsonResponse([]));
      return Promise.reject(new Error(`Unhandled ${url} ${init?.method}`));
    }));
  });

  it("runs the scheduling workflow and logs a decision", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    );

    await userEvent.click(screen.getAllByRole("button", { name: /admin center/i })[0]);
    await screen.findByText("Avoid protected blocks.");
    await userEvent.type(screen.getByLabelText("Meeting request"), meetingRequest.raw_text);
    await userEvent.click(screen.getByRole("button", { name: /parse request/i }));
    await screen.findByText("Customer meeting");

    await userEvent.click(screen.getByRole("button", { name: /generate recommendation/i }));
    await screen.findByText("Found a safe slot.");

    expect(screen.getByText("schedule")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /generate draft/i }));
    expect(screen.getByText("Please confirm whether that works on your side.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(screen.getAllByText("Customer meeting").length).toBeGreaterThan(1));
  });

  it("renders the separate DB-backed AI telemetry dashboard page", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <App />
      </QueryClientProvider>,
    );

    await userEvent.click(screen.getAllByRole("button", { name: "AI Dashboard" })[0]);

    await screen.findByText("AI Technical Dashboard");
    expect(screen.getByText("DB telemetry")).toBeInTheDocument();
    expect(screen.getByText("inspect calendar conflicts")).toBeInTheDocument();
    expect(screen.getByText("AI telemetry window is healthy")).toBeInTheDocument();
  });
});

function jsonResponse(payload: unknown) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve(payload)
  } as Response;
}
