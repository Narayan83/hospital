import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import text

from app.core.database import AsyncSessionLocal


async def main() -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(
                "SELECT code, name, pattern, is_selected, is_active "
                "FROM patient_no_formats ORDER BY sort_order"
            )
        )
        rows = result.fetchall()
        print(f"patient_no_formats: {len(rows)} rows")
        for row in rows:
            print(" ", row)
        menu = await session.execute(
            text("SELECT code, label, is_active FROM menus WHERE code = 'patient_id_format'")
        )
        print("patient_id_format menu:", menu.fetchall())


if __name__ == "__main__":
    asyncio.run(main())
