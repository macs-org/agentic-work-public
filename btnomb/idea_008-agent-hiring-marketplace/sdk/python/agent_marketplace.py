from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


@dataclass
class AgentMarketplaceClient:
    base_url: str
    api_key: str
    timeout: int = 30

    def _headers(self) -> dict[str, str]:
        return {"X-API-Key": self.api_key, "Content-Type": "application/json"}

    def register_agent(self, **payload: Any) -> dict[str, Any]:
        return self._post("/agents", payload)

    def discover_tasks(self, agent_id: str) -> list[dict[str, Any]]:
        return self._get(f"/agents/{agent_id}/tasks")

    def bid(self, task_id: str, agent_id: str, cost_usdc: float, estimated_hours: float, proposal: str) -> dict[str, Any]:
        return self._post(f"/tasks/{task_id}/bids", {
            "agent_id": agent_id,
            "cost_usdc": cost_usdc,
            "estimated_hours": estimated_hours,
            "proposal": proposal,
        })

    def submit_work(self, task_id: str, agent_id: str, artifact_url: str, summary: str) -> dict[str, Any]:
        return self._post(f"/tasks/{task_id}/submissions", {
            "agent_id": agent_id,
            "artifact_url": artifact_url,
            "summary": summary,
        })

    def _get(self, path: str) -> Any:
        response = requests.get(self.base_url.rstrip("/") + path, headers=self._headers(), timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> Any:
        response = requests.post(self.base_url.rstrip("/") + path, json=payload, headers=self._headers(), timeout=self.timeout)
        response.raise_for_status()
        return response.json()
