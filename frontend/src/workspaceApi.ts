import { rest } from "./api";
import type { Role } from "./navigation";

export type User = {
  id: string;
  username: string;
  role: Role;
  enabled: boolean;
  node_id: string | null;
};
export type RuntimeStatus = {
  runtime_ready: boolean;
  settings: { enabled: boolean; max_tokens: number; timeout_seconds: number };
  instructions?: { chat: string; organize: string };
};
export type CaseSummary = {
  id: string;
  title: string;
  status: "active" | "archived";
  revision: number;
  updated_at: string;
  created_at: string;
};
export type CaseReview = {
  id: string;
  revision: number;
  summary: string;
  created_at: string;
};
export type CaseRecord = CaseSummary & {
  reviews?: CaseReview[];
  details: {
    draft: string;
    summary: string;
    reviewed: boolean;
    messages: { role: "user" | "assistant"; content: string }[];
    quality_warnings?: string[];
    last_output_truncated?: boolean;
  };
};
export type HospitalNode = {
  id: string;
  label: string;
  effective_status: string;
  training_allowed: boolean;
  transport: string;
  transport_binding: {
    flower_node_id: string;
    public_key_sha256: string;
  } | null;
  details: { suspended_until?: string };
};
export type ApplicationRecord = {
  id: string;
  organization: string;
  contact_name: string;
  contact_email: string;
  location: string;
  registration_reference: string;
  intended_use: string;
  username: string;
  node_id?: string;
  status: "pending" | "approved" | "rejected";
};
export const workspaceApi = {
  runtime: (): Promise<RuntimeStatus> => rest("/api/llm/status"),
  session: (): Promise<{ user: User; csrf: string }> => rest("/api/auth/me"),
  cases: (): Promise<CaseSummary[]> => rest("/api/cases"),
  case: (id: string): Promise<CaseRecord> =>
    rest(`/api/cases/${encodeURIComponent(id)}`),
  node: (): Promise<HospitalNode> => rest("/api/client/node"),
  applications: (): Promise<ApplicationRecord[]> =>
    rest("/api/admin/hospital-applications"),
};
