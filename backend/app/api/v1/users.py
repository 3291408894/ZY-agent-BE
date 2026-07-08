"""
用户路由 (PBI_01) — 个人资料、修改密码、学习仪表盘
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_response
from app.schemas.user import ChangePasswordReq, UpdateProfileReq
from app.services.user_service import UserService

router = APIRouter()


# ================================================================
# GET /users/profile — 获取个人信息
# ================================================================
@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前登录用户的完整个人资料。

    需要有效的 JWT Token（Header: Authorization: Bearer <token>）。
    """
    service = UserService(db)
    user = await service.get_profile(current_user.id)

    return make_response(
        data={
            "id": user.id,
            "email": user.email,
            "phone": user.phone,
            "nickname": user.nickname,
            "grade": user.grade,
            "subjects": user.subjects or [],
            "textbook_version": user.textbook_version,
            "avatar_url": user.avatar_url,
            "school_name": user.school_name,
            "bio": user.bio,
            "role": user.role,
            "created_at": user.created_at.isoformat(),
        }
    )


# ================================================================
# PUT /users/profile — 更新个人信息
# ================================================================
@router.put("/profile")
async def update_profile(
    req: UpdateProfileReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    更新当前用户的个人设置。

    可更新字段：nickname, grade, subjects, textbook_version
    仅更新用户显式提供的字段（其他字段保持不变）。
    """
    service = UserService(db)
    user = await service.update_profile(current_user.id, req)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCode.USER_NOT_FOUND, "message": "用户不存在", "detail": None},
        )
    await db.commit()
    await db.refresh(user)  # commit 后刷新，避免 MissingGreenlet
    return make_response(
        data={
            "id": user.id,
            "nickname": user.nickname,
            "grade": user.grade,
            "subjects": user.subjects or [],
            "textbook_version": user.textbook_version,
        },
        message="个人资料已更新",
    )


# ================================================================
# PUT /users/password — 修改密码（已登录）
# ================================================================
@router.put("/password")
async def change_password(
    req: ChangePasswordReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    已登录用户修改密码。

    需要提供旧密码进行验证，新密码长度 8-64 位。
    """
    service = UserService(db)
    ok = await service.change_password(current_user.id, req)

    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": ErrorCode.PARAM_INVALID,
                "message": "旧密码验证失败",
                "detail": None,
            },
        )

    return make_response(message="密码修改成功，请使用新密码重新登录")


# ================================================================
# GET /users/theme-preferences — 获取主题偏好
# ================================================================
@router.get("/theme-preferences")
async def get_theme_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的主题偏好（护眼模式、字体大小、暗色模式等）"""
    prefs = current_user.theme_preferences or {}
    return make_response(data={
        "font_size": prefs.get("fontSize", "medium"),
        "theme_mode": prefs.get("themeMode", "light"),
        "color_scheme": prefs.get("colorScheme", "eye-care"),
        "reading_mode": prefs.get("readingMode", False),
    })


# ================================================================
# PUT /users/theme-preferences — 保存主题偏好
# ================================================================
@router.put("/theme-preferences")
async def save_theme_preferences(
    prefs: dict,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    保存用户主题偏好。

    请求体示例：
    {"fontSize": "large", "themeMode": "dark", "colorScheme": "eye-care", "readingMode": false}
    """
    current_user.theme_preferences = {
        "fontSize": prefs.get("fontSize", "medium"),
        "themeMode": prefs.get("themeMode", "light"),
        "colorScheme": prefs.get("colorScheme", "eye-care"),
        "readingMode": prefs.get("readingMode", False),
    }
    await db.flush()
    return make_response(data=current_user.theme_preferences, message="主题偏好已保存")


# ================================================================
# GET /users/dashboard — 学习仪表盘
# ================================================================
@router.get("/dashboard")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    获取当前用户的学习仪表盘数据。

    包含：累计学习时长、做题统计、正确率、近期记录、薄弱知识点、学习推荐。
    """
    service = UserService(db)
    data = await service.get_dashboard(current_user.id)

    return make_response(data=data)
