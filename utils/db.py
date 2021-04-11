import asyncpg


class Database(asyncpg.Pool):
    pass


def create_pool(
        dsn=None, *,
        min_size=10,
        max_size=10,
        max_queries=50000,
        max_inactive_connection_lifetime=300.0,
        setup=None,
        init=None,
        loop=None,
        connection_class=asyncpg.connection.Connection,
        record_class=asyncpg.protocol.Record,
        **connect_kwargs
):
    return Database(
        dsn,
        connection_class=connection_class,
        record_class=record_class,
        min_size=min_size,
        max_size=max_size,
        max_queries=max_queries,
        loop=loop,
        setup=setup,
        init=init,
        max_inactive_connection_lifetime=max_inactive_connection_lifetime,
        **connect_kwargs
    )
