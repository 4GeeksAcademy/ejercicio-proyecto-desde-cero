from sqlalchemy import func, select

from app.modules.courses.models import Course
from app.seed_demo import seed


async def test_seed_creates_courses_with_photos_and_is_idempotent(session):
    await seed()
    await seed()  # segunda vez: no duplica
    session.expire_all()
    assert (await session.execute(select(func.count()).select_from(Course))).scalar_one() == 8
    assert (
        await session.execute(select(func.count()).select_from(Course).where(Course.cover_image_url.is_(None)))
    ).scalar_one() == 0
    alts = (await session.execute(select(Course.cover_image_alt))).scalars().all()
    assert all(a and len(a) > 10 for a in alts)  # todas con texto alternativo
