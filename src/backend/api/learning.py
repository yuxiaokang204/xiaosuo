"""
学习引擎端点 — /api/learning
"""
from fastapi import APIRouter

from .deps import _ensure_services_ready, learning_engine
from .models import FeedbackRequest

router = APIRouter(prefix="/api/learning", tags=["Learning"])


@router.get("/stats")
async def get_learning_stats():
    _ensure_services_ready()
    return {"stats": learning_engine.get_statistics()}


@router.post("/feedback")
async def submit_feedback(req: FeedbackRequest):
    """提交用户反馈，学习引擎从中学习风格偏好"""
    _ensure_services_ready()

    class _FB:
        def __init__(self):
            self.feedback_type = req.feedback_type
            self.before_text = req.before_text
            self.after_text = req.after_text
            self.metadata = req.metadata

    learning_engine.learn_from_feedback(_FB())
    return {"success": True, "total_feedback": learning_engine.get_statistics()["total_feedback"]}


@router.post("/clear")
async def clear_learning():
    _ensure_services_ready()
    learning_engine.clear_learning()
    return {"success": True, "message": "学习数据已清除"}