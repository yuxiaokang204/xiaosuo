"""
学习引擎路由 - 反馈和学习统计
"""
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(tags=["学习"])


class FeedbackRequest(BaseModel):
    chapter_id: Optional[str] = None
    feedback_type: str = "style_edit"
    before_text: Optional[str] = None
    after_text: Optional[str] = None
    metadata: Optional[dict] = None


@router.get("/learning/stats")
async def get_learning_stats(engine=None):
    """获取学习引擎统计信息"""
    if engine is None:
        global learning_engine
        if learning_engine is None:
            from ..core.learning_engine import LearningEngine
            learning_engine = LearningEngine()
        engine = learning_engine
    return {"stats": engine.get_statistics()}


@router.post("/learning/feedback")
async def submit_feedback(req: FeedbackRequest, engine=None):
    """提交用户反馈，学习引擎从中学习风格偏好"""
    if engine is None:
        global learning_engine
        if learning_engine is None:
            from ..core.learning_engine import LearningEngine
            learning_engine = LearningEngine()
        engine = learning_engine

    class _FB:
        def __init__(self):
            self.feedback_type = req.feedback_type
            self.before_text = req.before_text
            self.after_text = req.after_text
            self.metadata = req.metadata

    engine.learn_from_feedback(_FB())
    return {"success": True, "total_feedback": engine.get_statistics()["total_feedback"]}


@router.post("/learning/clear")
async def clear_learning(engine=None):
    """清除学习数据"""
    if engine is None:
        global learning_engine
        if learning_engine is None:
            from ..core.learning_engine import LearningEngine
            learning_engine = LearningEngine()
        engine = learning_engine
    engine.clear_learning()
    return {"success": True, "message": "学习数据已清除"}


# 全局回退变量
learning_engine = None
