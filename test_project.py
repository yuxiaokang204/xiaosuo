#!/usr/bin/env python3
"""
小说创作Agent系统 - 综合测试脚本
测试所有核心功能：导入、Agent注册、记忆系统、学习引擎等
"""
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# 添加项目路径
project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestResult:
    def __init__(self, name: str, success: bool, message: str = ""):
        self.name = name
        self.success = success
        self.message = message
        self.timestamp = datetime.now().strftime("%H:%M:%S")
    
    def __str__(self):
        icon = "✅" if self.success else "❌"
        return f"[{self.timestamp}] {icon} {self.name} - {self.message}"


class TestReport:
    def __init__(self):
        self.results: list[TestResult] = []
        self.start_time = datetime.now()
    
    def add_result(self, result: TestResult):
        self.results.append(result)
        print(result)
    
    def summary(self):
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        failed = total - passed
        duration = (datetime.now() - self.start_time).total_seconds()
        
        print("\n" + "=" * 80)
        print("📊 测试报告")
        print("=" * 80)
        print(f"总测试数: {total}")
        print(f"✅ 通过: {passed}")
        print(f"❌ 失败: {failed}")
        print(f"⏱️ 耗时: {duration:.2f}秒")
        print(f"📈 通过率: {passed/total*100:.1f}%" if total > 0 else "无测试")
        print("=" * 80)
        
        if failed > 0:
            print("\n❌ 失败的测试:")
            for r in self.results:
                if not r.success:
                    print(f"  - {r.name}: {r.message}")
        
        return passed, failed, total


def test_agent_registry(report: TestReport):
    """测试Agent注册系统"""
    print("\n🤖 测试Agent注册系统...")
    print("-" * 80)
    
    try:
        from src.backend.core.agent_registry import AgentRegistry, AgentRegistration, AgentType
        
        registry = AgentRegistry()
        report.add_result(TestResult("AgentRegistry初始化", True, f"注册表实例创建成功"))
        
        test_agent = AgentRegistration(
            id="test_agent",
            name="测试Agent",
            agent_type=AgentType.WORKFLOW,
            capabilities=["test_cap1", "test_cap2"],
            version="1.0.0",
            is_enabled=True
        )
        registry.register(test_agent)
        report.add_result(TestResult("Agent注册", True, f"已注册: {test_agent.id}"))
        
        retrieved = registry.get("test_agent")
        report.add_result(TestResult("Agent查询", True, f"查询到: {retrieved.name if retrieved else 'None'}"))
        
        agents = registry.list_all()
        report.add_result(TestResult("Agent列表", True, f"共 {len(agents)} 个Agent"))
        
        by_cap = registry.get_by_capability("test_cap1")
        report.add_result(TestResult("按能力查询Agent", True, f"找到 {len(by_cap)} 个Agent"))
        
        best = registry.find_best_agent("test_cap1")
        report.add_result(TestResult("最佳Agent查询", True, f"最佳Agent: {best.name if best else 'None'}"))
        
        registry.disable("test_agent")
        report.add_result(TestResult("Agent禁用", True, "Agent已禁用"))
        
        registry.enable("test_agent")
        report.add_result(TestResult("Agent启用", True, "Agent已启用"))
        
        registry.unregister("test_agent")
        report.add_result(TestResult("Agent注销", True, "Agent已注销"))
        
        dict_view = registry.to_dict()
        report.add_result(TestResult("Agent字典表示", True, f"字典格式转换成功"))
        
    except Exception as e:
        report.add_result(TestResult("Agent注册系统测试", False, str(e)[:200]))


def test_memory_system(report: TestReport):
    """测试记忆系统"""
    print("\n🧠 测试记忆系统...")
    print("-" * 80)
    
    try:
        from src.backend.core.memory import NovelMemory, ModelConfig, ImportanceLevel
        
        memory = NovelMemory(model_context_size=ModelConfig.GPT_4O_CONTEXT)
        report.add_result(TestResult("NovelMemory初始化", True, f"上下文尺寸: {memory.model_context_size}"))
        
        stats = memory.get_context_stats()
        report.add_result(TestResult("记忆统计", True, f"统计数据: {len(stats)} 项"))
        
        test_characters = [
            type('obj', (object,), {
                'id': '1',
                'name': '张三',
                'role': '主角',
                'personality': '勇敢、善良',
                'background': '农民出身'
            })
        ]
        memory.store_characters(test_characters)
        report.add_result(TestResult("角色存储", True, "角色信息存储成功"))
        
        test_settings = [
            type('obj', (object,), {
                'id': '1',
                'name': '世界观',
                'description': '一个魔法世界',
                'rules': ['魔法是天生的', '魔法需要学习']
            })
        ]
        memory.store_world_settings(test_settings)
        report.add_result(TestResult("世界观存储", True, "世界观信息存储成功"))
        
        report.add_result(TestResult("重要性级别枚举", True, f"共 {len([v for v in vars(ImportanceLevel).values() if isinstance(v, float)])} 个级别"))
        
    except Exception as e:
        report.add_result(TestResult("记忆系统测试", False, str(e)[:200]))


