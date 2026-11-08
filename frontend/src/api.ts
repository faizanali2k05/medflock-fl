export type Activity = {
  sequence: number;
  eventId: string;
  createdAt: string;
  kind: string;
  details: Record<string, any>;
};
export type Run = {
  id: string;
  status: string;
  createdAt: string;
  config: Record<string, any>;
  result?: any;
  error: string | null;
};
export type Dataset = {
  id: string;
  name: string;
  sha256: string;
  contract: any;
  profile: any;
  provenance: any;
};
export type Model = {
  id: string;
  runId: string;
  status: string;
  manifest: any;
};
export type Node = {
  id: string;
  label: string;
  status: string;
  kind: string;
  lastSeen: string | null;
  details: any;
};
export type Dashboard = {
  runs: Run[];
  datasets: Dataset[];
  models: Model[];
  nodes: Node[];
  activityCursor: number;
};

let csrf = "";
export function setCsrf(value: string) {
  csrf = value;
}
export function authHeaders(): Record<string, string> {
  return csrf ? { "X-CSRF-Token": csrf } : {};
}
export async function rest(path: string, method = "GET", body?: unknown) {
  const form = body instanceof FormData;
  const response = await fetch(path, {
    method,
    credentials: "same-origin",
    headers: {
      ...authHeaders(),
      ...(!form && body ? { "Content-Type": "application/json" } : {}),
    },
    body: body ? (form ? body : JSON.stringify(body)) : undefined,
  });
  if (response.status === 401)
    window.dispatchEvent(new Event("medflock-expired"));
  const value = await response.json();
  if (!response.ok)
    throw Error(
      typeof value.detail === "string"
        ? value.detail
        : JSON.stringify(value.detail),
    );
  return value;
}

export async function streamCase(
  body: unknown,
  onDraft: (text: string) => void,
) {
  const response = await fetch("/api/llm/generate-stream", {
    method: "POST",
    credentials: "same-origin",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (response.status === 401)
    window.dispatchEvent(new Event("medflock-expired"));
  if (!response.ok) {
    const error = await response.json();
    throw Error(
      typeof error.detail === "string"
        ? error.detail
        : "Unable to start inference",
    );
  }
  const reader = response.body?.getReader();
  if (!reader) throw Error("Streaming response unavailable");
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done)
        throw Error(
          "Connection ended before completion. Reload the saved case before retrying.",
        );
      buffer += decoder.decode(value, { stream: true });
      let end;
      while ((end = buffer.indexOf("\n\n")) !== -1) {
        const event = buffer.slice(0, end);
        buffer = buffer.slice(end + 2);
        if (!event.startsWith("data: ")) continue;
        const message = JSON.parse(event.slice(6));
        if (message.type === "draft") onDraft(message.text);
        if (message.type === "error") throw Error(message.detail);
        if (message.type === "complete") return message.result;
      }
    }
  } finally {
    await reader.cancel();
  }
}

export async function gql<T = any>(
  query: string,
  variables: Record<string, unknown> = {},
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch("/graphql", {
    method: "POST",
    signal,
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ query, variables }),
  });
  if (response.status === 401)
    window.dispatchEvent(new Event("medflock-expired"));
  if (!response.ok)
    throw Error(
      response.status === 401
        ? "Authentication required. Open Access to sign in."
        : `API returned ${response.status}`,
    );
  const body = await response.json();
  if (body.errors)
    throw Error(body.errors.map((error: any) => error.message).join("; "));
  return body.data;
}

export const DASHBOARD = `query Dashboard {
  runs(limit:50) { id status createdAt config error }
  datasets { id name sha256 contract profile provenance }
  models { id runId status manifest }
  nodes { id label status kind lastSeen details }
  activityCursor
}`;
export const ACTIVITY = `query Activity($after:Int!){activity(after:$after,limit:200){sequence eventId createdAt kind details}}`;
export const START = `mutation Start($config:JSON!,$key:String!){startRun(config:$config,requestKey:$key){id status}}`;
export const DETAIL = `query Run($id:String!){run(id:$id){id status createdAt config result error}}`;
export const CANCEL = `mutation Cancel($id:String!){cancelRun(id:$id)}`;
export const NODE_STATUS = `mutation NodeStatus($id:String!,$status:String!){setNodeStatus(id:$id,status:$status){id status}}`;
export const ACTIVATE = `mutation Activate($id:String!,$reason:String!){activateModel(id:$id,reason:$reason){id status}}`;
export const PREDICT = `mutation Predict($id:String!,$features:JSON!){predict(modelId:$id,features:$features)}`;

export function mergeActivity(
  previous: Activity[],
  incoming: Activity[],
  limit = 100,
): Activity[] {
  const unique = new Map(previous.map((event) => [event.sequence, event]));
  incoming.forEach((event) => unique.set(event.sequence, event));
  return [...unique.values()]
    .sort((a, b) => a.sequence - b.sequence)
    .slice(-limit);
}
