# -*- coding: utf-8 -*-
"""看板数据路由：按项目读取最新快照。"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, list_visible_projects, require_project_access
from ..models import User
from ..repositories import get_metric_repository
from ..schemas import DashboardResponse
from ..services import get_dashboard

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("", response_model=DashboardResponse)
def dashboard(
    project_id: int | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if project_id is None:
        # 未指定项目：取该用户可见项目中的第一个
        visible = list_visible_projects(db, user)
        if not visible:
            raise HTTPException(
                status_code=404, detail="暂无可见项目，请联系管理员将你加入项目"
            )
        project = visible[0]
    else:
        # 复用项目可见性校验（admin 全可见 / 普通用户须为成员）
        project = require_project_access(project_id, user, db)

    result = get_dashboard(get_metric_repository(db), project)
    return DashboardResponse(
        project_id=project.id,
        project_name=project.name,
        source=result["source"],
        updated_at=result["updated_at"],
        data=result["data"],
    )
