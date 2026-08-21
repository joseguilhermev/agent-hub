import time

from fastapi import APIRouter, HTTPException, Query, status

from agent_hub.dependencies import AdminUser, database
from agent_hub.schemas import AdminUser as AdminUserSchema
from agent_hub.schemas import Agent, AgentAssignment, AgentRequest, AgentRequestUpdate
from agent_hub.schemas import AgentUsageEvent, AgentUsageSummary, UsageDashboard

router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/agent-requests", response_model=list[AgentRequest])
def list_agent_requests(admin: AdminUser) -> list[AgentRequest]:
    with database.connect() as connection:
        rows = connection.execute(
            """SELECT requests.*, users.email AS user_email
               FROM agent_requests AS requests
               JOIN users ON users.id = requests.user_id
               ORDER BY CASE requests.status WHEN 'pending' THEN 0 ELSE 1 END,
                        requests.created_at DESC, requests.id DESC"""
        ).fetchall()
    return [AgentRequest.model_validate(dict(row)) for row in rows]


@router.put("/agent-requests/{request_id}", response_model=AgentRequest)
def update_agent_request(
    request_id: str, body: AgentRequestUpdate, admin: AdminUser
) -> AgentRequest:
    with database.connect() as connection:
        result = connection.execute(
            "UPDATE agent_requests SET status = ?, updated_at = unixepoch() WHERE id = ?",
            (body.status, request_id),
        )
        if result.rowcount == 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Agent request not found")
        row = connection.execute(
            """SELECT requests.*, users.email AS user_email
               FROM agent_requests AS requests
               JOIN users ON users.id = requests.user_id
               WHERE requests.id = ?""",
            (request_id,),
        ).fetchone()
    return AgentRequest.model_validate(dict(row))


@router.get("/usage", response_model=UsageDashboard)
def usage_dashboard(
    admin: AdminUser, days: int = Query(default=30, ge=1, le=365)
) -> UsageDashboard:
    cutoff = int(time.time()) - days * 86_400
    with database.connect() as connection:
        totals = connection.execute(
            """SELECT COUNT(DISTINCT CASE WHEN event_type = 'conversation' THEN conversation_id END) AS conversations,
                      COUNT(*) AS interactions, COUNT(DISTINCT user_id) AS users,
                      COALESCE(SUM(input_chars), 0) AS input_chars,
                      COALESCE(SUM(output_items), 0) AS output_items,
                      COALESCE(SUM(attachment_bytes), 0) AS attachment_bytes
               FROM agent_usage WHERE created_at >= ?""",
            (cutoff,),
        ).fetchone()
        agent_rows = connection.execute(
            """SELECT agents.id, agents.name,
                      COUNT(DISTINCT CASE WHEN usage.event_type = 'conversation' THEN usage.conversation_id END) AS conversations,
                      COUNT(usage.id) AS interactions,
                      COUNT(DISTINCT usage.user_id) AS users,
                      COALESCE(SUM(usage.input_chars), 0) AS input_chars,
                      COALESCE(SUM(usage.output_items), 0) AS output_items,
                      COALESCE(SUM(usage.attachment_count), 0) AS attachment_count,
                      COALESCE(SUM(usage.attachment_bytes), 0) AS attachment_bytes,
                      COALESCE(ROUND(AVG(CASE WHEN usage.duration_ms > 0 THEN usage.duration_ms END)), 0) AS average_duration_ms,
                      MAX(usage.created_at) AS last_used_at
               FROM agents LEFT JOIN agent_usage AS usage
                 ON usage.agent_id = agents.id AND usage.created_at >= ?
               GROUP BY agents.id, agents.name
               ORDER BY interactions DESC, agents.name COLLATE NOCASE""",
            (cutoff,),
        ).fetchall()
        recent_rows = connection.execute(
            """SELECT usage.*, agents.name AS agent_name, users.email AS user_email
               FROM agent_usage AS usage
               JOIN agents ON agents.id = usage.agent_id
               JOIN users ON users.id = usage.user_id
               WHERE usage.created_at >= ?
               ORDER BY usage.created_at DESC, usage.id DESC LIMIT 50""",
            (cutoff,),
        ).fetchall()
    return UsageDashboard(
        days=days,
        total_conversations=totals["conversations"],
        total_interactions=totals["interactions"],
        active_users=totals["users"],
        input_chars=totals["input_chars"],
        output_items=totals["output_items"],
        attachment_bytes=totals["attachment_bytes"],
        agents=[AgentUsageSummary(
            agent_id=row["id"], agent_name=row["name"],
            conversations=row["conversations"], interactions=row["interactions"],
            users=row["users"], input_chars=row["input_chars"],
            output_items=row["output_items"], attachment_count=row["attachment_count"],
            attachment_bytes=row["attachment_bytes"],
            average_duration_ms=row["average_duration_ms"], last_used_at=row["last_used_at"],
        ) for row in agent_rows],
        recent=[AgentUsageEvent.model_validate(dict(row)) for row in recent_rows],
    )


@router.get("/users", response_model=list[AdminUserSchema])
def list_users(admin: AdminUser) -> list[AdminUserSchema]:
    with database.connect() as connection:
        users = connection.execute(
            "SELECT id, email, role FROM users ORDER BY created_at, id"
        ).fetchall()
        assignments = connection.execute(
            "SELECT user_id, agent_id FROM user_agents ORDER BY created_at, agent_id"
        ).fetchall()
    by_user: dict[str, list[str]] = {row["id"]: [] for row in users}
    for row in assignments:
        by_user[row["user_id"]].append(row["agent_id"])
    return [
        AdminUserSchema(
            id=row["id"], email=row["email"], role=row["role"],
            agent_ids=by_user[row["id"]],
        )
        for row in users
    ]


@router.get("/agents", response_model=list[Agent])
def list_all_agents(admin: AdminUser) -> list[Agent]:
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT id, name FROM agents ORDER BY created_at, id"
        ).fetchall()
    return [Agent(id=row["id"], name=row["name"]) for row in rows]


@router.put("/users/{user_id}/agents", response_model=AdminUserSchema)
def assign_agents(
    user_id: str, body: AgentAssignment, admin: AdminUser
) -> AdminUserSchema:
    agent_ids = list(dict.fromkeys(body.agent_ids))
    with database.connect() as connection:
        user = connection.execute(
            "SELECT id, email, role FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
        if agent_ids:
            placeholders = ",".join("?" for _ in agent_ids)
            count = connection.execute(
                f"SELECT COUNT(*) AS count FROM agents WHERE id IN ({placeholders})",
                agent_ids,
            ).fetchone()["count"]
            if count != len(agent_ids):
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Unknown agent")
        connection.execute("DELETE FROM user_agents WHERE user_id = ?", (user_id,))
        connection.executemany(
            "INSERT INTO user_agents (user_id, agent_id) VALUES (?, ?)",
            [(user_id, agent_id) for agent_id in agent_ids],
        )
    return AdminUserSchema(
        id=user["id"], email=user["email"], role=user["role"],
        agent_ids=agent_ids,
    )
