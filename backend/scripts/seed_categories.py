import asyncio
from sqlalchemy import select
from app.core.database import SessionLocal
from app.models import Category

CATEGORIES=["Technology","Education","Jobs & Career","Travel","Local Help","Housing","Shopping","Transportation","Finance","Daily Life","Other"]

async def main():
    async with SessionLocal() as db:
        for i,name in enumerate(CATEGORIES):
            slug=name.lower().replace(" & ","-").replace(" ","-")
            if not await db.scalar(select(Category).where(Category.slug==slug)):
                db.add(Category(name=name,slug=slug,sort_order=i))
        await db.commit()
        print(f"Seeded {len(CATEGORIES)} categories")

if __name__=="__main__":asyncio.run(main())