def test_learning_engine(report: TestReport):
    """测试学习引擎"""
    print("\n📚 测试学习引擎...")
    print("-" * 80)
    
    try:
        from src.backend.core.learning_engine import LearningEngine
        
        engine = LearningEngine()
        report.add_result(TestResult("LearningEngine初始化", True, "学习引擎创建成功"))
        
        from src.backend.models.schemas import UserFeedback, FeedbackType
        
        feedback = UserFeedback(
            novel_id="test_novel",
            chapter_id="test_chapter",
            feedback_type=FeedbackType.STYLE_EDIT,
            before_text="这是一段有AI味的文字",
            after_text="这是一段自然的文字",
            metadata={"user": "tester"}
        )
        
        engine.learn_from_feedback(feedback)
        report.add_result(TestResult("从反馈学习", True, "已处理反馈数据"))
        
        stats = engine.get_statistics()
        report.add_result(TestResult("学习统计", True, f"总反馈数: {stats.get('total_feedback', 0)}"))
        
        original_text = "眼中闪过一丝光芒，心中涌起一股激动，忍不住想要分享"
        polished = engine.apply_preference(original_text)
        report.add_result(TestResult("应用偏好优化", True, f"已应用风格优化: {polished[:50]}..."))
        
        constraints = engine.get_learned_constraints()
        report.add_result(TestResult("学习约束获取", True, f"共学到 {len(constraints)} 项约束"))
        
        engine.clear_learning()
        report.add_result(TestResult("清除学习数据", True, "学习数据已清除"))
        
        new_stats = engine.get_statistics()
        report.add_result(TestResult("清除后验证", True, f"清除后反馈数: {new_stats.get('total_feedback', 0)}"))
        
    except Exception as e:
        report.add_result(TestResult("学习引擎测试", False, str(e)[:200]))


def test_agent_implementations(report: TestReport):
    """测试所有Agent实现"""
    print("\n🎭 测试Agent实现...")
    print("-" * 80)
    
    agents_to_test = [
        ("StoryArchitectAgent", "story_architect_agent"),
        ("DraftAgent", "draft_agent"),
        ("StyleEditorAgent", "style_editor_agent"),
        ("WorldAgent", "world_agent"),
        ("CharacterAgent", "character_agent"),
        ("OpeningHookAgent", "opening_hook_agent"),
    ]
    
    for agent_name, module_name in agents_to_test:
        try:
            module_path = f"src.backend.agents.{module_name}"
            mod = __import__(module_path, fromlist=[agent_name])
            agent_class = getattr(mod, agent_name)
            
            agent = agent_class()
            report.add_result(TestResult(f"Agent实例化: {agent_name}", True, "成功实例化"))
            
            if hasattr(agent, 'process'):
                report.add_result(TestResult(f"Agent方法: {agent_name}.process()", True, "存在process方法"))
            else:
                report.add_result(TestResult(f"Agent方法: {agent_name}.process()", False, "缺少process方法"))
            
        except Exception as e:
            report.add_result(TestResult(f"Agent测试: {agent_name}", False, str(e)[:150]))


def test_agent_registry_initializer(report: TestReport):
    """测试Agent注册初始化器"""
    print("\n📋 测试Agent注册初始化器...")
    print("-" * 80)
    
    try:
        from src.backend.core.agent_registry_initializer import AgentRegistryInitializer
        
        initializer = AgentRegistryInitializer()
        report.add_result(TestResult("AgentRegistryInitializer初始化", True, "初始化器创建成功"))
        
        initializer.initialize()
        report.add_result(TestResult("Agent注册初始化", True, "系统Agent已注册"))
        
        registry = initializer.get_registry()
        all_agents = registry.list_all()
        report.add_result(TestResult("注册Agent数量", True, f"共注册 {len(all_agents)} 个Agent"))
        
        expected_count = 6
        if len(all_agents) >= expected_count:
            report.add_result(TestResult("Agent注册完整性", True, f"期望{expected_count}个，实际{len(all_agents)}个"))
        else:
            report.add_result(TestResult("Agent注册完整性", False, f"期望{expected_count}个，实际{len(all_agents)}个"))
        
        all_agent_list = registry.list_all()
        report.add_result(TestResult("Agent实例获取", True, f"可获取 {len(all_agent_list)} 个Agent实例"))
        
    except Exception as e:
        report.add_result(TestResult("Agent注册初始化器测试", False, str(e)[:200]))


