"""API 设计示例 — FastAPI 微服务。

演示规范中的所有 API 设计要点：
- URL 设计: /api/v1/users（名词复数，kebab-case，版本号）
- HTTP 方法: GET/POST 对应读/创建
- 统一响应: {code, message, data}
- 错误码体系: 40401, 40001, 40901
- 分页: page + page_size
- 排序: sort_by + sort_order
- 过滤: ?status=active

运行: uvicorn main:app --reload
文档: http://localhost:8000/docs
"""
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(
    title="用户管理 API",
    description="演示 RESTful API 设计规范",
    version="1.0.0",
)


# === 统一响应模型 ===

class ApiResponse(BaseModel):
    """所有接口统一使用此响应格式。"""
    code: int = 0
    message: str = "ok"
    data: object = None


class ListData(BaseModel):
    """列表响应 data 结构。"""
    items: list
    total: int
    page: int
    page_size: int


# === 数据模型 ===

class UserCreate(BaseModel):
    """创建用户请求体。"""
    name: str = Field(..., min_length=1, max_length=50, description="用户名")
    email: str = Field(..., pattern=r"^[^@]+@[^@]+\.[^@]+$", description="邮箱")


class UserResponse(BaseModel):
    """用户响应。"""
    id: str
    name: str
    email: str


# === 模拟数据 ===

_users: dict[str, dict] = {
    "user_001": {"id": "user_001", "name": "张三", "email": "zhangsan@example.com"},
    "user_002": {"id": "user_002", "name": "李四", "email": "lisi@example.com"},
    "user_003": {"id": "user_003", "name": "王五", "email": "wangwu@example.com"},
}


# === 错误码常量 ===

class ErrorCodes:
    USER_NOT_FOUND = 40401
    MISSING_FIELD = 40001
    DUPLICATE_EMAIL = 40901


# === API 端点 ===

@app.get("/api/v1/users", response_model=ApiResponse)
def list_users(
    page: int = Query(1, ge=1, description="页码，从 1 开始"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    sort_by: str = Query("id", description="排序字段"),
    sort_order: str = Query("asc", pattern="^(asc|desc)$", description="排序方向"),
    search: str | None = Query(None, description="搜索关键词"),
):
    """GET /api/v1/users — 用户列表（分页+排序+搜索）。

    演示要点：
    - page 从 1 开始
    - page_size 默认 20，最大 100
    - sort_by + sort_order 参数
    - search 参数（可选）
    """
    users = list(_users.values())

    # 搜索
    if search:
        users = [
            u for u in users
            if search.lower() in u["name"].lower() or search.lower() in u["email"].lower()
        ]

    # 排序
    reverse = sort_order == "desc"
    users.sort(key=lambda u: u.get(sort_by, ""), reverse=reverse)

    # 分页
    total = len(users)
    start = (page - 1) * page_size
    items = users[start : start + page_size]

    return ApiResponse(
        code=0,
        message="ok",
        data=ListData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        ),
    )


@app.get("/api/v1/users/{user_id}", response_model=ApiResponse)
def get_user(user_id: str):
    """GET /api/v1/users/:id — 获取单个用户。

    演示要点：
    - 资源不存在返回 40401
    - 错误 message 对开发者友好
    """
    user = _users.get(user_id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"code": ErrorCodes.USER_NOT_FOUND, "message": f"用户不存在: {user_id}"},
        )
    return ApiResponse(code=0, message="ok", data=user)


@app.post("/api/v1/users", status_code=201, response_model=ApiResponse)
def create_user(body: UserCreate):
    """POST /api/v1/users — 创建用户。

    演示要点：
    - 201 Created
    - Pydantic 自动校验（name 长度、email 格式）
    - 业务规则校验（邮箱重复）
    """
    # 业务校验：邮箱唯一
    for user in _users.values():
        if user["email"] == body.email:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": ErrorCodes.DUPLICATE_EMAIL,
                    "message": f"邮箱已被注册: {body.email}",
                },
            )

    user_id = f"user_{len(_users) + 1:03d}"
    user = {"id": user_id, "name": body.name, "email": body.email}
    _users[user_id] = user

    return ApiResponse(code=0, message="ok", data=user)


# === 全局异常处理：统一错误响应格式 ===

from fastapi.responses import JSONResponse
from fastapi import Request


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """将 HTTPException 转换为统一错误响应格式。"""
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": detail["code"], "message": detail["message"], "data": None},
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code * 100, "message": str(detail), "data": None},
    )


@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """Pydantic 校验失败的统一响应。"""
    return JSONResponse(
        status_code=422,
        content={
            "code": 42201,
            "message": "请求参数校验失败",
            "data": None,
        },
    )
