# -*- coding: utf-8 -*-
"""项目管理路由：项目 CRUD、成员管理、手动同步。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import (
    get_current_user,
    require_admin,
    require_project_access,
    require_project_admin,
)
from ..models import Project, User
from ..repositories import (
    get_conversation_repository,
    get_metric_repository,
    get_project_member_repository,
    get_project_repository,
    get_provider_repository,
    get_user_repository,
)
from ..schemas import (
    ConversationPage,
    ConversationSyncRequest,
    ConversationSyncResult,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
    SyncRequest,
    SyncResult,
)
from ..security import decrypt_secret, encrypt_secret, mask_secret
from ..services import (
    SCOPE_APP_COUNT,
    SCOPE_TOKEN,
    sync_conversations,
    sync_dashboard,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])

VALID_PROJECT_ROLES = {"project_admin", "member"}


def _to_out(db: Session, p: Project) -> ProjectOut:
    provider = get_provider_repository(db).get_by_key(p.provider_type_key)
    member_count = len(get_project_member_repository(db).list_by_project(p.id))
    latest = get_metric_repository(db).get_latest(p.id)
    return ProjectOut(
        id=p.id,
        name=p.name,
        provider_type_key=p.provider_type_key,
        provider_display_name=provider.display_name if provider else p.provider_type_key,
        host=p.host,
        region=p.region,
        is_active=p.is_active,
        secret_id_masked=mask_secret(p.secret_id),
        secret_key_masked=mask_secret(decrypt_secret(p.secret_key_enc)),
        member_count=member_count,
        last_sync_at=latest.created_at if latest else None,
        last_sync_source=latest.source if latest else None,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _validate_provider_type(db: Session, type_key: str) -> None:
    provider = get_provider_repository(db).get_by_key(type_key)
    if not provider:
        raise HTTPException(status_code=400, detail="所选 Provider 类型不存在")
    if not provider.implemented:
        raise HTTPException(status_code=400, detail="所选 Provider 尚未实现，暂不可用")
    if not provider.enabled:
        raise HTTPException(status_code=400, detail="所选 Provider 已被禁用")


@router.get("", response_model=list[ProjectOut])
def list_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """admin 看全部项目；普通用户仅看自己所属项目。"""
    repo = get_project_repository(db)
    projects = repo.list_all() if user.role == "admin" else repo.list_for_user(user.id)
    return [_to_out(db, p) for p in projects]


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    repo = get_project_repository(db)
    if repo.get_by_name(body.name):
        raise HTTPException(status_code=400, detail="项目名称已存在")
    _validate_provider_type(db, body.provider_type_key)
    project = Project(
        name=body.name.strip(),
        provider_type_key=body.provider_type_key,
        host=body.host.strip(),
        region=body.region,
        is_active=body.is_active,
        secret_id=body.secret_id.strip(),
        secret_key_enc=encrypt_secret(body.secret_key.strip()),
    )
    repo.add(project)
    return _to_out(db, project)


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project: Project = Depends(require_project_access), db: Session = Depends(get_db)
):
    return _to_out(db, project)


@router.put("/{project_id}", response_model=ProjectOut)
def update_project(
    body: ProjectUpdate,
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    repo = get_project_repository(db)
    if body.name and body.name != project.name:
        if repo.get_by_name(body.name):
            raise HTTPException(status_code=400, detail="项目名称已存在")
        project.name = body.name.strip()
    if body.provider_type_key is not None:
        _validate_provider_type(db, body.provider_type_key)
        project.provider_type_key = body.provider_type_key
    if body.host is not None:
        project.host = body.host.strip()
    if body.region is not None:
        project.region = body.region
    if body.is_active is not None:
        project.is_active = body.is_active
    if body.secret_id is not None:
        project.secret_id = body.secret_id.strip()
    if body.secret_key:  # 留空表示不修改
        project.secret_key_enc = encrypt_secret(body.secret_key.strip())
    repo.save(project)
    return _to_out(db, project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    repo = get_project_repository(db)
    project = repo.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    repo.delete(project)


# ---------------- 成员管理 ----------------
def _member_out(db: Session, member) -> ProjectMemberOut:
    user = get_user_repository(db).get(member.user_id)
    return ProjectMemberOut(
        id=member.id,
        user_id=member.user_id,
        username=user.username if user else f"#{member.user_id}",
        project_role=member.project_role,
        created_at=member.created_at,
    )


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
def list_members(
    project: Project = Depends(require_project_access), db: Session = Depends(get_db)
):
    members = get_project_member_repository(db).list_by_project(project.id)
    return [_member_out(db, m) for m in members]


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    body: ProjectMemberCreate,
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    if body.project_role not in VALID_PROJECT_ROLES:
        raise HTTPException(status_code=400, detail="非法项目角色")
    if not get_user_repository(db).get(body.user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    member_repo = get_project_member_repository(db)
    if member_repo.get(project.id, body.user_id):
        raise HTTPException(status_code=400, detail="该用户已是项目成员")
    member = member_repo.add(project.id, body.user_id, body.project_role)
    return _member_out(db, member)


@router.delete(
    "/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    user_id: int,
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    member_repo = get_project_member_repository(db)
    member = member_repo.get(project.id, user_id)
    if not member:
        raise HTTPException(status_code=404, detail="成员不存在")
    member_repo.delete(member)


# ---------------- 手动同步（按范围 scope） ----------------
SCOPE_CONVERSATIONS = "conversations"
VALID_SYNC_SCOPES = {SCOPE_APP_COUNT, SCOPE_TOKEN, SCOPE_CONVERSATIONS}
SCOPE_LABELS = {
    SCOPE_APP_COUNT: "应用数量",
    SCOPE_TOKEN: "token消耗",
    SCOPE_CONVERSATIONS: "应用对话记录",
}


@router.post("/{project_id}/sync", response_model=SyncResult)
def sync(
    body: SyncRequest = SyncRequest(),
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    """按用户选择的范围同步数据。

    scopes 为 app_count / token / conversations 的子集；留空默认 [app_count, token]。
    """
    scopes = body.scopes if body.scopes is not None else [SCOPE_APP_COUNT, SCOPE_TOKEN]
    scopes = list(dict.fromkeys(scopes))  # 去重保序
    if not scopes:
        raise HTTPException(status_code=400, detail="请至少选择一个同步范围")
    invalid = [s for s in scopes if s not in VALID_SYNC_SCOPES]
    if invalid:
        raise HTTPException(status_code=400, detail=f"非法同步范围：{invalid}")

    sources: list[str] = []
    details: dict = {}
    msg_parts: list[str] = []

    # 看板部分（应用数量 / token 消耗）
    dashboard_scopes = {s for s in scopes if s in (SCOPE_APP_COUNT, SCOPE_TOKEN)}
    if dashboard_scopes:
        _, src = sync_dashboard(get_metric_repository(db), project, dashboard_scopes)
        sources.append(src)
        details["dashboard"] = {"scopes": sorted(dashboard_scopes), "source": src}
        labels = "、".join(SCOPE_LABELS[s] for s in scopes if s in dashboard_scopes)
        msg_parts.append(f"{labels} 已同步")

    # 对话记录部分
    if SCOPE_CONVERSATIONS in scopes:
        now = datetime.now()
        begin = body.conv_begin or (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
        end = body.conv_end or now.strftime("%Y-%m-%d %H:%M:%S")
        conv = sync_conversations(
            get_conversation_repository(db),
            project,
            begin=begin,
            end=end,
            max_records_per_app=body.max_records_per_app,
        )
        sources.append(conv["source"])
        details["conversations"] = conv
        msg_parts.append(
            f"应用对话记录：{conv['app_count']} 个应用拉取 {conv['fetched']} 条，"
            f"新增 {conv['inserted']} 条"
        )

    overall_source = "live" if sources and all(s == "live" for s in sources) else "mock"
    message = "；".join(msg_parts)
    if overall_source == "mock":
        message += "（部分或全部为 Mock 演示数据）"

    return SyncResult(
        ok=overall_source == "live",
        source=overall_source,
        message=message,
        synced_at=datetime.utcnow(),
        scopes=scopes,
        details=details,
    )


# ---------------- 对话记录同步 / 查询 ----------------
@router.post("/{project_id}/sync-conversations", response_model=ConversationSyncResult)
def sync_conversation_records(
    body: ConversationSyncRequest = ConversationSyncRequest(),
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    """遍历项目下所有应用，拉取对话记录并去重入库。时间范围默认最近 7 天。"""
    now = datetime.now()
    begin = body.begin or (now - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
    end = body.end or now.strftime("%Y-%m-%d %H:%M:%S")

    result = sync_conversations(
        get_conversation_repository(db),
        project,
        begin=begin,
        end=end,
        max_records_per_app=body.max_records_per_app,
    )
    source = result["source"]
    message = (
        f"同步完成：{result['app_count']} 个应用，拉取 {result['fetched']} 条，"
        f"新增入库 {result['inserted']} 条"
        + ("" if source == "live" else "（Mock 演示数据）")
    )
    return ConversationSyncResult(
        source=source,
        app_count=result["app_count"],
        fetched=result["fetched"],
        inserted=result["inserted"],
        message=message,
        synced_at=datetime.utcnow(),
    )


@router.get("/{project_id}/conversations", response_model=ConversationPage)
def list_conversations(
    app_biz_id: str | None = Query(default=None),
    begin: str | None = Query(default=None, description="起始时间 YYYY-MM-DD HH:MM:SS"),
    end: str | None = Query(default=None, description="结束时间 YYYY-MM-DD HH:MM:SS"),
    keyword: str | None = Query(default=None, description="搜索问题/回答"),
    intent: str | None = Query(default=None, description="意图分类"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    project: Project = Depends(require_project_access),
    db: Session = Depends(get_db),
):
    """分页查询已入库的对话记录，支持按应用/时间/关键词/意图过滤。"""
    repo = get_conversation_repository(db)
    total = repo.count(
        project.id, app_biz_id, begin=begin, end=end, keyword=keyword, intent=intent
    )
    items = repo.list_records(
        project.id,
        app_biz_id,
        limit=limit,
        offset=offset,
        begin=begin,
        end=end,
        keyword=keyword,
        intent=intent,
    )
    return ConversationPage(total=total, items=items)


@router.get("/{project_id}/conversation-apps", response_model=list[str])
def list_conversation_apps(
    project: Project = Depends(require_project_access),
    db: Session = Depends(get_db),
):
    """返回该项目有对话记录的 app_biz_id 去重列表（供前端过滤下拉）。"""
    return get_conversation_repository(db).list_app_ids(project.id)
