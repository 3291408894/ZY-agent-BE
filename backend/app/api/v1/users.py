"""
用户路由 (PBI_01) — 个人资料、仪表盘
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.common import ErrorCode, make_response
from app.schemas.user import UpdateProfileReq, UserProfileResp
from app.services.user_service import UserService

router = APIRouter()


@router.get("/profile", summary="获取个人信息")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前登录用户的个人资料"""
    service = UserService(db)
    user = await service.get_profile(current_user.id)
    return make_response(
        data=UserProfileResp(
            id=user.id,
            email=user.email,
            phone=user.phone,
            nickname=user.nickname,
            grade=user.grade,
            subjects=user.subjects or [],
            textbook_version=user.textbook_version,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ).model_dump()
    )


@router.put("/profile", summary="更新个人信息")
async def update_profile(
    req: UpdateProfileReq,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改年级、学科偏好、教材版本等"""
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
        data=UserProfileResp(
            id=user.id,
            email=user.email,
            phone=user.phone,
            nickname=user.nickname,
            grade=user.grade,
            subjects=user.subjects or [],
            textbook_version=user.textbook_version,
            avatar_url=user.avatar_url,
            created_at=user.created_at,
            updated_at=user.updated_at,
        ).model_dump(),
        message="更新成功",
    )


@router.get("/dashboard", summary="学习仪表盘")
async def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """聚合展示学习统计数据"""
    service = UserService(db)
    data = await service.get_dashboard(current_user.id)
    return make_response(data=data)
