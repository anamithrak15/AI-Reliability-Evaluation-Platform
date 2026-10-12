import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import * as runsApi from "../api/runs";
import { makeResult, RUN_ID } from "../test/fixtures";
import type { CaseDetail } from "../types/run";
import CaseInspectionPage from "./CaseInspectionPage";

vi.mock("../api/runs");

function detail(over: Partial<CaseDetail> = {}): CaseDetail {
  return {
    case_key: "billing-001",
    input: { messages: [{ role: "user", content: "I was charged twice." }] },
    expected_output: { category: "billing" },
    evaluation_config: { type: "classification" },
    tags: ["billing"],
    results: [makeResult({ model_alias: "accurate-model" })],
    ...over,
  };
}

const renderPage = () => render(<CaseInspectionPage runId={RUN_ID} caseKey="billing-001" />);

beforeEach(() => {
  vi.mocked(runsApi.getCaseDetail).mockResolvedValue(detail());
});

describe("CaseInspectionPage", () => {
  it("fetches the right case and shows prompt, expectation and output", async () => {
    renderPage();
    expect(await screen.findByText("I was charged twice.")).toBeInTheDocument();
    expect(runsApi.getCaseDetail).toHaveBeenCalledWith(RUN_ID, "billing-001");
    expect(screen.getByText("classification")).toBeInTheDocument();
    // Once for the expectation and once for the model output.
    expect(screen.getAllByText(/"category": "billing"/, { selector: "pre" })).toHaveLength(2);
    expect(screen.getByText("pass")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Run 11111111/ })).toHaveAttribute("href", `#/runs/${RUN_ID}`);
  });

  it("shows loading first", () => {
    vi.mocked(runsApi.getCaseDetail).mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole("status")).toHaveTextContent("Loading case");
  });

  it("marks partial failures without hiding the successful model", async () => {
    vi.mocked(runsApi.getCaseDetail).mockResolvedValue(
      detail({
        results: [
          makeResult({ model_alias: "accurate-model" }),
          makeResult({
            model_alias: "flaky-model", status: "timeout", output: null, metrics: {},
            error_code: "timeout", error_message_redacted: "model timed out",
          }),
        ],
      }),
    );
    renderPage();
    expect(await screen.findByText(/1 of 2 model results did not succeed/)).toBeInTheDocument();
    expect(screen.getByText(/timeout: model timed out/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /accurate-model/ })).toBeInTheDocument();
  });

  it("says so when an unscored result has no quality", async () => {
    vi.mocked(runsApi.getCaseDetail).mockResolvedValue(detail({ results: [makeResult({ metrics: {} })] }));
    renderPage();
    expect(await screen.findByText("not scored")).toBeInTheDocument();
  });

  it("explains an empty result list for a run in progress", async () => {
    vi.mocked(runsApi.getCaseDetail).mockResolvedValue(detail({ results: [], expected_output: null }));
    renderPage();
    expect(await screen.findByText(/No results yet/)).toBeInTheDocument();
    expect(screen.getByText("No expected output")).toBeInTheDocument();
  });

  it("shows a not-found error with retry", async () => {
    vi.mocked(runsApi.getCaseDetail)
      .mockRejectedValueOnce(new ApiError(404, "case_not_found", "Case not found in this run's dataset version"))
      .mockResolvedValueOnce(detail());
    renderPage();
    expect(await screen.findByRole("alert")).toHaveTextContent("Case not found");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByText("I was charged twice.")).toBeInTheDocument();
  });
});
