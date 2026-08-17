import argparse
import asyncio
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import User

async def main(email:str,username:str,password:str):
    async with SessionLocal() as db:
        user=await db.scalar(select(User).where(User.email==email))
        if user:
            user.role="admin";user.account_status="active"
        else:
            user=User(name="Global Help Network Admin",username=username,email=email,password_hash=hash_password(password),country="",city="",role="admin")
            db.add(user)
        await db.commit();print(f"Admin ready: {email}")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--email",required=True);p.add_argument("--username",required=True);p.add_argument("--password",required=True);a=p.parse_args();asyncio.run(main(a.email,a.username,a.password))
