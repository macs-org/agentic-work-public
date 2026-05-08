export type MarketplaceTask = {
  id: string;
  title: string;
  category: string;
  budget_usdc: number;
  status: string;
  capability_match?: number;
};

export class AgentMarketplaceClient {
  constructor(private baseUrl: string, private apiKey: string) {}

  async registerAgent(payload: Record<string, unknown>) {
    return this.post('/agents', payload);
  }

  async discoverTasks(agentId: string): Promise<MarketplaceTask[]> {
    return this.get(`/agents/${agentId}/tasks`);
  }

  async bid(taskId: string, payload: {agent_id: string; cost_usdc: number; estimated_hours: number; proposal: string}) {
    return this.post(`/tasks/${taskId}/bids`, payload);
  }

  async submitWork(taskId: string, payload: {agent_id: string; artifact_url: string; summary: string}) {
    return this.post(`/tasks/${taskId}/submissions`, payload);
  }

  private headers() {
    return {'Content-Type': 'application/json', 'X-API-Key': this.apiKey};
  }

  private async get(path: string) {
    const res = await fetch(this.baseUrl.replace(/\/$/, '') + path, {headers: this.headers()});
    if (!res.ok) throw new Error(`Marketplace GET ${path} failed: ${res.status} ${await res.text()}`);
    return res.json();
  }

  private async post(path: string, payload: unknown) {
    const res = await fetch(this.baseUrl.replace(/\/$/, '') + path, {method: 'POST', headers: this.headers(), body: JSON.stringify(payload)});
    if (!res.ok) throw new Error(`Marketplace POST ${path} failed: ${res.status} ${await res.text()}`);
    return res.json();
  }
}
