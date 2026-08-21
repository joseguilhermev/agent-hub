from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from agent_hub.dependencies import CurrentUser, database
from agent_hub.schemas import Agent, AgentCreate, AgentRequest, AgentRequestCreate

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/requests", response_model=list[AgentRequest])
def list_agent_requests(user: CurrentUser) -> list[AgentRequest]:
    with database.connect() as connection:
        rows = connection.execute(
            """SELECT requests.*, users.email AS user_email
               FROM agent_requests AS requests
               JOIN users ON users.id = requests.user_id
               WHERE requests.user_id = ?
               ORDER BY requests.created_at DESC, requests.id DESC""",
            (user.id,),
        ).fetchall()
    return [AgentRequest.model_validate(dict(row)) for row in rows]


@router.post("/requests", response_model=AgentRequest, status_code=status.HTTP_201_CREATED)
def request_agent(body: AgentRequestCreate, user: CurrentUser) -> AgentRequest:
    request = AgentRequest(
        id=uuid4().hex,
        user_id=user.id,
        user_email=user.email,
        name=body.name.strip(),
        reason=body.reason.strip(),
        status="pending",
        created_at=0,
    )
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO agent_requests (id, user_id, name, reason) VALUES (?, ?, ?, ?)",
            (request.id, user.id, request.name, request.reason),
        )
        row = connection.execute(
            "SELECT created_at FROM agent_requests WHERE id = ?", (request.id,)
        ).fetchone()
    return request.model_copy(update={"created_at": row["created_at"]})


@router.get("", response_model=list[Agent])
def list_agents(user: CurrentUser) -> list[Agent]:
    with database.connect() as connection:
        rows = connection.execute(
            """SELECT agents.id, agents.name FROM agents
               JOIN user_agents ON user_agents.agent_id = agents.id
               WHERE user_agents.user_id = ? ORDER BY agents.created_at, agents.id""",
            (user.id,),
        ).fetchall()
    return [Agent(id=row["id"], name=row["name"]) for row in rows]


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED)
def create_agent(body: AgentCreate, user: CurrentUser) -> Agent:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    agent = Agent(id=uuid4().hex, name=body.name.strip())
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO agents (id, user_id, name, encrypted_secret) VALUES (?, ?, ?, ?)",
            (agent.id, user.id, agent.name, database.encrypt(body.secret)),
        )
        connection.execute(
            "INSERT INTO user_agents (user_id, agent_id) VALUES (?, ?)",
            (user.id, agent.id),
        )
    return agent


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(agent_id: str, user: CurrentUser) -> None:
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Administrator access required")
    with database.connect() as connection:
        result = connection.execute(
            "DELETE FROM agents WHERE id = ?", (agent_id,)
        )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent not found")
