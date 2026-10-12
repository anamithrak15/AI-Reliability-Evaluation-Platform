import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as datasetsApi from "../api/datasets";
import * as runsApi from "../api/runs";
import { BASE_ID, makeRun, page, RUN_ID } from "../test/fixtures";
import RunsPage from "./RunsPage";

vi.mock("../api/runs");
vi.mock("../api/datasets");

beforeEach(() => {
  vi.mocked(datasetsApi.listDatasets).mockResolvedValue(page([]));
  vi.mocked(runsApi.listModels).mockResolvedValue([]);
  vi.mocked(runsApi.listProfiles).mockResolvedValue([]);
});

describe("RunsPage", () => {
  it("shows a loading state first", () => {
    vi.mocked(runsApi.listRuns).mockReturnValue(new Promise(() => {}));
    render(<RunsPage />);
    expect(screen.getByText("Loading runs...")).toHaveAttribute("role", "status");
  });

  it("explains what to do when there are no runs", async () => {
    vi.mocked(runsApi.listRuns).mockResolvedValue(page([]));
    render(<RunsPage />);
    expect(await screen.findByText(/No runs yet/)).toBeInTheDocument();
  });

  it("lists runs with links, models and status", async () => {
    vi.mocked(runsApi.listRuns).mockResolvedValue(
      page([makeRun(), makeRun({ id: BASE_ID, status: "completed_with_errors" })]),
    );
    render(<RunsPage />);
    const link = await screen.findByRole("link", { name: RUN_ID.slice(0, 8) });
    expect(link).toHaveAttribute("href", `#/runs/${RUN_ID}`);
    expect(screen.getByText("completed with errors")).toBeInTheDocument();
  });

  it("shows an error with a working retry", async () => {
    vi.mocked(runsApi.listRuns)
      .mockRejectedValueOnce(new Error("API unreachable"))
      .mockResolvedValueOnce(page([makeRun()]));
    render(<RunsPage />);
    expect(await screen.findByRole("alert")).toHaveTextContent("API unreachable");
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(await screen.findByRole("link", { name: RUN_ID.slice(0, 8) })).toBeInTheDocument();
  });
});
