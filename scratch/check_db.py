import asyncio
import asyncpg

async def main():
    for db in ['auth_db', 'profile_db', 'roadmap_db']:
        try:
            conn = await asyncpg.connect(f'postgresql://postgres@localhost:5435/{db}')
            tables = await conn.fetch("SELECT tablename FROM pg_tables WHERE schemaname='public'")
            print(f"{db} tables: {[r['tablename'] for r in tables]}")
            await conn.close()
        except Exception as e:
            print(f"{db} error: {e}")

if __name__ == '__main__':
    asyncio.run(main())
