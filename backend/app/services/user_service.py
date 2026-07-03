"""
用户服务层 — 注册、登录、资料管理 (PBI_01)
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import LearningProfile, User
from app.schemas.user import LoginReq, RegisterReq, UpdateProfileReq


class UserService:
    """用户业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, req: RegisterReq) -> User:
        """注册新用户，自动创建学习档案"""
        # TODO: 校验邮箱/手机号唯一性
        user = User(
            email=req.email,
            phone=req.phone,
            hashed_password=hash_password(req.password),
            grade=req.grade,
            subjects=req.subjects,
        )
        self.db.add(user)
        await self.db.flush()

        # 自动创建学习档案
        profile = LearningProfile(user_id=user.id)
        self.db.add(profile)
        await self.db.flush()

        return user

    async def login(self, req: LoginReq) -> dict | None:
        """登录验证，成功返回 token + 用户信息，失败返回 None"""
        # 按邮箱或手机号查找
        stmt = select(User).where(
            (User.email == req.login) | (User.phone == req.login)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(req.password, user.hashed_password):
            return None

        access_token = create_access_token(str(user.id))

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": 86400,
            "user": {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "nickname": user.nickname,
                "grade": user.grade,
                "subjects": user.subjects or [],
                "textbook_version": user.textbook_version,
                "avatar_url": user.avatar_url,
            },
        }

    async def get_profile(self, user_id: str) -> User | None:
        """获取用户信息"""
        return await self.db.get(User, user_id)

    async def update_profile(self, user_id: str, req: UpdateProfileReq) -> User | None:
        """更新用户资料"""
        user = await self.db.get(User, user_id)
        if not user:
            return None

        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        await self.db.flush()
        return user

    async def get_dashboard(self, user_id: str) -> dict:
        """聚合仪表盘数据"""
        # TODO: 从各表聚合真实数据
        profile = await self.db.get(LearningProfile, user_id)
        return {
            "total_study_time": profile.total_study_time if profile else 0,
            "total_exercises": profile.total_exercises if profile else 0,
            "correct_rate": profile.correct_rate if profile else 0.0,
            "recent_summaries": [],
            "recent_exercises": [],
            "recommendations": [],
            "weak_points": profile.weak_points if profile else [],
        }
