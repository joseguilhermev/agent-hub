import json
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class AgentConfig:
    id: str
    name: str
    secret: str = field(repr=False)


def load_agents() -> list[AgentConfig]:
    load_dotenv()
    raw = os.getenv("AGENTS", "").strip()
    if raw:
        try:
            values = json.loads(raw)
            agents = [AgentConfig(**value) for value in values]
        except (json.JSONDecodeError, TypeError, KeyError) as error:
            raise RuntimeError(
                "AGENTS must be a JSON array of id, name, and secret objects"
            ) from error
    elif secret := os.getenv("SECRET", "").strip():
        agents = [AgentConfig(id="default", name="Default agent", secret=secret)]
    else:
        agents = []

    if len({agent.id for agent in agents}) != len(agents):
        raise RuntimeError("Agent IDs must be unique")
    if any(not agent.id or not agent.name or not agent.secret for agent in agents):
        raise RuntimeError("Agent id, name, and secret cannot be empty")
    return agents
