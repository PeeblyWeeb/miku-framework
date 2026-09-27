from alembic import context

config = context.config


with config.attributes["engine"].begin() as connection:
    context.configure(
        connection=connection,
        target_metadata=config.attributes["target_metadata"],
    )

    with context.begin_transaction():
        context.run_migrations()
