"""GraphQL exposes focused views and durable event cursors over the shared application service."""

import strawberry
from fastapi import Depends
from graphql import GraphQLError
from sqlalchemy import func, select
from starlette.requests import Request
from strawberry.extensions import QueryDepthLimiter
from strawberry.fastapi import GraphQLRouter
from strawberry.scalars import JSON
from strawberry.types import Info

from medflock.accounts import quota
from medflock.security import authenticate
from medflock.store import datasets, fleet, models, runs, stream
from medflock.training.data import default_contract


@strawberry.type
class Run:
    id: str
    status: str
    created_at: str
    config: JSON
    result: JSON | None
    error: str | None


@strawberry.type
class Dataset:
    id: str
    name: str
    created_at: str
    sha256: str
    contract: JSON
    profile: JSON
    provenance: JSON


@strawberry.type
class Node:
    id: str
    label: str
    status: str
    kind: str
    last_seen: str | None
    details: JSON


@strawberry.type
class Model:
    id: str
    run_id: str
    status: str
    manifest: JSON


@strawberry.type
class Activity:
    sequence: int
    event_id: str
    created_at: str
    kind: str
    details: JSON


def cast(cls, row):
    return cls(**{name: row.get(name) for name in cls.__annotations__})


def service(info, role="read"):
    info.context["principal"].require(role)
    return info.context["service"]


def bounded(limit):
    if not 1 <= limit <= 200:
        raise ValueError("Limit must be between 1 and 200")
    return limit


@strawberry.type
class Query:
    @strawberry.field
    def activity_cursor(self, info: Info) -> int:
        with service(info).store.engine.connect() as connection:
            return connection.execute(select(func.max(stream.c.sequence))).scalar() or 0

    @strawberry.field
    def runs(self, info: Info, limit: int = 30) -> list[Run]:
        return [cast(Run, row) for row in service(info).store.list(runs, bounded(limit))]

    @strawberry.field
    def run(self, info: Info, id: str) -> Run | None:
        row = service(info).store.get(runs, id)
        return cast(Run, row) if row else None

    @strawberry.field
    def datasets(self, info: Info) -> list[Dataset]:
        return [cast(Dataset, row) for row in service(info).store.list(datasets)]

    @strawberry.field
    def nodes(self, info: Info) -> list[Node]:
        return [cast(Node, row) for row in service(info).store.list(fleet)]

    @strawberry.field
    def models(self, info: Info) -> list[Model]:
        return [cast(Model, row) for row in service(info).store.list(models)]

    @strawberry.field
    def activity(self, info: Info, after: int = 0, limit: int = 100) -> list[Activity]:
        if after < 0:
            raise ValueError("Cursor cannot be negative")
        return [cast(Activity, row) for row in service(info).store.activity(after, bounded(limit))]

    @strawberry.field
    def default_contract(self, info: Info) -> JSON:
        service(info)
        return default_contract().model_dump()


def user_error(operation):
    try:
        return operation()
    except ValueError as error:
        raise GraphQLError(str(error), extensions={"code": "BAD_USER_INPUT"}) from error


@strawberry.type
class Mutation:
    @strawberry.mutation
    def start_run(self, info: Info, config: JSON, request_key: str) -> Run:
        workbench = service(info, "researcher")
        quota(workbench.store, "training:" + info.context["principal"].subject, 3, 3600)
        return user_error(lambda: cast(Run, workbench.submit(config, request_key)))

    @strawberry.mutation
    def cancel_run(self, info: Info, id: str) -> bool:
        return service(info, "researcher").store.cancel(id)

    @strawberry.mutation
    def register_node(self, info: Info, id: str, label: str) -> Node:
        return user_error(lambda: cast(Node, service(info, "operator").register_node(id, label)))

    @strawberry.mutation
    def set_node_status(self, info: Info, id: str, status: str) -> Node:
        return user_error(lambda: cast(Node, service(info, "operator").set_node_status(id, status)))

    @strawberry.mutation
    def activate_model(self, info: Info, id: str, reason: str) -> Model:
        return user_error(lambda: cast(Model, service(info, "operator").promote(id, reason)))

    @strawberry.mutation
    def predict(self, info: Info, model_id: str, features: JSON) -> JSON:
        return user_error(lambda: service(info).predict(model_id, features))


schema = strawberry.Schema(
    query=Query, mutation=Mutation, extensions=[lambda: QueryDepthLimiter(max_depth=8)]
)


def router():
    def context(request: Request, principal=Depends(authenticate)):
        return {"principal": principal, "service": request.app.state.service}

    return GraphQLRouter(
        schema, context_getter=context, allow_queries_via_get=False, graphql_ide="graphiql"
    )
