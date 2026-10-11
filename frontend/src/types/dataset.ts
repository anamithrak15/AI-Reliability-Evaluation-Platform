export interface DatasetSummary {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  version_count: number;
  latest_version_number: number | null;
}

export interface VersionSummary {
  id: string;
  dataset_id: string;
  version_number: number;
  schema_version: string;
  content_hash: string;
  case_count: number;
  created_at: string;
}

export interface TestCase {
  id: string;
  case_key: string;
  input: { messages: { role: string; content: string }[] };
  expected_output: Record<string, unknown> | null;
  evaluation_config: { type: string } & Record<string, unknown>;
  tags: string[];
}

export interface VersionDetail extends VersionSummary {
  cases: TestCase[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface DatasetCreated {
  dataset: DatasetSummary;
  version: VersionSummary;
}
