import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import * as comparisonApi from "../api/comparison";
import * as runsApi from "../api/runs";
import { BASE_ID, makeComparison, makeRegressions, makeRun, makeSummary, page, RUN_ID } from "../test/fixtures";
import ComparisonPage from "./ComparisonPage";

vi.mock("../api/runs");
vi.mock("../api/comparison");

const baselineRun = makeRun({
  id: BASE_ID,
  config: { ...makeRun().config, model_aliases: ["accurate-model"] },
});

beforeEach(() => {
  vi.mocked(runsApi.getRun).mockResolvedValue(makeRun());
  vi.mocked(runsApi.listRuns).mockResolvedValue(page([makeRun(), baselineRun]));
  vi.mocked(comparisonApi.getComparison).mockResolvedValue(makeComparison());
  vi.mocked(comparisonApi.getRegressions).mockResolvedValue(makeRegressions());
});

describe("ComparisonPage", () => {
  it("shows metrics, never presenting missing cost as zero", async () => {
    render(<ComparisonPage id={RUN_ID} />);
    const row = (await screen.findAllByRole("cell", { name: "fast-model" }))[0].closest("tr")!;
    expect(within(row).getByText("unavailable")).toBeInTheDocument();
    expect(within(row).getByText(/120 ms \/ 180 ms/)).toBeInTheDocument();
    expect(within(row).getByText("168 / 24")).toBeInTheDocument();
  });

  it("shows the recommendation with its scope note", async () => {
    render(<ComparisonPage id={RUN_ID} />);
    expect(await screen.findByText(/ranks first with an overall score/)).toBeInTheDocument();
    expect(screen.getByText(/applies only to this workload/)).toBeInTheDocument();
  });

  it("explains why a model is ineligible and that nothing is recommended", async () => {
    vi.mocked(comparisonApi.getComparison).mockResolvedValue(
      makeComparison({
        ranking: {
          ...makeComparison().ranking,
          recommended: null,
          explanation: "No model satisfies the constraints.",
          models: [
            {
              model_alias: "fast-model", eligible: false, reasons: ["quality 0.333 below minimum 0.500"],
              components: {}, missing_components: [], overall_score: null, rank: null,
            },
          ],
        },
      }),
    );
    render(<ComparisonPage id={RUN_ID} />);
    expect(await screen.findByText("No eligible model")).toBeInTheDocument();
    expect(screen.getByText("quality 0.333 below minimum 0.500")).toBeInTheDocument();
  });

  it("highlights failures in the summary", async () => {
    vi.mocked(comparisonApi.getComparison).mockResolvedValue(
      makeComparison({ models: [makeSummary({ failure_rate: 0.5, success_rate: 0.5 })] }),
    );
    render(<ComparisonPage id={RUN_ID} />);
    expect(await screen.findByText("50.0%", { selector: "td.bad" })).toBeInTheDocument();
  });

  it("says so when no baseline is selected and disables Apply", async () => {
    render(<ComparisonPage id={RUN_ID} />);
    expect(await screen.findByText("No baseline selected.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeDisabled();
  });

  it("lists only other finished runs as baseline candidates", async () => {
    vi.mocked(runsApi.listRuns).mockResolvedValue(
      page([makeRun(), baselineRun, makeRun({ id: "44444444-4444-4444-8444-444444444444", status: "running" })]),
    );
    render(<ComparisonPage id={RUN_ID} />);
    const select = await screen.findByLabelText("Baseline");
    expect(within(select).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "none",
      expect.stringContaining(BASE_ID.slice(0, 8)),
    ]);
  });

  it("renders regression findings with severity", async () => {
    vi.mocked(comparisonApi.getRegressions).mockResolvedValue(
      makeRegressions({
        state: "evaluated",
        baseline_run_id: BASE_ID,
        highest_severity: "critical",
        findings: [
          {
            model_alias: "fast-model", metric_name: "quality_score", baseline_value: 1, current_value: 0.333,
            delta: -0.667, severity: "critical", explanation: "Quality 0.333 is below the absolute minimum 0.500.",
          },
        ],
      }),
    );
    render(<ComparisonPage id={RUN_ID} />);
    expect(await screen.findByText(/highest severity critical/)).toHaveClass("sev-critical");
    expect(screen.getByText(/below the absolute minimum/)).toBeInTheDocument();
    expect(screen.getByText("-0.667")).toBeInTheDocument();
  });

  it("reports an evaluated baseline with no findings as no regressions", async () => {
    vi.mocked(comparisonApi.getRegressions).mockResolvedValue(
      makeRegressions({ state: "evaluated", baseline_run_id: BASE_ID }),
    );
    render(<ComparisonPage id={RUN_ID} />);
    expect(await screen.findByText("no regressions detected")).toBeInTheDocument();
  });

  it("shows why an incompatible baseline cannot be used", async () => {
    vi.mocked(comparisonApi.getRegressions).mockResolvedValue(
      makeRegressions({ state: "incompatible", baseline_run_id: BASE_ID, incompatibilities: ["dataset content differs"] }),
    );
    render(<ComparisonPage id={RUN_ID} />);
    expect(await screen.findByText(/Baseline is not comparable: dataset content differs/)).toBeInTheDocument();
  });

  it("applies a chosen baseline and reloads", async () => {
    vi.mocked(comparisonApi.setBaseline).mockResolvedValue(makeRun({ baseline_run_id: BASE_ID }));
    render(<ComparisonPage id={RUN_ID} />);
    await userEvent.selectOptions(await screen.findByLabelText("Baseline"), BASE_ID);
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(comparisonApi.setBaseline).toHaveBeenCalledWith(RUN_ID, BASE_ID);
    expect(comparisonApi.getRegressions).toHaveBeenCalledTimes(2);
  });

  it("surfaces the server's reason when the baseline is rejected", async () => {
    vi.mocked(comparisonApi.setBaseline).mockRejectedValue(
      new ApiError(409, "incompatible_baseline", "Baseline is not comparable with this run", [
        { loc: "baseline_run_id", message: "dataset content differs (baseline v1, current v2)" },
      ]),
    );
    render(<ComparisonPage id={RUN_ID} />);
    await userEvent.selectOptions(await screen.findByLabelText("Baseline"), BASE_ID);
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(await screen.findByText(/dataset content differs \(baseline v1, current v2\)/)).toHaveClass("bad");
  });

  it("shows a loading state, then an error with retry for an unfinished run", async () => {
    vi.mocked(comparisonApi.getComparison).mockRejectedValueOnce(
      new ApiError(409, "run_not_finished", "Run has not finished yet"),
    );
    render(<ComparisonPage id={RUN_ID} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByRole("alert")).toHaveTextContent("Run has not finished yet");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect((await screen.findAllByRole("cell", { name: "fast-model" })).length).toBeGreaterThan(0);
  });
});
