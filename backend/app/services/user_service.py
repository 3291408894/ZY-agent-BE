"""
用户服务层 — 注册、登录、密码重置、资料管理、仪表盘 (PBI_01)
"""

import random
import string

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import LearningProfile, User
from app.schemas.user import (
    ChangePasswordReq,
    LoginReq,
    RegisterReq,
    ResetPasswordReq,
    ResetPasswordVerifyReq,
    UpdateProfileReq,
)


class UserService:
    """用户业务逻辑"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ================================================================
    # 注册
    # ================================================================

    async def register(self, req: RegisterReq) -> User:
        """注册新用户，自动创建学习档案。若邮箱/手机号已存在则返回 None"""
        # 校验唯一性
        if req.email:
            exists = await self._check_exists(email=req.email)
            if exists:
                return None
        if req.phone:
            exists = await self._check_exists(phone=req.phone)
            if exists:
                return None

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

    async def _check_exists(self, email: str | None = None, phone: str | None = None) -> bool:
        """检查邮箱或手机号是否已被注册"""
        conditions = []
        if email:
            conditions.append(User.email == email)
        if phone:
            conditions.append(User.phone == phone)
        if not conditions:
            return False

        stmt = select(User.id).where(*conditions).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    # ================================================================
    # 登录
    # ================================================================

    async def login(self, req: LoginReq) -> dict | None:
        """登录验证，成功返回 token + 用户信息，失败返回 None"""
        stmt = select(User).where(
            (User.email == req.login) | (User.phone == req.login)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not verify_password(req.password, user.hashed_password):
            return None

        if not user.is_active:
            return None

        user_id = str(user.id)
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
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

    # ================================================================
    # Token 刷新
    # ================================================================

    async def refresh_access_token(self, refresh_token: str) -> dict | None:
        """使用 refresh token 获取新的 access token"""
        try:
            payload = decode_token(refresh_token)
        except ValueError:
            return None

        if payload.get("type") != "refresh":
            return None

        user_id = payload["sub"]
        user = await self.db.get(User, user_id)
        if not user or not user.is_active:
            return None

        new_access = create_access_token(user_id)
        new_refresh = create_refresh_token(user_id)

        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "expires_in": settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }

    # ================================================================
    # 密码重置（优先 Redis，不可用时降级为内存存储）
    # ================================================================
    _reset_codes: dict = {}  # 降级用内存存储: {target: (code, expire_timestamp)}

    async def _store_reset_code(self, target: str, code: str) -> None:
        """存储验证码（Redis 优先，失败则内存）"""
        try:
            redis = await get_redis()
            await redis.setex(f"reset_code:{target}", 300, code)
            return
        except Exception:
            pass
        # 降级：内存存储，5 分钟有效
        import time
        self._reset_codes[target] = (code, time.time() + 300)

    async def _get_reset_code(self, target: str) -> str | None:
        """获取验证码（Redis 优先，失败则内存）"""
        try:
            redis = await get_redis()
            return await redis.get(f"reset_code:{target}")
        except Exception:
            pass
        # 降级：内存获取
        import time
        entry = self._reset_codes.get(target)
        if entry:
            code, expire = entry
            if time.time() < expire:
                return code
            del self._reset_codes[target]
        return None

    async def _delete_reset_code(self, target: str) -> None:
        """删除已使用的验证码"""
        try:
            redis = await get_redis()
            await redis.delete(f"reset_code:{target}")
            return
        except Exception:
            pass
        self._reset_codes.pop(target, None)

    async def send_reset_code(self, req: ResetPasswordReq) -> str | None:
        """发送密码重置验证码，返回接收者标识（邮箱或手机号），失败返回 None"""
        stmt = select(User).where(
            (User.email == req.email) if req.email else (User.phone == req.phone)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        # 生成 6 位数字验证码
        code = "".join(random.choices(string.digits, k=6))
        target = req.email or req.phone

        await self._store_reset_code(target, code)

        # TODO: 实际项目接入邮件/短信服务发送验证码
        import logging
        logging.getLogger("uvicorn").info(f"[密码重置] 验证码已发送至 {target}: {code}")

        return target

    async def verify_reset_code(self, req: ResetPasswordVerifyReq) -> User | None:
        """校验验证码并重置密码，成功返回用户，失败返回 None"""
        target = req.email or req.phone
        stored_code = await self._get_reset_code(target)

        if not stored_code or stored_code != req.code:
            return None

        # 验证码正确，查找用户
        stmt = select(User).where(
            (User.email == req.email) if req.email else (User.phone == req.phone)
        )
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        # 更新密码
        user.hashed_password = hash_password(req.new_password)
        await self.db.flush()

        # 删除已使用的验证码
        await self._delete_reset_code(target)

        return user

    # ================================================================
    # 用户资料
    # ================================================================

    async def get_profile(self, user_id: str) -> User | None:
        """获取用户信息"""
        return await self.db.get(User, user_id)

    async def update_profile(self, user_id: str, req: UpdateProfileReq) -> User | None:
        """更新用户资料（年级、学科偏好、教材版本等）"""
        user = await self.db.get(User, user_id)
        if not user:
            return None

        update_data = req.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)

        await self.db.flush()
        return user

    async def change_password(self, user_id: str, req: ChangePasswordReq) -> bool:
        """已登录用户修改密码，成功返回 True"""
        user = await self.db.get(User, user_id)
        if not user:
            return False

        if not verify_password(req.old_password, user.hashed_password):
            return False

        user.hashed_password = hash_password(req.new_password)
        await self.db.flush()
        return True

    # ================================================================
    # 仪表盘
    # ================================================================

    async def get_dashboard(self, user_id: str) -> dict:
        """聚合仪表盘数据（学习统计 + 近期记录 + 推荐）"""
        from app.models.summary import Summary
        from app.models.exercise import Exercise, ExerciseAttempt

        # --- 1. 统计数据：从 exercise_attempts 表实时计算 ---
        # 做题总数
        total_exercises_stmt = (
            select(func.count())
            .select_from(ExerciseAttempt)
            .where(ExerciseAttempt.user_id == user_id)
        )
        total_exercises = (await self.db.execute(total_exercises_stmt)).scalar() or 0

        # 正确数 & 正确率
        correct_stmt = (
            select(func.count())
            .select_from(ExerciseAttempt)
            .where(
                ExerciseAttempt.user_id == user_id,
                ExerciseAttempt.is_correct == True,
            )
        )
        correct_count = (await self.db.execute(correct_stmt)).scalar() or 0
        correct_rate = round(correct_count / total_exercises, 2) if total_exercises > 0 else 0.0

        # 学习时长估算：总结数 × 10分钟 + 做题数 × 2分钟（单位：秒）
        summary_count_stmt = (
            select(func.count())
            .select_from(Summary)
            .where(Summary.user_id == user_id)
        )
        summary_count = (await self.db.execute(summary_count_stmt)).scalar() or 0
        total_study_time = summary_count * 600 + total_exercises * 120

        # --- 2. 近期总结：最近 5 条 ---
        recent_summaries_stmt = (
            select(Summary)
            .where(Summary.user_id == user_id)
            .order_by(Summary.created_at.desc())
            .limit(5)
        )
        recent_summaries_rows = (await self.db.execute(recent_summaries_stmt)).scalars().all()
        recent_summaries = [
            {
                "id": s.id,
                "source_content": s.source_content[:100] if s.source_content else "",
                "summary_text": s.summary_text[:200] if s.summary_text else "",
                "mode": s.mode,
                "knowledge_points": s.knowledge_points or [],
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in recent_summaries_rows
        ]

        # --- 3. 近期做题记录：最近 5 条（含习题信息和作答结果） ---
        recent_attempts_stmt = (
            select(ExerciseAttempt, Exercise)
            .join(Exercise, ExerciseAttempt.exercise_id == Exercise.id)
            .where(ExerciseAttempt.user_id == user_id)
            .order_by(ExerciseAttempt.created_at.desc())
            .limit(5)
        )
        recent_attempts_rows = (await self.db.execute(recent_attempts_stmt)).all()
        recent_exercises = [
            {
                "attempt_id": attempt.id,
                "exercise_id": exercise.id,
                "question": exercise.question[:200] if exercise.question else "",
                "question_type": exercise.question_type,
                "subject": exercise.subject,
                "difficulty": exercise.difficulty,
                "knowledge_points": exercise.knowledge_points or [],
                "user_answer": attempt.user_answer,
                "is_correct": attempt.is_correct,
                "score": attempt.score,
                "created_at": attempt.created_at.isoformat() if attempt.created_at else None,
            }
            for attempt, exercise in recent_attempts_rows
        ]

        # --- 4. 薄弱知识点：从错题中统计 ---
        weak_kp_stmt = (
            select(Exercise.knowledge_points)
            .join(ExerciseAttempt, ExerciseAttempt.exercise_id == Exercise.id)
            .where(
                ExerciseAttempt.user_id == user_id,
                ExerciseAttempt.is_correct == False,
            )
            .order_by(ExerciseAttempt.created_at.desc())
            .limit(50)
        )
        weak_kp_rows = (await self.db.execute(weak_kp_stmt)).scalars().all()
        kp_counter: dict[str, int] = {}
        for kp_list in weak_kp_rows:
            for kp in (kp_list or []):
                name = kp if isinstance(kp, str) else kp.get("name", str(kp))
                kp_counter[name] = kp_counter.get(name, 0) + 1
        weak_points = sorted(kp_counter, key=kp_counter.get, reverse=True)[:10]

        # --- 5. 学习推荐：基于薄弱知识点生成 ---
        recommendations = []
        if weak_points:
            top_weak = weak_points[:3]
            recommendations.append({
                "type": "review",
                "title": "针对性复习",
                "description": f"你在 {', '.join(top_weak)} 方面需要加强，建议回顾相关知识点并做专项练习。",
                "knowledge_points": top_weak,
            })
        if summary_count > 0:
            recommendations.append({
                "type": "summary",
                "title": "继续课文学习",
                "description": f"你已完成 {summary_count} 篇课文总结，继续保持！尝试用 AI 助手深入理解文章。",
                "action": "generate_summary",
            })
        if total_exercises > 0:
            recommendations.append({
                "type": "practice",
                "title": "巩固练习",
                "description": f"已完成 {total_exercises} 道习题，正确率 {int(correct_rate * 100)}%。建议每天保持 5-10 道练习量。",
                "action": "start_practice",
            })
        else:
            recommendations.append({
                "type": "get_started",
                "title": "开始首次练习",
                "description": "你还没有做过习题，试试 AI 智能出题功能，检测当前水平吧！",
                "action": "start_practice",
            })

        # --- 6. 同步更新 LearningProfile（保持档案数据一致） ---
        stmt = select(LearningProfile).where(LearningProfile.user_id == user_id)
        result = await self.db.execute(stmt)
        profile = result.scalar_one_or_none()
        if profile:
            profile.total_study_time = total_study_time
            profile.total_exercises = total_exercises
            profile.correct_rate = correct_rate
            profile.weak_points = weak_points
            await self.db.flush()

        return {
            "total_study_time": total_study_time,
            "total_exercises": total_exercises,
            "correct_rate": correct_rate,
            "recent_summaries": recent_summaries,
            "recent_exercises": recent_exercises,
            "recommendations": recommendations,
            "weak_points": weak_points,
        }
