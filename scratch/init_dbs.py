import asyncio
import asyncpg

async def main():
    conn = await asyncpg.connect(user="postgres", host="127.0.0.1", port=5435, database="postgres")
    print("Connected to PostgreSQL on 5435.")
    for db in ["auth_db", "profile_db", "roadmap_db"]:
        row = await conn.fetchrow("SELECT datname FROM pg_database WHERE datname = $1", db)
        if not row:
            await conn.execute(f'CREATE DATABASE "{db}"')
            print(f"Created database {db}")
        else:
            print(f"Database {db} already exists.")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
