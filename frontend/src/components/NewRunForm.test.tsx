import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import * as datasetsApi from "../api/datasets";
import * as runsApi from "../api/runs";
import { page } from "../test/fixtures";
import type { DatasetSummary } from "../types/dataset";
import NewRunForm from "./NewRunForm";

vi.mock("../api/runs");
vi.mock("../api/datasets");

const dataset: DatasetSummary = {
  id: "55555555-5555-4555-8555-555555555555",
  name: "support-tickets",
  description: null,
  created_at: "2026-10-12T10:00:00Z",
  version_count: 1,
  latest_version_number: 1,
};

beforeEach(() => {
  vi.mocked(runsApi.listModels).mockResolvedValue([
    { alias: "fast-model", provider: "mock", description: "" },
    { alias: "accurate-model", provider: "mock", description: "" },
  ]);
  vi.mocked(runsApi.listProfiles).mockResolvedValue([{ name: "classification-v1", description: "" }]);
  vi.mocked(datasetsApi.listVersions).mockResolvedValue([]);
});

describe("NewRunForm", () => {
  it("shows loading, then asks for a dataset only when there really are none", async () => {
    vi.mocked(datasetsApi.listDatasets).mockResolvedValue(page([]));
    render(<NewRunForm />);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(await screen.findByText("Create a dataset first.")).toBeInTheDocument();
  });

  it("does not claim there are no datasets when loading failed, and can retry", async () => {
    vi.mocked(datasetsApi.listDatasets)
      .mockRejectedValueOnce(new ApiError(500, "api_unreachable", "Cannot reach the API"))
      .mockResolvedValueOnce(page([dataset]));
    vi.mocked(datasetsApi.listVersions).mockResolvedValue([
      {
        id: "v1", dataset_id: dataset.id, version_number: 1, schema_version: "1.0",
        content_hash: "h", case_count: 6, created_at: "2026-10-12T10:00:00Z",
      },
    ]);
    render(<NewRunForm />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach the API");
    expect(screen.queryByText("Create a dataset first.")).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(await screen.findByRole("button", { name: "Start run" })).toBeEnabled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows why a run could not be started", async () => {
    vi.mocked(datasetsApi.listDatasets).mockResolvedValue(page([dataset]));
    vi.mocked(datasetsApi.listVersions).mockResolvedValue([
      {
        id: "v1", dataset_id: dataset.id, version_number: 1, schema_version: "1.0",
        content_hash: "h", case_count: 6, created_at: "2026-10-12T10:00:00Z",
      },
    ]);
    vi.mocked(runsApi.createRun).mockRejectedValue(
      new ApiError(429, "rate_limited", "Too many requests; slow down and retry shortly"),
    );
    render(<NewRunForm />);
    await userEvent.click(await screen.findByRole("button", { name: "Start run" }));
    expect(await screen.findByText(/Too many requests/)).toBeInTheDocument();
  });
});
