import { request } from "./client";
import type {
  DatasetCreated,
  DatasetSummary,
  Page,
  VersionDetail,
  VersionSummary,
} from "../types/dataset";

const BASE = "/api/v1/datasets";

export const listDatasets = (limit = 50, offset = 0) =>
  request<Page<DatasetSummary>>(`${BASE}?limit=${limit}&offset=${offset}`);

export const getDataset = (id: string) => request<DatasetSummary>(`${BASE}/${id}`);

export const listVersions = (id: string) => request<VersionSummary[]>(`${BASE}/${id}/versions`);

export const getVersion = (id: string, versionNumber: number) =>
  request<VersionDetail>(`${BASE}/${id}/versions/${versionNumber}`);

export const createDataset = (payload: unknown) =>
  request<DatasetCreated>(BASE, { method: "POST", body: payload });

export const createVersion = (id: string, payload: unknown) =>
  request<VersionSummary>(`${BASE}/${id}/versions`, { method: "POST", body: payload });