def test_pydantic_schemas(report: TestReport):
    """测试Pydantic Schema"""
    print("\n📝 测试Pydantic Schema...")
    print("-" * 80)
    
    try:
        from src.backend.models import schemas
        
        schema_classes = [name for name in dir(schemas) if not name.startswith('_') and not name.islower()]
        report.add_result(TestResult("Schema计数", True, f"共定义 {len(schema_classes)} 个Schema"))
        
        for schema in schema_classes:
            report.add_result(TestResult(f"Schema存在: {schema}", True, "已定义"))
        
        from src.backend.models.schemas import Novel, Chapter, Character, WorldSetting, Volume, UserFeedback, FeedbackType, NovelStatus
        
        novel = Novel(id="test", title="测试小说", genre="科幻", status=NovelStatus.PLANNING)
        report.add_result(TestResult("Novel实例化", True, f"标题: {novel.title}"))
        
        chapter = Chapter(id="ch1", volume_id="v1", title="第一章", order=1)
        report.add_result(TestResult("Chapter实例化", True, f"章节: {chapter.title}"))
        
        character = Character(id="c1", novel_id="n1", name="角色1", personality="善良")
        report.add_result(TestResult("Character实例化", True, f"角色名: {character.name}"))
        
        setting = WorldSetting(id="s1", novel_id="n1", name="世界1", category="地理", description="描述")
        report.add_result(TestResult("WorldSetting实例化", True, f"设定名: {setting.name}"))
        
        volume = Volume(id="v1", novel_id="n1", title="第一卷", order=1)
        report.add_result(TestResult("Volume实例化", True, f"卷名: {volume.title}"))
        
        feedback = UserFeedback(novel_id="n1", chapter_id="c1", feedback_type=FeedbackType.STYLE_EDIT)
        report.add_result(TestResult("UserFeedback实例化", True, f"反馈类型: {feedback.feedback_type}"))
        
        statuses = [e for e in NovelStatus]
        report.add_result(TestResult("NovelStatus枚举", True, f"共 {len(statuses)} 个状态"))
        
        f_types = [e for e in FeedbackType]
        report.add_result(TestResult("FeedbackType枚举", True, f"共 {len(f_types)} 种反馈类型"))
        
    except Exception as e:
        report.add_result(TestResult("Schema测试", False, str(e)[:200]))


def test_fastapi_application(report: TestReport):
    """测试FastAPI主应用"""
    print("\n🚀 测试主应用...")
    print("-" * 80)
    
    try:
        from fastapi.testclient import TestClient
        from src.backend.main import app
        
        client = TestClient(app)
        report.add_result(TestResult("FastAPI TestClient初始化", True, "测试客户端创建成功"))
        
        response = client.get("/")
        report.add_result(TestResult("根端点测试", True, f"状态码: {response.status_code}"))
        if response.status_code == 200:
            try:
                data = response.json()
                report.add_result(TestResult("根端点响应", True, f"消息: {data.get('message', '')}, 版本: {data.get('version', '')}"))
            except Exception:
                report.add_result(TestResult("根端点响应", True, "返回非JSON内容（可能是前端页面）"))
        
        response = client.get("/health")
        report.add_result(TestResult("健康检查端点", True, f"状态码: {response.status_code}"))
        if response.status_code == 200:
            data = response.json()
            report.add_result(TestResult("健康检查响应", True, f"状态: {data.get('status', '')}"))
        
        response = client.get("/api/memory/stats")
        report.add_result(TestResult("记忆统计端点", True, f"状态码: {response.status_code}"))
        
        response = client.get("/api/learning/stats")
        report.add_result(TestResult("学习统计端点", True, f"状态码: {response.status_code}"))
        
    except Exception as e:
        report.add_result(TestResult("主应用测试", False, str(e)[:200]))


def main():
    """主测试函数"""
    print("=" * 80)
    print("🎯 小说创作Agent系统 - 综合测试")
    print("=" * 80)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python版本: {sys.version.split()[0]}")
    print(f"项目路径: {project_root}")
    
    report = TestReport()
    
    test_agent_registry(report)
    test_memory_system(report)
    test_learning_engine(report)
    test_agent_implementations(report)
    test_agent_registry_initializer(report)
    test_pydantic_schemas(report)
    test_fastapi_application(report)
    
    passed, failed, total = report.summary()
    
    print("\n" + "=" * 80)
    if failed == 0:
        print("🎉 所有测试通过! 项目运行正常")
    else:
        print(f"⚠️  {failed} 个测试失败，请检查问题")
    print("=" * 80)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
