import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as runsApi from "./api/runs";
import { Banner, Route } from "./App";
import { ErrorBoundary } from "./components/StateViews";
import { RUN_ID } from "./test/fixtures";

vi.mock("./api/runs");
vi.mock("./api/datasets");
vi.mock("./api/comparison");
vi.mock("./pages/DatasetsPage", () => ({ default: () => <p>datasets page</p> }));
vi.mock("./pages/RunsPage", () => ({ default: () => <p>runs page</p> }));
vi.mock("./pages/RunDetailPage", () => ({ default: ({ id }: { id: string }) => <p>run detail {id}</p> }));
vi.mock("./pages/ComparisonPage", () => ({ default: ({ id }: { id: string }) => <p>comparison {id}</p> }));
vi.mock("./pages/CaseInspectionPage", () => ({
  default: ({ runId, caseKey }: { runId: string; caseKey: string }) => (
    <p>
      case {caseKey} of {runId}
    </p>
  ),
}));

beforeEach(() => {
  vi.mocked(runsApi.listModels).mockResolvedValue([]);
});

describe("Route", () => {
  it.each([
    ["#/datasets", "datasets page"],
    ["#/runs", "runs page"],
    [`#/runs/${RUN_ID}`, `run detail ${RUN_ID}`],
    [`#/runs/${RUN_ID}/compare`, `comparison ${RUN_ID}`],
    [`#/runs/${RUN_ID}/cases/billing-001`, `case billing-001 of ${RUN_ID}`],
  ])("routes %s", (hash, text) => {
    render(<Route hash={hash} />);
    expect(screen.getByText(text)).toBeInTheDocument();
  });

  it.each(["#/nope", "#/runs/not-a-uuid", `#/runs/${RUN_ID}/cases/bad key!`, `#/runs/${RUN_ID}/other`])(
    "shows a not-found page for %s",
    (hash) => {
      render(<Route hash={hash} />);
      expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Go to datasets" })).toHaveAttribute("href", "#/datasets");
    },
  );

  it("does not reflect markup from the hash", () => {
    render(<Route hash={'#/<img src=x onerror=alert(1)>'} />);
    expect(document.querySelector("img")).toBeNull();
  });
});

describe("Banner", () => {
  it("says demo mode when only mock models exist", async () => {
    vi.mocked(runsApi.listModels).mockResolvedValue([{ alias: "fast-model", provider: "mock", description: "" }]);
    render(<Banner />);
    expect(await screen.findByText(/Demo mode/)).toBeInTheDocument();
  });

  it("lists live models when enabled", async () => {
    vi.mocked(runsApi.listModels).mockResolvedValue([
      { alias: "fast-model", provider: "mock", description: "" },
      { alias: "llama-local", provider: "ollama", description: "" },
    ]);
    render(<Banner />);
    expect(await screen.findByText(/Live models enabled: llama-local/)).toBeInTheDocument();
  });

  it("falls back to demo wording when the models call fails", async () => {
    vi.mocked(runsApi.listModels).mockRejectedValue(new Error("down"));
    render(<Banner />);
    expect(await screen.findByText(/Demo mode/)).toBeInTheDocument();
  });
});

describe("ErrorBoundary", () => {
  it("contains a crashing page and offers a way out", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    const Boom = () => {
      throw new Error("render exploded");
    };
    render(
      <ErrorBoundary>
        <Boom />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("render exploded");
    expect(screen.getByRole("link", { name: "Back to datasets" })).toBeInTheDocument();
  });
});
