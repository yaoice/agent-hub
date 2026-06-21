# -*- coding: utf-8 -*-
"""项目管理路由：项目 CRUD、成员管理、手动同步。"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
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
    get_sync_job_repository,
    get_user_repository,
)
from ..schemas import (
    ConversationAppOption,
    ConversationPage,
    ConversationStats,
    ConversationSyncRequest,
    ConversationSyncResult,
    IntentSlice,
    ProjectCreate,
    ProjectMemberCreate,
    ProjectMemberOut,
    ProjectOut,
    ProjectUpdate,
    SyncJobOut,
    SyncRequest,
    SyncResult,
    TrendPoint,
)
from ..security import decrypt_secret, encrypt_secret, mask_secret
from ..services import (
    SCOPE_APP_COUNT,
    SCOPE_TOKEN,
    min_sync_interval_seconds,
    run_conversation_sync_job,
    seconds_until_next_sync,
    sync_conversations,
    sync_dashboard,
)

router = APIRouter(prefix="/api/projects", tags=["projects"])

VALID_PROJECT_ROLES = {"project_admin", "member"}


def _guard_conv_sync_rate(project: Project) -> None:
    """对话同步最小间隔限频：过于频繁时拒绝，避免重复全量拉取拖垮性能。"""
    wait = seconds_until_next_sync(project)
    if wait > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"对话同步过于频繁，请 {wait} 秒后再试"
                f"（最小间隔 {min_sync_interval_seconds() // 60} 分钟）"
            ),
        )


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
# 注：对话记录同步已独立到「对话记录」页（异步任务），不在本接口范围内。
VALID_SYNC_SCOPES = {SCOPE_APP_COUNT, SCOPE_TOKEN}
SCOPE_LABELS = {
    SCOPE_APP_COUNT: "应用数量",
    SCOPE_TOKEN: "token消耗",
}


@router.post("/{project_id}/sync", response_model=SyncResult)
def sync(
    body: SyncRequest = SyncRequest(),
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    """按用户选择的范围同步看板数据。

    scopes 为 app_count / token 的子集；留空默认 [app_count, token]。
    对话记录同步请使用「对话记录」页（独立的异步任务接口）。
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
    fallback_reasons: list[str] = []

    # 看板部分（应用数量 / token 消耗）
    dashboard_scopes = {s for s in scopes if s in (SCOPE_APP_COUNT, SCOPE_TOKEN)}
    if dashboard_scopes:
        _, src, errs = sync_dashboard(get_metric_repository(db), project, dashboard_scopes)
        sources.append(src)
        details["dashboard"] = {
            "scopes": sorted(dashboard_scopes),
            "source": src,
            "errors": errs,
        }
        labels = "、".join(SCOPE_LABELS[s] for s in scopes if s in dashboard_scopes)
        if src == "live":
            msg_parts.append(f"{labels} 已同步（实时数据）")
        else:
            msg_parts.append(f"{labels} 同步未取到实时数据，已回退 Mock 演示数据")
        fallback_reasons.extend(errs)

    overall_source = "live" if sources and all(s == "live" for s in sources) else "mock"
    message = "；".join(msg_parts)
    if overall_source == "mock" and fallback_reasons:
        # 去重保序，向用户清晰说明回退到 Mock 的具体原因
        seen: set[str] = set()
        uniq = [r for r in fallback_reasons if not (r in seen or seen.add(r))]
        message += "。回退原因：" + "；".join(uniq)

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
    """遍历项目下所有应用，拉取对话记录并去重入库。

    默认增量同步（以已入库水位线为起点）；带 full=true 时按 begin 全量回补。
    受最小同步间隔限频保护，过于频繁将返回 429。
    """
    _guard_conv_sync_rate(project)
    now = datetime.now()
    begin = body.begin or (now - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
    end = body.end or now.strftime("%Y-%m-%d %H:%M:%S")

    result = sync_conversations(
        get_conversation_repository(db),
        project,
        begin=begin,
        end=end,
        max_records_per_app=body.max_records_per_app,
        incremental=not body.full,
    )
    get_project_repository(db).save(project)  # 持久化同步水位时间
    source = result["source"]
    mode = "全量" if body.full else "增量"
    message = (
        f"同步完成（{mode}）：{result['app_count']} 个应用，拉取 {result['fetched']} 条，"
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


# ---------------- 异步对话同步任务（后台执行 + 进度轮询） ----------------
CONV_JOB_SCOPE = "conversations"


@router.post("/{project_id}/conversation-sync-jobs", response_model=SyncJobOut)
def start_conversation_sync_job(
    background: BackgroundTasks,
    body: ConversationSyncRequest = ConversationSyncRequest(),
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    """启动一次后台对话同步任务，立即返回任务对象，前端据此轮询进度。

    - 受最小同步间隔限频保护（429）。
    - 同一项目同一时刻仅允许一个进行中的对话同步任务（409）。
    """
    _guard_conv_sync_rate(project)
    job_repo = get_sync_job_repository(db)
    if job_repo.has_active(project.id, CONV_JOB_SCOPE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="已有进行中的对话同步任务，请等待其完成后再试",
        )
    now = datetime.now()
    begin = body.begin or (now - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
    end = body.end or now.strftime("%Y-%m-%d %H:%M:%S")
    incremental = not body.full
    job = job_repo.create(project.id, CONV_JOB_SCOPE, incremental)
    background.add_task(
        run_conversation_sync_job,
        job.id,
        project.id,
        begin,
        end,
        body.max_records_per_app,
        incremental,
    )
    return job


@router.get(
    "/{project_id}/conversation-sync-jobs/latest", response_model=Optional[SyncJobOut]
)
def latest_conversation_sync_job(
    project: Project = Depends(require_project_access),
    db: Session = Depends(get_db),
):
    """返回该项目最近一次对话同步任务（无则返回 null），用于前端进入页面时恢复进度。"""
    return get_sync_job_repository(db).latest_for_project(project.id, CONV_JOB_SCOPE)


@router.get("/{project_id}/conversation-sync-jobs/{job_id}", response_model=SyncJobOut)
def get_conversation_sync_job(
    job_id: int,
    project: Project = Depends(require_project_access),
    db: Session = Depends(get_db),
):
    """查询指定同步任务状态（按项目归属校验）。"""
    job = get_sync_job_repository(db).get_for_project(project.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    return job


@router.post(
    "/{project_id}/conversation-sync-jobs/{job_id}/cancel", response_model=SyncJobOut
)
def cancel_conversation_sync_job(
    job_id: int,
    project: Project = Depends(require_project_admin),
    db: Session = Depends(get_db),
):
    """请求终止一个进行中的对话同步任务（协作式：后台任务在处理下一个应用前停止）。"""
    repo = get_sync_job_repository(db)
    job = repo.get_for_project(project.id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    if not repo.request_cancel(project.id, job_id):
        raise HTTPException(status_code=409, detail="任务已结束，无法终止")
    return repo.get_for_project(project.id, job_id)


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


@router.get("/{project_id}/conversation-apps", response_model=list[ConversationAppOption])
def list_conversation_apps(
    project: Project = Depends(require_project_access),
    db: Session = Depends(get_db),
):
    """返回该项目有对话记录的应用列表（app_biz_id + 应用名称），供前端过滤下拉。"""
    options = get_conversation_repository(db).list_app_options(project.id)
    return [ConversationAppOption(app_biz_id=aid, app_name=name) for aid, name in options]


@router.get("/{project_id}/conversation-stats", response_model=ConversationStats)
def conversation_stats(
    app_biz_id: str | None = Query(default=None),
    begin: str | None = Query(default=None, description="起始时间 YYYY-MM-DD HH:MM:SS"),
    end: str | None = Query(default=None, description="结束时间 YYYY-MM-DD HH:MM:SS"),
    keyword: str | None = Query(default=None, description="搜索问题/回答"),
    intent: str | None = Query(default=None, description="意图分类"),
    project: Project = Depends(require_project_access),
    db: Session = Depends(get_db),
):
    """对话记录统计：按天趋势 + 意图分布，过滤条件与列表一致。"""
    repo = get_conversation_repository(db)
    flt = dict(app_biz_id=app_biz_id, begin=begin, end=end, keyword=keyword, intent=intent)
    trend = repo.trend_by_day(project.id, **flt)
    intents = repo.intent_distribution(project.id, **flt)
    return ConversationStats(
        trend=[TrendPoint(date=d, count=c) for d, c in trend],
        intents=[IntentSlice(name=n, count=c) for n, c in intents],
        total=sum(c for _, c in trend),
    )
