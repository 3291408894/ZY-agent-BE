"""
M1 认证模块 — 端到端 API 测试

运行方式:
    python tests/api/test_auth_e2e.py
"""

import asyncio
import uuid

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_auth_flow():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:

        # 每次运行使用唯一邮箱，避免数据库残留冲突
        test_email = f"test_{uuid.uuid4().hex[:8]}@zhiyi.com"
        test_phone = f"138{uuid.uuid4().hex[:8]}"

        print(f"测试账号: {test_email}")
        print()

        # ==========================================
        # 1. 健康检查
        # ==========================================
        r = await c.get("/api/v1/health")
        assert r.status_code == 200
        print(f"1.  Health Check        | {r.status_code} | {r.json()['status']}")

        # ==========================================
        # 2. 参数校验 —— 缺 email/phone 应拒绝
        # ==========================================
        r = await c.post("/api/v1/auth/register", json={
            "password": "Abc123456!",
            "grade": "七年级",
        })
        assert r.status_code == 400 and r.json()["code"] == 40001
        print(f"2.  Register (缺参数)   | {r.status_code} | 校验通过")

        # ==========================================
        # 3. 正常注册
        # ==========================================
        r = await c.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": "Abc123456!",
            "grade": "七年级",
            "subjects": ["语文", "数学", "英语"],
        })
        assert r.status_code == 201 and r.json()["code"] == 0
        user_id = r.json()["data"]["user_id"]
        print(f"3.  Register (正常)     | {r.status_code} | user_id={user_id}")

        # ==========================================
        # 4. 重复注册应拒绝
        # ==========================================
        r = await c.post("/api/v1/auth/register", json={
            "email": test_email,
            "password": "Abc123456!",
            "grade": "七年级",
        })
        assert r.status_code == 409 and r.json()["code"] == 40901
        print(f"4.  Register (重复)     | {r.status_code} | 409 冲突")

        # ==========================================
        # 5. 正常登录
        # ==========================================
        r = await c.post("/api/v1/auth/login", json={
            "login": test_email,
            "password": "Abc123456!",
        })
        assert r.status_code == 200 and r.json()["code"] == 0
        data = r.json()["data"]
        token = data["access_token"]
        refresh_token = data["refresh_token"]
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == test_email
        print(f"5.  Login (正常)        | {r.status_code} | token={token[:20]}... | user={data['user']['nickname']}")

        # ==========================================
        # 6. 密码错误应拒绝
        # ==========================================
        r = await c.post("/api/v1/auth/login", json={
            "login": test_email,
            "password": "WrongPassword!",
        })
        assert r.status_code == 401
        print(f"6.  Login (错误密码)    | {r.status_code} | 401 拒绝")

        # ==========================================
        # 7. 获取个人信息
        # ==========================================
        r = await c.get("/api/v1/users/profile", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200
        profile = r.json()["data"]
        assert profile["email"] == test_email
        assert profile["grade"] == "七年级"
        print(f"7.  GET Profile         | {r.status_code} | email={profile['email']} | grade={profile['grade']}")

        # ==========================================
        # 8. 更新个人信息
        # ==========================================
        r = await c.put("/api/v1/users/profile", json={
            "nickname": "小明",
            "textbook_version": "部编版",
        }, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        print(f"8.  PUT Profile         | {r.status_code} | {r.json()['message']}")

        # ==========================================
        # 9. 确认更新生效
        # ==========================================
        r = await c.get("/api/v1/users/profile", headers={
            "Authorization": f"Bearer {token}",
        })
        p = r.json()["data"]
        assert p["nickname"] == "小明"
        assert p["textbook_version"] == "部编版"
        print(f"9.  Verify Update       | nickname={p['nickname']} | textbook={p['textbook_version']}")

        # ==========================================
        # 10. 学习仪表盘
        # ==========================================
        r = await c.get("/api/v1/users/dashboard", headers={
            "Authorization": f"Bearer {token}",
        })
        assert r.status_code == 200
        d = r.json()["data"]
        assert "total_study_time" in d
        assert "weak_points" in d
        print(f"10. Dashboard           | {r.status_code} | study_time={d['total_study_time']} | exercises={d['total_exercises']}")

        # ==========================================
        # 11. 未登录访问应拒绝
        # ==========================================
        r = await c.get("/api/v1/users/profile")
        assert r.status_code == 401
        print(f"11. No Auth             | {r.status_code} | 401 拒绝")

        # ==========================================
        # 12. 刷新 Token
        # ==========================================
        r = await c.post("/api/v1/auth/refresh", json={
            "refresh_token": refresh_token,
        })
        assert r.status_code == 200
        new_token = r.json()["data"]["access_token"]
        print(f"12. Refresh Token       | {r.status_code} | new_token={new_token[:20]}...")

        # ==========================================
        # 13. 修改密码
        # ==========================================
        r = await c.put("/api/v1/users/password", json={
            "old_password": "Abc123456!",
            "new_password": "NewPass789!",
        }, headers={"Authorization": f"Bearer {new_token}"})
        assert r.status_code == 200
        print(f"13. Change Password     | {r.status_code} | {r.json()['message']}")

        # ==========================================
        # 14. 旧密码登录应失败
        # ==========================================
        r = await c.post("/api/v1/auth/login", json={
            "login": test_email,
            "password": "Abc123456!",
        })
        assert r.status_code == 401
        print(f"14. Old Pwd Login       | {r.status_code} | 401 拒绝")

        # ==========================================
        # 15. 新密码登录成功
        # ==========================================
        r = await c.post("/api/v1/auth/login", json={
            "login": test_email,
            "password": "NewPass789!",
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["user"]["email"] == test_email
        assert len(data["access_token"]) > 0
        print(f"15. New Pwd Login       | {r.status_code} | 登录成功")

        # ==========================================
        # 16. 发送重置密码验证码
        # ==========================================
        r = await c.post("/api/v1/auth/reset-password", json={
            "email": test_email,
        })
        assert r.status_code == 200
        print(f"16. Reset Pwd Send      | {r.status_code} | {r.json()['message']}")

        # ==========================================
        # 17. 不存在的用户重置密码
        # ==========================================
        r = await c.post("/api/v1/auth/reset-password", json={
            "email": "noone@zhiyi.com",
        })
        assert r.status_code == 404
        print(f"17. Reset Nonexist      | {r.status_code} | 404 拒绝")

        print()
        print("=" * 60)
        print("  M1 认证模块 — 全部 17 项测试通过！")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_auth_flow())
