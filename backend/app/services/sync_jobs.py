# -*- coding: utf-8 -*-
"""异步对话同步任务执行：在后台运行，持续把进度/结果写回 SyncJob，供前端轮询。"""
from __future__ import annotations

import logging

from ..database import SessionLocal
from ..repositories import (
    get_conversation_repository,
    get_project_repository,
    get_sync_job_repository,
)
from .conversations import sync_conversations

logger = logging.getLogger(__name__)


def run_conversation_sync_job(
    job_id: int,
    project_id: int,
    begin: str,
    end: str,
    max_records_per_app: int,
    incremental: bool,
) -> None:
    """后台执行一次对话同步，使用独立 DB 会话，并把进度/结果写回 SyncJob。"""
    db = SessionLocal()
    try:
        job_repo = get_sync_job_repository(db)
        project = get_project_repository(db).get(project_id)
        if project is None:
            job_repo.mark_failed(job_id, "项目不存在")
            logger.error("对话同步任务[%s] 失败：项目[%s] 不存在", job_id, project_id)
            return
        job_repo.mark_running(job_id)
        logger.info(
            "对话同步任务[%s] 开始：项目[%s]，%s，范围 %s ~ %s",
            job_id,
            project_id,
            "增量" if incremental else "全量",
            begin,
            end,
        )

        def _progress(done: int, total: int, fetched: int) -> None:
            job_repo.update_progress(job_id, done, total, fetched)

        result = sync_conversations(
            get_conversation_repository(db),
            project,
            begin=begin,
            end=end,
            max_records_per_app=max_records_per_app,
            incremental=incremental,
            progress_cb=_progress,
            should_cancel=lambda: job_repo.is_cancelling(job_id),
        )
        get_project_repository(db).save(project)  # 持久化同步水位时间
        source = result["source"]
        mode = "增量" if incremental else "全量"
        if result.get("cancelled"):
            message = (
                f"已终止（{mode}）：已处理 {result['app_count']} 个应用前停止，"
                f"已入库 {result['inserted']} 条"
            )
            job_repo.mark_cancelled(job_id, message)
            logger.info("对话同步任务[%s] 已终止：%s", job_id, message)
            return
        message = (
            f"同步完成（{mode}）：{result['app_count']} 个应用，拉取 {result['fetched']} 条，"
            f"新增入库 {result['inserted']} 条"
            + ("" if source == "live" else "（Mock 演示数据）")
        )
        job_repo.mark_success(
            job_id,
            source=source,
            app_total=result["app_count"],
            fetched=result["fetched"],
            inserted=result["inserted"],
            message=message,
        )
        logger.info("对话同步任务[%s] 成功：%s", job_id, message)
    except Exception as exc:  # noqa: BLE001 - 任何异常都标记任务失败，避免任务悬挂
        logger.exception("对话同步任务[%s] 异常失败：%s", job_id, exc)
        try:
            get_sync_job_repository(db).mark_failed(job_id, str(exc))
        except Exception:  # noqa: BLE001
            logger.exception("对话同步任务[%s] 标记失败状态时再次异常", job_id)
    finally:
        db.close()
